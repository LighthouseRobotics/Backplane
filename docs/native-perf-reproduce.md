# Reproduce native before/after measurements

Use Linux x86-64, Bun 1.4.3, an existing Xvfb and the same system fonts and
hardware for both binaries. Obtain baseline and candidate artifacts with their
source/toolchain/hash receipts. Both apps must use LLVM 19, `-O3`,
`BACKPLANE_LOW_MEM=1`, `BACKPLANE_JOBS=2` and `BACKPLANE_GOOGLE_BAKE=0`.
Check the actual binary hashes against those receipts before running. Build
the shared helper before taking measurements, if it is not already available:

```sh
mkdir -p build
cc -O2 test/tools/xpoke.c -o build/xpoke -lX11
bun test/tools/perf_fixture_test.ts
# Requires an already-built production shared-client bridge:
bun test/tools/perf_fixture_codec_test.ts mobile/build/assets/bridge.js
```

This candidate contains the independent clipping optimization on the existing
mask renderer. Select its required renderer validation explicitly:

```sh
scripts/validate-contribution.sh renderer --renderer-profile keep-plan
```

The lane requires 49 named correctness controls, 100 complete indexed paired
plan samples, native i18n and independent Xvfb pixel readback. Full check/proof,
unit and app-build gates are separate. The original glyph-cache experiment and
its 705-sample benchmark remain on their external branch/evidence; they are
not prerequisites or app performance acceptance for this candidate.

Generate the same fixture for both apps. It contains 12 history threads, 1,500
messages, two local bot threads, their bot events, a room and an uberbot. The
history-only predecessor lacked the room/uberbot required by normal mode; its
failed workload is not valid performance acceptance. The current generated
fixture is **1,520 events, 556,794 bytes**, SHA-256
`ac5f4374d7946569b420d7b2ca2d5890c99d54d323a819a6d66beaf2d824b543`.
No copied user history or provider credentials are needed.

```sh
OUT=$(mktemp -d "${TMPDIR:-/tmp}/bp-native-comparison.XXXXXX")
bun test/tools/perf_fixture.ts "$OUT/fixture.jsonl" > "$OUT/fixture-receipt.json"
sha256sum "$OUT/fixture.jsonl"
```

Set `BASE_BIN` and `CAND_BIN` to the downloaded native `dist/backplane` files,
and set `BASE_SOURCE` and `CAND_SOURCE` to their full 40-character source labels.
Save the original artifact receipts alongside the results. For a CI-applied
snapshot, the candidate label is the immutable **input commit containing the
patch**; also retain its checkout commit, expected applied tree, patch hash and
artifact hash. An older product HEAD does not identify an uncommitted snapshot.
The declared labels/flags in a report do not substitute for artifact receipts.

The following four fresh processes share the same fixture, driver, helper and
flags. Run them serially while holding the actual build/measurement lock.
The dedicated displays and ports must be unused; the driver refuses to share
an existing display. It creates private app homes and stand-in executables.
Do not pass a live log or an installed app path.

```bash
[[ $BASE_SOURCE =~ ^[0-9a-f]{40}$ && $CAND_SOURCE =~ ^[0-9a-f]{40}$ ]] || exit 2
FLAGS='LLVM=19;CFLAGS=-O3;LOW_MEM=1;JOBS=2;GOOGLE_BAKE=0'
sha256sum "$BASE_BIN" "$CAND_BIN" build/xpoke test/tools/perf_load.ts \
  test/tools/native_display.ts test/tools/native_display_compare.ts > "$OUT/inputs.sha256"
(
  exec 9>/tmp/bp-wt-build.lock
  flock -x 9
  run() {
    side=$1; mode=$2; binary=$3; source=$4; display=$5; port=$6
    dir="$OUT/$side-$mode"; mkdir -p "$dir/tmp" "$dir/controller-home"
    phases=(--phases idle,bg,fg,type,input-display,open,normal --pixel-inputs)
    [[ $mode = cold ]] || phases=(--phases open --pixel-opens)
    code=0
    env TMPDIR="$dir/tmp" HOME="$dir/controller-home" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
      bun test/tools/perf_load.ts --bin "$binary" --log "$OUT/fixture.jsonl" \
      --xpoke "$PWD/build/xpoke" --xvfb /usr/bin/Xvfb --exclusive-display \
      --display "$display" --port "$port" --agents 10 --secs 5 \
      --source-sha "$source" --build-flags "$FLAGS" "${phases[@]}" \
      --out "$dir/raw.json" --keep > "$dir/stdout.log" 2> "$dir/stderr.log" || code=$?
    printf '%s\n' "$code" > "$dir/execution.exit"
  }
  run baseline cold "$BASE_BIN" "$BASE_SOURCE" :91 3891
  run candidate cold "$CAND_BIN" "$CAND_SOURCE" :92 3892
  run baseline warm "$BASE_BIN" "$BASE_SOURCE" :91 3891
  run candidate warm "$CAND_BIN" "$CAND_SOURCE" :92 3892
  for surface in input title; do
    mode=cold; [[ $surface = input ]] || mode=warm
    code=0
    bun test/tools/native_display_compare.ts "$OUT/baseline-$mode/raw.json" \
      "$OUT/candidate-$mode/raw.json" --out "$OUT/compare-$surface.json" \
      > "$OUT/compare-$surface.log" 2>&1 || code=$?
    printf '%s\n' "$code" > "$OUT/compare-$surface.exit"
  done
)
```

The configured five seconds applies to timed phases. Typing, displayed input,
opens and normal mode run fixed event workloads and take longer. Do not stop
the candidate because the baseline misses a budget. Keep every run's execution
exit, phase checks and missing-sample verdicts. A zero driver exit does not mean
every target passed. Each comparison needs exit zero **and** a parsed `pass`
verdict with the expected identities; file existence alone proves nothing.

The cold run does not calibrate the ten thread-open targets before measuring
their first visits. Input-display separately warms its composer glyphs during
calibration, then observes all 132 additions/Backspaces at the X-server boundary.
The separate warm run calibrates titles and observes ten opens. Reference
comparisons require all 12 composer prefixes or all 21 title targets and reject
self-consistent candidate calibration errors relative to the baseline. The
planner's fresh-render text, polygon, background and scroll regressions remain
a separate correctness anchor.

Preserve the original targets: frame p99 8 ms, streaming/input 16 ms, open 50 ms
and agent-line p99 2 ms. Report failing baseline and candidate results explicitly.
The normal workload's **Status tab remains visually unverified** (`null` check).
The observers cover the selected title and an ASCII composer region, not the
entire timeline, other UI regions, compositor, physical input or scanout.

Keep raw reports, traces and demand journals outside Git. A reviewable report
should contain source/artifact/fixture hashes, the actual flags/toolchain and
hardware, sample counts, per-phase p99/max values, budget verdicts, independent
reference verdicts and links to the raw artifacts. Do not commit large traces or
claim simulator/microbenchmark results establish whole-app or physical budgets.
