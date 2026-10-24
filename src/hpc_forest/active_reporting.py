"""Auditable live-control costs, coverage, decisions and their measured descendants."""
from __future__ import annotations

import csv
import json

from .active_contract import enabled, settings
from .active_state import state
from .core import atomic_json


def summary(db):
    if not enabled(db.get("config")):
        return {"mode": "off"}
    current = state(db, db.get("current_epoch"))
    jobs = [db.get("active_control:" + identity, {}) for identity in current["jobs"]]
    calls = [c for j in jobs for c in j.get("calls", [])]
    known = [c["usage"]["tokens"] for c in calls if c.get("usage", {}).get("token_accounting") == "exact"
             and type(c["usage"].get("tokens")) is int]
    return {"mode": settings(db.get("config"))["mode"], "revision": current["revision"],
            "created_trees": current["children"], "suspended": current["suspended"], "closed": current["closed"],
            "analysts": {r: {k: v for k, v in a.items() if k != "report"} for r, a in current["analysts"].items()},
            "control_calls": len(calls), "known_tokens": sum(known), "unknown_usage_calls": len(calls) - len(known),
            "model_wall_seconds_sum": sum(c.get("elapsed_seconds", 0) for c in calls),
            "warning": "Model wall times overlap research; do not add them to campaign wall time",
            "decision_batches": len(current["decisions"]),
            "applied_actions": sum(a["status"] == "applied" for d in current["decisions"].values() for a in d["actions"])}


def export(db, output):
    result = summary(db)
    if result["mode"] == "off":
        return result
    current = state(db, db.get("current_epoch"))
    jobs = [db.get("active_control:" + identity, {}) for identity in current["jobs"]]
    atomic_json(output / "active-architecture.json", {"summary": result, "state": current,
        "jobs": [{k: v for k, v in j.items() if k != "history"} for j in jobs]})
    calls = []
    for job in jobs:
        for call in job["calls"]:
            usage = call.get("usage", {})
            calls.append({"job_id": job["id"], "kind": job["kind"], "tree": job["role"],
                "snapshot_id": job["snapshot_id"], "call": call["number"], "status": call["status"],
                "elapsed_seconds": call.get("elapsed_seconds"), "tokens": usage.get("tokens"),
                "accounting": usage.get("token_accounting", "unknown"), "error": call.get("error"),
                "visible_records": len(job["visible_ids"]), "total_records": job["coverage"]["total_records"],
                "detailed_reads": len(job["coverage"]["reads"])})
    decisions = []
    for batch in current["decisions"].values():
        for action in batch["actions"]:
            descendants = []
            for row in db.rows("SELECT id,mission,result FROM trials WHERE epoch=?", (db.get("current_epoch"),)):
                mission = json.loads(row["mission"])
                if mission.get("control_decision_id") == action["id"] or action["id"] in mission.get("advice_ids", []):
                    descendants.append({"id": row["id"], "outcome": json.loads(row["result"] or "{}")})
            decisions.append({"decision_id": action["id"], "snapshot_id": batch["snapshot_id"],
                "revision": batch["resulting_revision"], "kind": action["action"]["kind"],
                "tree": action.get("created_tree", action["action"]["tree"]), "status": action["status"],
                "reason": action.get("reason", ""), "rationale": action["action"]["rationale"],
                "sources": json.dumps(action["action"]["source_ids"]), "descendants": json.dumps(descendants)})
    for name, rows, fields in [
        ("active-control.csv", calls, ["job_id", "kind", "tree", "snapshot_id", "call", "status", "elapsed_seconds",
          "tokens", "accounting", "error", "visible_records", "total_records", "detailed_reads"]),
        ("active-decisions.csv", decisions, ["decision_id", "snapshot_id", "revision", "kind", "tree", "status",
          "reason", "rationale", "sources", "descendants"]),
    ]:
        with (output / name).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    return result
