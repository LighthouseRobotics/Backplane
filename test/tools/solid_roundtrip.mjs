// bend test/tools/solid_roundtrip.bend -o build/solid-roundtrip.mjs
// node test/tools/solid_roundtrip.mjs build/solid-roundtrip.mjs [output directory]
// No CAD installation or downloaded fixture: labeled asymmetric triangles
// become a real GLB, then pass through the hub encoder and browser decoder.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';
const {default:B}=await import(pathToFileURL(resolve(process.argv[2])));
const source=readFileSync(new URL('../../src/web/solid.js',import.meta.url),'utf8')
  .replace('import App from "./app.bend";', 'const App = {};')+'\nexport {mesh};';
const {cbor,mesh,isPlot}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const list=xs=>xs.reduceRight((tail,head)=>({$: 'Con',head,tail}),{$:'Nil'});
const array=xs=>{const out=[];for(;xs.$!=='Nil';xs=xs.tail)out.push(xs.head);return out;};
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const normal=p=>{const n=cross(p[1].map((x,i)=>x-p[0][i]),p[2].map((x,i)=>x-p[0][i]));const d=Math.hypot(...n);return n.map(x=>x/d);};
const near=(a,b,why,eps=1e-5)=>{assert.equal(a.length,b.length,why);a.forEach((x,i)=>assert.ok(Math.abs(x-b[i])<eps,`${why}[${i}]: ${x} != ${b[i]}`));};
// Board coordinates in millimetres, Z up. Top +Z, underside -Z, side +X;
// unequal legs and signed coordinates expose mirrored geometry and bounds.
const landmarks=[
 {name:'FRONT_RED_F.Cu',rgb:0xff0000,p:[[2,3,1.6],[7,3,1.6],[2,9,1.6]]},
 {name:'BACK_BLUE_B.Cu',rgb:0x0000ff,p:[[-4,-2,-1],[-4,4,-1],[1,-2,-1]]},
 {name:'RIGHT_GREEN',rgb:0x00ff00,p:[[11,-3,0],[11,5,0],[11,-3,4]]},
];
function fixture(step) {
 const chunks=[];const nodes=[];const meshes=[];const accessors=[];const bufferViews=[];const materials=[];let offset=0;
 for(const [i,t] of landmarks.entries()) {
   const pts=t.p.map(p=>step?p:p.map((_,a)=>[p[0]/1000,p[2]/1000,-p[1]/1000][a]));
   const buf=Buffer.alloc(36);pts.flat().forEach((x,j)=>buf.writeFloatLE(x,j*4));chunks.push(buf);
   bufferViews.push({buffer:0,byteOffset:offset,byteLength:36});offset+=36;
   accessors.push({bufferView:i,componentType:5126,count:3,type:'VEC3'});
   materials.push({name:t.name,pbrMetallicRoughness:{baseColorFactor:[(t.rgb>>16)/255,((t.rgb>>8)&255)/255,(t.rgb&255)/255,1]}});
   meshes.push({name:t.name,primitives:[{attributes:{POSITION:i},material:i,mode:4}]});
   nodes.push({name:t.name,mesh:i});
 }
 const doc={asset:{version:'2.0',generator:'Backplane synthetic orientation regression'},scene:0,scenes:[{nodes:nodes.map((_,i)=>i)}],nodes,meshes,accessors,bufferViews,materials,buffers:[{byteLength:offset}]};
 let json=Buffer.from(JSON.stringify(doc));json=Buffer.concat([json,Buffer.alloc((4-json.length%4)%4,32)]);
 const bin=Buffer.concat(chunks);const head=Buffer.alloc(20);head.writeUInt32LE(0x46546c67,0);head.writeUInt32LE(2,4);head.writeUInt32LE(28+json.length+bin.length,8);head.writeUInt32LE(json.length,12);head.writeUInt32LE(0x4e4f534a,16);
 const bh=Buffer.alloc(8);bh.writeUInt32LE(bin.length,0);bh.writeUInt32LE(0x004e4942,4);return Buffer.concat([head,json,bh,bin]);
}
// Production Solid.thin snaps X/Z to cell centres at 1/1000 of the
// model diagonal; wire encoding then rounds to 10 micrometres. Up/height
// stays unchanged. Bound the expected planar movement independently from
// the fixture dimensions, without allowing a reflected landmark.
const planarTolerance=Math.hypot(15,12,5)/1000*100/2+0.50001;
const reports=[];
for(const step of [false,true]) {
 const bytes=fixture(step);const input=list([...bytes]);
 const parts=array(B.parts(input).parts);assert.deepEqual(parts.map(p=>p.name).sort(),landmarks.map(p=>p.name).sort());
 const triangles=array(B.triangles(input,step));assert.equal(triangles.length,3);
 const packet=Uint8Array.from(array(B.packet(input,step)));
 assert.ok(isPlot(packet));const o=cbor(packet);assert.equal(o.key,'2|fixture|orientation.glb');assert.equal(o.n,3);
 const decoded=mesh(o);assert.equal(decoded.count,9);
 for(const [i,t] of triangles.entries()) {
   const rgb=t.color>>>0;const target=landmarks.find(p=>p.rgb===rgb);assert.ok(target,`unknown color ${rgb}`);
   const p=Array.from(decoded.pos.slice(i*9,i*9+9));near(p,target.p.flat().map(x=>x*100),target.name+' board position',planarTolerance);
   near(p.filter((_,j)=>j%3===2),target.p.map(q=>q[2]*100),target.name+' exact layer height');
   near(Array.from(decoded.nrm.slice(i*9,i*9+3)),normal(target.p),target.name+' face normal');
   const native=[[t.ax,t.ay,t.az],[t.bx,t.by,t.bz],[t.cx,t.cy,t.cz]];
   near(native.flatMap(([x,y,z])=>[x*100000,-z*100000,y*100000]),p,target.name+' native/source rotation',planarTolerance);
   const sourceN=normal(native);near([sourceN[0],-sourceN[2],sourceN[1]],normal(target.p),target.name+' determinant and winding');
 }
 const expected=[-400,-300,-100,1100,900,400];near(decoded.box,expected,'decoder signed bounds',planarTolerance);near(o.box3,decoded.box,'encoder/decoder exact signed bounds');
 // Top and bottom positions align with board XY and stay on their own sides.
 assert.equal(normal(landmarks[0].p)[2],1);assert.equal(normal(landmarks[1].p)[2],-1);
 assert.ok(landmarks[0].p[0][2]>0 && landmarks[1].p[0][2]<0);
 reports.push({source:step?'STEP converter millimetres, upright':'KiCad/glTF metres, Y up',labels:parts.map(p=>p.name),triangles:o.n,box:decoded.box,positionNormalWinding:'pass',planarToleranceWireUnits:planarTolerance,layerHeights:'exact'});
 if(process.argv[3]) {mkdirSync(process.argv[3],{recursive:true});writeFileSync(resolve(process.argv[3],step?'step-orientation.glb':'board-orientation.glb'),bytes);writeFileSync(resolve(process.argv[3],step?'step-orientation.cbor':'board-orientation.cbor'),packet);}
}
console.log(JSON.stringify({runtime:process.version,productionDecoder:'src/web/solid.js mesh/cbor',reports},null,2));
