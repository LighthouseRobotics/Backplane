"""Read-only verification of appended completed comparisons; no app launch.

Budget failures are valid evidence and remain failures. This checks complete
reports, receipt/source bindings, exact independent content and recorded verdicts;
it never treats execution success or file existence as performance acceptance.
"""
import hashlib
import json
import math
from pathlib import PurePosixPath
import re

FLAGS = "LLVM=19;CFLAGS=-O3;LOW_MEM=1;JOBS=2;GOOGLE_BAKE=0"
LIMITS = {"frame_p99_ms": 8, "streaming_or_input_ms": 16,
          "open_ms": 50, "agent_line_p99_ms": 2}
DISPLAY_FIELDS = ["schema_version", "inputs_enabled", "opens_enabled", "input_cache",
                  "open_cache", "boundary", "physical_scanout_verified", "input_probe",
                  "input_repeats", "composer_region", "header_region", "caret_normalization"]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def relative(value):
    path = PurePosixPath(value)
    require(not path.is_absolute() and ".." not in path.parts, "unsafe comparison path")
    return path


def read(root, path):
    return json.loads((root / relative(path)).read_text())


def quantile(values, fraction):
    return sorted(values)[math.ceil(len(values) * fraction) - 1] if values else None


def failed_comparison(directory, surface, status):
    """Preserve an exited comparator with its actual log and absent JSON."""
    require(int((directory / f"compare-{surface}.exit").read_text()) != 0,
            "failed reference comparison has a successful exit")
    require(status["status"] == "FAIL" and bool(status.get("error")),
            "failed reference comparison promoted to pass")
    require(not (directory / f"compare-{surface}.json").exists(),
            "this failed comparator emitted no JSON; fabricated output is forbidden")
    require(bool((directory / f"compare-{surface}.log").read_text().strip()),
            "failed reference comparison error log missing")


def phase_checks(phase, display, mode):
    """Recompute the pinned driver's checks from its retained numeric report."""
    name, stats = phase["name"], phase["stats"]
    frame, inp, line = (stats[key] for key in ("ui.frame", "ui.input", "hub.agent_line"))
    key, opens = phase["key_to_frame"], phase["opens_ms"]
    inputs = [x["elapsed_ms"] for x in display["demands"] if x["kind"] == "input" and x["phase"] == name]
    titles = [x["elapsed_ms"] for x in display["demands"] if x["kind"] == "open" and x["phase"] == name]
    require(phase["displayed_input_ms"] == inputs and phase["displayed_open_ms"] == titles,
            "displayed latency samples differ from exact content demands")

    def complete(values, count):
        return len(values) == count and all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in values)

    expected = {}
    if name == "input-display":
        expected["all displayed input events observed"] = complete(inputs, 132)
        expected["displayed input p99<=16ms"] = complete(inputs, 132) and quantile(inputs, .99) <= 16
    if name == "open" and mode == "warm":
        expected["all ten displayed opens observed"] = complete(titles, 10)
        expected["displayed open<=50ms"] = complete(titles, 10) and max(titles) <= 50
    if name != "idle":
        require(len(phase["stream_windows"]) == 10, "missing independent provider stream coverage")
        for window in phase["stream_windows"].values():
            require(window["sustained"] == (window["count"] > 0 and window["longest_gap_ms"] <= 2000),
                    "sustained-stream guard changed or disagrees with samples")
        expected["all agents streaming"] = all(x["sustained"] is True for x in phase["stream_windows"].values())
    if name == "open":
        expected["all ten opens sampled"] = complete(opens, 10)
    if name == "normal":
        expected["Status tab observed"] = None
    expected["frame p99<=8ms"] = frame["p99"] <= 8 if frame["n"] else None
    if name in ("bg", "idle"):
        expected["no frame>16ms"] = frame["over16"] == 0 if frame["n"] else None
    if name in ("type", "normal"):
        expected["input p99<=16ms"] = inp["p99"] <= 16 if inp["n"] else None
        expected["key>frame p99<=16ms"] = key["p99"] <= 16 if key["n"] else None
    if name == "open" and not opens:
        expected["open<=50ms"] = None
    elif opens:
        expected["open<=50ms"] = complete(opens, 10 if name == "open" else 2) and max(opens) <= 50
    if name != "idle":
        expected["agent_line p99<=2ms"] = line["p99"] <= 2 if line["n"] else None
    require(phase["checks"] == expected, "reported checks omit coverage or disagree with original numeric budgets")


