# Native rendering evidence — failed app budgets, focused planning follow-up

The completed baseline/glyph-candidate comparison **does not show an overall
native latency improvement**. Both apps fail the required budgets. The later
main-only clipping comparison also fails all four run verdicts and has mixed
timings. The first integrated attempt has a sustained-stream execution failure;
the unchanged final repetition fails the independent empty-composer pixel
comparison. All completed runs fail latency targets. Focused planning gains do
not establish app acceptance.

All measurements use generated history and stand-in providers. This compact
bundle contains original report bytes, receipts, small logs and review sources.
It excludes app binaries, generated builds, temporary homes, screenshots and
large Chrome traces. Original reports retain temporary path/host metadata;
these paths are provenance, not portable execution locations. Trace hashes are
retained in the original summary, but the large traces are not bundled.

## Completed app comparison

See `whole-app-original/summary.json`, the four `raw.json` reports, and
`compare-input.json`/`compare-title.json`. Execution exit zero and exact
independent pixels are separate from latency acceptance.

| Metric | Baseline | Glyph candidate | Target |
|---|---:|---:|---:|
| Normal frame p99 | 158.156 ms | 164.750 ms | ≤8 ms |
| Typing frame p99 | 70.122 ms | 105.419 ms | ≤8 ms |
| Displayed-input phase frame p99 | 84.557 ms | 155.331 ms | ≤8 ms |
| Idle / background maximum frame | 7.097 / 29.451 ms | 7.263 / 25.640 ms | ≤16 ms |
| Typing processing input p99 | 139.374 ms | 245.406 ms | ≤16 ms |
| Displayed input p99, 132 demands per app | 522.123 ms | 823.491 ms | ≤16 ms |
| Maximum processing cold open, 10 per app | 186.932 ms | 185.281 ms | ≤50 ms |
| Maximum displayed warm open, 10 per app | 136.654 ms | 163.908 ms | ≤50 ms |
| Normal agent-line p99 | 66.310 ms | 58.358 ms | ≤2 ms |
| Independent composer / title targets | 12 / 21, PASS | 12 / 21, PASS | Exact equality |

No budget is waived for a failing baseline. The observer covers selected title
and ASCII composer regions at the X server, not the whole timeline, compositor,
physical input or scanout. Status-tab visual coverage is explicitly null.
Composer calibration warms glyphs; separate warm-open calibration visits title
targets before demand measurement. Cold opens are a separate processing metric.
This is one paired four-run experiment, not repeat-based confidence evidence.

## Exact identities

The complete machine/flags/source metadata is in
`whole-app-original/artifact-identities.json` and the original raw reports.

