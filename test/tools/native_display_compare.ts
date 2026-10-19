// Compare independently captured baseline/candidate pixel references. This
// rejects a candidate that consistently calibrates its own wrong pixels.
// It compares content and experiment identity, not latency-budget verdicts.
import { strict as assert } from "node:assert";
import { readFileSync, writeFileSync } from "node:fs";

const sha = /^[0-9a-f]{64}$/;
const fields = ["schema_version", "inputs_enabled", "opens_enabled", "input_cache", "open_cache", "boundary", "physical_scanout_verified", "input_probe", "input_repeats", "composer_region", "header_region", "caret_normalization"];
function mapOf(value: unknown, name: string): Record<string,string> {
  assert(value && typeof value === "object" && !Array.isArray(value), `${name}: missing target map`);
  const entries = Object.entries(value);
  for (const [key, digest] of entries) assert(typeof digest === "string" && sha.test(digest), `${name}: invalid SHA-256 for ${JSON.stringify(key)}`);
  assert.equal(new Set(entries.map(([,v]) => v)).size, entries.length, `${name}: indistinguishable target pixels`);
  return value as Record<string,string>;
}
function region(value: unknown, name: string) {
  assert(Array.isArray(value) && value.length === 4 && value.every(Number.isInteger)
    && value[0] >= 0 && value[1] >= 0 && value[2] > 0 && value[3] > 0, `${name}: invalid region`);
}
function targets(report: any, label: string) {
  const d = report.native_display;
  assert(d && d.enabled === true, `${label}: native displayed-content observations are missing`);
  for (const field of fields) assert(Object.hasOwn(d,field), `${label}: missing native_display.${field}`);
  assert.equal(d.schema_version,1,`${label}: unsupported observer schema`);
  assert.equal(d.boundary,"xserver-readback",`${label}: different observation boundary`);
  assert.equal(d.physical_scanout_verified,false,`${label}: unverified physical boundary claim`);
  assert.equal(typeof d.inputs_enabled,"boolean"); assert.equal(typeof d.opens_enabled,"boolean");
  assert(d.inputs_enabled || d.opens_enabled,`${label}: no displayed-content surface enabled`);
  region(d.composer_region,`${label}: composer`); region(d.header_region,`${label}: header`);
  const input = mapOf(d.input_targets,`${label}: input`), title = mapOf(d.targets,`${label}: title`);
  const prefixes = ["",...Array.from(d.input_probe ?? "",(_:unknown,i:number) => d.input_probe.slice(0,i+1))];
  if (d.inputs_enabled) {
    assert(typeof d.input_probe === "string" && /^[A-Za-z0-9]+$/.test(d.input_probe),`${label}: expected ASCII probe missing`);
    assert(Number.isInteger(d.input_repeats) && d.input_repeats > 0,`${label}: invalid input repeat count`);
    assert.equal(d.input_cache,"warm-calibrated",`${label}: input cache mode`);
    assert.equal(d.caret_normalization,"exact solid dark/light theme caret colors replaced with corresponding panel colors",`${label}: different caret normalization`);
    assert.deepEqual(Object.keys(input).sort(),prefixes.sort(),`${label}: missing/extra input prefixes`);
  } else assert.deepEqual(input,{},`${label}: disabled input surface has targets`);
  if (d.opens_enabled) {
    assert(Number.isInteger(report.agents) && report.agents >= 1 && report.agents <= 26,`${label}: invalid agent count`);
    assert.equal(d.open_cache,"warm-calibrated",`${label}: open cache mode`);
    const names = ["zqlong",...Array.from({length:10},(_,i) => `zqopen${String.fromCharCode(97+i)}`),...Array.from({length:report.agents},(_,i) => `zqrun${String.fromCharCode(97+i)}`)];
    assert.deepEqual(Object.keys(title).sort(),names.sort(),`${label}: missing/extra title targets`);
  } else assert.deepEqual(title,{},`${label}: disabled title surface has targets`);
  const demands = d.demands;
  assert(Array.isArray(demands),`${label}: observed demands missing`);
  let previous = 0;
  for (const demand of demands) {
    assert(Number.isInteger(demand.revision) && demand.revision > previous,`${label}: nonmonotonic demand revision`);
    previous = demand.revision;
    assert.equal(demand.boundary,d.boundary,`${label}: demand boundary differs`);
    const expected = demand.kind === "input" ? input[demand.draft] : demand.kind === "open" ? title[demand.title] : undefined;
    assert(expected,`${label}: demand has no calibrated target`);
    assert.equal(demand.expected_pixel_sha256,expected,`${label}: demand expectation differs from reference`);
    assert.equal(demand.pixel_sha256,expected,`${label}: observed wrong/stale target`);
    assert.deepEqual(demand.region,demand.kind === "input" ? d.composer_region : d.header_region,`${label}: demand region differs`);
    assert(Number.isFinite(demand.elapsed_ms) && demand.elapsed_ms >= 0 && demand.elapsed_ms <= 2000,`${label}: invalid observation duration`);
    assert(Number.isFinite(demand.dispatch_started_ms) && Number.isInteger(demand.samples) && demand.samples >= 1,`${label}: missing observation timing/samples`);
    assert(typeof demand.thread === "string" && demand.thread.length > 0,`${label}: demand thread missing`);
  }
  if (d.inputs_enabled) {
    const actual = demands.filter((r:any) => r.kind === "input" && r.phase === "input-display");
    const expected: {draft:string;key:string}[] = [];
    let draft = "";
    for(let repeat=0;repeat<d.input_repeats;repeat++) {
      for(const key of d.input_probe) { draft += key; expected.push({draft,key}); }
      for(let i=0;i<d.input_probe.length;i++) { draft=draft.slice(0,-1); expected.push({draft,key:"BackSpace"}); }
    }
    assert.deepEqual(actual.map((r:any) => ({draft:r.draft,key:r.key})),expected,`${label}: missing/reordered input demands`);
  }
  if (d.opens_enabled) {
    assert.deepEqual(demands.filter((r:any) => r.kind === "open" && r.phase === "open").map((r:any) => r.title),Array.from({length:10},(_,i) => `zqopen${String.fromCharCode(97+i)}`),`${label}: missing/reordered title-open demands`);
  }
  return {display:d,input,title};
}

