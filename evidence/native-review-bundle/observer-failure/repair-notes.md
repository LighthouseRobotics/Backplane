# Native observer calibration and cleanup repair

Portable fixture/docs follow-up: `e40664a96` (16 fixture controls and three
production shared-codec controls passed). Measurement harness repair:
`62fa318989b092aa8712825a4c75f1e4f0c6bcbf`, three TypeScript files only.
No Bend/product source, built app artifact or combined checkout was changed.

The first complete-run attempt in `native-app-perf-20261019` produced no valid
performance result. Baseline and candidate threw during composer calibration;
the top-level awaited rejection escaped cleanup, leaving their owned X servers
until the enclosing systemd unit exited. Later warm runs refused those displays.
All failed evidence is preserved.

Actual private baseline screenshots establish that the default composer ROI
`444,788,600,32` covers the intended text, and normalized caret captures remain
stable across 30 frames over 2.1 seconds with ten stand-ins streaming. Replaying
60 characters and 60 Backspaces reproduced the calibration failure: the old
100 ms + 80 ms reads differed in 82 normalized grayscale text pixels in ROI
box `38,10,53,17`. Those pixels changed to the panel background. This is queued
text finishing a frame, not a caret-color mismatch. Screenshots, exact ROI PPM
pairs and the transition-color log are in `native-observer-debug`.

Calibration now waits for exactly unchanged pixels over 300 ms, with at least
three samples and a five-second bound. Each next prefix must differ from its
previous reference. The empty-draft reference is captured on the pristine
new thread before typing, and post-deletion calibration must match it. Title
calibration uses the same bounded changed/stable guard. Pairwise distinct
references remain required. Measured input demand timestamps still precede
dispatch; exact expected-pixel observation, two-second observation timeout and
all original latency budgets are unchanged.

The main execution now has a global try/catch/finally. Cleanup stops its owned
timers and captured app/X-server processes exactly once. A failure also writes
an explicitly incomplete raw result and `failure.json`, retaining calibration
state, completed phase names, targets, trace location and demand journal.

Actual same-artifact baseline and candidate diagnostics completed `type` and
`input-display` with all ten streams sustained, 12 distinct reference prefixes
and all 132 input observations each. Independent reference comparison passes in
`native-observer-fixed-input-comparison.json`. These runs verify the repair;
their latency budgets still fail. They are not the required complete four-run
performance result.

A deliberately wrong `0,0,1,1` ROI was rejected by calibration. Its incomplete
raw result and failure file survive, both captured process IDs have exited,
and the owned X display and listener are released; see
`native-observer-failure-cleanup/cleanup-assertions.json`. Port checks also
exposed normal kernel TIME_WAIT after the server exited. Task-local preflight
now uses SO_REUSEADDR, permitting ordinary port reuse while still refusing a
live listener. Owned loopback tests cover both outcomes.

Existing changed/stale/wrong/late demand and caret controls remain passing;
seven new calibration controls cover delayed/transient pixels, an incorrect
empty reference, unchanged and oscillating pixels, and late completion. All 29
independent reference-comparison controls pass. Current verifier tests include
the actual downloaded baseline layout/hash/toolchain and separate synthetic
report controls; no synthetic receipt is claimed as actual CI evidence.

The app artifacts remain identified by their original receipts (baseline
`b39a80e56`, candidate CI input `96f32a75b`, applied product tree `19b386b54`).
The repaired observer is a separately committed measurement source, verified
byte for byte in both worktrees including its imported stand-in/CBOR helpers.
The task-local artifact identity output records both source identities.
An actual downloaded-artifact preflight passes with:

```sh
BP_PERF_HARNESS_COMMIT=62fa318989b092aa8712825a4c75f1e4f0c6bcbf \
  python3 evidence/native-app-perf-evidence.py prepare \
  artifacts/native-baseline/dist/backplane artifacts/native-baseline \
  artifacts/native-candidate/artifacts/dist/backplane artifacts/native-candidate \
  evidence/native-observer-harness-preflight
```

The parent coordinator owns the new complete matched run and final metrics.
Status-tab coverage remains null, and title/composer observations do not certify
full timeline content, compositor or physical input/scanout. No push, PR,
deployment or release was performed for these follow-ups.
