// Real Mac stock CLI GLB -> actual Bend parser/encoder -> production web decoder.
// Node --stack-size=196608 is required for the deliberately non-phone parse probe.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const [mode,...args]=process.argv.slice(2);
const sha=b=>createHash('sha256').update(b).digest('hex');
const solid=readFileSync(new URL('../../src/web/solid.js',import.meta.url),'utf8')
  .replace('import App from "./app.bend";','const App = {};')+'\nexport {View,mesh};';
const moduleUrl='data:text/javascript;base64,'+Buffer.from(solid).toString('base64');
if(mode==='encode') {
  const [generated,input,out]=args.map(p=>resolve(p));mkdirSync(out,{recursive:true});
  const {default:B}=await import(pathToFileURL(generated));const bytes=readFileSync(input);
  assert.equal(bytes.readUInt32LE(0),0x46546c67);assert.equal(bytes.readUInt32LE(4),2);
  let xs={$:'Nil'};for(let i=bytes.length-1;i>=0;i--)xs={$:'Con',head:bytes[i],tail:xs};
  const parts=[];for(let p=B.parts(xs).parts;p.$!=='Nil';p=p.tail)parts.push(p.head.name);
  const values=[];for(let p=B.packet(xs,false);p.$!=='Nil';p=p.tail)values.push(p.head);
  const packet=Uint8Array.from(values),S=await import(moduleUrl),mesh=S.mesh(S.cbor(packet));
  assert.ok(mesh.count>1000,'real board has a nontrivial triangle mesh');
  assert.ok(mesh.box.every(Number.isFinite));for(let i=0;i<3;i++)assert.ok(mesh.box[i+3]>mesh.box[i]);
  const report={source:'Mac stock KiCad GLB -> production Bend Glb.parse/Mesh.tris/Solid.thin/Plot.msg.solid -> actual src/web/solid.js cbor/mesh',
    node:process.version,parserHost:process.platform,stackKiB:196608,parts,vertices:mesh.count,box:mesh.box,
    generatedModuleSha256:sha(readFileSync(generated)),glbSha256:sha(bytes),packetSha256:sha(packet),decoderSourceSha256:sha(readFileSync(new URL('../../src/web/solid.js',import.meta.url)))};
  writeFileSync(resolve(out,'board.cbor'),packet);writeFileSync(resolve(out,'parse.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
} else if(mode==='render') {
  const out=resolve(args[0]),packet=readFileSync(resolve(out,'board.cbor'));
  const {chromium}=await import(pathToFileURL(resolve(process.env.PLAYWRIGHT_MODULE ?? 'tools/browser/node_modules/playwright-core/index.mjs')));
  const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME,args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  try {
    const page=await browser.newPage({viewport:{width:900,height:700},deviceScaleFactor:1});
    await page.setContent('<style>body{margin:0;background:#181a1c}canvas{width:900px;height:700px}</style><canvas></canvas>');
    const view=await page.evaluate(async({url,bytes})=>{
      const S=await import(url),v=new S.View(document.querySelector('canvas'));if(!v.gl)throw Error('production WebGL unavailable');
      const m=S.mesh(S.cbor(Uint8Array.from(bytes)));v.show(m);v.cam.aim(0,0.8);v.draw();
      const gl=v.gl,pixels=new Uint8Array(900*700*4);gl.readPixels(0,0,900,700,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
      const colors=new Set();for(let i=0;i<pixels.length;i+=4)colors.add(pixels[i]+','+pixels[i+1]+','+pixels[i+2]);
      const debug=gl.getExtension('WEBGL_debug_renderer_info');return {vertices:m.count,box:m.box,colors:colors.size,renderer:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER)};
    },{url:moduleUrl,bytes:[...packet]});
    assert.ok(view.vertices>1000 && view.colors>10);assert.ok(view.box.every(Number.isFinite));
    const prefix=process.platform;await page.screenshot({path:resolve(out,prefix+'-board.png')});
    const report={host:process.platform,source:'production src/web/solid.js View/cbor/mesh',browser:await browser.version(),packetSha256:sha(packet),...view};
    writeFileSync(resolve(out,prefix+'-view.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
  } finally {await browser.close();}
} else throw Error('encode MODULE GLB OUT | render OUT');