- Product baseline: `30884966ef59c383581bcd1b7653f8f739cf009e`.
- Baseline artifact source: `b39a80e56da5b1a352e6b8811252906c03073f54`
  ([build run](https://github.com/LighthouseRobotics/Backplane/actions/runs/39243941943));
  only its temporary CI workflow differs from the product baseline.
- Glyph candidate immutable input: `96f32a75b1290336686d491bf6b82e1c4cafa140`,
  applied tree `19b386b54d5cca154bcb6976bf20cd1c39178912`, product snapshot
  represented by `e0b7548fdf9da49d5a5e42647c42395492bc6047`
  ([proof/build run](https://github.com/LighthouseRobotics/Backplane/actions/runs/39245186632)).
  Full source/check/proof/build and 53-artifact verification receipts are included.
- Baseline app SHA-256:
  `ff0a3b18b3e3f3ceac54d8b0ac84b62169c48a6042a141b5d935130dfa1c2c48`.
- Glyph candidate app SHA-256:
  `470e92153fbf700eff31ec16d92bcf66af1e989c96c53e7c8061d77cd73bc210`.
- Both app builds: LLVM 19.1.1, Bend 2.0.36, Bun 1.4.3, `-O3`,
  LOW_MEM=1, JOBS=2, GOOGLE_BAKE=0.
- Separate measurement commit: `62fa318989b092aa8712825a4c75f1e4f0c6bcbf`.
  Its exact driver, observer, comparator, stand-in and fixture sources are under
  `harness/`. This newer harness is not claimed to be part of the older apps.
- Fixture: `fixture/events.jsonl`, 1,520 events, 556,794 bytes, SHA-256
  `ac5f4374d7946569b420d7b2ca2d5890c99d54d323a819a6d66beaf2d824b543`.
  The history-only predecessor lacked the bot room/uberbot required by normal
  mode and is not accepted as complete workload evidence.

The candidate CI input label identifies the patch-bearing input commit.
Checkout commit + applied tree + patch hash + app hash identify the actual
product bytes. Merely labeling an experiment with an old product HEAD would
not establish this relationship. Fork results do not create upstream checks.

## Focused clipping follow-up

Profiles put normal mean layout/raster at 20.96/20.77 ms. Tile planning averages
6.37 ms normal, 7.36 ms typing and 8.81 ms during displayed input. `Keep.eq`
previously called two helpers that independently clipped the same run/polygon.
The frozen five-file patch in `focused-plan/native-latency.patch` computes that
shape once and preserves the exact comparison result.

The final native log has **49 passing controls** and **100 indexed paired
full-plan samples**, using actual FreeType glyphs in the same binary. Old and
new plans identify six changed tiles and have identical images. Controls cover
removed/inserted/reordered ops, empty clipped runs, absent regions, visible
changed polygon/text, changed background, scroll hints and stale-pixel negatives.
Nearest-rank planning p50/p99 is **1,064/1,675 → 820/1,304 µs**. This is a
planning result, not a displayed-input or whole-app result.

The focused build uses LLVM 19 `-O3`, LOW_MEM=1, JOBS=1, GOOGLE_BAKE=0. Its build
and run hold the shared lock in a bounded systemd unit (MemoryHigh 3 GiB,
MemoryMax 5 GiB, CPUQuota 200%, nice 19, JSC hint 1 GiB). No app, hub or provider
is launched by this benchmark. The affected compiler-proof extraction passes;
the local `--verdict` attempt explicitly fails for missing Lean/kernel.

The glyph-plus-clipping frozen candidate's full check/proof/build now passes
([run](https://github.com/LighthouseRobotics/Backplane/actions/runs/39255309878)):
immutable input `419658d1ac4f5bead70271a769cb9a0e928ee6e5`, tree
`328e208e407130d0fd7514116208b1fae40cd249`, 986 source files and 54 artifacts.
Its full receipt is included, with no binaries. The completed build does not
establish a latency gain. This unselected experimental candidate has no new
whole-app result in this bundle.

A separate main-only alternative is frozen from 30884966 without the glyph API
integration. Its original focused evidence is in `main-only-plan/`: 49 controls,
100 pairs, exact images/six changed tiles and planning p50/p99
**1,663/1,848 → 1,459/1,686 µs**. All 2,170 old laws remain byte-identical with one
additive exact-step law. Selected commit
`af6527f41f9828ef483dfaae9e5bd3b1884ebf49` passed full check/proof/build;
the earlier commit-gate snapshot still records the build pending at that time. The exact
five public source blobs are included under `source/main-only/`, with immutable
commit origins. Its later full verification binds 972 sources, 54 artifacts,
input `24c1af12945c5bfa9571c9dc302cc063e31f933a`, tree `3177124742934fe86aad60c068a6159f136dad34`
and binary `f48159d3e70d7bffbbb52afd61bcaea1f08b0a419cf386be2f292c9fb5f3b39c`.

The completed standalone four-run experiment is recorded separately in
`whole-app-main-only/`. All executions exit zero; all four verdicts remain
`TARGET_FAIL`. Independent composer/title comparisons pass with 12/21 targets.

| Standalone metric | Baseline | Main-only candidate | Target |
|---|---:|---:|---:|
| Normal frame p99 | 163.815 ms | 171.035 ms | ≤8 ms |
| Displayed input p99 | 650.391402 ms | 515.998916 ms | ≤16 ms |
| Maximum processing cold open | 213.021 ms | 207.693 ms | ≤50 ms |
| Maximum displayed warm open | 162.077479 ms | 178.375960 ms | ≤50 ms |

This mixed pair does not show an overall app improvement. It is one experiment,
without repeat-based confidence evidence. Neither focused result substitutes
for whole-app measurement.

## Later combined proof and test-only follow-up

The combined candidate full check/proof passed for tree
`829c295f86a8e973d54abed64a689b05bc7e3376`, frozen source commit
`f30b5a3d8619b71ae922ca2cea9618726091492f`. Its verification metadata binds
1,069 source files and receipt SHA-256
`de00da220026a1177afb3f52961a5673d384603d5ab6308b38195bc3a4ea8881`.
That historical proof-only record contains no app binary. A later full native
receipt binds the same frozen source to 1,069 sources, 54 artifacts and binary
`6e0906044805f64128bd42ea63b6493c397c2c72c54cf2dc2282b7d9ab482fb2`.
It is retained separately from the earlier proof-only receipt. Later commit
`7c7629dfb7b008ecfa6867c9e85f55f8a4d192e3` changes only
`test/tools/kicad_platform_e2e.ts`; its Bend diff is empty, and its final platform
CI was pending in that historical record. The frozen receipt binds f30's
checked tree, not that later test-only tree. Keep these identities distinct.
The later genuine 7c native/mac/CI verifications and schema2 producer receipts
are included under `provenance/final7c/`. The final producer's `dist/backplane`
has exactly the same hash and byte count as the measured frozen f30 binary;
`final-app-binary-equivalence.json` binds these separate producer identities.
The local source fingerprint also matches final 7c and reports a clean tree.

The first executed integrated attempt is retained in
`whole-app-integrated-retry2/`. Its candidate cold run records `EXECUTION_FAIL`:
two of ten streams exceeded the unchanged
2,000 ms sustained-stream guard during opens (gaps 2,117.45 / 2,320.32 ms).
All 132 composer demands were observed; that does not establish valid sustained
workload execution. The other three runs exit zero with `TARGET_FAIL`; the
independent 12-composer/21-title comparisons pass. Overall status stays
`incomplete_or_fail`. Normal frame p99 is 207.818 → 241.419 ms; maximum warm
displayed open is 176.395826 → 208.973494 ms. These are failed-attempt statistics,
not a valid sustained-workload improvement claim. This attempt remains retained.

The unchanged final repetition is under `whole-app-integrated-repeat3/`. All
four executions exit zero with `TARGET_FAIL`; every active streaming phase
passes the unchanged sustained-stream guard. Title comparison passes, but
composer comparison exits 1 and emits no JSON. The preserved error log reports
only the empty-prefix hashes differing: baseline
`9c69d25a423e0498f135341249430715e7d851b9829a02123e6fb3954a7a4934`, candidate
`40793bc68e3f859ab6b5ffc92eedd2372b9cbc9b6b59c5414cd10819fd1ef6c1`.
All eleven nonempty prefix hashes agree. The comparison remains **FAIL**;
the absent `compare-input.json` must not be replaced by a fabricated pass.
No more whole-app repetitions are planned.

Separate untimed diagnosis in `diagnostic/` reproduces both exact empty hashes
in each binary, with eleven captures per side. The pinned normalization leaves
three pixels of the empty placeholder's first A different across caret blink
states (ROI x14,y15..17). Caret-on covers those pixels; replacing the solid caret
color with panel color removes underlying placeholder pixels that remain when
the caret is off. Both apps produce the same nonempty `Backplane42` hash. This
explains an observer limitation in the empty placeholder, and does not turn the
original strict comparison into a pass. No hash aliases, region, threshold,
deadline or measured harness bytes changed. Metadata and exact capture source
are included; local PPM/PNG images remain excluded. The earlier offline check's
`root_cause: PENDING` field is retained as a historical pre-diagnosis record.

Final-repetition normal frame p99 is 237.451 → 385.420 ms; maximum warm displayed
open is 173.375510 → 149.028861 ms. These values remain above the unchanged
8/50 ms targets, and the failed composer comparison prevents an independent
displayed-input content acceptance claim. No overall app improvement is shown.

The first
integrated directory failed provenance before executing any app because the
old helper expected the baseline build-script hash. The reviewed changes are
lock detection and portable time/RSS wrappers; compiler optimization flags are
unchanged. The retry uses exact audited script hashes and rejects unknown
scripts or flag mutations. Preserve the failed preflight, the audit and all
three exact helper versions alongside the retry's reports. No future
result is claimed. `comparison-index.json` records each experiment independently.

## Final real-CAD receipt

`final-real-cad/` retains the schema2 receipt, its independent verification and
all four step logs for final 7c source using the exact producer-bound app.
It passes 41 review/release and 28 history assertions against real pinned bp.4
KiCad, with 30 nonempty export files totaling 419,157 bytes. The local fixture's
source, annotated tag and manifest agree; publish is false. This is not a
clean-design assertion. Export files and app binaries are excluded from this
compact bundle; their hashes are metadata, not revalidated omitted bytes.
The fresh pinned-release asset query is retained under `provenance/final7c/`.
It lists only the Linux runtime. The macOS native CI receipts do not establish
real pinned-KiCad macOS acceptance; that runtime remains unavailable.

## Laws and authorship

`preservation/glyph-law-mapping.json` includes every before/after statement:
all 2,170 old public laws remain, 2,161 are byte-identical and nine retain the
same frame/tile/scroll/caret/cat guarantee with universal table/key parameters.
The old/new table exact-frame law additionally quantifies independent tables,
without requiring their equality. Three cache-agreement laws are additive.
The fused follow-up leaves all 2,173 statements byte-identical and adds only
`keep_step_exact`; its source audit and hashes are included. Statement review
does not replace exact-source proof.

Original #157 commits and their integrated commits retain i2cjak as author;
see `preservation/authorship.json`. #232's unfinished production/trust/release/
deploy hooks remain excluded. `standalone-main-feasibility.md` records the
separate option of applying only the clipping change to main, without assuming
the glyph integration is beneficial.

## Verify and reproduce

The bundle verification is read-only and starts no application:

```sh
python3 verify.py
python3 -B tools/verify_app_sets_test.py
sha256sum -c SHA256SUMS
bun harness/test/tools/native_display_compare.ts \
  whole-app-original/baseline-cold/raw.json \
  whole-app-original/candidate-cold/raw.json
bun harness/test/tools/native_display_compare.ts \
  whole-app-original/baseline-warm/raw.json \
  whole-app-original/candidate-warm/raw.json
bun harness/test/tools/native_display_test.ts
bun harness/test/tools/native_display_compare_test.ts
bun harness/test/tools/perf_fixture_test.ts
```

`reproduction/original-native-app-perf-evidence.py` is the recovered original
measurement helper, SHA-256
`376053ba7b21ef826b0e031d8977f839f54ae0d9cb5451af167390cdc3a1ba81`, exactly
matching the original `measurement-inputs.sha256` entry. It is archived as
provenance; its original local paths are not portable reproduction commands.
The main-only helper is retained separately with SHA-256
`1cef2aa2e9f58a1bbe8c3644083b1e1aade2fd24a76d99e0872f3ab49468f31c`.
Each completed comparison's exact helper must match its own input checksum list;
a newer helper is never substituted for earlier bytes.
The integrated helper SHA-256 is
`3f24c474ddba1ae245462d7fefcf3027451b97803fd12ed871f81e5f4b683e76`.
The exact reviewed build scripts, audit and 25 passing offline helper controls
are retained. The first preflight's original status and error log are under
`failed-integrated-preflight/`; no app ran in that attempt.
`tools/verify_app_sets.py` checks completed report/receipt/source bindings and
recomputes the original numeric verdicts, including null Status coverage and
the 2,000 ms sustained-stream guard. Its 20 offline controls reject stale or
self-consistent wrong candidate pixels, removed budgets, altered metrics,
misbound historical helpers and promoted failures. They also accept the real
missing-JSON comparator failure and reject fabricated passing JSON or an absent
error log. These checks launch no app.

`harness/docs/native-perf-reproduce.md` gives the four serial private-home runs,
same fixture/hardware/flags, displays :91/:92, ports 3891/3892, ten stand-in
streams, five-second timed phases and fixed typing/open workloads. Hold the
actual `/tmp/bp-wt-build.lock` around all measurements; do not build during them.
Preserve all failed budgets and partial failures. Original per-run `command.sh`
files record the actual invocation with original paths.

For the glyph-plus-clipping focused benchmark, apply its patch to separately
obtained 62fa source and verify `provenance/native-latency-source.sha256`.
For the selected main-only benchmark, use the exact af652 commit or the
corresponding five source blobs/patch, and verify
`main-only-plan/native-plan-only-source.sha256`. Then run the normal full
check/proof gate and:

```sh
BACKPLANE_LOW_MEM=1 BACKPLANE_JOBS=1 BACKPLANE_CFLAGS=-O3 \
  BACKPLANE_GOOGLE_BAKE=0 scripts/build-app.sh \
  test/native/keep_plan_bench.bend build/keep_plan_bench
flock /tmp/bp-wt-build.lock build/keep_plan_bench > keep-plan-bench.log
```

No artifact binaries are bundled; obtain the exact CI artifacts and validate
their receipt hashes before any new app run. The generated bundle manifest
hashes every included original byte sequence and identifies its source. It
checks the bundle's integrity, not an omitted binary or a future experiment.
`tools/refresh_bundle_v2.py` appends whitelisted evidence with explicit origins,
retains immutable originals, refreshes manifest/checksums, and rebuilds an
archive only after `verify.py` passes. See `PUBLISHING.md` for parent commands.
The original refresh helper remains preserved; v2 also whitelists comparator
error logs so a failed comparison without JSON retains its original output.
