"""Export the compact R3 comparison and verify preserved hashes; no search calls."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    study = Path(__file__).resolve().parents[1]
    repo = study.parents[1]
    results = study / "results"
    analysis = read(results / "analysis.json")
    protocol = read(study / "protocol.json")
    validation = repo / "evidence/admission-recovery-full-20261027"
    errors = []
    manifests = {
        "frozen_engine": {
            "src/hpc_forest/" + name: expected
            for name, expected in protocol["engine_files"].items()
        },
        "full_test_sources": read(validation / "manifest.json"),
    }
    checked = {}
    for label, manifest in manifests.items():
        changed = [
            name for name, expected in manifest.items()
            if not (repo / name).is_file() or digest(repo / name) != expected
        ]
        checked[label] = {"files": len(manifest), "changed": changed}
        errors.extend(label + ": " + name for name in changed)

    native_calls = 0
    native_audits = []
    for arm in analysis["arms"]:
        s = arm["summary"]
        path = results / f"{s['case']}-{s['condition']}-model-invocations.json"
        audit = read(path)
        native_calls += audit["native_invocations"]
        native_audits.append({"file": path.name, "sha256": digest(path),
                              "calls": audit["native_invocations"], "valid": audit["valid"]})
        if not audit["valid"]:
            errors.append("Invalid native audit: " + path.name)
        for key in ("pipeline_complete", "delivery_valid", "fresh_memory_verified"):
            if not s[key]:
                errors.append(f"{s['pair_id']}: {key}")
        if s["pc_relay"] or (s["model"], s["effort"]) != ("gpt-6-luna", "max"):
            errors.append("Runtime mismatch: " + s["pair_id"])

    codes = read(study / "delivered-codes/manifest.json")
    for code in codes:
        if digest(study / "delivered-codes" / code["file"]) != code["sha256"]:
            errors.append("Changed delivered code: " + code["file"])

    columns = ["case", "condition", "job_id", "model", "effort", "registered_speedup",
               "reserved_speedup", "registered_status", "reserved_status", "research_trials",
               "correct_trials", "trees", "max_depth", "elapsed_seconds", "charged_elapsed_seconds",
               "stop_reason", "advisor_calls", "advisor_reorders", "advisor_seconds"]
    comparison = results / "comparison.csv"
    with comparison.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for arm in sorted(analysis["arms"], key=lambda a: (a["summary"]["case"], a["summary"]["condition"])):
            writer.writerow({key: arm["summary"][key] for key in columns})

    completion = read(results / "completion.json")
    if not completion["complete"] or completion["analysis"]["audit_errors"]:
        errors.append("Incomplete common measurement")
    report = {
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "source_manifests": checked,
        "software_validation": read(validation / "result.json"),
        "native_calls": native_calls, "native_audits": native_audits,
        "unmodified_delivered_codes": len(codes),
        "common_measurement_complete": completion["complete"],
        "comparison_sha256": digest(comparison),
        "analysis_sha256": digest(results / "analysis.json"),
        "errors": errors, "valid": not errors,
        "scope": "Local evidence checks only; no model, benchmark, or search rerun.",
    }
    (results / "final-verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
