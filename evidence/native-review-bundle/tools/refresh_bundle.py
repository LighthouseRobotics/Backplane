#!/usr/bin/env python3
"""Append small evidence, retain origins, verify, then refresh bundle/archive.

Run from the task root. Original copied/git-blob members are immutable. Add
later receipts and experiments under new names. Documentation generated for the
bundle may be edited before refresh. No application, build or Git write runs.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

LIMIT = 2 * 1024 * 1024
PATTERNS = {
    "private_key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "github_token": r"gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}",
    "provider_key": r"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,}",
    "bearer_credential": r"(?i)bearer\s+[A-Za-z0-9_.~-]{12,}",
    "credential_assignment": r"(?i)(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|client[_-]?secret)\s*[=:]\s*[\"']?[A-Za-z0-9_./+~-]{12,}",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_rel(value):
    rel = PurePosixPath(value)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ValueError("unsafe bundle path")
    if any(part in {"home", "controller-home", "__pycache__"} for part in rel.parts):
        raise ValueError("home/cache files are outside the compact evidence scope")
    return rel


def inspected(data, label):
    if len(data) > LIMIT:
        raise ValueError(f"oversized member (large artifacts/traces excluded): {label}")
    text = data.decode("utf-8")
    if "\x00" in text:
        raise ValueError(f"binary member excluded: {label}")
    for name, pattern in PATTERNS.items():
        if re.search(pattern, text):
            raise ValueError(f"credential-pattern review required: {label} ({name})")


def collect(bundle):
    paths = []
    for path in bundle.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symlink excluded: {path.relative_to(bundle)}")
        if path.is_file():
            paths.append(path)
    return sorted(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--add", nargs=2, action="append", default=[], metavar=("SOURCE", "DEST"))
    parser.add_argument("--git-file", nargs=4, action="append", default=[], metavar=("REPO", "COMMIT", "SOURCE", "DEST"))
    parser.add_argument("--add-report-set", nargs=2, action="append", default=[], metavar=("SOURCE_DIR", "DEST_PREFIX"))
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    bundle, source_root = args.bundle.resolve(), args.source_root.resolve()
    archive = args.archive.resolve() if args.archive else None
    if archive and (archive == bundle or bundle in archive.parents):
        raise ValueError("archive must be outside the bundle")
    old = json.loads((bundle / "manifest.json").read_text())
    origins = {entry["path"]: entry["origin"] for entry in old["files"]}
    existing = collect(bundle)
    # Check original data before staging. Generated review docs may change.
    for entry in old["files"]:
        path = bundle / safe_rel(entry["path"])
        if not path.is_file():
            raise ValueError(f"previous member removed: {entry['path']}")
        if entry["origin"]["kind"] in {"copied", "git_blob"}:
            if digest(path.read_bytes()) != entry["sha256"]:
                raise ValueError(f"original member changed; append a new version: {entry['path']}")

    with tempfile.TemporaryDirectory(prefix=".native-review-stage-", dir=bundle.parent) as tmp:
        stage = Path(tmp) / bundle.name
        shutil.copytree(bundle, stage)

        def add(data, dest, origin):
            rel = str(safe_rel(dest))
            inspected(data, rel)
            path = stage / rel
            if path.exists() and path.read_bytes() != data:
                raise ValueError(f"refusing to overwrite member; use a new experiment/version: {rel}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            origins.setdefault(rel, {**origin, "original_sha256": digest(data)})

        def copy(source, dest):
            source = Path(source)
            if source.is_symlink():
                raise ValueError("symlink sources are excluded")
            source = source.resolve()
            rel = source.relative_to(source_root)
            safe_rel(str(rel))
            if source.is_symlink() or not source.is_file():
                raise ValueError("source must be an ordinary file")
            add(source.read_bytes(), dest, {"kind": "copied", "source_path": str(rel)})

        for source, dest in args.add:
            copy(source, dest)
        for repo, commit, source, dest in args.git_file:
            if not re.fullmatch(r"[0-9a-f]{40}", commit):
                raise ValueError("git source requires a full immutable commit")
            safe_rel(source)
            data = subprocess.check_output(["git", "-C", repo, "show", f"{commit}:{source}"])
            add(data, dest, {"kind": "git_blob", "source_commit": commit, "source_path": source})
        tops = ["raw.json", "status.json", "execution.exit", "command.sh", "stdout.log", "stderr.log",
                "artifact-identities.json", "summary.json", "compare-input.json", "compare-title.json",
                "compare-input.exit", "compare-title.exit", "machine-before.json", "measurement-bun-version.txt",
                "measurement-inputs.sha256", "measurement-lock.txt", "status.tsv", "baseline.source-label",
                "candidate.source-label", "load-before.txt", "load-after.txt"]
        for source, prefix in args.add_report_set:
            source = Path(source).resolve()
            selected = [Path(name) for name in tops if (source / name).is_file()]
            for run in ["baseline-cold", "candidate-cold", "baseline-warm", "candidate-warm"]:
                selected += [Path(run) / name for name in tops[:6] + tops[-2:] if (source / run / name).is_file()]
            if not any(path.name == "raw.json" for path in selected):
                raise ValueError("report set has no raw.json; no automatic directory recursion is allowed")
            for rel in selected:
                copy(source / rel, str(safe_rel(prefix) / rel))

        scanned = 0
        for path in collect(stage):
            if path.relative_to(stage).as_posix() in {"manifest.json", "SHA256SUMS"}:
                continue
            inspected(path.read_bytes(), path.relative_to(stage))
            scanned += 1
        scan = {"verdict": "pass", "scope": "Whitelisted small text evidence; originals preserved; no applications/builds launched",
                "files_scanned": scanned, "credential_pattern_matches": [],
                "homes_binaries_generated_builds_images_large_traces_included": False,
                "original_local_host_and_temporary_path_metadata_retained": True,
                "note": "Pattern scan is not a guarantee to detect every possible secret. New experiment acceptance is not inferred from file presence."}
        (stage / "safety-scan.json").write_text(json.dumps(scan, indent=2) + "\n")
        entries = []
        for path in collect(stage):
            rel = str(path.relative_to(stage))
            if rel in {"manifest.json", "SHA256SUMS"}:
                continue
            data = path.read_bytes()
            origin = origins.get(rel, {"kind": "generated", "description": "Review documentation, tools or validation generated for the bundle",
                                       "original_sha256": digest(data)})
            entries.append({"path": rel, "bytes": len(data), "sha256": digest(data), "origin": origin})
        updated = {**old, "files": entries}
        (stage / "manifest.json").write_text(json.dumps(updated, indent=2) + "\n")
        (stage / "SHA256SUMS").write_text("".join(digest(path.read_bytes()) + "  " + str(path.relative_to(stage)) + "\n"
                                                    for path in collect(stage) if path != stage / "SHA256SUMS"))
        subprocess.run([sys.executable, str(stage / "verify.py")], cwd=stage, check=True, timeout=60)
        for line in (stage / "SHA256SUMS").read_text().splitlines():
            expected, rel = line.split("  ", 1)
            if digest((stage / safe_rel(rel)).read_bytes()) != expected:
                raise ValueError("checksum verification failed")
        staged_archive = Path(tmp) / "bundle.tar.gz"
        if archive:
            with staged_archive.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
                with tarfile.open(fileobj=gz, mode="w|") as tar:
                    for path in collect(stage):
                        data = path.read_bytes()
                        info = tarfile.TarInfo(bundle.name + "/" + str(path.relative_to(stage)))
                        info.size, info.mtime, info.mode = len(data), 0, 0o644
                        tar.addfile(info, io.BytesIO(data))
        # No original file is removed or overwritten with different bytes.
        for path in collect(stage):
            rel = path.relative_to(stage)
            dest = bundle / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists() or dest.read_bytes() != path.read_bytes():
                temp = dest.with_name(dest.name + ".refresh-tmp")
                shutil.copyfile(path, temp)
                os.replace(temp, dest)
        if archive:
            archive.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged_archive, archive)
            archive.with_name(archive.name + ".sha256").write_text(digest(archive.read_bytes()) + "  " + archive.name + "\n")
        print(f"Verified/refreshed {len(entries)} members; all prior original origins retained.")
        if archive:
            print(f"Archive: {archive} ({archive.stat().st_size} bytes, SHA-256 {digest(archive.read_bytes())})")
        print("New measurements require their own receipt/content/budget review; this tool never promotes them to passes.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
