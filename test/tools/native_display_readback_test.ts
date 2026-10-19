import { strict as assert } from "node:assert";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
const args=process.argv.slice(2);
if(args.length!==3) throw new Error("usage: bun native_display_readback_test.ts XPOKE FIXTURE XVFB");
if(existsSync('/tmp/.X11-unix/X94'))throw new Error('display :94 already in use');
const [xpoke,fixture,xvfb]=args.map(p=>resolve(p));
const xs=Bun.spawn([xvfb,':94','-screen','0','200x150x24','-nolisten','tcp'],{stdout:'ignore',stderr:'pipe'});
let fx: ReturnType<typeof Bun.spawn> | undefined;
try {
 await Bun.sleep(300);
 fx=Bun.spawn([fixture],{env:{...process.env,DISPLAY:':94'},stdin:'pipe',stdout:'pipe',stderr:'pipe'});
 const reader=fx.stdout.getReader();
 const first=new TextDecoder().decode((await reader.read()).value); const id=/window (\d+)/.exec(first)![1];
 async function color(name:string,r:number,g:number,b:number) {
  fx!.stdin!.write(name+'\n'); fx!.stdin!.flush(); await reader.read();
  const p=Bun.spawn([xpoke,'pixels','2','3','8','4'],{env:{...process.env,DISPLAY:':94',XPOKE_WIN:id},stdout:'pipe',stderr:'pipe'});
  const got=new Uint8Array(await new Response(p.stdout).arrayBuffer()); assert.equal(await p.exited,0);
  const head=new TextEncoder().encode('P6\n8 4\n255\n');const want=new Uint8Array(head.length+8*4*3);want.set(head);
  for(let i=head.length;i<want.length;i+=3)want.set([r,g,b],i);
  assert.deepEqual(got,want);
 }
 await color('red',255,0,0);await color('green',0,255,0);
 console.log('xpoke pixels independently read exact red/green RGB bytes from X-server fixture');
} finally {fx?.kill();xs.kill();if(fx)await fx.exited;await xs.exited;}