def targets(report, mode):
    display = report["native_display"]
    require(all(key in display for key in DISPLAY_FIELDS), "missing display metadata")
    require(display["enabled"] is True and display["schema_version"] == 1, "missing observer")
    require(display["boundary"] == "xserver-readback" and display["physical_scanout_verified"] is False,
            "wrong or unsupported presentation boundary")
    require(display["inputs_enabled"] == (mode == "cold") and display["opens_enabled"] == (mode == "warm"),
            "wrong cold/warm observation surface")
    for name in ("composer_region", "header_region"):
        region = display[name]
        require(isinstance(region, list) and len(region) == 4 and all(type(x) is int for x in region)
                and min(region[:2]) >= 0 and min(region[2:]) > 0, "invalid observer region")
    for name in ("input_targets", "targets"):
        mapping = display[name]
        require(isinstance(mapping, dict) and all(isinstance(x, str) and re.fullmatch("[0-9a-f]{64}", x)
                                                for x in mapping.values()), "invalid pixel target map")
        require(len(set(mapping.values())) == len(mapping), "indistinguishable pixel targets")
    if mode == "cold":
        require(display["input_probe"] == "Backplane42" and display["input_repeats"] == 6,
                "different input workload")
        prefixes = [display["input_probe"][:i] for i in range(12)]
        require(set(display["input_targets"]) == set(prefixes) and display["targets"] == {},
                "missing or extra composer/title targets")
        require(display["input_cache"] == "warm-calibrated", "wrong input cache scope")
    else:
        names = {"zqlong", *("zqopen" + chr(97 + i) for i in range(10)),
                 *("zqrun" + chr(97 + i) for i in range(10))}
        require(set(display["targets"]) == names and display["input_targets"] == {},
                "missing or extra warm title targets")
        require(display["open_cache"] == "warm-calibrated", "wrong open cache scope")
    previous = 0
    for demand in display["demands"]:
        require(type(demand["revision"]) is int and demand["revision"] > previous,
                "nonmonotonic displayed-content demand")
        previous = demand["revision"]
        expected = (display["input_targets"].get(demand.get("draft")) if demand["kind"] == "input"
                    else display["targets"].get(demand.get("title")) if demand["kind"] == "open" else None)
        require(expected and demand["expected_pixel_sha256"] == expected and demand["pixel_sha256"] == expected,
                "wrong/stale/unmapped displayed content")
        require(demand["boundary"] == display["boundary"], "demand boundary changed")
        require(demand["region"] == display["composer_region" if demand["kind"] == "input" else "header_region"],
                "demand region changed")
        require(math.isfinite(demand["elapsed_ms"]) and 0 <= demand["elapsed_ms"] <= 2000
                and math.isfinite(demand["dispatch_started_ms"]) and type(demand["samples"]) is int
                and demand["samples"] >= 1 and bool(demand["thread"]), "missing demand timing/thread")
    if mode == "cold":
        expected, draft = [], ""
        for _ in range(6):
            for key in display["input_probe"]:
                draft += key
                expected.append((draft, key))
            for _ in display["input_probe"]:
                draft = draft[:-1]
                expected.append((draft, "BackSpace"))
        actual = [(x["draft"], x["key"]) for x in display["demands"]
                  if x["kind"] == "input" and x["phase"] == "input-display"]
        require(actual == expected, "missing/reordered 132 composer demands")
    else:
        actual = [x["title"] for x in display["demands"] if x["kind"] == "open" and x["phase"] == "open"]
        require(actual == ["zqopen" + chr(97 + i) for i in range(10)], "missing/reordered ten opens")
    return display


