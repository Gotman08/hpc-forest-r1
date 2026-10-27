"""Immutable, paginated evidence at a live analyst or Mother milestone."""
from __future__ import annotations

import json

from .active_contract import VERSION, settings
from .active_state import children, imports, state
from .core import digest
from .independent_budget import forecast_independent
from .observer_snapshot import _development, _record
from .performance_evidence import compared


def watermark(db, epoch, role=None):
    query = "SELECT id FROM trials WHERE epoch=? AND state<>'pending'"
    args = [epoch]
    if role:
        query += " AND role=?"
        args.append(role)
    return [r["id"] for r in db.rows(query + " ORDER BY created,id", args)]


def freeze(controller, epoch, role=None):
    db, root = controller.db, controller.root
    current = state(db, epoch)
    assignments = {c["role"]: c for c in children(db, epoch)}
    allowed = set(imports(db, epoch, role)) if role else None
    evaluations = {}
    for row in db.rows("SELECT * FROM evaluations WHERE epoch=? ORDER BY id", (epoch,)):
        evaluations.setdefault(row["experiment_id"], []).append({"phase": row["phase"],
                                                                "outcome": json.loads(row["payload"])})
    baseline_id = f"baseline-e{epoch}"
    baseline = next(v["outcome"] for v in evaluations[baseline_id] if v["phase"] == "search")
    records = [_record(root, baseline_id, "baseline", baseline, evaluations=evaluations[baseline_id])]
    warnings = []
    # Recent evidence appears first, but every older record remains addressable.
    for row in db.rows("SELECT * FROM trials WHERE epoch=? AND state<>'pending' ORDER BY created DESC,id", (epoch,)):
        own = role is None or row["role"] == role
        development, missing = _development(root, row)
        if own or row["id"] in allowed:
            records.append(_record(root, row["id"], "trial", json.loads(row["result"] or "{}"),
                mission=json.loads(row["mission"]), evaluations=evaluations.get(row["id"], [])))
        records.extend(r for r in development if own or r["id"] in allowed)
        if own:
            warnings.extend(missing)
    baseline_profile = records[0]["performance_by_configuration"]
    for record in records:
        record["performance_by_configuration"] = compared(record["performance_by_configuration"], baseline_profile)
    unavailable = db.get(f"active_unavailable:{epoch}", {})
    trees = {r: {**child, "suspended": r in current["suspended"],
                 "unavailable_reason": unavailable.get(r),
                 "completed_ids": watermark(db, epoch, r)} for r, child in assignments.items()}
    for tree_role, tree in trees.items():
        own = [record for record in records if record["kind"] == "trial"
               and (record.get("mission") or {}).get("role") == tree_role]
        valid = [record for record in own if record["outcome"].get("correct") is True
                 and record["outcome"].get("mean_seconds")]
        examples = own[:1] + ([min(valid, key=lambda r: r["outcome"]["mean_seconds"])] if valid else [])
        tree["measured_examples"] = list({record["id"]: {
            "id": record["id"], "measured_outcome": {k: record["outcome"].get(k)
                for k in ("status", "correct", "mean_seconds", "score", "commit")},
            "source_paths": list(record["source_files"]),
            "performance_by_configuration": record["performance_by_configuration"]} for record in examples}.values())
    reports = current["analysts"] if role is None else {role: current["analysts"].get(role, {})}
    dossier = {"version": VERSION, "epoch": epoch, "role": role,
               "plan_revision": current["revision"], "trees": trees if role is None else {role: trees[role]},
               "records": records, "warnings": warnings,
               "reports_as_interpretations": reports,
               "contract": {"protocol_id": db.get("protocol_id"), "protocol": controller.config["protocol"],
                   "hardware": db.get("identity"), "compiler": controller.config.get("compiler"),
                   "statement": controller.config["forest"].get("statement"),
                   "model": controller.config["codex"]["model"], "reasoning_effort": controller.config["codex"]["reasoning_effort"]},
               "budget": forecast_independent(db), "inflight": db.get(f"research_pending:{epoch}", [])}
    from .evolution_archive import view as diversity_view
    from .exploration_context import summarize

    for tree_role, tree in dossier["trees"].items():
        tree["exploration"] = summarize([r for r in records
            if (r.get("mission") or {}).get("role") == tree_role])

    archive = diversity_view(db, epoch, role=role, authorized_ids=allowed or ())
    if archive is not None:
        dossier["diverse_measured_sources"] = archive
    if role and settings(controller.config)["code_analysis"]:
        from .active_analysis import packet

        dossier["code_packet"] = packet(dossier)
    from .active_lifecycle import guarded, hypotheses, lifecycle

    if guarded(db):
        dossier.update(closure_guard=True, lifecycle=lifecycle(current),
                       closure_hypotheses=hypotheses(current) if role is None else [])
        if role is None:
            from .active_closure_evidence import packet as closure_packet

            dossier["closure_code_packet"] = closure_packet(dossier)
    dossier["snapshot_id"] = digest(dossier)
    return dossier
