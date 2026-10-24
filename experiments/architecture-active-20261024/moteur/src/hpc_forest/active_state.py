"""Controller-owned forest decisions, separate from measured rewards and the initial plan."""
from __future__ import annotations

import copy
import json
import math
import time

from .active_contract import VERSION, enabled
from .core import InfrastructureError, canonical


def key(epoch):
    return f"active_forest:{epoch}"


def state(db, epoch):
    return db.get(key(epoch), {"version": VERSION, "revision": 0, "children": [],
        "suspended": [], "imports": {}, "advice": {}, "analysts": {}, "jobs": [],
        "decisions": {}, "mother_watermark": None, "closed": False})


def children(db, epoch):
    initial = db.get(f"forest_plan:{epoch}", {}).get("children", [])
    return [*initial, *state(db, epoch)["children"]]


def imports(db, epoch, role):
    return state(db, epoch)["imports"].get(role, [])


def measured_source(db, epoch, identity):
    """Only final, correct, measured programs can seed trees or an integration."""
    row = db.one("SELECT * FROM trials WHERE id=? AND epoch=? AND state<>'pending'", (identity, epoch))
    if row:
        outcome, mission = json.loads(row["result"] or "{}"), json.loads(row["mission"])
        result = {**outcome, "id": identity, "role": row["role"],
                  "transformations": mission.get("transformations", {}), "ordinal": mission["ordinal"]}
    else:
        row = db.one("SELECT v.payload FROM epochs e JOIN evaluations v ON v.experiment_id=e.baseline_id "
                     "WHERE e.id=? AND e.baseline_id=? AND v.phase='search'", (epoch, identity))
        result = {**json.loads(row["payload"]), "id": identity, "role": "baseline", "transformations": {}} if row else {}
    seconds = result.get("mean_seconds")
    if (result.get("correct") is not True or not result.get("commit")
            or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0
            or result.get("score") is None):
        raise InfrastructureError("A seed requires a correct measured final program: " + identity)
    return result


def _action(db, epoch, current, action, decision_id):
    from .independent_budget import forecast_independent

    kind, role = action["kind"], action["tree"]
    config = db.get("config")
    if kind == "share" and not enabled(config, "sharing"):
        raise InfrastructureError("Evidence sharing is disabled in this ablation")
    if kind == "integrate" and not enabled(config, "full"):
        raise InfrastructureError("Intermediate integration is disabled in this ablation")
    if current["closed"]:
        raise InfrastructureError("Research admissions are permanently closed")
    if kind in {"branch", "integrate"}:
        selected = [measured_source(db, epoch, identity) for identity in action["source_ids"]]
        if len({item["commit"] for item in selected}) != len(selected):
            raise InfrastructureError("An integration needs distinct source programs")
        initial = db.get(f"forest_plan:{epoch}")["children"]
        category = "intermediate_integration" if kind == "integrate" else "research"
        for existing in [*initial, *current["children"]]:
            if existing.get("kind", "research") == category and any(
                " ".join(existing[field].split()).casefold() == " ".join(action[field].split()).casefold()
                for field in ("subject", "objective")
            ):
                raise InfrastructureError("A distinct objective requires a distinct research branch")
        prefix = "Gm" if kind == "integrate" else "T"
        roles = [c["role"] for c in [*initial, *current["children"]]]
        index = max([int(r[len(prefix):]) for r in roles if r.startswith(prefix)
                     and r[len(prefix):].isdigit()] or [0]) + 1
        role = prefix + str(index)
        if not forecast_independent(db, [role])["can_admit"]:
            raise InfrastructureError("No budget for this new experiment before confirmation")
        base = min(selected, key=lambda item: item["mean_seconds"])
        child = {"role": role, "subject": action["subject"], "objective": action["objective"],
                 "stop_condition": action["stop_condition"], "base_commit": base["commit"],
                 "base_source_id": base["id"], "source_ids": action["source_ids"],
                 "kind": category,
                 "control_decision_id": decision_id}
        current["children"].append(child)
        current["imports"][role] = action["source_ids"][:]
        return {"created_tree": role, "base_source_id": base["id"]}
    if kind == "close":
        current["closed"] = True
    elif kind == "suspend":
        if role not in current["suspended"]:
            current["suspended"].append(role)
    elif kind == "resume":
        current["suspended"] = [r for r in current["suspended"] if r != role]
    elif kind == "share":
        previous = current["imports"].get(role, [])
        current["imports"][role] = list(dict.fromkeys([*previous, *action["source_ids"]]))
    elif kind == "continue":
        current["advice"][role] = {"decision_id": decision_id, "interpretation": action}
    return {}


def apply(db, epoch, job_id, snapshot, decision):
    """Apply a receipt once; state and its decision ledger commit in one transaction.

    No TreeQuest, evaluator, file or model side effect takes place here. Tree
    initialization and admissions consume this durable desired state afterwards.
    """
    current = state(db, epoch)
    if job_id in current["decisions"]:
        return current["decisions"][job_id]
    stale = snapshot["plan_revision"] != current["revision"]
    results = []
    for index, action in enumerate(decision["decisions"]):
        identity = f"{job_id}:{index}"
        proposed = copy.deepcopy(current)
        try:
            if stale:
                raise InfrastructureError("Stale plan revision; decision not applied")
            if db.get(f"search_closed:{epoch}") is not None:
                raise InfrastructureError("Search already closed")
            detail = _action(db, epoch, proposed, action, identity)
            current = proposed
            results.append({"id": identity, "action": action, "status": "applied", **detail})
        except InfrastructureError as exc:
            results.append({"id": identity, "action": action, "status": "rejected", "reason": str(exc)})
    if any(item["status"] == "applied" for item in results):
        current["revision"] += 1
    receipt = {"snapshot_id": snapshot["snapshot_id"], "plan_revision": snapshot["plan_revision"],
               "resulting_revision": current["revision"], "actions": results, "applied_at": time.time()}
    known = {identity for tree in snapshot["trees"].values() for identity in tree["completed_ids"]}
    receipt["newer_evidence_ids"] = [r["id"] for r in db.rows(
        "SELECT id FROM trials WHERE epoch=? AND state<>'pending' ORDER BY created,id", (epoch,)) if r["id"] not in known]
    current["decisions"][job_id] = receipt
    # Use SQL directly: nested Registry.set/event calls would commit too early.
    with db.connection:
        db.connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)", (key(epoch), canonical(current)))
        db.connection.execute("INSERT INTO events(kind,payload,created) VALUES(?,?,?)",
                              ("active_decision", canonical(receipt), receipt["applied_at"]))
    return receipt


def context(db, mission):
    current = state(db, mission.epoch)
    analyst = current["analysts"].get(mission.role, {})
    return {"plan_revision": current["revision"], "analyst_report_id": analyst.get("report_id"),
            "analyst_interpretation": analyst.get("report"),
            "mother_interpretation": current["advice"].get(mission.role),
            "authorized_import_ids": current["imports"].get(mission.role, []),
            "warning": "Model interpretations, not correctness, rewards or measured performance"}