def verify_selected_comparisons(root):
    index = read(root, "comparison-index.json")
    audit = read(root, "provenance/completed/native-perf-build-script-audit.json")
    require(audit["result"] == "pass" and audit["failed_attempt_app_executions"] == 0, "preflight audit changed")
    require(audit["historical_main_only_helper_sha256"] ==
            sha((root / "reproduction/main-only-native-app-perf-evidence.py").read_bytes()), "historical helper audit differs")
    for script, names in {"scripts/build-app.sh": ("baseline-build-app.sh", "integrated-build-app.sh"),
                          "scripts/cc-unit.sh": ("baseline-cc-unit.sh", "integrated-cc-unit.sh")}.items():
        for side, name in zip(("baseline", "candidate"), names):
            require(sha((root / "source/build-scripts" / name).read_bytes()) == audit["files"][script][side + "_sha256"],
                    "audited build-script source binding differs")
    require("25 artifact-layout/summary/port controls passed" in
            (root / "bundle-checks/integrated-helper-controls.log").read_text(), "reviewed helper controls missing")
    for attempt in index["preflight_failures"]:
        require(attempt["app_executions"] == 0, "provenance-only failure gained app execution")
        directory = root / relative(attempt["directory"])
        status = (directory / "status.tsv").read_text()
        require("provenance\tFAIL\t1" in status and "overall\tINCOMPLETE_OR_FAIL\t1" in status
                and "RUNNING" not in status, "failed preflight status changed")
        require("candidate build flags cannot use baseline default script" in
                (directory / "provenance.log").read_text(), "failed preflight reason missing")
    results = []
    for entry in index["comparisons"]:
        if entry["state"] == "pending":
            results.append({"id": entry["id"], "status": "PENDING"})
            continue
        require(entry["state"] == "completed", "unknown comparison state")
        prefix = str(relative(entry["directory"]))
        identity = read(root, prefix + "/artifact-identities.json")
        full = read(root, entry["verification"])
        receipt_data = (root / relative(entry["receipt"])).read_bytes()
        receipt = json.loads(receipt_data)
        require(full["result"] == "pass" and full["build_exit"] == 0 and full["run_conclusion"] == "success",
                "completed genuine build receipt required")
        require(sha(receipt_data) == full["receipt_sha256"] and receipt["error"] is None
                and receipt["check_exit"] == 0 and receipt["proof_verdict"] == 0
                and receipt["complete_check_and_proof_log"] is True and receipt["build_exit"] == 0,
                "build/proof receipt binding failed")
        require(full["verified_files"] == entry["source_files"] == receipt["expected_files"]
                and full["verified_artifacts"] == 54 == len(receipt["artifacts"]), "source/artifact count differs")
        candidate = identity["candidate"]
        for key, value in {"source_label": full["input_commit"], "applied_tree": full["tree"],
                           "receipt_sha256": full["receipt_sha256"], "binary_sha256": full["binary_sha256"],
                           "checkout_commit": receipt["checkout_commit"], "patch_sha256": receipt["patch_sha256"]}.items():
            require(candidate[key] == value, "candidate identity differs from genuine receipt: " + key)
        require(full["current_head"] == entry["product_commit"] and full["tree"] == entry["product_tree"],
                "committed product/source tree differs")
        app = [x for x in receipt["artifacts"] if x["path"].endswith("/dist/backplane")]
        require(len(app) == 1 and app[0]["sha256"] == candidate["binary_sha256"], "receipt native artifact missing")
        original = read(root, "whole-app-original/artifact-identities.json")
        require(identity["baseline"] == original["baseline"],
                "baseline artifact identity changed")
        require(identity["measurement_harness"] == original["measurement_harness"]
                and identity["toolchain"] == original["toolchain"], "measurement harness or toolchain changed")
        require(receipt["input_commit"] == full["input_commit"] and receipt["applied_tree"] == full["tree"],
                "receipt source differs from full verification")
        require(identity["fixture_sha256"] == "ac5f4374d7946569b420d7b2ca2d5890c99d54d323a819a6d66beaf2d824b543"
                and identity["build_flags"] == FLAGS, "fixture or build flags differ")
        helper = (root / relative(entry["measurement_helper"])).read_bytes()
        inputs = (root / prefix / "measurement-inputs.sha256").read_text().splitlines()
        require(any(line.split()[0] == sha(helper) and line.endswith("/evidence/native-app-perf-evidence.py")
                    for line in inputs), "historical measurement helper does not match experiment inputs")
        summary = read(root, prefix + "/summary.json")
        require(summary["limits"] == LIMITS, "performance targets changed")
        reports, statuses = {}, []
        for side in ("baseline", "candidate"):
            for mode in ("cold", "warm"):
                name = side + "-" + mode
                report = read(root, prefix + "/" + name + "/raw.json")
                status = read(root, prefix + "/" + name + "/status.json")
                execution = int((root / prefix / name / "execution.exit").read_text())
                wanted = {"idle", "bg", "fg", "type", "input-display", "open", "normal"} if mode == "cold" else {"open"}
                require({p["name"] for p in report["phases"]} == wanted and len(report["phases"]) == len(wanted),
                        "missing/duplicate workload phases")
                require(report["binary_sha256"] == identity[side]["binary_sha256"]
                        and report["source_sha_declared"] == identity[side]["source_label"], "measured artifact differs")
                require(report["build_flags_declared"] == FLAGS and report["log_sha256"] == identity["fixture_sha256"]
                        and report["agents"] == 10 and report["secs"] == 5 and report["bot_streaming"] is True
                        and report["stray_agents"] == [], "workload, fixture or isolation differs")
                for raw, source in (("harness_sha256", "test/tools/perf_load.ts"),
                                    ("observer_sha256", "test/tools/native_display.ts")):
                    require(report[raw] == identity["measurement_harness"]["files"][source], "raw measurement source differs")
                display = targets(report, mode)
                failed, unknown = [], []
                for phase in report["phases"]:
                    phase_checks(phase, display, mode)
                    require(bool(phase["checks"]), "phase verdicts missing")
                    for check, value in phase["checks"].items():
                        require(value is True or value is False or value is None, "invalid target verdict")
                        if value is False:
                            failed.append({"phase": phase["name"], "check": check})
                        elif value is None:
                            unknown.append({"phase": phase["name"], "check": check})
                derived = "EXECUTION_FAIL" if execution else "TARGET_FAIL" if failed else "UNVERIFIED" if unknown else "PASS"
                require(status["status"] == derived and status["execution_exit"] == execution,
                        "run status hides an execution, workload or budget failure")
                if execution:
                    require(bool(status.get("error")), "failed execution reason missing")
                else:
                    require(status["failed_checks"] == failed and status["unverified_checks"] == unknown,
                            "run status hides a failed or unverified budget")
                require(summary["runs"][name] == status, "summary run status differs from raw status")
                reports[name], statuses = report, statuses + [derived]
        comparison_passes = []
        for surface, mode, counts in [("input", "cold", (12, 0)), ("title", "warm", (0, 21))]:
            a, b = reports["baseline-" + mode], reports["candidate-" + mode]
            comparison_status = summary["independent_reference_comparisons"][surface]
            code = int((root / prefix / f"compare-{surface}.exit").read_text())
            if code:
                failed_comparison(root / prefix, surface, comparison_status)
                comparison_passes.append(False)
                continue
            for field in ["log_sha256", "log_bytes", "harness_sha256", "observer_sha256", "xpoke_sha256", "machine"]:
                require(a[field] == b[field], "independent experiment metadata differs: " + field)
            for field in DISPLAY_FIELDS + ["input_targets", "targets"]:
                require(a["native_display"][field] == b["native_display"][field], "independent reference pixels/metadata differ")
            raw = (root / prefix / f"compare-{surface}.json").read_bytes()
            comparison = read(root, prefix + f"/compare-{surface}.json")
            require(comparison["verdict"] == "pass"
                    and (comparison["input_targets"], comparison["title_targets"]) == counts,
                    "comparison execution, verdict or target coverage failed")
            for field, value in {"baseline_binary_sha256": a["binary_sha256"], "candidate_binary_sha256": b["binary_sha256"],
                                 "baseline_source": a["source_sha_declared"], "candidate_source": b["source_sha_declared"],
                                 "fixture_sha256": identity["fixture_sha256"], "harness_sha256": a["harness_sha256"]}.items():
                require(comparison[field] == value, "comparison receipt/source identity differs")
            require(summary["independent_reference_comparisons"][surface] ==
                    {"status": "PASS", "exit": 0, "report_sha256": sha(raw)}, "comparison summary binding failed")
            comparison_passes.append(True)
        derived = "pass" if all(status == "PASS" for status in statuses) and all(comparison_passes) else "incomplete_or_fail"
        require(summary["result"] == derived, "summary promotes target failures to acceptance")
        results.append({"id": entry["id"], "status": derived, "runs": statuses,
                        "independent_comparisons": dict(zip(("input", "title"), comparison_passes))})
    return results
