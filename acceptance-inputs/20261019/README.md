# Temporary frozen contribution acceptance

This contributor-fork support branch stores product changes as data, preserving
the focused branches' proof-before-commit gate. It contains no applied product
Bend changes and enables no deployment, release or production hook.

`manifest.json` identifies the exact source HEAD, captured worktree status,
private-index Git tree, patch hash and complete per-file SHA256 table for each
scope. Capture uses the working bytes, including staged and unstaged tracked
edits and intentional new source/test/documentation files. Generated build,
check, test and Python cache outputs are excluded. Each patch was independently
applied to a second private index starting at the recorded base commit; its
resulting tree must equal the captured tree. Real source indexes remain intact.

Capture explicitly includes live paths from the real index as well as HEAD and
desired untracked paths. A newly staged file modified again in the working tree
is absent from both HEAD and the untracked list; its current bytes must still be
included, even when deliberately tracked despite ignore rules. The fake-repo
selftest covers this case and verifies that real staged bytes remain unchanged.
The corrected followup matrix runs KiCad only, leaving the original seven
accepted/ongoing scopes and native build untouched.

The temporary workflow runs only on this named branch in the contributor fork.
Each isolated Ubuntu job saves the payload outside the checkout, detaches at the
recorded base, applies one patch with `--index`, and requires the resulting tree
and every source file's SHA256 to match. The staged index is intentional; this
does not claim a clean source checkout. The workflow pins Bend and Bun and runs
`CHECK_JOBS=1 CHECK_SHARDS=4 scripts/check.sh all`. It retains every Bend call's
raw output and status, independently checks the proof verdict with the
repository's existing verdict parser, and rejects missing or incomplete logs.

The native job builds the same verified source after a successful full check,
using clang 19 and the repository's low-memory build lane. Other jobs only check
and prove. Jobs upload logs, full source identity, patch and manifest, toolchain
identity, exit statuses, and artifact SHA256 values even on failure. A receipt
says pass only after exact source verification and complete successful checks;
the native receipt also requires its successful build and expected outputs.

The local capture/roundtrip result is preparation evidence, not a proof result.
Remote receipts are authoritative for each immutable input commit and applied
tree. A later support push cannot cancel these jobs because concurrency is
specific to the input commit. No PR is created for this temporary branch.
