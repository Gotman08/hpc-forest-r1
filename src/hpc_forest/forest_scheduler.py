"""Independent ask/generate/measure/tell loops for Mother's research trees.

Only generation runs on worker threads. The controller owns every registry and
TreeQuest update, and admits at most one unfinished trial per research tree.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from queue import SimpleQueue

from hpc_forest.search.binary import SearchExhausted

from .adaptive_budget import admit, record_timing
from .backends import Generated
from .core import BudgetExhausted, ForestError, Mission
from .forest import research_roles
from .operator_control import stop_requested


def _generate(controller, mission, context):
    started = time.time()
    try:
        generated = controller.backend.generate(mission, context, controller.config, controller.root)
    except Exception as exc:
        generated = exc
    return generated, started, time.time()


def run_research(controller, epoch, baseline, max_rounds=None):
    """Start all N trees together, then refill each as soon as its score is known.

    max_rounds is the existing explicit checkpoint boundary, never a campaign
    quota. A normal run has no per-tree node, depth, cycle or token limit.
    """
    db, epoch_id = controller.db, epoch["id"]
    roles = research_roles(db, epoch_id)
    cursor_key = f"plan_cursor:{epoch_id}"
    runtime_key = f"research_scheduler:{epoch_id}"
    pending_key = f"research_pending:{epoch_id}"
    counts = {role: db.one("SELECT count(*) AS n FROM trials WHERE epoch=? AND role=?",
                         (epoch_id, role))["n"] for role in roles}
    limits = {role: counts[role] + max_rounds for role in roles} if max_rounds is not None else {}
    initial = not any(counts.values())
    first_receipt = db.get(f"forest_wave:{epoch_id}:0")
    if first_receipt and not db.get(f"research_initial_dispatch:{epoch_id}"):
        raise ForestError("An interrupted initial research wave cannot replay its model invocations")
    completed = SimpleQueue()
    pending, exhausted = {}, set()
    fatal = None
    runtime = {"policy": "independent-v1", "parallelism": len(roles),
               "one_pending_trial_per_tree": True, "status": "running"}
    db.set(runtime_key, runtime)

    def publish_pending():
        # Completion timestamps are supplied by workers, without accessing SQLite.
        entries = []
        for future, (mission, _, started) in pending.items():
            entry = {"role": mission.role, "mission_id": mission.id, "started_at": started,
                     "phase": "generation"}
            if future.done():
                _, _, finished = future.result()
                entry.update(phase="evaluation", generation_finished_at=finished)
            entries.append(entry)
        db.set(pending_key, entries)

    def eligible(role):
        return (role not in exhausted and not any(m.role == role for m, _, _ in pending.values())
                and (not limits or counts[role] < limits[role]))

    def submit(pool, mission, context, slot):
        started = time.time()
        future = pool.submit(_generate, controller, mission, context)
        pending[future] = (mission, slot, started)
        counts[mission.role] += 1
        future.add_done_callback(completed.put)
        db.event("research_node_submitted", {"experiment_id": mission.id, "role": mission.role,
                 "ordinal": mission.ordinal, "submitted_at": started})
        publish_pending()

    def refill(pool, preferred=None):
        nonlocal fatal
        if stop_requested(controller):
            return
        ordered = ([preferred] if preferred else []) + [r for r in roles if r != preferred]
        for role in ordered:
            if not eligible(role):
                continue
            publish_pending()
            slot = None
            try:
                admit(db, [role])
                slot = db.reserve("search", "role:" + role)
                mission, context, slot = controller._new_mission(role, epoch, slot)
            except SearchExhausted as exc:
                if slot:
                    db.settle_tokens(slot, 0)
                exhausted.add(role)
                db.event("tree_exhausted", {"role": role, "reason": str(exc)})
                continue
            except BudgetExhausted:
                if slot:
                    db.settle_tokens(slot, 0)
                continue  # A shorter idle tree can still fit; retry after another result.
            except (ForestError, OSError, ValueError) as exc:
                if slot:
                    row = db.one("SELECT mission FROM trials WHERE slot_id=? AND state='pending'", (slot,))
                    if row:
                        abandoned = Mission(**json.loads(row["mission"]))
                        controller._complete_generation(abandoned, slot,
                            Generated(0, {"llm_calls": 0, "generation_not_started": "setup_failure"},
                                      error=str(exc), infrastructure_error=True), baseline)
                        counts[role] += 1
                    else:
                        db.settle_tokens(slot, 0)
                fatal = "infrastructure_error"
                db.event("research_setup_failed", {"role": role, "reason": str(exc)})
                return  # Drain the other admitted models rather than cancelling their trials.
            if not context:
                counts[role] += 1
                exhausted.add(role)
                continue
            submit(pool, mission, context, slot)

    try:
        with ThreadPoolExecutor(max_workers=len(roles), thread_name_prefix="forest-tree") as pool:
            if initial and (max_rounds is None or max_rounds > 0) and not stop_requested(controller):
                slots = db.reserve_research_wave(roles, 0)
                batch = []
                try:
                    # Prepare the complete initial forest before invoking any generation.
                    for role in roles:
                        mission, context, slot = controller._new_mission(role, epoch, slots[role])
                        if not context:
                            raise ForestError("Initial research tree has no generation context")
                        batch.append((mission, context, slot))
                except (ForestError, OSError, ValueError):
                    controller.search.recover_pending()
                    for slot in slots.values():
                        db.settle_tokens(slot, 0)
                    raise
                first_started, first_remaining = time.monotonic(), set(roles)
                db.set(f"research_initial_dispatch:{epoch_id}", {
                    "claimed_at": time.time(), "mission_ids": [mission.id for mission, _, _ in batch]})
                for mission, context, slot in batch:
                    submit(pool, mission, context, slot)
            else:
                first_remaining = set()
                refill(pool)

            while pending:
                future = completed.get()
                mission, slot, _ = pending[future]
                generated, started, finished = future.result()
                record_timing(db, "generation:" + mission.role, finished - started)
                # All other completed generations are visible to the queue forecast.
                publish_pending()
                node_fatal = controller._complete_generation(mission, slot, generated, baseline)
                pending.pop(future)
                publish_pending()
                db.event("research_node_settled", {"experiment_id": mission.id, "role": mission.role,
                         "ordinal": mission.ordinal, "settled_at": time.time()})
                db.set(cursor_key, min(counts[r] - int(any(m.role == r for m, _, _ in pending.values()))
                                       for r in roles))
                if mission.role in first_remaining:
                    first_remaining.remove(mission.role)
                    if not first_remaining:
                        # Kept as an observation of the initial cohort, never as a barrier.
                        record_timing(db, f"research_wave:{len(roles)}", time.monotonic() - first_started)
                controller._notify_progress()
                fatal = fatal or node_fatal
                if not fatal:
                    refill(pool, mission.role)

        if fatal:
            status = fatal
        elif stop_requested(controller):
            status = "search_complete"
            runtime["stop_reason"] = "operator_stop"
        elif limits and all(counts[r] >= limits[r] or r in exhausted for r in roles):
            status = "checkpointed"
        elif len(exhausted) == len(roles):
            status = "search_complete"
        else:
            status = "budget_exhausted"
            db.event("budget_stop", {"reason": "No independent research node fits before finalization"})
        runtime.update(status=status, settled_nodes_by_tree=counts)
        db.set(runtime_key, runtime)
        db.set("status", status)
    finally:
        # ThreadPoolExecutor has drained every admitted generation before assembly.
        db.set(pending_key, [])
