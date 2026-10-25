"""Controller-owned closure review and bounded exploration of measured progress."""
from __future__ import annotations

import json
import math
import time
from statistics import stdev

from .active_contract import enabled, settings
from .active_state import children, key, state
from .core import InfrastructureError, digest
from .independent_budget import forecast_independent


def guarded(db):
    cfg = db.get("config")
    return enabled(cfg, "steering") and settings(cfg)["closure_guards"]


def lifecycle(current):
    return current.setdefault("lifecycle", {"closing": None, "review_revision": 0,
        "protections": {}, "protected_seconds_reserved": 0.0, "protection_limit_seconds": None,
        "observed_ids": [], "idle_review_key": None, "closure_history": []})


def completed(db, epoch, role=None):
    rows = db.rows("SELECT id,role,result,mission FROM trials WHERE epoch=? AND state<>'pending' "
                   "ORDER BY created,id", (epoch,))
    return [r for r in rows if (role is None or r["role"] == role) and r["role"] != "G"]


def ids(db, epoch, role=None):
    return [r["id"] for r in completed(db, epoch, role)]


def initialize(db, epoch):
    if not guarded(db):
        return
    current = state(db, epoch)
    life = lifecycle(current)
    if life["protection_limit_seconds"] is None:
        estimate = forecast_independent(db)
        available = estimate["remaining_seconds"]
        if available is None:
            available = db.get("config")["budget"].get("wall_seconds", 3600) or 3600
        life["protection_limit_seconds"] = max(0, available - estimate["reserve_seconds"]) * settings(
            db.get("config"))["progress_budget_fraction"]
        db.set(key(epoch), current)


def observe(db, epoch, identity):
    if not guarded(db):
        return
    current = state(db, epoch)
    life = lifecycle(current)
    if identity in life["observed_ids"]:
        return
    life["observed_ids"].append(identity)
    rows = completed(db, epoch)
    row = next((r for r in rows if r["id"] == identity), None)
    if row is None or json.loads(row["mission"]).get("kind") == "intermediate_integration":
        db.set(key(epoch), current)
        return
    result = json.loads(row["result"] or "{}")
    before = [json.loads(r["result"] or "{}") for r in rows[:rows.index(row)] if r["role"] == row["role"]]
    valid = [r for r in before if r.get("correct") is True and r.get("mean_seconds") and r.get("score") is not None]
    cfg = settings(db.get("config"))
    seconds = result.get("mean_seconds")
    measured = (result.get("correct") is True and result.get("score") is not None
                and type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0)
    best = min(valid, key=lambda r: r["mean_seconds"]) if valid else None

    def dispersion(outcome):
        samples = outcome.get("times") or []
        return stdev(samples) if len(samples) > 1 else 0.0

    # A conservative exploration trigger, not a significance or speedup claim.
    threshold = max(best["mean_seconds"] * cfg["progress_gain"],
                    2 * max(dispersion(best), dispersion(result))) if measured and best else 0.0
    gain = measured and (best is None or best["mean_seconds"] - seconds > threshold)
    changed = not any(r.get("commit") == result.get("commit") for r in valid)
    if gain and changed:
        life["protections"][row["role"]] = {"source_id": identity, "remaining": cfg["progress_trials"],
            "reason": "first_correct" if not valid else "measured_progress", "admissions": []}
        life["review_revision"] += 1
        if row["role"] in current["suspended"]:
            current["suspended"].remove(row["role"])
            db.event("active_late_progress_resumed", {"role": row["role"], "source_id": identity})
        db.event("active_progress_detected", {"role": row["role"], **life["protections"][row["role"]]})
    db.set(key(epoch), current)


def analysis_current(db, epoch, role, *, attempted=False):
    item = state(db, epoch)["analysts"].get(role, {})
    expected = ids(db, epoch, role)
    if not expected:
        return True
    if item.get("reviewed_ids") == expected and item.get("status") == "complete":
        return True
    return attempted and item.get("watermark") == expected and item.get("status") == "unavailable"


def analysis_needed(db, epoch, role):
    if not guarded(db) or analysis_current(db, epoch, role, attempted=True):
        return False
    life = lifecycle(state(db, epoch))
    return bool(life["closing"] or life["protections"].get(role, {}).get("remaining"))


def protection_admissible(db, epoch, role):
    if role in db.get(f"active_unavailable:{epoch}", {}):
        return False
    life = lifecycle(state(db, epoch))
    item = life["protections"].get(role, {})
    if item.get("remaining", 0) <= 0:
        return False
    forecast = forecast_independent(db, [role])
    cost = forecast.get("candidate_work_seconds", forecast["next_work_seconds"])
    return (forecast["can_admit"] and cost <= max(0, (life["protection_limit_seconds"] or 0)
            - life["protected_seconds_reserved"]))


def waiting_for_analysis(db, epoch, role):
    return (guarded(db) and protection_admissible(db, epoch, role)
            and not analysis_current(db, epoch, role, attempted=True))


def admitted(db, epoch, role, identity):
    if not guarded(db):
        return
    current = state(db, epoch)
    life = lifecycle(current)
    item = life["protections"].get(role, {})
    if item.get("remaining", 0) <= 0 or identity in item.get("admissions", []):
        return
    protected = protection_admissible(db, epoch, role)
    estimate = forecast_independent(db, [role]) if protected else {}
    cost = estimate.get("candidate_work_seconds", estimate.get("next_work_seconds", 0.0))
    # Ordinary follow-ups also satisfy the progress window. Otherwise an
    # exhausted protection envelope would leave it open forever and analyze
    # every subsequent trial instead of returning to the configured cadence.
    item["remaining"] -= 1
    item["admissions"].append(identity)
    life["protected_seconds_reserved"] += cost
    db.set(key(epoch), current)
    db.event("active_protected_admission" if protected else "active_unprotected_followup", {
        "role": role, "experiment_id": identity, "protected": protected,
        "source_id": item["source_id"], "estimated_seconds": cost, "remaining_trials": item["remaining"]})


