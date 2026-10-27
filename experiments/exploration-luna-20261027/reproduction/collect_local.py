"""Collect a verified common-results archive without modifying campaign evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("extracted", type=Path)
    parser.add_argument("study", type=Path)
    args = parser.parse_args()
    if args.extracted.exists() or (args.study / "results").exists():
        raise FileExistsError("Use fresh extraction and results directories")
    args.extracted.mkdir(parents=True)
    with tarfile.open(args.archive, "r:gz") as archive:
        archive.extractall(args.extracted, filter="data")
    destination = args.study / "results"
    shutil.copytree(args.extracted / "comparison", destination)
    for name in ("completion.json", "recovered-archives.json", "measurement-statuses.json"):
        shutil.copyfile(args.extracted / name, destination / name)
    for distribution in ("registered", "reserved"):
        shutil.copyfile(args.extracted / distribution / "common-measurements.json",
                        destination / f"measurements-{distribution}.json")
    analysis = json.loads((destination / "analysis.json").read_text(encoding="utf-8"))
    codes = args.study / "delivered-codes"
    codes.mkdir(exist_ok=False)
    manifest = []
    for arm in analysis["arms"]:
        summary = arm["summary"]
        if not summary["delivery_valid"]:
            continue
        identity = f"r{summary['repeat']}-{summary['condition']}"
        folder = f"source-{summary['case']}-{identity}"
        source = args.extracted / "registered" / folder / "src/candidate.cpp"
        name = f"{summary['case']}-{identity}.cpp"
        raw = source.read_bytes()
        (codes / name).write_bytes(raw)
        manifest.append({"case": summary["case"], "repeat": summary["repeat"], "condition": summary["condition"],
                         "job_id": summary["job_id"], "source": str(source), "file": name,
                         "sha256": hashlib.sha256(raw).hexdigest(), "unmodified": True})
    (codes / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with args.archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    receipt = {"archive": str(args.archive), "archive_sha256": digest,
               "extracted": str(args.extracted), "delivered_code_files": len(manifest),
               "summary": analysis["summary"]}
    (destination / "local-collection.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
