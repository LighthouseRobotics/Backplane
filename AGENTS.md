# Backplane (Bend)

An agentic hardware development environment: an agent harness with
deterministic viewers for KiCad boards, schematics, and STEP models. It is a
ground-up rewrite of Backplane (formerly a T3Code fork; this repo now lives
at `i2cjak/Backplane`) in [Bend](https://bend-lang.com), so the rules that matter are laws the compiler
checks.

When using Bend:
- run `bend guide` to learn it
- use `LAWS.bend` to keep important rules
- run `bend PROOF.bend` before committing
- parallelize the code whenever possible

## Focused references

- For ownership and subsystem constraints, search `docs/agent-layout.md` by task terms or source path and read the matching paragraphs before editing that area. This is the original complete layout catalog; its rules still apply.
- For build, dev, packaging, benchmarks or headless checks, read the relevant section of `docs/agent-commands.md`. Native builds must use scripts/build-app.sh, never bare bend compilation on an in-use machine.
- For Bend edits or compiler/runtime failures, search `docs/agent-bend-traps.md` for the relevant construct/error and read the matching notes. Read the guide once if unfamiliar; avoid repeating it on routine continuations.
- Keep detailed discoveries in these reference files instead of growing startup instructions. Do not load all references for an unrelated or documentation-only edit.

Quick checks: `scripts/check.sh` checks Bend and proofs; `scripts/test.sh` runs core tests. Use affected end-to-end tests as required below. LAWS.bend is human-owned: never weaken or delete laws without explicit consent.

## House rules

- Developing (anything that gets compiled) ends the same way every time: test it (`scripts/check.sh`, the tests and e2e checks it touches), open a PR, merge it, then update every development server in use from the merged `main` (`scripts/dev.sh install h@backplane`, then `scripts/dev.sh install` here, last), and if the phone apps changed (`src/mobile/`, `mobile/`, anything bridge.js is built from), put a new build on TestFlight (`scripts/build-ios.sh archive`, `mobile/README.md`). Check each server reports the new version (`/hello`) and is listening. Never cut a release (a `v*` tag) for this; releases happen only when the user asks for one.
- Every feature matches everywhere: the native window, the web client, and both phone apps (iOS and Android). A feature is not done until all four have it, driven by the same Bend defs, and each is built (and tried where a device or simulator is at hand).

- Never kill processes by name or pattern; only PIDs you captured.
- The binary refuses unknown flags (exit 2) and a second hub on a home (exit 1), but still never run the installed `backplane` to probe it: without `--home` a good flag set starts the live hub, and older installs ignore unknown flags. Ask `/hello`; test with your own build, a temp `--home`, a port 3799+ and `--no-tailscale`.
- Never write to live user data (`~/.backplane-bend/`). Tests use a temp `BACKPLANE_HOME`.
- Persisted events stay decodable forever. Add event variants; never change the meaning of an existing one.
- No continuous repaint loops. The viewer animates only while a fade is in flight, then stops requesting frames.
- The UI is dumb: every decision (order, settle state, fade alpha, what's visible) comes from a Bend def with a law behind it where possible.
- Square corners, minimal copy, no decorative headings.
- Before pushing, verify the GitHub account (`i2cjak`), the remote, and the branch.
