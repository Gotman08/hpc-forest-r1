"""Verify the frozen engine, all assigned searches and locally preserved evidence."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    study = Path(__file__).resolve().parents[1]
    repo = study.parents[1]
    results = study / "results"
    validation = repo / "evidence/exploration-final-full-20261027"
    protocol = read(study / "protocol.json")
    assigned = read(study / "monitoring-paths.json")
    analysis = read(results / "analysis.json")
    completion = read(results / "completion.json")
    software = read(validation / "result.json")
    errors, checked, audits = [], {}, []
    manifests = {
        "frozen_engine": {"src/hpc_forest/" + name: value
                          for name, value in protocol["engine_files"].items()},
        "final_test_sources": read(validation / "manifest.json"),
    }
    for label, manifest in manifests.items():
        changed = [name for name, expected in manifest.items()
                   if not (repo / name).is_file() or digest(repo / name) != expected]
        checked[label] = {"files": len(manifest), "changed": changed}
        errors.extend(label + ": " + name for name in changed)

    expected = {(a["case"], a["repeat"], a["condition"]): a for a in assigned}
    reported = {}
    for arm in analysis["arms"]:
        s = arm["summary"]
        key = (s["case"], s["repeat"], s["condition"])
        if key in reported:
            errors.append("Duplicate assigned arm: " + str(key))
        reported[key] = s
    if set(expected) != set(reported):
        errors.append("Assigned/reported arm mismatch")
    native_calls = 0
    for key, arm in expected.items():
        identity = f"{key[0]}-r{key[1]}-{key[2]}"
        s = reported.get(key, {})
        model_path = results / (identity + "-model-invocations.json")
        exploration_path = results / (identity + "-exploration.json")
        stop_path = results / (identity + "-stop-timeline.json")
        entry = {"arm": identity}
        if model_path.is_file():
            model = read(model_path)
            native_calls += model["native_invocations"]
            entry.update(model_audit_sha256=digest(model_path),
                         native_calls=model["native_invocations"],
                         model_settings_valid=model["valid"])
            if not model["valid"]:
                errors.append(identity + ": model invocation audit")
        else:
            errors.append(identity + ": missing model audit")
        if exploration_path.is_file():
            exploration = read(exploration_path)["summary"]
            entry["exploration_audit_sha256"] = digest(exploration_path)
            if not exploration["archive_enabled"]:
                errors.append(identity + ": archive disabled")
            for audit_key, result_key in (("research_trials", "research_trials"),
                                          ("correct_measured_trials", "correct_trials")):
                if exploration[audit_key] != s.get(result_key):
                    errors.append(identity + ": inconsistent " + audit_key)
        else:
            errors.append(identity + ": missing exploration audit")
        if stop_path.is_file():
            control = read(stop_path)
            entry["control_audit_sha256"] = digest(stop_path)
            entry["mother_receipts_verified"] = control["summary"]["receipts_verified"]
            entry["mother_receipts_missing_or_invalid"] = control["summary"]["receipts_missing_or_invalid"]
            if control["errors"] or not control["summary"]["request_chain_verified"]:
                errors.append(identity + ": Mother conversation chain")
        else:
            errors.append(identity + ": missing stop/control audit")
        for field in ("pipeline_complete", "delivery_valid", "fresh_memory_verified"):
            if not s.get(field):
                errors.append(identity + ": " + field)
        if s.get("pc_relay") is not False or (s.get("model"), s.get("effort")) != ("gpt-6-luna", "max"):
            errors.append(identity + ": runtime settings mismatch")
        if str(s.get("job_id")) != str(arm["job_id"]):
            errors.append(identity + ": allocation mismatch")
        for field, value in (("target_seconds", protocol["search_target_seconds_per_arm"]),
                             ("cap_seconds", protocol["end_to_end_cap_seconds_per_arm"])):
            if s.get(field) != value:
                errors.append(identity + ": budget mismatch " + field)
        audits.append(entry)
    for case in {key[0] for key in expected}:
        for repeat in {key[1] for key in expected}:
            pair = [reported.get((case, repeat, c), {}) for c in ("off", "corrected")]
            for field in ("seed", "target_seconds", "cap_seconds", "charged_planning_seconds"):
                if pair[0].get(field) != pair[1].get(field):
                    errors.append(f"{case}-r{repeat}: unequal {field}")

    code_manifest = read(study / "delivered-codes/manifest.json")
    for code in code_manifest:
        if digest(study / "delivered-codes" / code["file"]) != code["sha256"]:
            errors.append("Changed delivered code: " + code["file"])
    if len(code_manifest) != sum(s.get("delivery_valid") is True for s in reported.values()):
        errors.append("Delivered source count mismatch")
    if software.get("exit_code") != 0 or not software.get("source_unchanged"):
        errors.append("Full software validation failed or sources changed")
    if not completion["complete"] or completion["analysis"]["audit_errors"]:
        errors.append("Common measurement incomplete or audit errors")
    transfer_audit = read(results / "transfer-audit.json")
    if not transfer_audit["valid"]:
        errors.append("Independent preserved-evidence transfer audit failed")
    report = {
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "source_manifests": checked, "software_validation": software,
        "assigned_arms": len(expected), "reported_arms": len(reported),
        "native_calls": native_calls, "arm_audits": audits,
        "unmodified_delivered_codes": len(code_manifest),
        "common_measurement_complete": completion["complete"],
        "analysis_sha256": digest(results / "analysis.json"),
        "comparison_sha256": digest(results / "exploration-comparison.csv"),
        "transfer_audit_sha256": digest(results / "transfer-audit.json"),
        "valid": not errors, "errors": errors,
        "scope": "Read-only evidence validation, no additional model or benchmark calls. "
                 "Equal configured budgets do not mean identical elapsed time or token counts.",
    }
    (results / "final-verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(json.dumps(report))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
