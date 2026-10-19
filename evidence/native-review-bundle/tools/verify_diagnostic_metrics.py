"""Cross-check final compact metrics and untimed diagnostic metadata."""
from tools.verify_app_sets import quantile, read, require, sha


def verify_diagnostic_metrics(root):
    aggregate = read(root, "native-final-performance-summary.json")
    require(aggregate["limits_ms"] == {"frame_p99": 8, "streaming_input": 16, "open": 50,
                                       "agent_line_p99": 2}, "aggregate targets changed")
    directories = {"glyph-original": "whole-app-original", "main-only": "whole-app-main-only",
                   "integrated-attempt2": "whole-app-integrated-retry2",
                   "integrated-repeat3": "whole-app-integrated-repeat3"}
    require(set(aggregate["experiments"]) == set(directories), "aggregate omitted an attempted experiment")
    for name, prefix in directories.items():
        experiment = aggregate["experiments"][name]
        summary = read(root, prefix + "/summary.json")
        require(experiment["summary_result"] == summary["result"]
                and experiment["independent_reference_comparisons"] == summary["independent_reference_comparisons"],
                "aggregate promotes an experiment or comparison outcome")
        for side in ("baseline", "candidate"):
            cold = read(root, prefix + "/" + side + "-cold/raw.json")
            warm = read(root, prefix + "/" + side + "-warm/raw.json")
            phases = {phase["name"]: phase for phase in cold["phases"]}
            opened = warm["phases"][0]["displayed_open_ms"]
            inputs = phases["input-display"]["displayed_input_ms"]
            expected = {"normal_frame_p99_ms": phases["normal"]["stats"]["ui.frame"]["p99"],
                        "typing_frame_p99_ms": phases["type"]["stats"]["ui.frame"]["p99"],
                        "displayed_input_p99_ms": quantile(inputs, .99), "displayed_input_count": len(inputs),
                        "normal_agent_line_p99_ms": phases["normal"]["stats"]["hub.agent_line"]["p99"],
                        "cold_processing_open_max_ms": max(phases["open"]["opens_ms"]),
                        "warm_displayed_open_max_ms": max(opened), "warm_open_count": len(opened),
                        "cold_status": read(root, prefix + "/" + side + "-cold/status.json")["status"],
                        "warm_status": read(root, prefix + "/" + side + "-warm/status.json")["status"],
                        "binary_sha256": cold["binary_sha256"]}
            require(experiment["measurements"][side] == expected, "aggregate metric/status differs from original reports")

    diagnostic = read(root, "diagnostic/verification.json")
    states = {"40793bc68e3f859ab6b5ffc92eedd2372b9cbc9b6b59c5414cd10819fd1ef6c1",
              "9c69d25a423e0498f135341249430715e7d851b9829a02123e6fb3954a7a4934"}
    text = "b66c26cd5e7dc3662ab0612652dbbca9dfe1ad69d73b897d785bff6c9c073d96"
    require(diagnostic["result"] == "observer_empty_placeholder_blink_false_positive_reproduced_in_both_binaries"
            and diagnostic["original_reports_edited"] is False
            and diagnostic["thresholds_deadlines_ROI_aliases_or_measured_harness_changed"] is False,
            "diagnostic edited or promoted original experiment")
    require(sha((root / "diagnostic/capture-empty-composer.ts").read_bytes()) == diagnostic["diagnostic_source_sha256"]
            and diagnostic["observer_sha256"] == "4f061be549654f91c210eaa4dc99910a9db828a23316683f01428b6c0d0824fa",
            "untimed diagnostic source or pinned observer differs")
    for side in ("baseline", "candidate"):
        observed = diagnostic["sides"][side]
        records = read(root, "diagnostic/" + side + "/captures.json")["records"]
        require(observed["capture_count"] == len(records) == 11 and len(observed["captures"]) == 11,
                "diagnostic capture count changed")
        require(set(observed["empty_states"]) == states and observed["different_pixels"] == 3
                and observed["difference_bbox_roi"] == [14, 15, 15, 18], "empty-state diagnostic scope changed")
        require({r["sha256"] for r in records if r["name"] != "text"} == states
                and [r["sha256"] for r in records if r["name"] == "text"] == [text],
                "both exact empty states/nonempty pixels were not reproduced")
        require(all(observed["captures"][r["name"]]["normalized_sha256"] == r["sha256"] for r in records),
                "diagnostic record/hash binding differs")
    difference = read(root, "diagnostic/candidate/empty-difference.json")
    for field in ("difference_bbox_roi", "different_pixels", "color_pairs"):
        require(difference[field] == diagnostic["sides"]["baseline"][field] == diagnostic["sides"]["candidate"][field],
                "diagnostic pixel difference differs across binaries")
    comparison = read(root, "whole-app-integrated-repeat3/summary.json")["independent_reference_comparisons"]["input"]
    require(comparison["status"] == "FAIL", "diagnosis must not retroactively accept strict comparison")
    return {"four_experiment_metrics": "match original reports", "untimed_diagnostic": "both binary metadata agree",
            "strict_original_comparison": "FAIL", "scope": "PPM/PNG omitted; pixel bytes are not recomputed here."}
