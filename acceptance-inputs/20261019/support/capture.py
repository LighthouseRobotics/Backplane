#!/usr/bin/env python3
"""Capture exact product snapshots as data without touching their Git indexes."""
import argparse, hashlib, json, os, pathlib, subprocess, tempfile

BASE = '30884966ef59c383581bcd1b7653f8f739cf009e'
SOURCES = {'release':'repo','lifecycle':'lifecycle','kicad':'kicad','history':'viewers',
           'orientation':'orientation','native':'native-glyph','ios':'ios-lifecycle','browser':'browser-takeover'}
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('scopes', nargs='+', choices=SOURCES)
parser.add_argument('--task-root', type=pathlib.Path, required=True)
args=parser.parse_args()
payload=pathlib.Path(__file__).resolve().parent.parent
manifest_path=payload/'manifest.json'
manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'schema':1,'base_commit':BASE,'scopes':{}}
allowed={'.bend','.md','.js','.mjs','.ts','.tsx','.jsx','.c','.h','.sh','.py','.yml','.yaml','.json','.jsonl','.html','.css','.swift','.kt','.kts','.toml','.txt','.patch'}

def git(repo,*command,env=None):
    return subprocess.check_output(['git','-C',str(repo),*command],env=env)
def digest(data):return hashlib.sha256(data).hexdigest()
def wanted(name):
    path=pathlib.PurePosixPath(name)
    if any(p.startswith(('.bend-check.','.bend-test.')) or p in ['build','dist','node_modules','__pycache__','.backplane'] for p in path.parts):return False
    if path.suffix in ['.pyc','.pyo']:return False
    return path.suffix in allowed and (len(path.parts)==1 or path.parts[0] in ['src','test','tests','docs','scripts','tools','mobile','i18n','patches','.github'])

for scope in args.scopes:
    repo=(args.task_root/SOURCES[scope]).resolve()
    real_index=pathlib.Path(os.fsdecode(git(repo,'rev-parse','--git-path','index')).strip())
    if not real_index.is_absolute():real_index=repo/real_index
    original_index=digest(real_index.read_bytes())
    head=git(repo,'rev-parse','HEAD').decode().strip()
    status=git(repo,'status','--porcelain=v1','--untracked-files=all').decode().splitlines()
    untracked=[os.fsdecode(x) for x in git(repo,'ls-files','-z','--others','--exclude-standard').split(b'\0') if x]
    included=sorted(x for x in untracked if wanted(x))
    excluded=sorted(set(untracked)-set(included))
    with tempfile.TemporaryDirectory(prefix='bp-acceptance-index-') as temp:
        env=dict(os.environ,GIT_INDEX_FILE=str(pathlib.Path(temp)/'snapshot.index'),GIT_OPTIONAL_LOCKS='0')
        git(repo,'read-tree',head,env=env)
        git(repo,'add','-u','--','.',env=env)
        if included:git(repo,'add','--',*included,env=env)
        tree=git(repo,'write-tree',env=env).decode().strip()
        patch=git(repo,'diff','--cached','--binary','--full-index',BASE,'--',env=env)
        patch_path=payload/(scope+'.patch');patch_path.write_bytes(patch)
        # Independently apply the payload to a BASE-only private index.
        round_env=dict(os.environ,GIT_INDEX_FILE=str(pathlib.Path(temp)/'roundtrip.index'),GIT_OPTIONAL_LOCKS='0')
        git(repo,'read-tree',BASE,env=round_env)
        git(repo,'apply','--cached','--check',str(patch_path),env=round_env)
        git(repo,'apply','--cached',str(patch_path),env=round_env)
        round_tree=git(repo,'write-tree',env=round_env).decode().strip()
        if tree!=round_tree:raise SystemExit(f'{scope}: patch roundtrip tree mismatch')
        files=[]
        reader=subprocess.Popen(['git','-C',str(repo),'cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
        try:
            for row in git(repo,'ls-files','--stage','-z',env=env).split(b'\0'):
                if not row:continue
                header,raw_name=row.split(b'\t',1);mode,oid,stage=header.decode().split()
                if stage!='0' or mode=='160000':raise SystemExit(f'{scope}: unsupported index entry {row!r}')
                reader.stdin.write(oid.encode()+b'\n');reader.stdin.flush()
                info=reader.stdout.readline().decode().split()
                if len(info)!=3 or info[1]!='blob':raise SystemExit(f'{scope}: missing blob {oid}')
                data=reader.stdout.read(int(info[2]));assert reader.stdout.read(1)==b'\n'
                path=repo/os.fsdecode(raw_name)
                live=os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()
                if live!=data:raise SystemExit(f'{scope}: Git filters changed working bytes for {path}')
                files.append({'path':os.fsdecode(raw_name),'mode':mode,'git_blob':oid,'bytes':len(data),'sha256':digest(data)})
        finally:
            reader.stdin.close();reader.stdout.close();reader.wait()
        table=(json.dumps(files,indent=2,ensure_ascii=False)+'\n').encode()
        (payload/(scope+'.files.json')).write_bytes(table)
    after_index=digest(real_index.read_bytes())
    if original_index!=after_index:raise SystemExit(f'{scope}: real source index changed during capture')
    if git(repo,'rev-parse','HEAD').decode().strip()!=head:raise SystemExit(f'{scope}: HEAD changed during capture')
    manifest['scopes'][scope]={'source_worktree':SOURCES[scope], 'source_head':head,
       'source_branch':git(repo,'branch','--show-current').decode().strip(),'source_status':status,
       'source_index_sha256_before':original_index,'source_index_sha256_after':after_index,
       'included_untracked':included,'excluded_untracked':excluded,'expected_tree':tree,
       'patch':scope+'.patch','patch_bytes':len(patch),'patch_sha256':digest(patch),
       'files':scope+'.files.json','files_sha256':digest(table),'file_count':len(files),
       'roundtrip_tree':round_tree,'roundtrip':'pass'}
    manifest_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    print(f'{scope}: {tree}, {len(files)} files, {len(patch)} patch bytes, roundtrip/index preservation pass',flush=True)
