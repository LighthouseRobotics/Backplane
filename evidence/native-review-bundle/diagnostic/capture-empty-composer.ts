// Diagnostic captures only. This does not change measured reports or targets.
import { writeFileSync } from "node:fs";
import { displayPixels } from "/home/the-one/Documents/backplane-overnight-2026-10-19/native-glyph/test/tools/native_display.ts";
const out = process.argv[2], display = process.argv[3];
if (!out || ![":91", ":92"].includes(display)) throw new Error("explicit diagnostic output/display required");
const xpoke = "/home/the-one/Documents/backplane-overnight-2026-10-19/native-glyph/build/xpoke";
const pause = (ms:number) => new Promise(r => setTimeout(r,ms));
const env = {...process.env, DISPLAY:display};
async function poke(...args:string[]) {
  const p = Bun.spawn([xpoke,...args],{env,stdout:"pipe",stderr:"pipe"});
  const bytes = new Uint8Array(await new Response(p.stdout).arrayBuffer());
  if (await p.exited !== 0) throw new Error("diagnostic xpoke failed");
  return bytes;
}
const records:any[] = [];
async function capture(name:string) {
  const bytes = await poke("pixels","444","788","600","32");
  const normalized = displayPixels(bytes,600,32,true);
  writeFileSync(`${out}/${name}.ppm`,bytes);
  const record = {name,sha256:new Bun.CryptoHasher("sha256").update(normalized).digest("hex")};
  records.push(record); console.log(JSON.stringify(record));
}
await poke("ctrl","k"); await pause(200); await poke("type","zqruna"); await pause(200);
await poke("key","Return"); await pause(1600); await poke("click","832","850"); await pause(500);
for(let i=0;i<5;i++){await capture(`empty-before-${i}`);await pause(400);}
await poke("type","Backplane42"); await pause(700); await capture("text");
for(let i=0;i<11;i++) await poke("key","BackSpace"); await pause(600);
for(let i=0;i<5;i++){await capture(`empty-after-${i}`);await pause(400);}
writeFileSync(`${out}/window.ppm`,await poke("pixels","0","0","1400","900"));
writeFileSync(`${out}/captures.json`,JSON.stringify({scope:"Untimed diagnostic only; exact pinned observer normalization",records},null,2)+"\n");
