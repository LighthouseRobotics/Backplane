#!/usr/bin/env bash
# Centralized Linux native-glyph validation. This performs heavyweight Bend
# work: run only in the parent's bounded-memory queue, with no competing jobs.
# Usage: scripts/validate-native-glyph.sh [ABSOLUTE_EVIDENCE_DIRECTORY]
# If the parent already holds /tmp/bp-wt-build.lock, set
# BP_NATIVE_VALIDATE_LOCKED=1. Otherwise this script acquires the whole lock.
set -euo pipefail
if [[ ${BP_NATIVE_VALIDATE_LOCKED:-0} != 1 ]]; then
  command -v flock >/dev/null || { echo "flock is required for native validation" >&2; exit 1; }
  export BP_NATIVE_VALIDATE_LOCKED=1
  exec flock /tmp/bp-wt-build.lock "$0" "$@"
fi
export BP_BUILD_LOCKED=1
repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo"
out=${1:-$(mktemp -d "${TMPDIR:-/tmp}/bp-native-validation.XXXXXX")}
[[ $out = /* ]] || { echo "evidence directory must be absolute" >&2; exit 2; }
mkdir -p "$out" build
isolated_home=$(mktemp -d "${TMPDIR:-/tmp}/bp-native-home.XXXXXX")
trap 'rc=$?; result=FAIL; [[ $rc = 0 ]] && result=PASS; printf "overall\t%s\t%s\n" "$result" "$rc" >>"$out/status.tsv"; rm -rf "$isolated_home"; exit "$rc"' EXIT
export BACKPLANE_HOME="$isolated_home/backplane"
export BACKPLANE_GOOGLE_BAKE=0 BACKPLANE_LOW_MEM=1 BACKPLANE_JOBS=1
export CHECK_JOBS=1 TEST_JOBS=1 BEND_NO_TELEMETRY=1
export BUN_JSC_forceRAMSize=${BUN_JSC_forceRAMSize:-2147483648}
export BACKPLANE_CPUS=${BACKPLANE_CPUS-}
export BACKPLANE_CFLAGS=${BACKPLANE_CFLAGS:--O3}
unset TEST_SHARD TEST_SHARD_COUNT
printf 'stage\tstatus\texit_code\n' >"$out/status.tsv"
stages=(display-policy display-comparison xpoke-build surface-build display-readback fullcheck unit-tests glyph-native-build glyph-native-run glyph-native-samples i18n-native-build i18n-native-run)
for stage in "${stages[@]}"; do printf '%s\tPENDING\t\n' "$stage" >>"$out/status.tsv"; done
run() {
  local name=$1 verdict=$2 rc=0; shift 2
  printf '[native validation] %s\n' "$name"
  printf '%s\tRUNNING\t\n' "$name" >>"$out/status.tsv"
  "$@" >"$out/$name.log" 2>&1 || rc=$?
  if [[ $rc = 0 && $verdict = checks ]]; then
    if ! grep -q '^ok ' "$out/$name.log" || grep -Eq '^(FAIL|Error:)' "$out/$name.log"; then rc=1; fi
  fi
  if [[ $rc != 0 ]]; then
    printf '%s\tFAIL\t%s\n' "$name" "$rc" >>"$out/status.tsv"
    cat "$out/$name.log" >&2
    return "$rc"
  fi
  printf '%s\tPASS\t0\n' "$name" >>"$out/status.tsv"
}
git rev-parse HEAD >"$out/source-head.txt"
git status --short >"$out/source-status.txt"
git diff --binary HEAD >"$out/source.patch"
git ls-files -z --cached --others --exclude-standard '*.bend' '*.c' '*.h' '*.js' '*.ts' '*.py' 'scripts/*' |
  python3 -c 'import sys,pathlib,hashlib; paths=sorted(set(sys.stdin.buffer.read().split(b"\0"))-{b""}); [print(hashlib.sha256(pathlib.Path(p.decode()).read_bytes()).hexdigest(),p.decode()) for p in paths if pathlib.Path(p.decode()).is_file()]' >"$out/source-files.sha256"
bend version >"$out/bend-version.txt" 2>&1
bun --version >"$out/bun-version.txt"
"${CC:-clang}" --version >"$out/cc-version.txt"
python3 -c 'import json,os,platform; print(json.dumps({"machine":platform.uname()._asdict(),"cpu_count":os.cpu_count(),"build_flags":os.environ.get("BACKPLANE_CFLAGS"),"low_mem":os.environ.get("BACKPLANE_LOW_MEM"),"jobs":os.environ.get("BACKPLANE_JOBS"),"bend_heap_hint":os.environ.get("BUN_JSC_forceRAMSize")},indent=2))' >"$out/environment.json"
run display-policy exit bun test/tools/native_display_test.ts
run display-comparison checks bun test/tools/native_display_compare_test.ts
x11=()
if [[ -n ${BACKPLANE_X11:-} ]]; then x11=(-I"$BACKPLANE_X11/include" -L"$BACKPLANE_X11/lib/x86_64-linux-gnu"); fi
run xpoke-build exit "${CC:-clang}" -O2 "${x11[@]}" test/tools/xpoke.c -o build/xpoke -lX11
run surface-build exit "${CC:-clang}" -O2 "${x11[@]}" test/tools/present_observer_fixture.c -o build/present_observer_fixture -lX11
xvfb=${BACKPLANE_TEST_XVFB:-$(command -v Xvfb || true)}
[[ -n $xvfb && -x $xvfb ]] || { printf 'display-readback\tFAIL\tmissing-Xvfb\n' >>"$out/status.tsv"; exit 1; }
run display-readback exit bun test/tools/native_display_readback_test.ts "$repo/build/xpoke" "$repo/build/present_observer_fixture" "$xvfb"
run fullcheck exit scripts/check.sh all
run unit-tests exit scripts/test.sh
run glyph-native-build exit scripts/build-app.sh test/native/glyph_table_bench.bend build/glyph_table_bench
run glyph-native-run checks env HOME="$isolated_home" XDG_CACHE_HOME="$isolated_home/cache" build/glyph_table_bench
run glyph-native-samples exit python3 test/tools/glyph_bench_report.py "$out/glyph-native-run.log" "$out/glyph-native-summary.json"
run i18n-native-build exit scripts/build-app.sh test/native/i18n_smoke.bend build/i18n_native_smoke
run i18n-native-run checks env HOME="$isolated_home" XDG_CACHE_HOME="$isolated_home/cache" build/i18n_native_smoke
sha256sum build/glyph_table_bench build/i18n_native_smoke build/xpoke build/present_observer_fixture >"$out/binaries.sha256"
printf 'Validation logs: %s\n' "$out"
printf 'Whole-app baseline/candidate measurements and independent pixel comparisons remain separate required stages.\n'
