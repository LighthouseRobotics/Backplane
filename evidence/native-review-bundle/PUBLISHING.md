# Parent publication preparation — no publication performed

This is a compact data-only support bundle. The original glyph comparison,
standalone selected comparison, failed integrated preflight and failed-workload
integrated retry and unchanged final repetition are retained separately, with
exact helpers and build receipts. The final repetition has healthy streams but
fails the empty-composer independent pixel comparison; its JSON was not emitted.
Final producer equivalence, native/mac/CI and real-CAD evidence are included.
Do not treat collection completion, execution
exit zero or independent content equality as latency acceptance.
Do not overwrite `whole-app-original/` or discard failed outcomes. Preserve its
exact bytes and source mapping. Add a separate main-only experiment if that
candidate is used; the two candidates are not interchangeable.

Review the final file whitelist, credential scan and bundle verification.
Exclude app/build files, temporary homes (including their tokens), provider
state, screenshots and large traces. Only generated workload data belongs here.
Original reports retain local host/path metadata for reproducibility.

The parent prepared an empty orphan worktree `native-evidence` on branch
`evidence/native-performance-2026-10-19` in the verified contributor fork
`LighthouseRobotics/Backplane`; no push has occurred. The parent should re-check the
authenticated account, remote and branch before any push. Create an isolated
checkout and orphan branch so only `evidence/native-review-bundle/` is staged;
inspect the complete staged file list before committing. Public source copies
under the evidence folder are provenance; do not modify production source paths
on this support branch and do not merge or deploy anything.

Publish the unpacked folder once, without duplicating the compressed archive in
Git. Capture the resulting full support commit and use it in `PR-LINK-TEXT.md`.
An optional archive can be attached separately with its own SHA-256. The parent
owns final gating, wording, commit, push and PR publication. Bundle preparation
may stage the whitelisted data-only files for inspection; it performs no
support-branch commit, push or PR publication.

## Refresh without losing provenance

The reusable helper is `tools/refresh_bundle_v2.py` (task copy:
`evidence/refresh-native-review-bundle.py`). Run from the task root and pass
the bundle path explicitly. `--add SOURCE DEST` appends a small UTF-8 evidence
file with its original relative source path and hash. `--git-file REPO COMMIT
SOURCE DEST` records an exact full-commit blob. Existing copied/git-source bytes
cannot be overwritten or deleted. Use a new name for a completed receipt rather
than replacing an earlier pending gate snapshot.

No more app repetitions are planned. Later untimed diagnostic text/metadata
must use a separate directory and must not relabel any historical verdict.
To refresh after appending reviewed diagnostic files, the command shape is:

```sh
python3 evidence/refresh-native-review-bundle.py \
  --bundle evidence/native-review-bundle \
  --add "$DIAGNOSTIC_FILE" "diagnostic/$DIAGNOSTIC_NAME" \
  --archive evidence/native-review-bundle.tar.gz
```

Set both diagnostic variables to actual reviewed text/metadata paths first. Report-set copying
uses a fixed file whitelist; it never recurses into temporary homes, builds,
tokens, screenshots or traces. A report-set append is preservation of evidence,
not a pass verdict. V2 preserves `compare-input.log` and `compare-title.log`,
including failures that emit no JSON. Explicitly review completeness, exact receipt/source
binding, independent content comparisons and every budget; update README with
the actual results. Failed and partial data stay failed or partial.

The helper stages changes in a temporary sibling directory, retains every old
origin, rejects changed original data or suspicious/binary/oversized members,
regenerates the manifest/checksums and executes `verify.py`. It replaces the
archive only after verification passes. A failure leaves the previous archive
bytes untouched. With no additions, use `--bundle` and `--archive` alone after
editing generated review documentation. The archive has deterministic headers;
its companion SHA-256 file names the archive without private absolute paths.
