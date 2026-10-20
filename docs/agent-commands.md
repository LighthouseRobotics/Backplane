## Commands

```sh
scripts/check.sh      # --check-only every .bend file, then bend PROOF.bend
scripts/test.sh       # run every test/*_test.bend (JS target, via bun)
scripts/build.sh      # native server binary + web bundle into dist/
scripts/build-app.sh src/app/main.bend build/backplane   # one native binary, compiled in parallel
dist/backplane        # run it (opens http://127.0.0.1:3787)
```

Trying a branch without CI or a release (use this, not a release, whenever the user wants to see or try a change):
- `scripts/dev.sh` builds the app and web client into `build/dev` (about 5 min) and runs them beside the installed Backplane: port 3788, home `~/.backplane-dev`, no tailnet, no self-update. It never touches `~/.backplane-bend`. Its window opens next to the user's. `scripts/dev.sh run --no-build` runs the last build again. For a headless check: `DISPLAY= BACKPLANE_DEV_HOME=$(mktemp -d) scripts/dev.sh run --no-build &`, capture the PID, probe `127.0.0.1:3788`, kill that PID.
- `scripts/dev.sh web` rebuilds only the web client (seconds); reload the page, no restart.
- `scripts/dev.sh install [user@host]` puts a full build over `~/.local/share/backplane` (here, or on that host over ssh) and restarts the service. The restart ends every session in the app, yours included, so update this machine last. The build is stamped `<next patch>-dev.<date>.<time>`, so the next real release replaces it and the updater never rolls it back.

Releases: `scripts/package.sh` makes the tarball the updater and install.sh use; `scripts/package-linux.sh` turns it into the AppImage and the `.deb`; `deploy/aur/PKGBUILD.in` is filled in by `release.yml`. A packaged install (`BACKPLANE_NO_UPDATE`, `$APPIMAGE`: `SV.Chan.managed`, laws `update_*_managed`) never updates itself; Settings says so (`U.Update.line`).

Native builds go through `scripts/build-app.sh`: bend emits the C, `scripts/cc-split.py` splits it into units, and clang compiles them at nice 19 on cores 0-3 (`BACKPLANE_JOBS`, `BACKPLANE_CPUS`), one build at a time machine-wide (`/tmp/bp-wt-build.lock`). About 2 minutes instead of 4+, and far less memory than one 30 MB file. Never run a bare `bend src/app/main.bend -o ...` on a machine someone is using.

Native builds need clang 19+ and X11 headers (`libx11-dev`). Without root, `~/.local/bin/clang` may be a `zig cc` shim, and `BACKPLANE_X11=~/.local/x11` points the build at headers extracted from the .deb.

Performance: every process keeps counters (`docs/perf.md`). ctrl+shift+h in the window shows the overlay, `curl -s 127.0.0.1:3787/debug/perf` gives the table, `BACKPLANE_TRACE=/tmp/t.json` writes a Perfetto trace, `BACKPLANE_LOG=debug` and `BACKPLANE_SLOW_MS=50` log more.

Typing speed: `scripts/build-app.sh test/native/type_bench.bend build/type_bench && build/type_bench` replays keys through the event, memo, layout and tiles with no window and prints ms per key. Scrolling: `test/native/scroll_bench.bend` the same for wheel notches up and down, and checks each frame against one drawn from scratch.

Many agents at once: `bun test/tools/agents_load.ts build/backplane build/wire --agents 1,10,50 --secs 20` starts a headless hub per count with a stand-in `claude` (Claude's stream-json: deltas, messages, tool calls; no model runs), streams from every thread at once and prints round trips, delta lag, rates, hub CPU and `/debug/perf`. The window's side: `build/agents_bench [MESSAGES [ENTRIES PER THREAD]]` (`test/native/agents_bench.bend`) hears a stream over 50 running threads and times each frame it asks for. Per-frame work must not grow with the log: read a thread's entries with `M.State.mine` and the links with `M.State.links` (the `Idx` filed on post), never by walking `entries`; another thread's delta asks for no frame (`U.Ui.shows`).

Headless UI checks: start Xvfb on `:77`, run `DISPLAY=:77 BACKPLANE_SNAP=/tmp/snap.ppm build/backplane --home /tmp/bp-x`, drive it with `build/xpoke` (`test/tools/xpoke.c`: click/type/key/wheel), and view frames with `scripts/ppm-to-png.py`.

