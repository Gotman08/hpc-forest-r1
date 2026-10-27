"""Portable, read-only dossiers of a confirmed campaign; no Registry migrations."""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from .core import ForestError, atomic_json, digest, file_digest
from .model_policy import require_identity
from .observer_contract import VERSION
from .support.sources import committed_source_snapshot


def _local_file(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ForestError("Observation artifact is missing or outside the campaign")
    return path


def _diagnostics(root, outcome):
    result = []
    for name in outcome.get("logs", []):
        try:
            path = _local_file(root, name)
            with path.open("rb") as stream:
                raw = stream.read(16001)
            result.append({"path": str(path.relative_to(root)), "sha256": file_digest(path),
                           "preview": raw[:16000].decode("utf8", errors="replace"),
                           "truncated": len(raw) > 16000})
        except (OSError, ForestError) as exc:
            result.append({"path": name, "unavailable": str(exc)})
    return result


def _record(root, key, kind, outcome, *, mission=None, evaluations=None, files=None):
    from .performance_evidence import profile

    record = {"id": key, "kind": kind, "outcome": outcome, "mission": mission,
              "evaluations": evaluations or [], "diagnostics": _diagnostics(root, outcome)}
    record["performance_by_configuration"] = profile(record["diagnostics"])
    if files is None and outcome.get("commit"):
        try:
            files = committed_source_snapshot(root / "repo", outcome["commit"])
        except (ForestError, OSError, ValueError) as exc:
            record["source_unavailable"] = str(exc)
    record["source_files"] = files or {}
    record["source_digest"] = digest(record["source_files"])
    return record


def _development(root, row):
    """Preserve repair attempts, including failures absent from final AB-MCTS rewards."""
    journal = root / "logs" / row["id"] / "node-harness.json"
    if not journal.is_file():
        return [], []
    records, warnings = [], []
    try:
        journal = _local_file(root, str(journal))
        if journal.stat().st_size > 4 * 1024 * 1024:
            raise ForestError("Development journal exceeds 4 MiB")
        attempts = json.loads(journal.read_text(encoding="utf8")).get("attempts", [])
        for attempt in attempts:
            if "development_outcome" not in attempt:
                continue
            source = _local_file(root, str(journal.parent / f"harness-source-{attempt['attempt']:02d}.json"))
            if source.stat().st_size > 4 * 1024 * 1024:
                raise ForestError("Development source snapshot exceeds 4 MiB")
            files = json.loads(source.read_text(encoding="utf8"))
            if not isinstance(files, dict) or any(not isinstance(v, str) for v in files.values()):
                raise ForestError("Invalid development source snapshot")
            record = _record(root, attempt["generation_id"], "development",
                             attempt["development_outcome"], files=files,
                             mission={"trial_id": row["id"], "attempt": attempt["attempt"]})
            record["source_provenance"] = {"path": str(source.relative_to(root)),
                                            "sha256": file_digest(source)}
            record["model_interpretation"] = attempt.get("proposal", {})
            records.append(record)
    except (OSError, ValueError, KeyError, ForestError) as exc:
        warnings.append(f"Development evidence incomplete for {row['id']}: {exc}")
    return records, warnings


def freeze(campaign: Path):
    """Use one SQLite read transaction; never initialize or modify the search registry."""
    root = campaign.resolve(strict=True)
    registry = _local_file(root, "registry.sqlite3")
    connection = sqlite3.connect(registry.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        meta = {row["key"]: json.loads(row["value"])
                for row in connection.execute("SELECT * FROM metadata")}
        config, epoch = meta["config"], meta["current_epoch"]
        require_identity(config.get("codex", {}))
        final = meta.get(f"final_g_confirmation:{epoch}", {})
        plan = meta.get(f"forest_plan:{epoch}", {})
        if (config.get("backend") != "codex" or config.get("forest", {}).get("policy") != "mother"
                or meta.get("status") != "confirmed" or not meta.get(f"confirmation_finished:{epoch}")
                or meta.get("best_confirmed", {}).get("epoch") != epoch
                or meta.get(f"postprocess:{epoch}", {}).get("status") != "complete"
                or final.get("status") not in {"confirmed", "rejected"}
                or plan.get("status") != "complete"):
            raise ForestError("Observation requires a completed Mother campaign and final confirmation")
        if connection.execute("SELECT 1 FROM trials WHERE state='pending'").fetchone():
            raise ForestError("Observation cannot start with pending research")
        assignments = {child["role"]: child for child in plan["children"]}
        # Assembly may create its own G-merge-* TreeQuest records. Only the N
        # Mother-assigned research trees receive analysts in this increment.
        trees = [dict(row) for row in connection.execute(
            "SELECT id,role,sha256 FROM trees WHERE epoch=? ORDER BY role", (epoch,))
            if row["role"] in assignments]
        if not trees or {tree["role"] for tree in trees} != set(assignments):
            raise ForestError("The completed forest does not match its planned research trees")
        baseline = f"baseline-e{epoch}"
        evaluations = {}
        for row in connection.execute("SELECT * FROM evaluations WHERE epoch=? ORDER BY id", (epoch,)):
            evaluations.setdefault(row["experiment_id"], []).append({
                "phase": row["phase"], "outcome": json.loads(row["payload"])})
        base = next(v["outcome"] for v in evaluations[baseline] if v["phase"] == "search")
        baseline_record = _record(root, baseline, "baseline", base, evaluations=evaluations[baseline])
        contract = {"epoch": epoch, "protocol_id": meta["protocol_id"],
                    "problem": config.get("problem"), "statement": config["forest"].get("statement"),
                    "protocol": config["protocol"], "hardware": meta.get("identity"),
                    "compiler": config.get("compiler"), "protected_manifest": meta.get("manifest"),
                    "model": config["codex"]["model"], "reasoning_effort": config["codex"]["reasoning_effort"],
                    "confirmation_finished": meta[f"confirmation_finished:{epoch}"]}
        dossiers = []
        for tree in trees:
            records, warnings = [baseline_record], []
            for row in connection.execute("SELECT * FROM trials WHERE tree_id=? ORDER BY created,id", (tree["id"],)):
                outcome = json.loads(row["result"] or "{}")
                records.append(_record(root, row["id"], "trial", outcome,
                    mission=json.loads(row["mission"]), evaluations=evaluations.get(row["id"], [])))
                development, missing = _development(root, row)
                records.extend(development)
                warnings.extend(missing)
            if len({r["id"] for r in records}) != len(records):
                raise ForestError("Duplicate evidence IDs in the observation snapshot")
            dossiers.append({"schema": VERSION, "tree": tree, "assignment": assignments[tree["role"]],
                             "contract": contract, "records": records, "warnings": warnings})
        receipt = {"epoch": epoch, "protocol_id": meta["protocol_id"],
                   "best_confirmed": meta["best_confirmed"], "final_g_confirmation": final,
                   "confirmation_finished": contract["confirmation_finished"],
                   "tree_checkpoints": {t["id"]: t["sha256"] for t in trees}}
        return receipt, dossiers
    except (sqlite3.Error, KeyError, StopIteration, ValueError) as exc:
        raise ForestError(f"Incomplete observation source: {exc}") from exc
    finally:
        connection.close()


def prepare(campaign: Path, destination: Path, *, max_calls=8):
    campaign, destination = campaign.resolve(strict=True), destination.resolve()
    if destination.is_relative_to(campaign) or campaign.is_relative_to(destination):
        raise ForestError("Write observation outside the preserved campaign")
    if destination.exists():
        raise ForestError("Observation destination already exists; use observe-run to resume it")
    if type(max_calls) is not int or not 1 <= max_calls <= 16:
        raise ForestError("Observation requires 1 to 16 calls per tree")
    receipt, dossiers = freeze(campaign)
    destination.mkdir(parents=True, exist_ok=False)
    trees = []
    for index, dossier in enumerate(dossiers, 1):
        name = f"tree-{index:03d}"
        atomic_json(destination / name / "snapshot.json", dossier)
        trees.append({"directory": name, "tree_id": dossier["tree"]["id"],
                      "role": dossier["tree"]["role"], "sha256": digest(dossier)})
    manifest = {"schema": VERSION, "mode": "observation-only", "session_id": uuid.uuid4().hex,
                "source_campaign": str(campaign), "source_receipt": receipt,
                "model": dossiers[0]["contract"]["model"], "reasoning_effort": dossiers[0]["contract"]["reasoning_effort"], "max_calls_per_tree": max_calls,
                "trees": trees, "search_feedback_enabled": False}
    atomic_json(destination / "manifest.json", manifest)
    return destination / "manifest.json"
