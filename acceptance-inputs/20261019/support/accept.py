#!/usr/bin/env python3
"""Verify immutable payloads and issue explicit proof/build receipts."""
import argparse, hashlib, json, os, pathlib, re, shutil, subprocess
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('operation',choices=['apply','verify','receipt'])
p.add_argument('--scope',required=True)
p.add_argument('--workspace',type=pathlib.Path,required=True)
p.add_argument('--evidence',type=pathlib.Path,required=True)
a=p.parse_args();root=a.workspace.resolve();out=a.evidence.resolve();out.mkdir(parents=True,exist_ok=True)
payload=pathlib.Path(__file__).resolve().parent.parent
manifest=json.loads((payload/'manifest.json').read_text());scope=manifest['scopes'][a.scope]
base=manifest['base_commit'];input_commit=os.environ.get('GITHUB_SHA','local-verification')
identity={'checkout_commit':base,'input_commit':input_commit,'scope':a.scope,
          'applied_tree':scope['expected_tree'],'patch_sha256':scope['patch_sha256']}
def sha(data):return hashlib.sha256(data).hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
def write(name,value):(out/name).write_text(json.dumps(value,indent=2)+'\n')
def validate_payload():
    patch=payload/scope['patch'];table=payload/scope['files']
    if sha(patch.read_bytes())!=scope['patch_sha256']:raise ValueError('patch hash mismatch')
    if sha(table.read_bytes())!=scope['files_sha256']:raise ValueError('full file table hash mismatch')
    return json.loads(table.read_text())
def verify():
    rows=validate_payload()
    if git('rev-parse','HEAD')!=base:raise ValueError('checkout commit differs from requested base')
    if git('write-tree')!=scope['expected_tree']:raise ValueError('applied index tree mismatch')
    names=[]
    for item in rows:
        path=root/item['path'];names.append(item['path'])
        raw=os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()
        if sha(raw)!=item['sha256']:raise ValueError('working byte mismatch: '+item['path'])
        if item['mode']=='100755' and not path.stat().st_mode & 0o111:raise ValueError('executable mode missing: '+item['path'])
    tracked=subprocess.check_output(['git','-C',str(root),'ls-files','-z']).split(b'\0')
    if sorted(os.fsdecode(x) for x in tracked if x)!=sorted(names):raise ValueError('candidate file set differs from expected full tree')
    subprocess.run(['git','-C',str(root),'diff','--exit-code','--quiet'],check=True)
    return dict(identity,verified_files=len(rows),index_is_intentionally_staged=True)
def status(name):
    path=out/name
    try:return int(path.read_text().strip())
    except (OSError,ValueError):return None
if a.operation=='apply':
    validate_payload()
    for name in ['manifest.json',scope['files'],scope['patch']]:shutil.copy2(payload/name,out/pathlib.Path(name).name)
    subprocess.run(['git','-C',str(root),'checkout','--detach',base],check=True)
    subprocess.run(['git','-C',str(root),'apply','--index',str(payload/scope['patch'])],check=True)
    result=verify();write('applied-source.json',result)
    print(json.dumps(result))
elif a.operation=='verify':
    result=verify();write('source-after.json',result);print(json.dumps(result))
else:
    error=None
    try:verified=verify()
    except (OSError,ValueError,subprocess.CalledProcessError) as e:error=str(e);verified=None
    # A receipt always exists, including after failed setup, proof or build.
    check_text=(out/'check.log').read_text(errors='replace') if (out/'check.log').exists() else ''
    complete=bool(re.search(r'^check: [0-9]+s$',check_text,re.M) and re.search(r'^proof: after check, total [0-9]+s$',check_text,re.M))
    accepted=verified is not None and status('check.exit')==0 and status('proof.verdict')==0 and status('proof.exit') in [0,1] and complete
    build_required=a.scope=='native'
    if build_required:
        try:
            if (root/'dist').is_dir():shutil.copytree(root/'dist',out/'artifacts/dist',dirs_exist_ok=True)
        except (OSError,shutil.Error) as e:
            error=(error+'; ' if error else '')+'artifact copy failed: '+str(e);accepted=False
        accepted=accepted and status('build.exit')==0 and (root/'dist/backplane').is_file() and (root/'dist/web/index.html').is_file()
    files=[]
    for path in sorted(out.rglob('*')):
        if path.is_file() and path.name!='receipt.json':
            try:files.append(dict(identity,path=str(path.relative_to(out)),bytes=path.stat().st_size,sha256=sha(path.read_bytes())))
            except OSError as e:
                error=(error+'; ' if error else '')+'artifact hash failed: '+str(e);accepted=False
    result=dict(identity,schema=1,source_head=scope['source_head'],expected_files=scope['file_count'],source_verified=verified,
                error=error,check_exit=status('check.exit'),proof_exit=status('proof.exit'),proof_verdict=status('proof.verdict'),
                complete_check_and_proof_log=complete,build_required=build_required,build_exit=status('build.exit'),
                job_status=os.environ.get('ACCEPTANCE_JOB_STATUS','unknown'),artifacts=files,
                result='pass' if accepted else 'fail')
    write('receipt.json',result);print(json.dumps({k:v for k,v in result.items() if k!='artifacts'},indent=2))
    raise SystemExit(0 if accepted else 1)
