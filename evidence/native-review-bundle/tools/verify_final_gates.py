"""Verify included final source/producer/platform/CAD evidence, not omitted apps."""
from tools.verify_app_sets import read, require, sha


def verify_final_gates(root):
    base = "provenance/final7c/"
    equivalence = read(root, base + "final-app-binary-equivalence.json")
    local = read(root, base + "final-source-local-verification.json")
    source = equivalence["final_source"]
    require(equivalence["result"] == local["result"] == "pass" and local["source"] == source,
            "final source verification/equivalence disagree")
    require(source == {"commit": "7c7629dfb7b008ecfa6867c9e85f55f8a4d192e3",
                       "sha256": "b1e02c0b99d09de0765cce3073c18843485e3c600e9df2b32ba9ff5e1c1e2eeb",
                       "files": 1069, "status": []}, "final producer source changed")
    require(local["mode_normalization"]["source_bytes_or_Git_modes_changed"] is False,
            "source normalization changed product bytes or Git modes")
    binary = "6e0906044805f64128bd42ea63b6493c397c2c72c54cf2dc2282b7d9ab482fb2"
    require(equivalence["binary_sha256"] == binary and equivalence["binary_bytes"] == 146234240,
            "final app equivalence changed")
    require(equivalence["frozen_source_commit"] == "f30b5a3d8619b71ae922ca2cea9618726091492f"
            and equivalence["frozen_source_tree"] == "829c295f86a8e973d54abed64a689b05bc7e3376",
            "executed frozen source changed")

    def receipt(path):
        data = (root / path).read_bytes()
        value = read(root, path)
        require(value["schema"] == 2 and value["result"] == "pass"
                and value["source"] == value["source_after"] == source,
                "schema2 lane/source/final status changed")
        directory = (root / path).parent
        for step in value["steps"]:
            require(step["result"] == "pass" and step["exit_code"] == 0
                    and sha((directory / step["log"]).read_bytes()) == step["log_sha256"],
                    "final lane step/log binding failed")
        return value, sha(data)

    for platform in ("native", "mac"):
        verification = read(root, base + platform + "-verification.json")
        require(verification["source"] == source, "platform verification source changed")
        for lane, metadata in verification["lanes"].items():
            _, digest = receipt(base + platform + "/" + lane + "/result.json")
            require(metadata["result"] == "pass" and metadata["receipt_sha256"] == digest,
                    "platform verification receipt binding failed")
    producer, producer_sha = receipt(base + "native/build/result.json")
    require(producer_sha == equivalence["final_producer_receipt_sha256"], "genuine producer receipt differs")
    artifact = [a for a in producer["artifacts"] if a["path"] == "dist/backplane"]
    require(len(artifact) == 1 and artifact[0] == equivalence["matching_artifact"]
            and artifact[0]["sha256"] == binary and artifact[0]["bytes"] == 146234240,
            "final producer artifact differs from executed app identity")
    ci = read(root, base + "ci-verification.json")
    require(ci["result"] == "pass" and ci["source_commit"] == source["commit"]
            and ci["all_job_conclusions_success"] is True and ci["jobs"]
            and all(j["status"] == "completed" and j["conclusion"] == "success"
                    and j["active"] == [] and j["failures"] == [] for j in ci["jobs"]),
            "final CI verification does not cover all successful jobs")

    cad, cad_sha = receipt("final-real-cad/result.json")
    cad_verification = read(root, "final-real-cad/verification.json")
    require(cad_verification["result"] == "pass" and cad_verification["source"] == source
            and cad_sha == cad_verification["schema2_receipt_sha256"]
            and cad_sha == "ee6c0d114d87df9a05e05040ce29deec046d5593767bad3438b95106a26b4023",
            "final CAD receipt binding failed")
    require(cad["provenance"]["build"] == cad_verification["producer"]
            and cad["provenance"]["build"]["receipt_sha256"] == producer_sha
            and cad["consumed"]["hub_binary"]["sha256"] == binary,
            "real CAD consumed a different producer artifact")
    require(cad_verification["steps_and_all_log_hashes_verified"] is True
            and cad_verification["review_assertions"] == 41 and cad_verification["history_assertions"] == 28
            and len(cad_verification["release_files"]) == 30
            and all(f["bytes"] > 0 for f in cad_verification["release_files"])
            and sum(f["bytes"] for f in cad_verification["release_files"]) == 419157
            and cad_verification["release_total_bytes"] == 419157
            and cad_verification["source_tag_manifest_agree"] is True,
            "real CAD review/export assertions changed")
    require(cad_verification["release_fixture_source_commit"] == cad_verification["release_fixture_tag_commit"],
            "CAD source/tag identity differs")
    for name, count in (("02.log", 41), ("03.log", 28)):
        lines = (root / "final-real-cad" / name).read_text().splitlines()
        require(sum(line.startswith("ok   ") for line in lines) == count and lines[-1] == "all ok",
                "CAD assertion count or terminal verdict differs from original log")
    return {"source_commit": source["commit"], "producer_receipt_sha256": producer_sha,
            "binary_sha256": binary, "real_cad_receipt_sha256": cad_sha,
            "scope": "Included source/receipt/log metadata verified; omitted app, external tool and exported-file bytes are not revalidated."}
