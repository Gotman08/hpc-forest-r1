"""Match preserved archives, verified downloads and commonly remeasured source files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("study", type=Path)
    args = parser.parse_args()
    results = args.study / "results"
    recovered = {item["archive"]: item for block in read(results / "recovered-archives.json")
                 for item in block.get("settled_archives", [])}
    codes = {Path(item["file"]).stem: item for item in read(args.study / "delivered-codes/manifest.json")}
    errors, rows = [], []
    for arm in read(args.study / "monitoring-paths.json"):
        identity = arm["stage"]
        receipt = read(args.study / "receipts" / (identity + ".json"))
        preserved = receipt["preservation"]
        recovered_item = recovered.get(preserved["archive"])
        if not preserved.get("verified") or recovered_item != preserved:
            errors.append(identity + ": preservation receipt differs from common recovery")
        if str(receipt["job_id"]) != str(arm["job_id"]):
            errors.append(identity + ": receipt allocation mismatch")
        by_name = {item["to"].replace("\\", "/").rsplit("/", 1)[-1]: item
                   for item in receipt["downloads"]}
        for suffix in ("-evidence.tar.gz", "-arm-result.json", "-delivered.cpp"):
            path = args.work / (identity + suffix)
            item = by_name.get(path.name, {})
            actual = digest(path) if path.is_file() else None
            matches = (item.get("ok") is True and item.get("verifie") is True
                       and actual is not None
                       and actual == item.get("remote_sha256")
                       and actual == item.get("empreinte_locale")
                       and actual == item.get("empreinte_distante"))
            if suffix == "-evidence.tar.gz":
                matches = matches and actual == preserved["archive_sha256"]
            if suffix == "-delivered.cpp":
                code = codes.get(identity, {})
                matches = matches and actual == code.get("sha256")
                matches = matches and actual == digest(args.study / "delivered-codes" / (identity + ".cpp"))
            rows.append({"arm": identity, "file": path.name, "sha256": actual, "valid": matches})
            if not matches:
                errors.append(identity + ": verified transfer mismatch " + suffix)
    report = {"files": rows, "valid": not errors, "errors": errors,
              "scope": "All eight preserved archives and delivered-source transfers; no mutation of evidence."}
    (results / "transfer-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"files": len(rows), "valid": report["valid"], "errors": errors}))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
