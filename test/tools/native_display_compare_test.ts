import { strict as assert } from "node:assert";
import { createHash } from "node:crypto";
import { compareNativeDisplay } from "./native_display_compare";
const hash = (value:string) => createHash("sha256").update(value).digest("hex");
const probe = "Backplane42";
function fixture(surface = "both") {
  const inputs = surface !== "titles", opens = surface !== "inputs";
  const input = inputs ? Object.fromEntries(["",...Array.from(probe,(_,i) => probe.slice(0,i+1))].map(s => [s,hash("input:"+s)])) : {};
  const title = opens ? Object.fromEntries(["zqlong",...Array.from({length:10},(_,i) => `zqopen${String.fromCharCode(97+i)}`),"zqruna","zqrunb"].map(s => [s,hash("title:"+s)])) : {};
  const d:any = {schema_version:1,enabled:true,inputs_enabled:inputs,opens_enabled:opens,input_cache:inputs?"warm-calibrated":"uncalibrated",open_cache:opens?"warm-calibrated":"uncalibrated",boundary:"xserver-readback",physical_scanout_verified:false,input_probe:probe,input_repeats:6,composer_region:[444,788,600,32],header_region:[312,12,180,30],caret_normalization:inputs?"exact solid dark/light theme caret colors replaced with corresponding panel colors":null,input_targets:input,targets:title,demands:[]};
  const observe = (row:any,digest:string) => d.demands.push({...row,revision:d.demands.length+1,boundary:d.boundary,thread:"fixture-thread",expected_pixel_sha256:digest,pixel_sha256:digest,dispatch_started_ms:d.demands.length*125,elapsed_ms:7,samples:1});
  let draft = "";
  if(inputs) for(let n=0;n<6;n++) {
    for(const key of probe) {draft+=key;observe({kind:"input",phase:"input-display",key,draft,region:d.composer_region},input[draft]);}
    for(let i=0;i<probe.length;i++) {draft=draft.slice(0,-1);observe({kind:"input",phase:"input-display",key:"BackSpace",draft,region:d.composer_region},input[draft]);}
  }
  if(opens) for(let i=0;i<10;i++) {const name=`zqopen${String.fromCharCode(97+i)}`;observe({kind:"open",phase:"open",title:name,region:d.header_region},title[name]);}
  return {log_sha256:hash("fixture"),log_bytes:555928,harness_sha256:hash("driver"),observer_sha256:hash("observer"),xpoke_sha256:hash("xpoke"),binary_sha256:hash("baseline binary"),source_sha_declared:"3".repeat(40),build_flags_declared:"LLVM19 -O3 LOW_MEM=1 JOBS=1",machine:{hostname:"fixture",platform:"linux",arch:"x64",release:"fixture-kernel",cpu_model:"fixture-cpu",cpu_count:8},agents:2,secs:5,phases:[...(inputs?[{name:"input-display"}]:[]),...(opens?[{name:"open"}]:[])],native_display:d};
}
let checks = 0;
const pass = (name:string,run:()=>void) => {run();checks++;console.log(`ok ${name}`);};
for(const surface of ["both","inputs","titles"]) pass(`independent ${surface} references agree`,() => {
  const baseline=fixture(surface),candidate=structuredClone(baseline);
  candidate.binary_sha256=hash("candidate binary");candidate.source_sha_declared="4".repeat(40);
  for(const d of candidate.native_display.demands) {d.thread="different-isolated-run-thread";d.elapsed_ms=25;}
  assert.equal(compareNativeDisplay(baseline,candidate).verdict,"pass"); // budget verdicts stay separate
});
function reject(name:string,mutate:(report:any)=>void,pattern:RegExp) {
  pass(name,()=>{const a=fixture(),b=structuredClone(a);mutate(b);assert.throws(()=>compareNativeDisplay(a,b),pattern);});
}
reject("self-calibrated wrong glyphs rejected",b => {
  const wrong=hash("consistently wrong glyph pixels");b.native_display.input_targets.Back=wrong;
  for(const d of b.native_display.demands)if(d.kind==="input"&&d.draft==="Back")d.expected_pixel_sha256=d.pixel_sha256=wrong;
},/composer reference pixels differ/);
reject("self-calibrated wrong header rejected",b => {
  const wrong=hash("consistently wrong title");b.native_display.targets.zqopena=wrong;
  for(const d of b.native_display.demands)if(d.title==="zqopena")d.expected_pixel_sha256=d.pixel_sha256=wrong;
},/title reference pixels differ/);
reject("missing prefix rejected",b=>delete b.native_display.input_targets.Back,/missing\/extra input prefixes/);
reject("duplicate prefix pixels rejected",b=>b.native_display.input_targets.Back=b.native_display.input_targets.B,/indistinguishable/);
reject("invalid target hash rejected",b=>b.native_display.targets.zqopena="not-a-sha",/invalid SHA/);
reject("stale observed pixels rejected",b=>b.native_display.demands[0].pixel_sha256=hash("stale"),/wrong\/stale/);
reject("missing input demand rejected",b=>b.native_display.demands.splice(0,1),/missing\/reordered input demands/);
reject("reordered input demands rejected",b=>{const r=b.native_display.demands[0];r.key="x";},/missing\/reordered input demands/);
reject("missing title demand rejected",b=>b.native_display.demands.pop(),/missing\/reordered title-open demands/);
reject("changed caret normalization rejected",b=>b.native_display.caret_normalization="mask all foreground pixels",/caret normalization/);
reject("changed demand region rejected",b=>b.native_display.demands[0].region=[0,0,600,32],/demand region differs/);
reject("self-consistent changed observer region rejected",b=>{
  b.native_display.composer_region=[450,788,600,32];
  for(const d of b.native_display.demands)if(d.kind==="input")d.region=b.native_display.composer_region;
},/composer_region: observer metadata differs/);
reject("missing observer metadata rejected",b=>delete b.native_display.schema_version,/missing native_display/);
reject("different boundary rejected",b=>b.native_display.boundary="app-counter",/different observation boundary/);
reject("different fixture rejected",b=>b.log_sha256=hash("other fixture"),/log_sha256/);
reject("different harness rejected",b=>b.harness_sha256=hash("other driver"),/harness_sha256/);
reject("different xpoke rejected",b=>b.xpoke_sha256=hash("other xpoke"),/xpoke_sha256/);
reject("different build flags rejected",b=>b.build_flags_declared="LLVM19 -O0",/build_flags_declared/);
reject("unknown build flags rejected",b=>b.build_flags_declared="unspecified",/build flags missing/);
reject("different hardware rejected",b=>b.machine.cpu_model="different CPU",/machine/);
reject("missing hardware identity rejected",b=>delete b.machine.cpu_model,/machine cpu_model missing/);
reject("missing phase identity rejected",b=>delete b.phases,/measured phase identity missing/);
reject("unknown source rejected",b=>b.source_sha_declared="unspecified",/full declared source SHA/);
reject("different load rejected",b=>b.secs=20,/secs/);
reject("duplicate demand revision rejected",b=>b.native_display.demands[1].revision=1,/nonmonotonic/);
reject("empty observers rejected",b=>{b.native_display.input_targets={};b.native_display.targets={};},/missing\/extra/);
console.log(`${checks} independent native display comparison controls passed`);
