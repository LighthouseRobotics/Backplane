# Perf bench: the window and hub under load

`test/tools/perf_load.ts` runs the native app (hub and window in one
process) on a copy of a real event log, with stand-in agents streaming, and
measures it phase by phase against the targets. Keep one immutable log
snapshot for a baseline/change comparison; each report records its byte
count and SHA-256 so different inputs are visible:

```sh
cp ~/.backplane-bend/events.jsonl /tmp/backplane-perf-snapshot.jsonl
bun test/tools/perf_load.ts --bin build/backplane --log /tmp/backplane-perf-snapshot.jsonl --out /tmp/perf-result.json
```

| target | metric |
|---|---|
| frame p99 ≤ 8 ms | `ui.frame` |
| no frame > 16 ms from background streaming | `ui.frame` in `idle` and `bg` |
| typing ≤ 16 ms | `ui.input` in `type` and `normal` (also shown: key>frame) |
| key handling through frame ≤ 16 ms | `ui.msg.win` + `ui.input` in `type` and `normal` |
| thread open ≤ 50 ms | Return in the palette to the frame showing the thread |
| agent line ≤ 2 ms | `hub.agent_line` p99 |

## Running it

```sh
scripts/build-app.sh src/app/main.bend build/backplane      # under the bend lock
cc -O2 test/tools/xpoke.c -o build/xpoke -lX11
bun test/tools/perf_load.ts --bin build/backplane --out /tmp/perf.json
```

Options: `--bin` (any branch's build), `--log` (default
`~/.backplane-bend/events.jsonl`, only read), `--port` (3799), `--display`
(`:77`; an Xvfb is started there if none runs, from `/tmp/xvfb-root`,
`/usr/bin` or `~/.local/bin`, see "Xvfb without root" below), `--agents`
(10), `--secs` (20 per phase), `--phases` (any of
`normal,idle,bg,fg,type,open,plane`), `--out` (raw JSON: every phase's
stats, top 25 spans, both perf.json readings), `--shots DIR` (a screenshot
at the end of each phase), `--keep` (keep the temp folder), `--hold` (set up,
start streaming and wait for `<tmp>/stop`, to look around by hand).
One run takes about 4 minutes.

`--fail-on-target` exits nonzero when a selected phase misses a target or
has no samples for a required metric. The default records failures and
exits successfully, which permits before/after runs while improving a
known slow build. Neither typing metric includes time spent waiting
before the window handles an event; these are processing measurements,
not complete input-to-pixels latency. The Status plane is selected by
its sidebar coordinates; include `--shots` when checking UI coverage.

The copied log's provider preference is overridden with the deterministic
stand-in protocol, including bot threads. Before timing begins, every load
thread must deliver parsed streaming deltas. Each streaming phase reports
per-thread delta counts and fails the workload if a thread falls below one
delivered update a second and now also records the longest receive gap
(at most two seconds, including both phase edges). Every local bot in
every posted room must respond during a normal-use run. Zero or dead
streams, unexpected provider processes and failed input commands make a
run invalid regardless of timing targets. `bun test/tools/perf_standin_test.ts`
checks the stand-in's JSON, deltas, subagent and shell events without a hub.
`bun test/tools/perf_guard_test.ts` rejects bursts followed by dead streams,
phase-edge gaps and partial/missing thread-open samples.

Thread opens must be observed through the native client's existing
`desk.look` selection reports, with ten complete timing windows in the
open phase. The same report can establish the uberbot selection, but not
which tab it rendered. Status-tab coverage therefore remains explicitly
unverified and cannot pass strict mode; screenshots remain necessary for
that visual check.

## What it measures

