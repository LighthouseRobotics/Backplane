# Applying only fused clipping to main

Read-only comparison against `30884966ef59c383581bcd1b7653f8f739cf009e` shows
the production change is independent of #157's glyph/table API. `Keep.step`
uses only `R.Op`, opaque `R.Shape`, `Region.hits/move/empty` and the existing
`Keep` helpers. Main already has the same previous comparator and helper
behavior. Its `keep_eq` public law has the same complete statement, and its
proof already has `ops_go_false`, `eq_op_f`, `keep_step_k` and `keep_step`.

The production step/continuation change, additive `keep_step_exact` law and
proof adapter can therefore transplant directly. It needs no `R.Tab`, `RKey`,
`KeySet`, tile cache-format or layout change. The old public laws can all remain
byte-identical, with one additive exact-step law.

The focused tests need small API adaptations because the bundled test imports
`glyph_table_test`, which is absent on main, and explicitly exercises the new
glyph table API. Use a tiny standalone synthetic face/cache fixture and
`Text.draw` instead of `Text.keydraw`; remove table arguments, the FSome table
field and Tile key-summary field in test/reference plans. Main already has
the same native FreeType face/warm API, including its existing face GTab field.
These are mechanical test changes, not a need to port #157.

After this read-only review, the parent authorized a new isolated main-only
candidate. It is now selected as commit
`af6527f41f9828ef483dfaae9e5bd3b1884ebf49` from 30884966, with
no glyph/layout/cache API integration. All 2,170 original
public laws remain byte-identical; only `keep_step_exact` is added. The focused
affected compiler proof passes. The separately built upstream-mask benchmark
passes 49 controls and 100 paired samples: old-reference planning p50/p99
1663/1848 µs versus 1459/1686 µs fused, with identical six changed tiles and
pixels. See `main-only-plan/` for original logs, summary, hashes, patch and audit.

That focused result is separate from both the glyph+clipping microbenchmark
and the original negative app experiment. Full check/proof/build passed; the
earlier included gate snapshot records the build pending at feature commit.
The later complete build receipt and matched standalone app comparison are now
included. That comparison has mixed timing and four TARGET_FAIL verdicts. It
does not show an overall app improvement. Both integrated attempts also remain
failed, one from a sustained-stream failure and the final repetition from an
independent empty-composer pixel mismatch. Retain all negative data.
