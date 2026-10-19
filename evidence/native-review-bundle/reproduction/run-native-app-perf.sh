#!/usr/bin/env bash
# Download artifacts first; this script builds nothing and never installs them.
# Usage: run-native-app-perf.sh BASELINE_BIN BASELINE_ARTIFACT_ROOT CANDIDATE_BIN CANDIDATE_ARTIFACT_ROOT NEW_OUTPUT_DIR
# Baseline artifact root contains build/candidate-{source,toolchain}.txt and
# build/candidate-artifacts.sha256. Candidate root contains the native frozen-CI
# receipt.json, manifest/patch/file table, clang.log, toolchain.log and artifacts/.
# Run directly, outside another holder of /tmp/bp-wt-build.lock.
set -euo pipefail
if [[ ${1:-} = --help ]]; then sed -n '2,8p' "$0"; exit 0; fi
[[ $# = 5 ]] || { sed -n '2,8p' "$0" >&2; exit 2; }
root=$(cd "$(dirname "$0")/.." && pwd)
baseline=$(realpath -e "$1"); baseline_artifact=$(realpath -e "$2")
candidate=$(realpath -e "$3"); candidate_artifact=$(realpath -e "$4")
out=$(realpath -m "$5")
[[ ! -e $out ]] || { echo 'Output directory must be new; prior measurements are preserved.' >&2; exit 2; }
mkdir -p "$(dirname "$out")"; mkdir "$out"
printf 'stage\tstatus\texit_code\n' > "$out/status.tsv"
for name in provenance baseline-cold candidate-cold baseline-warm candidate-warm compare-input compare-title; do
  printf '%s\tPENDING\t\n' "$name" >> "$out/status.tsv"
done
trap 'rc=$?; printf "overall\t%s\t%s\n" "$([[ $rc = 0 ]] && echo PASS || echo INCOMPLETE_OR_FAIL)" "$rc" >> "$out/status.tsv"' EXIT
for tool in flock python3 timeout realpath sha256sum; do command -v "$tool" >/dev/null || { echo "Missing $tool" >&2; exit 2; }; done
bun=${BP_PERF_BUN:-/tmp/backplane-contrib-tools/bun-linux-x64/bun}
xpoke=${BP_PERF_XPOKE:-$root/native-glyph/build/xpoke}
xvfb=${BP_PERF_XVFB:-$root/toolchain/bin/Xvfb}
driver=$root/native-glyph/test/tools/perf_load.ts
compare=$root/native-glyph/test/tools/native_display_compare.ts
helper=$root/evidence/native-app-perf-evidence.py
fixture=$root/evidence/native-fixture-bots.jsonl
for executable in "$baseline" "$candidate" "$bun" "$xpoke" "$xvfb"; do
  [[ -x $executable ]] || { echo "Not executable: $executable" >&2; exit 2; }
done
exec 9>/tmp/bp-wt-build.lock
flock -x 9
printf 'lock_pid=%s\nlock=/tmp/bp-wt-build.lock\n' "$$" > "$out/measurement-lock.txt"
if ! python3 "$helper" prepare "$baseline" "$baseline_artifact" "$candidate" "$candidate_artifact" "$out" > "$out/provenance.log" 2>&1; then
  printf 'provenance\tFAIL\t1\n' >> "$out/status.tsv"; cat "$out/provenance.log" >&2; exit 1
fi
printf 'provenance\tPASS\t0\n' >> "$out/status.tsv"
flags='LLVM=19;CFLAGS=-O3;LOW_MEM=1;JOBS=2;GOOGLE_BAKE=0'
sha256sum "$baseline" "$candidate" "$bun" "$xpoke" "$xvfb" "$driver" "$compare" "$helper" "$fixture" "$0" > "$out/measurement-inputs.sha256"
"$bun" --version > "$out/measurement-bun-version.txt"
python3 -c 'import json,os,platform; print(json.dumps({"uname":platform.uname()._asdict(),"cpu_count":os.cpu_count(),"load":os.getloadavg()},indent=2))' > "$out/machine-before.json"
run_measurement() {
  local side=$1 mode=$2 binary=$3 display=$4 port=$5 rc=0 verdict runout source
  runout=$out/$side-$mode; mkdir -p "$runout/tmp" "$runout/controller-home"
  source=$(cat "$out/$side.source-label")
  local phase_args=(--phases idle,bg,fg,type,input-display,open,normal --pixel-inputs)
  [[ $mode = cold ]] || phase_args=(--phases open --pixel-opens)
  printf '%s-%s\tRUNNING\t\n' "$side" "$mode" >> "$out/status.tsv"
  if ! python3 "$helper" ports "$port" "$display" > "$runout/preflight.log" 2>&1; then
    printf '%s-%s\tEXECUTION_FAIL\t1\n' "$side" "$mode" >> "$out/status.tsv"
    printf '{"status":"EXECUTION_FAIL","error":"dedicated port/display unavailable; see preflight.log"}\n' > "$runout/status.json"
    return
  fi
  local command=("$bun" "$driver" --bin "$binary" --log "$fixture" --xpoke "$xpoke" --xvfb "$xvfb"
    --exclusive-display --display "$display" --port "$port" --agents 10 --secs 5
    --source-sha "$source" --build-flags "$flags" "${phase_args[@]}" --out "$runout/raw.json" --keep)
  printf '%q ' "${command[@]}" > "$runout/command.sh"; printf '\n' >> "$runout/command.sh"
  cat /proc/loadavg > "$runout/load-before.txt"
  # Failed budgets do not abort the comparison: driver strict-target mode is
  # deliberately omitted. Every target verdict is retained and evaluated below.
  env TMPDIR="$runout/tmp" HOME="$runout/controller-home" XDG_CONFIG_HOME="$runout/controller-home/config" \
    XDG_CACHE_HOME="$runout/controller-home/cache" XDG_DATA_HOME="$runout/controller-home/data" \
    LANG=C.UTF-8 LC_ALL=C.UTF-8 BEND_NO_TELEMETRY=1 \
    timeout --signal=INT --kill-after=15s 900s "${command[@]}" > "$runout/stdout.log" 2> "$runout/stderr.log" || rc=$?
  printf '%s\n' "$rc" > "$runout/execution.exit"
  cat /proc/loadavg > "$runout/load-after.txt"
  if ! verdict=$(python3 "$helper" report "$runout/raw.json" "$out/artifact-identities.json" "$side" "$mode" "$rc" 2> "$runout/report-validation.log"); then
    verdict=EXECUTION_FAIL
    printf '{"status":"EXECUTION_FAIL","error":"report validator failed; see report-validation.log"}\n' > "$runout/status.json"
  fi
  printf '%s-%s\t%s\t%s\n' "$side" "$mode" "$verdict" "$rc" >> "$out/status.tsv"
}
# Serial fresh processes, dedicated displays and ports, one identical driver.
# Input-display warms only its composer calibration; ten cold open targets are
# first visited in the cold run. Warm title calibration is a separate process.
run_measurement baseline cold "$baseline" :91 3891
run_measurement candidate cold "$candidate" :92 3892
run_measurement baseline warm "$baseline" :91 3891
run_measurement candidate warm "$candidate" :92 3892
for surface in input title; do
  mode=cold; [[ $surface = input ]] || mode=warm
  code=0
  "$bun" "$compare" "$out/baseline-$mode/raw.json" "$out/candidate-$mode/raw.json" --out "$out/compare-$surface.json" > "$out/compare-$surface.log" 2>&1 || code=$?
  printf '%s\n' "$code" > "$out/compare-$surface.exit"
  result=PASS; [[ $code = 0 ]] || result=FAIL
  printf 'compare-%s\t%s\t%s\n' "$surface" "$result" "$code" >> "$out/status.tsv"
done
python3 "$helper" summary "$out"
