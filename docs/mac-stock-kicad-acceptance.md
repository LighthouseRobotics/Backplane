Temporary fork-only acceptance for the exact combined source. This branch is
not a product runtime distribution and does not publish or install an app on a
user machine. Only `mac-stock-kicad.yml` matches its push branch; its concurrency
group is separate from the combined acceptance run.

The [official Mac download page](https://www.kicad.org/download/macos/) lists
stock KiCad 10.0.7 and links to its
[official release](https://github.com/KiCad/kicad-source-mirror/releases/tag/10.0.7).
The [official release API](https://api.github.com/repos/KiCad/kicad-source-mirror/releases/tags/10.0.7)
identifies asset647189970, `kicad-unified-universal-10.0.7.dmg`, 1,404,855,631
bytes, SHA256 `fbc27419b841a9a2a8b143b5875a87b8bd943ffcf487d53c78a8fb6d24c59e27`.
These values are pinned in `test/fixtures/kicad-stock-macos-source.json`.
Metadata was checked 2026-10-19; the workflow checks size/digest before mounting.

The Mac lane mounts the verified DMG read-only in a new RUNNER_TEMP directory,
copies only its app bundle under a private per-user application directory,
verifies its code signature, and invokes that copy's CLI. It does not replace
an existing `/Applications` app or change quarantine/signatures. All fixture
homes/config paths are private. The actual production `Rt.discover`, `Rt.refresh`,
`Rt.resolve` and cached `Rt.boot` are compiled from the existing fixture's
exact C emitted on Linux, then executed on Mac. The per-user automatic fallback
is also exercised when there is no global app with precedence; any existing
global app is neither replaced nor executed. Stock CLI/version and resolver
health must agree. Stock `api-server --describe` must be unavailable: this is
not Backplane bp.4 IPC acceptance, and no Mac fork package is invented.

The pinned, licensed KiCad ecc83 demo is verified with the existing fixture
fetcher. Stock KiCad exports board/body, copper, pads and silkscreen to GLB.
The optional GUI observation launches only a contained stock PCB-editor
executable in the runner GUI session, captures its PID, waits five seconds,
tries a screenshot and terminates only that owned process. A running process
or first-run dialog is not reported as functional GUI/board acceptance.

The exported GLB then passes through the actual emitted production Bend parser,
triangle/thinning/packet encoder and actual web mesh decoder on Linux. This
diagnostic deliberately uses a 192MiB Node stack after raising the process
stack limit; it does not establish phone-stack performance or acceptance.
Actual production WebGL renders a screenshot on Linux and, in a separate Mac
job, the exact same encoded packet. Record host, renderer, browser, geometry,
source/module/GLB/packet hashes and screenshots. Render success requires real
WebGL and a nontrivial pixel/geometry result; failure remains a failed job.
No screenshot or Mac acceptance result is claimed until the run completes and
its artifacts are reviewed. These jobs do not run accounts or live hub data,
measure physical-device budgets, publish a release or exercise fork IPC.
