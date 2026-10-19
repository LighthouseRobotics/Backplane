#!/usr/bin/env python3
"""Private official stock KiCad installation and real Mac discovery/export probe."""
import argparse
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
import platform,shutil,signal,subprocess,tempfile,time,urllib.request

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--probe',type=Path,required=True)
parser.add_argument('--out',type=Path,default=Path('build/mac-stock'))
args=parser.parse_args();args.probe=args.probe.resolve(strict=True);args.out=args.out.resolve();args.out.mkdir(parents=True,exist_ok=True)
def interrupted(signum,_frame):raise KeyboardInterrupt(f'captured signal {signum}')
signal.signal(signal.SIGTERM,interrupted)
signal.signal(signal.SIGINT,interrupted)
source=json.loads(Path('test/fixtures/kicad-stock-macos-source.json').read_text())
report={'started':datetime.now(timezone.utc).isoformat(),'host':platform.platform(),'machine':platform.machine(),'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'package':source,'commands':[],'result':'running','ipc':'unavailable: stock package is not the published Backplane IPC fork'}
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  while block:=stream.read(1024*1024):h.update(block)
 return h.hexdigest()
def run(command,env=None,required=True,timeout=180):
 r=subprocess.run(list(map(str,command)),env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
 report['commands'].append({'argv':list(map(str,command)),'status':r.returncode,'output':r.stdout})
 if required and r.returncode:raise RuntimeError(f'{command}: {r.stdout}')
 return r

def gui(app,board,env):
 value={'scope':'private stock PCB editor launch observation, not GUI functional acceptance','status':'unavailable'}
 session=run(['launchctl','print',f'gui/{os.getuid()}'],required=False)
 if session.returncode:value['reason']='no accessible WindowServer GUI session';return value
 candidates=sorted(p for p in app.rglob('pcbnew') if p.is_file() and os.access(p,os.X_OK))
 if not candidates:value['reason']='stock package has no contained pcbnew GUI executable';return value
 executable=candidates[0].resolve();assert executable.is_relative_to(app.resolve())
 proc=None
 try:
  with (args.out/'gui.log').open('w') as log:
   proc=subprocess.Popen([str(executable),str(board)],env=env,stdout=log,stderr=subprocess.STDOUT)
   value.update(pid=proc.pid,executable=str(executable));time.sleep(5)
   value['aliveAfterSeconds']=5 if proc.poll() is None else 0
   if proc.poll() is not None:value.update(status='failed',exitCode=proc.returncode);return value
   image=args.out/'stock-gui.png';image.unlink(missing_ok=True)
   capture=run(['screencapture','-x',image],required=False,timeout=20)
   value['status']='launched'
   if capture.returncode:value['screenshot']='unavailable: '+capture.stdout
   else:
    assert image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n');value['screenshotSha256']=sha(image)
   return value
 except (OSError,ValueError,AssertionError,subprocess.TimeoutExpired) as error:
  value.update(status='unavailable',reason=str(error));return value
 finally:
  if proc and proc.poll() is None:
   proc.terminate()
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=10)

try:
 assert platform.system()=='Darwin','actual Mac only'
 run(['sw_vers']);run(['uname','-sm'])
 with tempfile.TemporaryDirectory(prefix='bp-stock-kicad-',dir=os.environ['RUNNER_TEMP']) as directory:
  root=Path(directory);mount=root/'mount';mount.mkdir();user=root/'user';home=root/'home';exe=root/'backplane'
  for p in (user,home,exe,user/'Library/Preferences',user/'Library/Caches'):p.mkdir(parents=True,exist_ok=True)
  env=dict(os.environ,HOME=str(user),CFFIXED_USER_HOME=str(user),KICAD_CONFIG_HOME=str(user/'kicad-config'),BACKPLANE_HOME=str(home),XDG_CONFIG_HOME=str(user/'config'),XDG_DATA_HOME=str(user/'data'))
  env.pop('BACKPLANE_KICAD',None);env.pop('BACKPLANE_KICAD_CLI',None)
  archive=root/source['filename'];request=urllib.request.Request(source['url'],headers={'User-Agent':'Backplane isolated stock KiCad acceptance'})
  with urllib.request.urlopen(request,timeout=120) as response,archive.open('wb') as output:
   while data:=response.read(1024*1024):output.write(data)
  assert archive.stat().st_size==source['bytes'] and sha(archive)==source['sha256'],'official package size/digest mismatch before mount'
  report['archiveVerified']=True
  attached=False
  try:
   response=run(['hdiutil','attach','-readonly','-nobrowse','-mountpoint',mount,'-plist',archive]);attached=True
   (args.out/'mount.plist').write_text(response.stdout)
   apps=sorted(p for p in mount.rglob('KiCad.app') if p.is_dir());assert len(apps)==1,apps
   app=user/'Applications/KiCad/KiCad.app';app.parent.mkdir(parents=True)
   run(['ditto',apps[0],app],timeout=240)
  finally:
   if attached or mount.is_mount():run(['hdiutil','detach',mount],timeout=60)
  cli=app/'Contents/MacOS/kicad-cli';assert cli.is_file()
  run(['codesign','--verify','--deep','--strict',app],timeout=120)
  signature=run(['codesign','-d','--verbose=4',app]);(args.out/'codesign.txt').write_text(signature.stdout)
  report['cliSha256']=sha(cli);version=run([cli,'version'],env=env);assert version.stdout.strip()==source['version'],version.stdout
  report['cliVersion']=version.stdout.strip()
  # Explicit discovery and healthy selection always stay inside the owned copy.
  selected_env=dict(env,BACKPLANE_KICAD=str(app),BACKPLANE_KICAD_CLI=str(cli))
  selection={}
  for mode in ('discover','refresh','resolve'):
   value=json.loads(run([args.probe,mode,home,exe],env=selected_env).stdout)
   assert value['cli']==str(cli),value
   if mode!='discover':assert value['status']=='stock' and value['runs'] is True and value['fork'] is False,value
   selection[mode]=value
  (home/'kicad-health.json').write_text(json.dumps(selection['refresh']))
  selection['boot']=json.loads(run([args.probe,'boot',home,exe],env=selected_env).stdout)
  assert selection['boot']['cli']==str(cli) and selection['boot']['status']=='stock',selection['boot']
  # Test actual per-user application fallback without touching /Applications.
  if not Path('/Applications/KiCad/KiCad.app').exists():
   for mode in ('discover','refresh','resolve'):
    value=json.loads(run([args.probe,mode,home,exe],env=env).stdout);assert value['cli']==str(cli) and value['source']=='app',value
    if mode!='discover':assert value['status']=='stock' and value['fork'] is False,value
    selection['automatic-'+mode]=value
  else:selection['automatic']={'status':'unavailable','reason':'an existing global KiCad app has precedence; it was not replaced or executed'}
  report['selection']=selection
  ipc=run([cli,'api-server','--describe'],env=env,required=False);assert ipc.returncode!=0,'unexpected stock fork API response; do not claim bp.4 IPC'
  run(['python3','scripts/fetch-cad-fixture.py','--out',args.out/'fixture'])
  board=args.out/'fixture/ecc83-pp.kicad_pcb';glb=args.out/'ecc83-board.glb';glb.unlink(missing_ok=True)
  run([cli,'pcb','export','glb','--help'],env=env)
  exported=run([cli,'pcb','export','glb','--force','--board-only','--include-tracks','--include-pads','--include-silkscreen','-o',glb,board],env=env,timeout=240)
  assert glb.read_bytes()[:4]==b'glTF' and glb.stat().st_size>1000
  report['export']={'glbSha256':sha(glb),'bytes':glb.stat().st_size,'fixtureSha256':sha(board)}
  gui_board=args.out/'gui-input/ecc83-pp.kicad_pcb';gui_board.parent.mkdir(exist_ok=True);shutil.copyfile(board,gui_board)
  report['gui']=gui(app,gui_board,env)
  report['probeSha256']=sha(args.probe);report['result']='pass'
except (OSError,ValueError,AssertionError,RuntimeError,subprocess.TimeoutExpired,KeyboardInterrupt) as error:
 report['result']='fail';report['error']=str(error)
finally:
 report['finished']=datetime.now(timezone.utc).isoformat();(args.out/'stock-result.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['result'],args.out/'stock-result.json')
raise SystemExit(0 if report['result']=='pass' else 1)
