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


def _planned(db, epoch, current):
    """Trees of the decision being applied, including those created by its earlier actions."""
    return [*db.get(f"forest_plan:{epoch}", {}).get("children", []), *current["children"]]


def _new_role(db, epoch, current, prefix):
    roles = [c["role"] for c in _planned(db, epoch, current)]
    return prefix + str(max([int(r[len(prefix):]) for r in roles if r.startswith(prefix)
                             and r[len(prefix):].isdigit()] or [0]) + 1)


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


def _action(db, epoch, current, action, decision_id, snapshot):
    from .active_lifecycle import guarded, lifecycle, request_close
    from .independent_budget import forecast_independent

    kind, role = action["kind"], action["tree"]
    config = db.get("config")
    if kind == "share" and not enabled(config, "sharing"):
        raise InfrastructureError("Evidence sharing is disabled in this ablation")
    if kind == "integrate" and not enabled(config, "full"):
        raise InfrastructureError("Intermediate integration is disabled in this ablation")
    if current["closed"]:
        raise InfrastructureError("Research admissions are permanently closed")
    if kind in {"resume", "continue"}:
        unavailable = db.get(f"active_unavailable:{epoch}", {}).get(role)
        if unavailable:
            raise InfrastructureError(f"Tree {role} cannot admit work ({unavailable}); "
                                      "continue/resume cannot bypass its limit")
    returns_to_work = kind in {"resume", "branch", "integrate", "refine"} or (
        kind == "continue" and role not in current["suspended"])
    if guarded(db) and returns_to_work:
        lifecycle(current)["closing"] = None
    if kind == "refine":
        return _refinement(db, epoch, current, action, decision_id)
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
        role = _new_role(db, epoch, current, "Gm" if kind == "integrate" else "T")
        estimate = forecast_independent(db, [role])
        if not estimate["can_admit"]:
            raise InfrastructureError("No budget for this new experiment before confirmation")
        review_cost = 0.0
        if guarded(db):
            controls = (["@analyst:" + role] if kind == "branch" else []) + ["@mother"]
            review_cost = forecast_independent(db, controls)["candidate_work_seconds"]
            unstarted = sum(c.get("experiment_budget_seconds", 0) for c in current["children"]
                            if not db.one("SELECT id FROM trials WHERE epoch=? AND role=? LIMIT 1", (epoch, c["role"])))
            required = max(estimate["next_work_seconds"], estimate["candidate_work_seconds"] + review_cost) + unstarted
            if (estimate["remaining_seconds"] is not None
                    and estimate["remaining_seconds"] < estimate["reserve_seconds"] + required):
                raise InfrastructureError("No budget for the new experiment and its analyst/Mother review before confirmation")
        base = min(selected, key=lambda item: item["mean_seconds"])
        child = {"role": role, "subject": action["subject"], "objective": action["objective"],
                 "stop_condition": action["stop_condition"], "base_commit": base["commit"],
                 "base_source_id": base["id"], "source_ids": action["source_ids"],
                 "kind": category,
                 "experiment_budget_seconds": estimate["candidate_work_seconds"] + review_cost,
                 "control_decision_id": decision_id}
        current["children"].append(child)
        current["imports"][role] = action["source_ids"][:]
        return {"created_tree": role, "base_source_id": base["id"]}
    if kind == "close":
        if guarded(db):
            return request_close(db, epoch, current, action, snapshot, decision_id)
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


def _refinement(db, epoch, current, action, decision_id):
    from .active_contract import settings
    from .independent_budget import forecast_independent

    if db.get("config").get("binary_tree", {}).get("enabled"):
        raise InfrastructureError("Seeded refinements require a TreeQuest policy")
    source = measured_source(db, epoch, action["source_ids"][0])
    if source["role"] != action["tree"]:
        raise InfrastructureError("A refinement source must belong to its target tree")
    parent = next(c for c in _planned(db, epoch, current) if c["role"] == action["tree"])
    for child in current["children"]:
        if child.get("kind") == "refinement" and child.get("base_source_id") == source["id"]:
            return {"existing_tree": child["role"], "base_source_id": source["id"]}
    estimate = forecast_independent(db, [action["tree"]])
    unstarted = sum(c.get("experiment_budget_seconds", 0) for c in current["children"]
                    if not db.one("SELECT id FROM trials WHERE epoch=? AND role=? LIMIT 1", (epoch, c["role"])))
    if (not estimate["can_admit"] or estimate["remaining_seconds"] is not None
            and estimate["remaining_seconds"] < estimate["reserve_seconds"] + estimate["next_work_seconds"] + unstarted):
        raise InfrastructureError("No budget for the measured continuation before final refinement and confirmation")
    role = _new_role(db, epoch, current, "T")
    child = {"role": role, "kind": "refinement", "subject": parent["subject"],
             "objective": parent["objective"] + "\nTargeted continuation: " + action["rationale"],
             "stop_condition": action["stop_condition"], "base_commit": source["commit"],
             "base_source_id": source["id"], "source_ids": [source["id"]],
             "cost_role": action["tree"], "refinement_trials": settings(db.get("config"))["progress_trials"],
             "experiment_budget_seconds": estimate["candidate_work_seconds"], "control_decision_id": decision_id}
    current["children"].append(child)
    current["imports"][role] = [source["id"]]
    return {"created_tree": role, "base_source_id": source["id"], "search_root": source["id"],
            "policy": "independent-measured-root-ab-mcts"}


def apply(db, epoch, job_id, snapshot, decision):
    """Apply a receipt once; state and its decision ledger commit in one transaction.

    No TreeQuest, evaluator, file or model side effect takes place here. Tree
    initialization and admissions consume this durable desired state afterwards.
    """
    from .active_lifecycle import guarded, invalidate, lifecycle

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
            if guarded(db) and action["kind"] == "close" and len(decision["decisions"]) != 1:
                raise InfrastructureError("Closure review must be a standalone decision")
            if guarded(db) and action["kind"] in {"continue", "refine"}:
                protection = lifecycle(current)["protections"].get(action["tree"], {})
                known = snapshot["trees"][action["tree"]]["completed_ids"]
                if protection.get("source_id") and protection["source_id"] not in known:
                    raise InfrastructureError("New measured evidence requires fresh continuation advice")
            invalidate(db, epoch, snapshot, action)
            detail = _action(db, epoch, proposed, action, identity, snapshot)
            current = proposed
            results.append({"id": identity, "action": action, "status": "applied", **detail})
        except InfrastructureError as exc:
            results.append({"id": identity, "action": action, "status": "rejected", "reason": str(exc)})
    if guarded(db) and any(r["status"] == "rejected" and "New measured evidence" in r["reason"] for r in results):
        lifecycle(current)["review_revision"] += 1
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
    from .active_lifecycle import ancestors

    current = state(db, mission.epoch)
    analyst = current["analysts"].get(mission.role, {})
    protections = current.get("lifecycle", {}).get("protections", {})
    parents = ancestors(db, mission.epoch, mission.id)
    protected = next((p for p in protections.values() if p["source_id"] in parents and p["remaining"]), None)
    return {"plan_revision": current["revision"], "analyst_report_id": analyst.get("report_id"),
            "analyst_interpretation": analyst.get("report"),
            "mother_interpretation": current["advice"].get(mission.role),
            "authorized_import_ids": current["imports"].get(mission.role, []),
            "protected_progress": protected,
            "warning": "Model interpretations, not correctness, rewards or measured performance"}
