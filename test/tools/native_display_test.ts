import { strict as assert } from "node:assert";
import { awaitDisplay, displayPixels } from "./native_display";
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
