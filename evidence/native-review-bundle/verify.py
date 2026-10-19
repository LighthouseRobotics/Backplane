#!/usr/bin/env python3
"""Verify this compact evidence bundle without launching apps or builds."""
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sys

sys.dont_write_bytecode = True
from tools.verify_app_sets import verify_selected_comparisons
from tools.verify_final_gates import verify_final_gates
from tools.verify_diagnostic_metrics import verify_diagnostic_metrics

ROOT = Path(__file__).resolve().parent


def load(path):
    return json.loads((ROOT / path).read_text())


manifest = load("manifest.json")
expected = set()
for item in manifest["files"]:
    rel = PurePosixPath(item["path"])
    assert not rel.is_absolute() and ".." not in rel.parts, "unsafe manifest path"
    path = ROOT / rel
    assert not path.is_symlink() and path.is_file(), f"missing/linked: {rel}"
    data = path.read_bytes()
    assert len(data) == item["bytes"], f"byte count: {rel}"
    assert hashlib.sha256(data).hexdigest() == item["sha256"], f"SHA-256: {rel}"
    if item["origin"]["kind"] in ("copied", "git_blob"):
        assert item["origin"]["original_sha256"] == item["sha256"], f"altered original: {rel}"
    assert str(rel) not in expected, f"duplicate: {rel}"
    expected.add(str(rel))
actual = {str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file()}
assert actual == expected | {"manifest.json", "SHA256SUMS"}, "unexpected/missing bundle file"

identity = load("whole-app-original/artifact-identities.json")
fixture = (ROOT / "fixture/events.jsonl").read_bytes()
assert len(fixture) == 556794 and len(fixture.splitlines()) == 1520
assert hashlib.sha256(fixture).hexdigest() == identity["fixture_sha256"]
assert identity["measurement_harness"]["commit"] == "62fa318989b092aa8712825a4c75f1e4f0c6bcbf"
for path, digest in identity["measurement_harness"]["files"].items():
    assert hashlib.sha256((ROOT / "harness" / path).read_bytes()).hexdigest() == digest

for side in ("baseline", "candidate"):
    for mode in ("cold", "warm"):
        prefix = f"whole-app-original/{side}-{mode}"
        report = load(prefix + "/raw.json")
        status = load(prefix + "/status.json")
        assert int((ROOT / prefix / "execution.exit").read_text()) == 0
        assert status["status"] == "TARGET_FAIL"
        assert report["binary_sha256"] == identity[side]["binary_sha256"]
        assert report["source_sha_declared"] == identity[side]["source_label"]
        assert report["log_sha256"] == identity["fixture_sha256"]
        assert report["agents"] == 10 and report["secs"] == 5
        assert report["build_flags_declared"] == identity["build_flags"]

for surface, count in (("input", 12), ("title", 21)):
    result = load(f"whole-app-original/compare-{surface}.json")
    assert result["verdict"] == "pass"
    assert result[f"{surface}_targets"] == count
    assert int((ROOT / f"whole-app-original/compare-{surface}.exit").read_text()) == 0
    assert result["baseline_binary_sha256"] == identity["baseline"]["binary_sha256"]
    assert result["candidate_binary_sha256"] == identity["candidate"]["binary_sha256"]

lines = (ROOT / "focused-plan/native-keep-plan-final-bench.log").read_text().splitlines()
assert not any(line.startswith("FAIL ") for line in lines)
assert len([line for line in lines if line.startswith("ok ")]) == 49
rows = [list(map(int, line.split(",")[1:])) for line in lines if line.startswith("sample,")]
assert len(rows) == 100 and sorted(row[0] for row in rows) == list(range(100))
assert all(row[3:] == [6, 6] for row in rows)


def stats(values):
    values = sorted(values)
    return {"p50": values[math.ceil(len(values) * .5) - 1],
            "p99": values[math.ceil(len(values) * .99) - 1],
            "min": values[0], "max": values[-1]}