The app runs with `BACKPLANE_TRACE`, so every span is in a trace with its
exact duration. Each phase is bounded by two `/debug/perf.json` readings;
their `proc.up_ms` is the trace's clock, so a phase's numbers are exactly the
spans inside it (percentiles are exact, not log2 buckets). cpu% is the whole
app process (hub and window) from `/proc`; hub% is the time in `hub.*`
spans over the wall time (how busy the hub's loop was); rss is the most seen.

key>frame adds the `ui.msg.win` that handled a key to its `ui.input` (which
starts after the handling, docs/perf.md). Neither has the time an event
waited in the queue before it was handled.

## Phases (run in this order, `normal` printed first)

- `idle`: the window on the longest real thread, nothing streaming: the
  caret's blink and nothing else.
- `bg`: 10 threads stream at once (6 with a subagent writing its own lines
  and a background shell, each with a progress line every 100 ms); the person
  posts in every room that has bots every 4 s, so bots wake and stream; the
  window stays on the long thread (nothing on screen changes).
- `fg`: the window on a streaming thread, its Subagents panel at work.
- `type`: 60 keys typed into that thread's composer, 8 a second, then
  deleted.
- `open`: 10 real threads (the next longest) opened one after another:
  ctrl+k, the title, Return. Only the Return is timed.
- `plane`: the uberbot's Status plane (its row at the top of the sidebar),
  wheel over it.
- `normal`: everything at once, as in a day's use: agents, subagents and
  bots streaming, typing in a streaming thread, scrolling it, opening the
  long thread and scrolling up, typing there, the Status plane, back to a
  streaming thread and typing.

The stand-in agent is a shell script speaking Claude's stream-json (3 text
deltas per 100 ms, every 3 s a finished paragraph, a Bash call and its
result). Threads are found by title through the palette: the long thread and
the 10 to open get unique titles (`zqlong`, `zqopena`..) appended to the copy.

## Safety

- The log is copied. Dropped: `DeviceRegistered`/`DeviceDropped`, hooks,
  peers, wakes, routines, locks, watched work, and push/voice/deploy/google
  settings. Delegated tasks still open are closed, `restart.continue` is off.
- Every path under the user's home is rewritten into the temp folder, so no
  thread's folder is a real one; `git`, `gh`, `claude` (the stand-in),
  `codex`, `grok`, `muse`, `notify-send`... on PATH are the bench's own. No
  repository, no live home, no phone is touched.
- HOME, the lock dir and the deploy locks are in the temp folder; the D-Bus
  address is a dead one.
- It refuses port 3787 and the installed binary, aborts if a child agent is
  not the stand-in, and stops only the PIDs it started (the app, and Xvfb if
  it started one). The stand-ins end when their hub is gone.

## Xvfb without root

```sh
mkdir -p /tmp/xvfb-deb && cd /tmp/xvfb-deb && apt-get download xvfb && dpkg -x xvfb_*.deb /tmp/xvfb-root
```

## Not covered

The web client: it needs the web bundle and a Chromium; not timed here.

Mailroom is an opt-in `--phases mail` workload. It files 5,000 conversations
and 50,000 bodies across six synthetic bots through `mail.send`, with
`mail.on` enabled only in the temporary home. Filing finishes and a list
plus a body read are verified before the timed phase. The phase scrolls
40 rows, types `needle`, opens ten conversations, then sends two mails per
second while the uberbot's Chat tab is selected. `--mail-convs N` and
`--mail-mails N` permit explicitly smaller smoke runs; the report records
those counts, so a smoke run cannot be mistaken for the full fixture.

The JSON includes `mail_read_rpc_ms` (real body-read roundtrips) separately
from `opens_ms` (native input processing through its frame). Native tab
coverage still needs the screenshots: the existing `desk.look` report
identifies the bot's thread but does not expose its tab or open mail.
The Mailroom pane reuses PW with `Mm.mail` as its key. Bot panes bypass
MainM, so the existing `ui.layout.mm.hit` metric does not measure that
pane cache; do not claim Mailroom cache hit coverage from that metric.

## Native displayed-content observations

`--pixel-opens` adds independent X-server title-region readback through
`xpoke pixels X Y W H`. The driver records a demand before dispatching Return
and polls the exact expected SHA-256 of the title pixels. A stale or different
thread header cannot complete that demand. The region must distinguish all
calibrated target threads and remain stable during calibration. Raw reports
include each demand revision, expected thread, region, observed digest,
sample count and elapsed dispatch-to-readback time. This includes input queue
waiting and observer overhead, unlike `ui.input` processing spans.

