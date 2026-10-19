#!/usr/bin/env python3
"""Require complete native glyph-benchmark samples and summarize their raw us."""
import csv
import json
import math
import sys
from pathlib import Path


def summarize(text):
    expected = {name: 100 for name in (
        "masks", "keys", "prekeyed", "table-guard", "convert-and-eq",
        "key-eq", "extension-plan",
    )}
    expected.update({name: 1 for name in (
        "font-open", "ascii-fill-table", "nonASCII-fill-table",
        "fill-redraw-and-byte-check", "cold-frame",
    )})
    samples = {}
    for row in csv.reader(text.splitlines()):
        if not row or row[0] != "sample":
            continue
        if len(row) != 5 or row[1] not in expected:
            raise ValueError(f"unexpected glyph sample: {row}")
        _, name, index, elapsed, count = row
        index, elapsed, count = int(index), int(elapsed), int(count)
        if min(index, elapsed, count) < 0:
            raise ValueError(f"negative glyph sample: {row}")
        samples.setdefault(name, []).append((index, elapsed, count))
    result = {}
    for name, n in expected.items():
        rows = samples.get(name, [])
        if len(rows) != n or {row[0] for row in rows} != set(range(n)):
            raise ValueError(f"{name}: expected {n} uniquely indexed samples; got {len(rows)}")
        values = sorted(row[1] for row in rows)
        result[name] = {"n": n, "p50_us": values[math.ceil(n * .50) - 1],
                        "p99_us": values[math.ceil(n * .99) - 1], "max_us": values[-1]}
    return {"scope": "Native glyph microbenchmark; whole-app targets require separate measurements.",
            "samples": result}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: glyph_bench_report.py NATIVE_BENCH.log OUTPUT.json")
    Path(sys.argv[2]).write_text(json.dumps(summarize(Path(sys.argv[1]).read_text()), indent=2) + "\n")
    print("705 complete native glyph samples summarized")