focused = load("focused-plan/native-keep-plan-final-summary.json")
assert focused["old_reference_us"] == stats([row[1] for row in rows])
assert focused["fused_us"] == stats([row[2] for row in rows])
assert focused["checks_passed"] == 49 and focused["samples"] == 100
audit = load("preservation/glyph-law-mapping.json")
assert audit["old_public_laws"] == 2170 and audit["glyph_public_laws"] == 2173
assert not audit["missing"] and len(audit["changed"]) == 9
fused = load("provenance/native-latency-law-audit.json")
assert not fused["missing"] and not fused["changed_statements"]
assert fused["added"] == ["keep_step_exact"]
main_lines = (ROOT / "main-only-plan/native-plan-only-bench.log").read_text().splitlines()
assert not any(line.startswith("FAIL ") for line in main_lines)
assert sum(line.startswith("ok ") for line in main_lines) == 49
main_rows = [list(map(int, line.split(",")[1:])) for line in main_lines if line.startswith("sample,")]
assert len(main_rows) == 100 and sorted(row[0] for row in main_rows) == list(range(100))
assert all(row[3:] == [6, 6] for row in main_rows)
main = load("main-only-plan/native-plan-only-summary.json")
assert main["old_reference_us"] == stats([row[1] for row in main_rows])
assert main["fused_us"] == stats([row[2] for row in main_rows])
main_audit = load("main-only-plan/native-plan-only-law-audit.json")
assert main_audit["old_public_laws"] == 2170 and main_audit["new_public_laws"] == 2171
assert not main_audit["missing"] and not main_audit["changed"]
assert main_audit["added"] == ["keep_step_exact"]

# Exact recovered helper, separately bound to the original experiment inputs.
helper = ROOT / "reproduction/original-native-app-perf-evidence.py"
helper_hash = hashlib.sha256(helper.read_bytes()).hexdigest()
assert helper_hash == "376053ba7b21ef826b0e031d8977f839f54ae0d9cb5451af167390cdc3a1ba81"
input_lines = (ROOT / "whole-app-original/measurement-inputs.sha256").read_text().splitlines()
assert any(line.split()[0] == helper_hash and line.endswith("/evidence/native-app-perf-evidence.py") for line in input_lines)

# These receipts bind completed gates; no omitted app bytes are revalidated here.
full = load("provenance/completed/native-latency-full-build-verification.json")
receipt_path = ROOT / "provenance/completed/native-latency-receipt.json"
assert hashlib.sha256(receipt_path.read_bytes()).hexdigest() == full["receipt_sha256"]
receipt = json.loads(receipt_path.read_text())
assert full["result"] == "pass" and full["verified_files"] == 986 and full["verified_artifacts"] == 54
assert full["build_exit"] == 0 and receipt["build_exit"] == 0 and receipt["check_exit"] == 0
assert receipt["proof_verdict"] == 0 and receipt["complete_check_and_proof_log"] is True
assert receipt["input_commit"] == full["input_commit"] and receipt["applied_tree"] == full["tree"]
assert len(receipt["artifacts"]) == 54
gate = load("provenance/completed/native-plan-only-commit-gate.json")
assert gate["result"] == "check_and_proof_step_pass"
assert gate["commit"] == "af6527f41f9828ef483dfaae9e5bd3b1884ebf49"
assert gate["proof_step"]["status"] == "completed" and gate["proof_step"]["conclusion"] == "success"
assert "pending at feature commit" in gate["build_status"]
for line in (ROOT / "main-only-plan/native-plan-only-source.sha256").read_text().splitlines():
    digest, path = line.split("  ", 1)
    assert hashlib.sha256((ROOT / "source/main-only" / path).read_bytes()).hexdigest() == digest
combined = load("provenance/completed/final-plan-combined-proof-verification.json")
mapping = load("provenance/completed/final-plan-combined-verified-commit.json")
assert combined["result"] == "pass" and combined["verified_files"] == 1069
assert combined["receipt_sha256"] == "de00da220026a1177afb3f52961a5673d384603d5ab6308b38195bc3a4ea8881"
assert combined["build_exit"] is None and combined["binary_sha256"] is None
assert mapping["frozen_proof_and_app_source_commit"] == "f30b5a3d8619b71ae922ca2cea9618726091492f"
assert mapping["tree"] == combined["tree"] and mapping["receipt_sha256"] == combined["receipt_sha256"]
assert mapping["final_non_bend_followup"]["commit"] == "7c7629dfb7b008ecfa6867c9e85f55f8a4d192e3"
assert mapping["final_non_bend_followup"]["Bend_source_diff"] == "empty"
assert mapping["final_non_bend_followup"]["changed_files"] == ["test/tools/kicad_platform_e2e.ts"]
selected = verify_selected_comparisons(ROOT)
final_gates = verify_final_gates(ROOT)
diagnostic_metrics = verify_diagnostic_metrics(ROOT)
print(f"PASS: {len(expected)} file hashes/origins, four original TARGET_FAIL reports, "
      "independent reference receipts, two separate 49-control/100-pair runs, preservation and completed gate bindings")
print("Selected comparison evidence:", json.dumps(selected, sort_keys=True))
print("Final producer/platform/CAD evidence:", json.dumps(final_gates, sort_keys=True))
print("Final metrics/untimed diagnostic metadata:", json.dumps(diagnostic_metrics, sort_keys=True))
print("Evidence integrity is separate from latency acceptance. No omitted app binary or pending result is verified here.")