def invalidate(db, epoch, snapshot, action):
    """Destructive decisions must refer to all currently settled relevant trials."""
    if not guarded(db) or action["kind"] not in {"suspend", "close"}:
        return
    roles = [action["tree"]] if action["kind"] == "suspend" else list(snapshot["trees"])
    known = {identity for role in roles for identity in snapshot["trees"][role]["completed_ids"]}
    actual = {identity for role in roles for identity in ids(db, epoch, role)}
    if actual - known:
        raise InfrastructureError("New measured evidence requires a fresh stop decision")
    if action["kind"] == "suspend" and protection_admissible(db, epoch, action["tree"]):
        raise InfrastructureError("Recent measured progress retains bounded exploration before suspension")


def hypotheses(current):
    result = []
    for role, analyst in current["analysts"].items():
        for index, hypothesis in enumerate(analyst.get("report", {}).get("hypotheses", [])):
            result.append({"tree": role, "report_id": analyst["report_id"], "index": index, **hypothesis})
    return result


def ready_for_mother(db, epoch):
    if not guarded(db):
        return True
    life = lifecycle(state(db, epoch))
    if not life["closing"]:
        return True
    if any(p["kind"] == "research" for p in db.get(f"research_pending:{epoch}", [])):
        return False
    return all(analysis_current(db, epoch, c["role"], attempted=True) for c in children(db, epoch)
               if c.get("kind") != "intermediate_integration")


def request_close(db, epoch, current, action, snapshot, decision_id):
    """Mutate only the passed transactional state; Registry writes belong to apply."""
    life = lifecycle(current)
    request = life["closing"]
    if request is None:
        life["closing"] = {"id": decision_id, "requested_at": time.time(), "evidence_ids": ids(db, epoch)}
        life["review_revision"] += 1
        return {"closure_pending": True, "reason": "drain_and_review"}
    frozen_request = snapshot.get("lifecycle", {}).get("closing")
    if not frozen_request or frozen_request["id"] != request["id"]:
        raise InfrastructureError("Closure requires a fresh decision after draining admitted work")
    if not ready_for_mother(db, epoch):
        raise InfrastructureError("Closure is waiting for admitted work and current analyst reports")
    frozen_reports = snapshot.get("reports_as_interpretations", {})
    if any(item.get("report_id") != frozen_reports.get(role, {}).get("report_id")
           for role, item in current["analysts"].items()):
        raise InfrastructureError("Closure requires the latest analyst reports")
    protected = [c["role"] for c in children(db, epoch) if protection_admissible(db, epoch, c["role"])]
    if protected:
        current["suspended"] = [r for r in current["suspended"] if r not in protected]
        life["closing"] = None
        life["review_revision"] += 1
        detail = {"closure_deferred": "protected_experiments", "resumed_roles": protected}
        life["closure_history"].append({"decision_id": decision_id, **detail})
        return detail
    reviews = action.get("hypothesis_review", [])
    expected = {(h["report_id"], h["index"]): h for h in hypotheses(current)}
    supplied = {(h["report_id"], h["index"]): h for h in reviews}
    if set(supplied) != set(expected) or len(supplied) != len(reviews):
        raise InfrastructureError("Closure must account for every latest analyst hypothesis")
    measured = {r["id"]: r for r in completed(db, epoch) if json.loads(r["result"] or "{}").get("score") is not None}
    for identity, review in supplied.items():
        if review["disposition"] == "tested" and not any(
                ref in measured and measured[ref]["role"] == expected[identity]["tree"]
                for ref in review["evidence_ids"]):
            raise InfrastructureError("A tested hypothesis requires a measured trial in its tree")
        if review["disposition"] == "budget" and forecast_independent(db, [expected[identity]["tree"]])["can_admit"]:
            raise InfrastructureError("The requested hypothesis still has admission budget")
    current["closed"] = True
    detail = {"closure_pending": False, "closure_confirmed": True,
              "hypotheses_reviewed": len(reviews), "unavailable_analyses": [c["role"] for c in children(db, epoch)
                if c.get("kind") != "intermediate_integration" and not analysis_current(db, epoch, c["role"])]}
    life["closure_history"].append({"decision_id": decision_id, **detail})
    return detail


def idle_review(db, epoch):
    """One bounded review per idle evidence state; no empty busy-wait loops."""
    if not guarded(db):
        return False
    current = state(db, epoch)
    life = lifecycle(current)
    marker = digest({"ids": ids(db, epoch), "suspended": current["suspended"]})
    if current["closed"] or life["idle_review_key"] == marker or not forecast_independent(db, ["@mother"])["can_admit"]:
        return False
    life["idle_review_key"] = marker
    life["closing"] = life["closing"] or {"id": "idle-" + marker, "requested_at": time.time(),
                                         "evidence_ids": ids(db, epoch), "implicit": True}
    life["review_revision"] += 1
    db.set(key(epoch), current)
    db.event("active_idle_review", {"evidence_ids": ids(db, epoch), "suspended": current["suspended"]})
    return True
