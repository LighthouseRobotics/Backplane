#!/usr/bin/env python3
"""Offline positive/negative checks; retained evidence bytes are never edited."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("app_sets", ROOT / "tools/verify_app_sets.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
original = app.read


def control(label, predicate, mutate):
    def changed(root, path):
        value = original(root, path)
        if predicate(path):
            value = copy.deepcopy(value)
            mutate(value)
        return value
    app.read = changed
    try:
        app.verify_selected_comparisons(ROOT)
    except (ValueError, AssertionError, KeyError, TypeError):
        print("ok", label)
    else:
        raise AssertionError("negative control accepted: " + label)
    finally:
        app.read = original


result = app.verify_selected_comparisons(ROOT)
assert result[0]["status"] == result[1]["status"] == "incomplete_or_fail"
assert result[0]["runs"] == ["TARGET_FAIL"] * 4
assert result[1]["runs"].count("EXECUTION_FAIL") == 1
assert result[2]["status"] == "incomplete_or_fail" and result[2]["runs"] == ["TARGET_FAIL"] * 4
assert result[2]["independent_comparisons"] == {"input": False, "title": True}
print("ok target failures, stream failure and independent pixel failure remain separate")

def phase(value, name):
    return next(p for p in value["phases"] if p["name"] == name)


def wrong_pixels(value):
    display = value["native_display"]
    display["input_targets"]["B"] = "f" * 64
    for demand in display["demands"]:
        if demand.get("draft") == "B":
            demand["expected_pixel_sha256"] = demand["pixel_sha256"] = "f" * 64


def hide_gap(value):
    for window in phase(value, "open")["stream_windows"].values():
        if window["longest_gap_ms"] > 2000:
            window["sustained"] = True


cold = lambda path: path == "whole-app-main-only/candidate-cold/raw.json"
control("self-consistent wrong candidate pixels cannot replace independent baseline", cold, wrong_pixels)
control("a missing frame budget cannot disappear", cold,
        lambda v: phase(v, "normal")["checks"].pop("frame p99<=8ms"))
control("numeric frame metric cannot disagree with verdict", cold,
        lambda v: phase(v, "normal")["stats"]["ui.frame"].update(p99=1))
control("Status null coverage cannot become true", cold,
        lambda v: phase(v, "normal")["checks"].update({"Status tab observed": True}))
control("stale observed pixels fail demand validation", cold,
        lambda v: v["native_display"]["demands"][0].update(pixel_sha256="0" * 64))
control("incomplete composer coverage fails", cold,
        lambda v: v["native_display"]["demands"].pop())
control("changed fixture fails", cold, lambda v: v.update(log_sha256="0" * 64))
control("changed measurement source fails", cold, lambda v: v.update(harness_sha256="0" * 64))
control("physical scanout cannot be claimed", cold,
        lambda v: v["native_display"].update(physical_scanout_verified=True))
control("false sustained label cannot hide unchanged 2s guard", 
        lambda p: p == "whole-app-integrated-retry2/candidate-cold/raw.json", hide_gap)
control("execution failure cannot become target-only failure",
        lambda p: p == "whole-app-integrated-retry2/candidate-cold/status.json",
        lambda v: v.update(status="TARGET_FAIL"))
control("target failures cannot become summary acceptance",
        lambda p: p == "whole-app-main-only/summary.json", lambda v: v.update(result="pass"))
control("failed pixel verdict cannot become passing evidence",
        lambda p: p == "whole-app-main-only/compare-input.json", lambda v: v.update(verdict="fail"))
control("changed source tree cannot pass receipt binding",
        lambda p: p == "provenance/completed/main-only-full-build-verification.json",
        lambda v: v.update(tree="0" * 40))
control("a later helper cannot replace historical experiment bytes",
        lambda p: p == "comparison-index.json",
        lambda v: v["comparisons"][0].update(measurement_helper="reproduction/integrated-native-app-perf-evidence.py"))
control("original targets cannot be waived for a failing baseline",
        lambda p: p == "whole-app-main-only/summary.json",
        lambda v: v["limits"].update(frame_p99_ms=1000))
with tempfile.TemporaryDirectory(prefix="bp-comparison-failure-control-") as tmp:
    directory = Path(tmp)
    (directory / "compare-input.exit").write_text("1\n")
    (directory / "compare-input.log").write_text("AssertionError: independent composer reference pixels differ\n")
    status = {"status": "FAIL", "error": "comparison exited 1"}
    app.failed_comparison(directory, "input", status)
    print("ok actual missing-JSON failure is valid evidence")
    (directory / "compare-input.json").write_text('{"verdict":"pass"}\n')
    try:
        app.failed_comparison(directory, "input", status)
    except ValueError:
        print("ok fabricated passing JSON cannot replace failed comparator")
    else:
        raise AssertionError("fabricated pass accepted")
    (directory / "compare-input.json").unlink()
    (directory / "compare-input.log").write_text("")
    try:
        app.failed_comparison(directory, "input", status)
    except ValueError:
        print("ok failed comparator requires its original error log")
    else:
        raise AssertionError("missing failure log accepted")
print("20 selected-evidence controls passed; no apps, builds or retained evidence mutations")
