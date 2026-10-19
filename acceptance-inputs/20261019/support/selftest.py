#!/usr/bin/env python3
"""Exercise acceptance guards using tiny fake repositories; no Bend invocation."""
import hashlib, json, os, pathlib, shutil, subprocess, tempfile

here=pathlib.Path(__file__).resolve().parent
def run(*args,**kw):return subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kw)
def sha(data):return hashlib.sha256(data).hexdigest()
with tempfile.TemporaryDirectory(prefix='bp-acceptance-selftest-') as temp:
    top=pathlib.Path(temp);repo=top/'repo';repo.mkdir()
    def git(*args):
        result=run('git','-C',str(repo),*args);result.check_returncode();return result.stdout
    git('init','-q');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
    source=repo/'source.txt';source.write_text('baseline\n');git('add','.');git('commit','-qm','fixture baseline')
    base=git('rev-parse','HEAD').decode().strip();source.write_text('candidate\n');git('add','.')
    tree=git('write-tree').decode().strip();blob=git('rev-parse',':source.txt').decode().strip()
    patch=git('diff','--cached','--binary','--full-index',base)
    payload=top/'payload';(payload/'support').mkdir(parents=True)
    helper=payload/'support/accept.py';shutil.copy2(here/'accept.py',helper)
    rows=[{'path':'source.txt','mode':'100644','git_blob':blob,'bytes':10,'sha256':sha(source.read_bytes())}]
    table=(json.dumps(rows)+'\n').encode();(payload/'fake.patch').write_bytes(patch);(payload/'fake.files.json').write_bytes(table)
    item={'expected_tree':tree,'patch':'fake.patch','patch_sha256':sha(patch),'files':'fake.files.json',
          'files_sha256':sha(table),'source_head':base,'file_count':1}
    manifest={'base_commit':base,'scopes':{'fake':item,'native':item}}
    (payload/'manifest.json').write_text(json.dumps(manifest))
    env=dict(os.environ,GITHUB_SHA='immutable-fixture-input',ACCEPTANCE_JOB_STATUS='success')
    evidence=top/'evidence';evidence.mkdir()
    def accept(operation,scope='fake'):
        return run('python3',str(helper),operation,'--scope',scope,'--workspace',str(repo),'--evidence',str(evidence),env=env)
    git('reset','--hard',base)
    result=accept('apply');assert result.returncode==0,result.stderr
    assert json.loads((evidence/'applied-source.json').read_text())['applied_tree']==tree
    (evidence/'check.log').write_text('check: 1s\nALL PROOFS CHECK\nproof: after check, total 2s\n')
    for name,value in [('check.exit',0),('proof.exit',0),('proof.verdict',0)]:
        (evidence/name).write_text(str(value)+'\n')
    assert accept('receipt').returncode==0,'healthy control rejected'
    (evidence/'proof.exit').unlink();assert accept('receipt').returncode!=0,'missing proof accepted'
    (evidence/'proof.exit').write_text('137\n');assert accept('receipt').returncode!=0,'killed proof accepted'
    (evidence/'proof.exit').write_text('0\n');(evidence/'check.exit').write_text('1\n')
    assert accept('receipt').returncode!=0,'failed check accepted'
    (evidence/'check.exit').write_text('0\n');source.write_text('changed during proof\n')
    assert accept('receipt').returncode!=0,'changed source accepted'
    source.write_text('candidate\n');assert accept('receipt','native').returncode!=0,'missing native build accepted'
    (repo/'dist/web').mkdir(parents=True);(repo/'dist/backplane').write_text('fake artifact\n')
    (repo/'dist/web/index.html').write_text('fake page\n');(evidence/'build.exit').write_text('0\n')
    assert accept('receipt','native').returncode==0,'native fixture control rejected'
    receipt=json.loads((evidence/'receipt.json').read_text())
    assert any(x['path']=='artifacts/dist/backplane' and x['input_commit']==env['GITHUB_SHA'] and x['sha256'] for x in receipt['artifacts'])
    (payload/'fake.patch').write_bytes(patch+b'corruption\n')
    assert accept('verify').returncode!=0,'corrupt payload accepted'
    fake=top/'fake-bend';fake.write_text('#!/bin/sh\nprintf "SOME PROOFS FAIL\\nError: 1 def relies on unsafe or foreign code:\\n- fixture\\n"\nexit 1\n');fake.chmod(0o755)
    result=run('bash',str(here/'bend-capture.sh'),'PROOF.bend',env=dict(env,ACCEPTANCE_EVIDENCE=str(evidence),ACCEPTANCE_REAL_BEND=str(fake)))
    assert result.returncode==1 and (evidence/'proof.exit').read_text()=='1\n'
    assert (evidence/'proof.log').read_bytes()==result.stdout,'wrapper changed proof bytes'
    engine=top/'bend2';engine.mkdir();(engine/'engine.js').write_text('fake toolchain engine\n')
    hashes=run('python3',str(here/'hash-tree.py'),str(engine))
    assert hashes.returncode==0 and sha((engine/'engine.js').read_bytes()).encode() in hashes.stdout
    assert run('python3',str(here/'hash-tree.py'),str(top/'missing-engine')).returncode!=0
print('PASS: healthy exact-tree receipts; missing/killed proof, failed checks, source drift, missing build and corrupt payload rejected; native artifacts hashed; wrapper preserves status/bytes')