Calibration visits every target before timing. These are explicitly **warm
opens** (`native_display.open_cache = warm-calibrated`); use a separate run
without this option for cold-cache processing measurements. The title region
establishes the shown thread title only. It does not certify all timeline
content, compositor presentation, scanout, Status-tab coverage, or physical
input latency. These observations do not enable the unfinished #232 release
or deployment gates. `bun test/tools/native_display_test.ts` checks accepted
changes plus stale, wrong-target, and indistinguishable-content controls.


`--phases input-display --pixel-inputs` adds a separate 132-event input
workload while the same ten stand-in agents stream. It calibrates the exact
composer glyph pixels for every prefix of `Backplane42` and the empty draft,
then types and erases the probe six times at eight events per second. Each
independent demand starts before its X event is dispatched and completes only
when its exact expected prefix reaches the X-server composer region. Prefixes
must have stable, pairwise-distinct digests after caret normalization; a region
that misses the text cannot pass calibration. The default region at 1400x900
is `444,788,600,32`; `--composer-roi X,Y,W,H` makes any explicit adjustment
visible in every demand. This phase keeps the original 60-key `type` workload
and its processing measurements separately available.

Only the two solid theme caret colors are replaced with their corresponding
panel colors before hashing the ASCII probe. All glyph pixels remain compared,
so blinking alone cannot satisfy a missing letter. The observer test preserves
both themes' glyph pixels, rejects missing/corrupt glyph pixels and wrong PPM
shape, and checks stale/wrong/late demands. Raw reports retain each expected
draft, key, region, digest, sample count and dispatch-to-readback duration;
`displayed_input_ms` applies the unchanged 16 ms p99 target and requires all
132 events. Calibration warms glyphs. These measurements include driver process
startup and independent readback overhead, and establish only this composer
region's content at the X server. They do not establish physical keyboard,
window compositor, full timeline or scanout latency.


Compare independently captured baseline/candidate pixel references before
accepting the displayed latency results:

```sh
bun test/tools/native_display_compare.ts baseline-input.json candidate-input.json --out input-pixels.json
bun test/tools/native_display_compare.ts baseline-warm-opens.json candidate-warm-opens.json --out open-pixels.json
bun test/tools/native_display_compare_test.ts
```

Both runs must supply `--source-sha FULL_40_CHARACTER_COMMIT` and the same
explicit `--build-flags 'LLVM19 -O3 LOW_MEM=1 JOBS=1'` label, matching the actual
builds. Reports include detected machine identity, observer schema, probe,
repeat count, ROIs, normalization and SHA-256 hashes of the fixture, driver,
observer, xpoke and binary. The comparison requires exact reference digests
and identical experiment metadata, complete ordered demands, and correct
observed digests. A candidate cannot pass by learning its own consistently
wrong glyph or title pixels. Separate reports may cover input and opens;
each enabled surface must be complete. This compares with the independent
baseline, and does not replace direct fresh-render correctness checks or any
latency target. The comparator's 29 controls exercise healthy comparisons,
self-consistent wrong content, invalid/missing observations and changed
experiment identities.

`BP_NATIVE_VALIDATE_LOCKED=1 scripts/validate-native-glyph.sh ABSOLUTE_LOG_DIR`
is the candidate's centralized validation entry point when the caller holds
`/tmp/bp-wt-build.lock`; otherwise omit that variable and the script acquires
the lock. Run it inside the parent's bounded-memory queue. It runs full
check/proof, every original unit test, independent X-server readback, the real
native glyph benchmark and native localization smoke tests. The glyph benchmark
must contain all 705 uniquely indexed samples; raw microseconds and summaries
are retained. Set `BACKPLANE_X11` and `BACKPLANE_TEST_XVFB` when using an extracted
X11 toolchain. It does not build or run the whole app; whole-app baseline and
candidate runs remain separately required.
