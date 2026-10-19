import { strict as assert } from "node:assert";
import { awaitDisplay, calibrateDisplay, displayPixels } from "./native_display";
async function scenario(values: string[], target = "target", before = "old") {
  let t = 0;
  return awaitDisplay(target, before, async () => { t += 2; return values.shift() ?? "stale"; }, () => t, async ms => {t += ms;}, 0, 20);
}
assert.deepEqual(await scenario(["old", "target"]), {elapsed_ms:8,samples:2,pixel_sha256:"target"});
await assert.rejects(scenario(["old", "old", "old"]), /timed out/);
await assert.rejects(scenario(["wrong", "wrong", "wrong"]), /timed out/);
await assert.rejects(scenario(["target"], "target", "target"), /does not distinguish/);
let late = 0;
await assert.rejects(awaitDisplay("target", "old", async () => { late = 21; return "target"; }, () => late, async () => {}, 0, 20), /timed out/);
console.log("native display demand: changed target accepted; stale, wrong, indistinguishable and late content rejected");
function ppm(colors: number[]) {
  const header = new TextEncoder().encode(`P6\n${colors.length} 1\n255\n`);
  const bytes = new Uint8Array(header.length + colors.length*3); bytes.set(header);
  colors.forEach((c,i) => bytes.set([c>>16,(c>>8)&255,c&255],header.length+i*3)); return bytes;
}
assert.deepEqual(displayPixels(ppm([14277092,6271999]),2,1,true), displayPixels(ppm([14277092,1250843]),2,1,true));
assert.deepEqual(displayPixels(ppm([1776929,2060241]),2,1,true), displayPixels(ppm([1776929,15855852]),2,1,true));
assert.notDeepEqual(displayPixels(ppm([14277092,6271999]),2,1,true), displayPixels(ppm([1250843,6271999]),2,1,true));
assert.notDeepEqual(displayPixels(ppm([14277092,1250843]),2,1,true), displayPixels(ppm([14277093,1250843]),2,1,true));
assert.throws(() => displayPixels(ppm([1,2]),3,1), /expected RGB PPM/);
console.log("composer observer: caret blink ignored; missing/corrupt glyph pixels and wrong region size distinguished");

async function calibration(values:string[],options:{before?:string;expected?:string}={}){
  let now=0,index=0;
  return calibrateDisplay(async()=>values[Math.min(index++,values.length-1)],{...options,stableMs:120,timeoutMs:500},()=>now,async ms=>{now+=ms;});
}
assert.equal(await calibration(["old","old","new","new","new","new"],{before:"old"}),"new");
assert.equal(await calibration(["wrong","wrong","empty","empty","empty","empty"],{expected:"empty"}),"empty");
assert.equal(await calibration(["old","new","old","new","new","new","new"],{before:"old"}),"new");
await assert.rejects(calibration(["old"],{before:"old"}),/timed out/);
await assert.rejects(calibration(["wrong"],{expected:"empty"}),/timed out/);
let clock=0,step=0;
await assert.rejects(calibrateDisplay(async()=>++step%2?"a":"b",{stableMs:120,timeoutMs:500},()=>clock,async ms=>{clock+=ms;}),/timed out/);
let lateCalibration=0;
await assert.rejects(calibrateDisplay(async()=>{lateCalibration=501;return "new";},{timeoutMs:500},()=>lateCalibration,async()=>{}),/timed out/);
console.log("calibration: delayed/transient frames settle; unchanged, wrong-empty, oscillating and late pixels rejected (7 controls)");
