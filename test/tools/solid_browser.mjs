// After solid_roundtrip.mjs has written its CBOR fixtures:
// PLAYWRIGHT_MODULE=/path/to/playwright-core/index.mjs CHROME=/path/to/chrome \
//   node test/tools/solid_browser.mjs FIXTURE_DIRECTORY
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const dir=resolve(process.argv[2]);
const source=readFileSync(new URL('../../src/web/solid.js',import.meta.url),'utf8').replace('import App from "./app.bend";','const App = {};')+'\nexport {View, mesh};';
const browser=await chromium.launch({executablePath:process.env.CHROME,headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const reports=[];
try {
 const page=await browser.newPage({viewport:{width:800,height:600},deviceScaleFactor:1});
 await page.setContent('<style>body{margin:0;background:#181a1c}canvas{width:800px;height:600px}</style><canvas id="solid"></canvas>');
 await page.evaluate(async url=>{window.S=await import(url);window.v=new S.View(document.querySelector('canvas'));if(!v.gl)throw new Error('WebGL unavailable');},'data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
 for(const fixture of ['board','step']) {
   const bytes=[...readFileSync(resolve(dir,fixture+'-orientation.cbor'))];
   for(const [name,pitch] of [['top',Math.PI/2-0.00001],['bottom',-Math.PI/2+0.00001],['oblique',0.5]]) {
     const result=await page.evaluate(({bytes,pitch})=>{
       v.show(S.mesh(S.cbor(Uint8Array.from(bytes))));v.cam.aim(0,pitch);v.draw();
       const gl=v.gl, pixels=new Uint8Array(800*600*4);gl.readPixels(0,0,800,600,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
       const sums={red:[0,0,0],blue:[0,0,0],green:[0,0,0]};
       for(let i=0;i<pixels.length;i+=4){const [r,g,b,a]=pixels.subarray(i,i+4);const c=r>100&&g<20&&b<20?'red':b>100&&r<20&&g<20?'blue':g>100&&r<20&&b<20?'green':null;if(c&&a){sums[c][0]+=i/4%800;sums[c][1]+=599-Math.floor(i/4/800);sums[c][2]++;}}
       return Object.fromEntries(Object.entries(sums).map(([k,[x,y,n]])=>[k,{x:x/n,y:y/n,pixels:n}]));
     },{bytes,pitch});
     assert.ok(result.red.pixels>100 && result.blue.pixels>100,fixture+'/'+name+' landmarks visible');
     if(name==='top'){assert.ok(result.red.x>result.blue.x,'+X points right');assert.ok(result.red.y<result.blue.y,'+Y points up from top');}
     if(name==='bottom')assert.ok(result.red.y>result.blue.y,'bottom camera reverses screen Y');
     if(name==='oblique')assert.ok(result.green.pixels>100,'side landmark visible');
     reports.push({fixture,view:name,landmarks:result});
     await page.screenshot({path:resolve(dir,fixture+'-'+name+'.png')});
   }
 }
 const report={browser:await browser.version(),renderer:'production src/web/solid.js WebGL, SwiftShader',reports};
 writeFileSync(resolve(dir,'solid-browser.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
} finally {await browser.close();}