export function compareNativeDisplay(baseline: any, candidate: any) {
  const a = targets(baseline,"baseline"), b = targets(candidate,"candidate");
  for (const field of ["log_sha256","harness_sha256","observer_sha256","xpoke_sha256"]) {
    assert(typeof baseline[field] === "string" && sha.test(baseline[field]),`baseline: missing ${field}`);
    assert.equal(candidate[field],baseline[field],`${field}: experiments used different bytes`);
  }
  for (const report of [baseline,candidate]) {
    assert(typeof report.binary_sha256 === "string" && sha.test(report.binary_sha256),"binary SHA-256 missing");
    assert(typeof report.source_sha_declared === "string" && /^[0-9a-f]{40}$/.test(report.source_sha_declared),"full declared source SHA missing");
    assert(typeof report.build_flags_declared === "string" && report.build_flags_declared && report.build_flags_declared !== "unspecified","build flags missing");
    assert(report.machine && typeof report.machine === "object","machine identity missing");
    for(const field of ["hostname","arch","platform","release","cpu_model"]) assert(typeof report.machine[field] === "string" && report.machine[field],`machine ${field} missing`);
    assert(Number.isInteger(report.machine.cpu_count) && report.machine.cpu_count > 0,"machine CPU count missing");
    assert(Number.isInteger(report.agents) && report.agents >= 1 && report.agents <= 26,"agent workload count missing");
    assert(Number.isFinite(report.secs) && report.secs > 0,"phase duration missing");
    assert(Array.isArray(report.phases) && report.phases.length > 0 && report.phases.every((p:any) => typeof p.name === "string" && p.name),"measured phase identity missing");
    assert.equal(new Set(report.phases.map((p:any) => p.name)).size,report.phases.length,"duplicate measured phase identity");
    if(report.native_display.inputs_enabled) assert(report.phases.some((p:any) => p.name === "input-display"),"displayed input phase missing");
    if(report.native_display.opens_enabled) assert(report.phases.some((p:any) => p.name === "open"),"displayed open phase missing");
  }
  for (const field of ["log_bytes","agents","secs","build_flags_declared","machine"]) assert.deepEqual(candidate[field],baseline[field],`${field}: experiments differ`);
  assert(Number.isInteger(baseline.log_bytes) && baseline.log_bytes > 0,"fixture byte count missing");
  assert.deepEqual(candidate.phases?.map((p:any) => p.name),baseline.phases?.map((p:any) => p.name),"measured phases differ");
  for (const field of fields) assert.deepEqual(b.display[field],a.display[field],`native_display.${field}: observer metadata differs`);
  assert.deepEqual(b.input,a.input,"composer reference pixels differ from independent baseline");
  assert.deepEqual(b.title,a.title,"title reference pixels differ from independent baseline");
  return { verdict:"pass", input_targets:Object.keys(a.input).length, title_targets:Object.keys(a.title).length,
    baseline_binary_sha256:baseline.binary_sha256, candidate_binary_sha256:candidate.binary_sha256,
    baseline_source:baseline.source_sha_declared, candidate_source:candidate.source_sha_declared,
    fixture_sha256:baseline.log_sha256, harness_sha256:baseline.harness_sha256,
    scope:"Exact calibrated RGB content and observer/workload identity agree with the independent baseline. Latency budgets and fresh-render semantic correctness require separate evidence." };
}

if (import.meta.main) {
  const [baseline,candidate,...rest] = process.argv.slice(2);
  if (!baseline || !candidate || (rest.length && (rest.length !== 2 || rest[0] !== "--out"))) throw new Error("usage: bun native_display_compare.ts BASELINE.json CANDIDATE.json [--out RESULT.json]");
  const result = compareNativeDisplay(JSON.parse(readFileSync(baseline,"utf8")),JSON.parse(readFileSync(candidate,"utf8")));
  const json = JSON.stringify(result,null,2)+"\n";
  if(rest.length) writeFileSync(rest[1],json);
  console.log(json.trim());
}
