"""Live evidence/decision loop with independent research trees and explicit capacity."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import SimpleQueue

from hpc_forest.search.binary import SearchExhausted

from . import active_control as controls
from . import active_lifecycle as lifecycle
from .active_contract import enabled, settings
from .active_snapshot import watermark
from .active_state import children, state
from .adaptive_budget import admit, record_timing
from .backends import Generated
from .core import BudgetExhausted, ForestError, InfrastructureError, Mission
from .forest_scheduler import _generate
from .operator_control import stop_requested


def due(db, epoch, role, cfg):
    if lifecycle.analysis_needed(db, epoch, role):
        return "progress_or_closure_review"
    previous = state(db, epoch)["analysts"].get(role, {}).get("watermark", [])
    done = watermark(db, epoch, role)
    fresh = set(done) - set(previous)
    if len(fresh) >= cfg["analysis_every"]:
        return "completed_trials"
    if not fresh:
        return None
    results = [(row["id"], json.loads(row["result"] or "{}")) for row in db.rows(
        "SELECT id,result FROM trials WHERE epoch=? AND role=? AND state<>'pending'", (epoch, role))]
    old = [v["mean_seconds"] for identity, v in results if identity not in fresh
           and v.get("correct") is True and v.get("mean_seconds")]
    base = db.one("SELECT payload FROM evaluations WHERE experiment_id=? AND phase='search'", (f"baseline-e{epoch}",))
    if base:
        old.append(json.loads(base["payload"])["mean_seconds"])
    if old and any(v.get("correct") is True and v.get("mean_seconds")
                   and v["mean_seconds"] < min(old) * (1 - cfg["surprise_gain"])
                   for identity, v in results if identity in fresh):
        return "measured_gain_surprise"
    # A newly observed failure category is informative after the first report.
    statuses = {v.get("status") for identity, v in results if identity not in fresh}
    if previous and any(v.get("correct") is not True and v.get("status") not in statuses
                        for identity, v in results if identity in fresh):
        return "new_failure_category"
    return None


def analyst_order(db, epoch):
    """Serve never-observed/least-recently observed trees before a new report."""
    current = state(db, epoch)
    positions = {identity: index for index, identity in enumerate(current["jobs"])}
    return sorted(children(db, epoch), key=lambda child: positions.get(
        current["analysts"].get(child["role"], {}).get("last_job"), -1))


def mother_due(db, epoch, cfg):
    """Batch ordinary reports; never delay a drained closure or idle recovery."""
    current = state(db, epoch)
    if current["mother_watermark"] == controls.report_watermark(current):
        return False
    if current.get("lifecycle", {}).get("closing"):
        return True
    seen = current.get("mother_reports", {})
    fresh = [role for role, item in current["analysts"].items()
             if item.get("report_id") and item["report_id"] != seen.get(role)]
    if not fresh:
        return False
    unavailable = db.get(f"active_unavailable:{epoch}", {})
    available = [c for c in children(db, epoch) if c.get("kind") != "intermediate_integration"
                 and c["role"] not in current["suspended"] and c["role"] not in unavailable]
    batch_size = min(cfg.get("mother_every_reports", 2), max(1, len(available)))
    new_trials = set(watermark(db, epoch)) - set(current.get("mother_evidence_ids", []))
    return len(fresh) >= batch_size or len(new_trials) >= cfg["analysis_every"]


def run_research(controller, epoch, baseline, max_rounds=None):
    db, epoch_id = controller.db, epoch["id"]
    cfg = settings(controller.config)
    initial_children = db.get(f"forest_plan:{epoch_id}")["children"]
    width = len(initial_children)
    completed, pending, exhausted = SimpleQueue(), {}, set()
    pending_key = f"research_pending:{epoch_id}"
    counts, limits, waiting = {}, {}, controls.recover(controller, epoch_id)
    fatal = None
    runtime = {"policy": "active-independent-v1", "mode": cfg["mode"], "research_workers": width,
               "control_workers": cfg["control_workers"], "parallelism": width + cfg["control_workers"],
               "one_pending_trial_per_tree": True, "status": "running"}

    def refresh():
        for index, child in enumerate(children(db, epoch_id)):
            role = child["role"]
            if role in counts:
                continue
            controller.search.initialize(epoch_id, role, controller.config["seed"] + epoch_id * 101 + index)
            counts[role] = len(watermark(db, epoch_id, role))
            if child.get("kind") == "intermediate_integration":
                limits[role] = 1  # One requested combination is one independently evaluated program.
            elif max_rounds is not None:
                limits[role] = counts[role] + max_rounds

    def publish():
        db.set(f"active_unavailable:{epoch_id}", {role: "exhausted" if role in exhausted else "checkpoint_limit"
            for role in counts if role in exhausted or role in limits and counts[role] >= limits[role]})
        entries = []
        for future, item in pending.items():
            entry = {"role": item["role"], "started_at": item["started"], "phase": "generation",
                     "kind": item["kind"]}
            if item["kind"] == "research":
                entry["mission_id"] = item["mission"].id
                if future.done():
                    entry.update(phase="evaluation", generation_finished_at=future.result()[2])
            else:
                entry["job_id"] = item["job"]["id"]
            entries.append(entry)
        db.set(pending_key, entries)

    def submit_node(pool, mission, context, slot):
        future = pool.submit(_generate, controller, mission, context)
        pending[future] = {"kind": "research", "role": mission.role, "mission": mission,
                           "slot": slot, "started": time.time()}
        counts[mission.role] += 1
        future.add_done_callback(completed.put)
        db.event("research_node_submitted", {"experiment_id": mission.id, "role": mission.role,
            "ordinal": mission.ordinal, "control_decision_id": mission.control_decision_id})
        publish()

    def dispatch_controls(pool):
        nonlocal waiting
        current = state(db, epoch_id)
        checkpoint = max_rounds is not None and all(
            r in exhausted or r in limits and counts[r] >= limits[r]
            for r in counts if not r.startswith("Gm"))
        if current["closed"] or db.get(f"active_mother_broken:{epoch_id}") or fatal or checkpoint or stop_requested(controller):
            for job in waiting:
                controls.stop_unadmitted(controller, job)
            waiting = []
            return
        active = [item["job"] for item in pending.values() if item["kind"] == "control"]
        capacity = cfg["control_workers"] - len(active)
        busy = [*active, *waiting]
        if (enabled(controller.config, "steering") and not any(j["kind"] == "mother" for j in busy)
                and (any(a.get("report_id") for a in current["analysts"].values())
                     or current.get("lifecycle", {}).get("closing"))
                and lifecycle.ready_for_mother(db, epoch_id)
                and mother_due(db, epoch_id, cfg)):
            try:
                admit(db, ["@mother"])
                waiting.insert(0, controls.create(controller, epoch_id, "mother"))
            except BudgetExhausted:
                pass
        for child in analyst_order(db, epoch_id):
            role = child["role"]
            if child.get("kind") == "intermediate_integration" or any(j["role"] == role for j in [*busy, *waiting]):
                continue
            reason = due(db, epoch_id, role, cfg)
            if not reason or len(waiting) >= capacity:
                continue
            try:
                admit(db, ["@analyst:" + role])
                job = controls.create(controller, epoch_id, "analyst", role)
                job["trigger"] = reason
                controls.save(controller, job)
                waiting.append(job)
            except BudgetExhausted:
                continue
        while waiting and capacity > 0:
            job = waiting.pop(0)
            dispatch = controls.admit_call(controller, job)
            if dispatch is None:
                continue
            request, sha, directory = dispatch
            future = pool.submit(controls.exchange, Path(controller.config["codex"]["mailbox_dir"]), request, sha, directory)
            pending[future] = {"kind": "control", "role": job["budget_role"], "job": job,
                               "started": job["calls"][-1]["started_at"]}
            future.add_done_callback(completed.put)
            capacity -= 1
            publish()

    def refill(pool):
        nonlocal fatal
        refresh()
        current = state(db, epoch_id)
        if current["closed"] or fatal or db.get(f"active_mother_broken:{epoch_id}") or stop_requested(controller):
            return
        if lifecycle.guarded(db) and current.get("lifecycle", {}).get("closing"):
            return  # Finish admitted work before reviewing closure.
        running = {item["role"] for item in pending.values() if item["kind"] == "research"}
        # Newly created experiments receive a fair admission; established trees
        # retain independent AB-MCTS state rather than a shared node selector.
        for role in sorted(counts, key=lambda r: (counts[r], list(counts).index(r))):
            if len(running) >= width:
                break
            if (role in running or role in exhausted or role in current["suspended"]
                    or role in limits and counts[role] >= limits[role]):
                continue
            if lifecycle.waiting_for_analysis(db, epoch_id, role):
                # If no analyst fits, keep the final reserve; idle review records why.
                continue
            slot = None
            try:
                admit(db, [role])
                slot = db.reserve("search", "role:" + role)
                mission, context, slot = controller._new_mission(role, epoch, slot)
            except SearchExhausted:
                if slot:
                    db.settle_tokens(slot, 0)
                exhausted.add(role)
                publish()
                continue
            except BudgetExhausted:
                if slot:
                    db.settle_tokens(slot, 0)
                continue
            except (ForestError, OSError, ValueError) as exc:
                if slot:
                    row = db.one("SELECT mission FROM trials WHERE slot_id=? AND state='pending'", (slot,))
                    if row:
                        mission = Mission(**json.loads(row["mission"]))
                        controller._complete_generation(mission, slot, Generated(0,
                            {"llm_calls": 0, "generation_not_started": "setup_failure"},
                            error=str(exc), infrastructure_error=True), baseline)
                    else:
                        db.settle_tokens(slot, 0)
                fatal = "infrastructure_error"
                db.event("research_setup_failed", {"role": role, "reason": str(exc)})
                return
            if not context:
                counts[role] += 1
                exhausted.add(role)
                continue
            lifecycle.admitted(db, epoch_id, role, mission.id)
            submit_node(pool, mission, context, slot)
            running.add(role)

    refresh()
    publish()
    db.set(f"research_scheduler:{epoch_id}", runtime)
    lifecycle.initialize(db, epoch_id)
    for identity in watermark(db, epoch_id):
        lifecycle.observe(db, epoch_id, identity)
    try:
        with ThreadPoolExecutor(max_workers=width + cfg["control_workers"], thread_name_prefix="forest-active") as pool:
            if not any(counts.values()) and (max_rounds is None or max_rounds > 0) and not stop_requested(controller):
                if db.get(f"forest_wave:{epoch_id}:0") and not db.get(f"research_initial_dispatch:{epoch_id}"):
                    raise InfrastructureError("Interrupted initial wave cannot replay model calls")
                roles = [c["role"] for c in initial_children]
                slots = db.reserve_research_wave(roles, 0)
                batch = []
                try:
                    for role in roles:
                        mission, context, slot = controller._new_mission(role, epoch, slots[role])
                        if not context:
                            raise InfrastructureError("Initial tree has no context")
                        batch.append((mission, context, slot))
                except (ForestError, OSError, ValueError):
                    controller.search.recover_pending()
                    for slot in slots.values():
                        db.settle_tokens(slot, 0)
                    raise
                db.set(f"research_initial_dispatch:{epoch_id}", {"claimed_at": time.time(),
                    "mission_ids": [m.id for m, _, _ in batch]})
                for mission, context, slot in batch:
                    submit_node(pool, mission, context, slot)
            else:
                dispatch_controls(pool)
                refill(pool)
            while True:
                if not pending:
                    checkpoint = max_rounds is not None and all(
                        r in exhausted or r in limits and counts[r] >= limits[r]
                        for r in counts if not r.startswith("Gm"))
                    if not fatal and not checkpoint and not stop_requested(controller) and lifecycle.idle_review(db, epoch_id):
                        dispatch_controls(pool)
                        refill(pool)
                    if (not pending and not fatal and not checkpoint and not stop_requested(controller)
                            and lifecycle.resume_after_idle_review(db, epoch_id, [
                                r for r in counts if not r.startswith("Gm")
                                and r not in exhausted and not (r in limits and counts[r] >= limits[r])
                            ])):
                        refill(pool)
                    if not pending:
                        break
                future = completed.get()
                item = pending[future]
                if item["kind"] == "control":
                    response, finished = future.result()
                    controls.finish_call(controller, item["job"], response, finished)
                    if item["job"]["status"] == "ready":
                        waiting.append(item["job"])
                else:
                    generated, started, finished = future.result()
                    record_timing(db, "generation:" + item["role"], finished - started)
                    publish()
                    node_fatal = controller._complete_generation(item["mission"], item["slot"], generated, baseline)
                    fatal = fatal or node_fatal
                    db.event("research_node_settled", {"experiment_id": item["mission"].id,
                        "role": item["role"], "settled_at": time.time()})
                    lifecycle.observe(db, epoch_id, item["mission"].id)
                pending.pop(future)
                publish()
                controller._notify_progress()
                dispatch_controls(pool)
                refill(pool)
        if db.get(f"active_mother_broken:{epoch_id}"):
            db.set("status", "infrastructure_error")
            raise InfrastructureError("Mother steering lost its native receipt; cannot replace or replay her conversation")
        current = state(db, epoch_id)
        research = [c["role"] for c in children(db, epoch_id) if c.get("kind") != "intermediate_integration"]
        if fatal:
            status = fatal
        elif stop_requested(controller):
            status = "search_complete"
            runtime["stop_reason"] = "operator_stop"
        elif current["closed"]:
            status = "search_complete"
        elif max_rounds is not None and all(counts[r] >= limits[r] or r in exhausted for r in research):
            status = "checkpointed"
        else:
            status = "budget_exhausted"
            if lifecycle.guarded(db):
                from .independent_budget import forecast_independent

                if all(r in exhausted for r in research):
                    status = "search_complete"
                    runtime["stop_reason"] = "all_trees_exhausted"
                elif any(forecast_independent(db, [r])["can_admit"] for r in research if r not in exhausted):
                    runtime.update(status="infrastructure_error", stop_reason="unresolved_control_stall")
                    db.set(f"research_scheduler:{epoch_id}", runtime)
                    db.set("status", "infrastructure_error")
                    raise InfrastructureError("Active control stalled with admissible research; "
                                              "no reviewed closure may be inferred")
                else:
                    runtime["stop_reason"] = "final_reserve_or_deadline"
        if current["closed"]:
            runtime["stop_reason"] = "reviewed_closure" if lifecycle.guarded(db) else "mother_closure"
        runtime.update(status=status, settled_nodes_by_tree=counts)
        db.set(f"research_scheduler:{epoch_id}", runtime)
        db.set("status", status)
    finally:
        db.set(pending_key, [])
