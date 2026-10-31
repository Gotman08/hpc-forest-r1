"""Measured final integration after draining the admitted research nodes."""
from __future__ import annotations

import json
import time
from pathlib import Path

from hpc_forest.memory.contract import guided

from .adaptive_budget import record_timing
from .core import ForestError, InfrastructureError
from .forest import forest_plan, pairwise_mother, persistent_mother, research_roles
from .gitops import make_worktree
from .node_harness import wrap_backend
from .support.budgets import mission_token_reservation, unlimited_tokens


def _mission(controller, epoch: dict, baseline: dict, state: dict, *, sources=None, merge=None):
    db, search = controller.db, controller.search
    role = "G-final" if merge is None or merge["final"] else f"G-merge-{merge['round']}-{merge['pair']}"
    tree = search.initialize(epoch["id"], role, controller.config["seed"] + epoch["id"] * 101 + 99)
    tokens = mission_token_reservation(controller.config)
    purpose = (f"memory:code:{merge['step']}" if guided(controller.config) and merge
               else "role:G" if merge is None else f"merge:{merge['step']}")
    slot = db.reserve("postprocess", f"postprocess:e{epoch['id']}:{purpose}", tokens)
    state["slot_id"] = slot
    db.set(f"postprocess:{epoch['id']}", state)
    base = min(sources, key=lambda row: row["mean_seconds"])["commit"] if merge is not None else epoch["base_commit"]
    if merge and merge.get("base_id"):
        base = next(row["commit"] for row in sources if row["id"] == merge["base_id"])
    mission = search.ask(tree, ["G"], epoch["id"], base, merge["step"] if merge else 1, "", slot,
                         budget_phase="postprocess")
    mission.worktree = str(controller.root / "worktrees" / mission.id)
    if sources is None:
        sources, seen = [], set()
        for candidate in db.archive(epoch["id"]):
            if candidate["tree_hash"] not in seen:
                sources.append(candidate)
                seen.add(candidate["tree_hash"])
    if not sources:
        sources = [{"id": f"baseline-e{epoch['id']}", "role": "baseline",
                    "commit": epoch["base_commit"], "transformations": {},
                    "mean_seconds": baseline["mean_seconds"], "baseline": True}]
    mission.sources = [source["id"] for source in sources]
    mission.source_commits = [source["commit"] for source in sources]
    search.update_mission(mission)
    state["active_mission_id"] = mission.id
    if merge is None or merge["final"]:
        state["mission_id"] = mission.id
    if merge is not None:
        state["steps"].append({**merge, "mission_id": mission.id,
            "input_ids": [source["id"] for source in sources],
            "input_commits": [source["commit"] for source in sources], "status": "started"})
    db.set(f"postprocess:{epoch['id']}", state)
    make_worktree(controller.root / "repo", Path(mission.worktree),
                  f"final/{controller.config['problem']}/G/{mission.id}", mission.base_commit)
    context = controller._context(mission, sources)
    if merge is not None and not guided(controller.config):
        context["integration_pair"] = {**merge, "input_ids": [s["id"] for s in sources],
            "context_compaction": "codex-cli-automatic"}
    if merge is not None and guided(controller.config):
        from hpc_forest.memory.retrieval import MemoryReader, bounded_page, card

        with MemoryReader(controller.root, mission, controller.config, epoch["protocol_id"]) as reader:
            ideas = [card(reader.exact(identity)) for identity in merge["idea_ids"]]
            context["integration_ideas"] = bounded_page(ideas, offset=0, total=len(ideas),
                maximum=context["memory"]["max_result_characters"])
        context["integration_selection"] = merge["selection"]
        if merge.get("protected_refinement"):
            context["post_integration_refinement"] = {"base_id": merge["base_id"],
                "source_ids": mission.sources, "round": merge["round"]}
        context["memory"]["evidence_ids"] = list(dict.fromkeys([
            *context["memory"]["evidence_ids"], *mission.sources, *merge["idea_ids"]]))
    return mission, context, slot


def _integrate(controller, epoch, baseline, state, *, sources=None, merge=None):
    mission, context, slot = _mission(controller, epoch, baseline, state, sources=sources, merge=merge)
    started = time.time()
    try:
        generated = controller.backend.generate(mission, context, controller.config, controller.root)
    except Exception as exc:
        generated = exc
    record_timing(controller.db, "generation:G", time.time() - started)
    fatal = controller._complete_generation(mission, slot, generated, baseline)
    trial = controller.db.one("SELECT result FROM trials WHERE id=?", (mission.id,))
    outcome = json.loads(trial["result"])
    mother = controller.db.get(f"mother_plan:final_synthesis:{epoch['id']}")
    failed = bool(fatal) or outcome["status"] in {"infrastructure_error", "cancelled_budget", "generation_failed"}
    if getattr(controller, "mother_enabled", False):
        failed |= not mother or mother.get("status") != "complete"
    if persistent_mother(controller.config):
        original = (forest_plan(controller.db, epoch["id"]) or {}).get("conversation") or {}
        resumed = (mother or {}).get("conversation") or {}
        usage = {} if isinstance(generated, Exception) else generated.usage
        native_usage = (usage.get("attempt_usage") or [usage])[-1]
        failed |= (not original or resumed.get("id") != original.get("id")
                   or resumed.get("thread_id") != original.get("thread_id")
                   or resumed.get("phase") != "assembly" or resumed.get("turn", 0) < 1
                   or resumed != native_usage.get("conversation"))
    if merge is not None:
        state["steps"][-1].update(status="failed" if failed else "complete",
            outcome=outcome, mother=mother, retained_ids=mission.sources)
        from hpc_forest.memory.contract import enabled as memory_enabled

        if memory_enabled(controller.config):
            row = controller.db.one("SELECT payload FROM memory_facts WHERE id=?", (mission.id,))
            if row:
                state["steps"][-1]["source_change"] = json.loads(row["payload"])["facts"].get("source_change")
        controller.db.set(f"postprocess:{epoch['id']}", state)
    if failed:
        # Leave the exact last attempted final program available for confirmation.
        if merge is None or merge["final"]:
            state.update(outcome=outcome, mother=mother)
        raise InfrastructureError("Mother integration failed: " + (fatal or outcome["status"]))
    return mission, outcome, mother


def _pairwise(controller, epoch, baseline, state):
    """Balanced reduction of the best measured program from each research tree."""
    roles = research_roles(controller.db, epoch["id"])
    champions = {}
    for candidate in controller.db.archive(epoch["id"]):
        if candidate["role"] in roles:
            champions.setdefault(candidate["role"], candidate)
    frontier = [champions[role] for role in roles if role in champions]
    state.update(integration_policy="pairwise", context_compaction="codex-cli-automatic",
        leaf_program_ids=[source["id"] for source in frontier],
        missing_valid_roles=[role for role in roles if role not in champions], steps=[])
    if not frontier:
        frontier = [{"id": f"baseline-e{epoch['id']}", "role": "baseline",
            "commit": epoch["base_commit"], "transformations": {},
            "mean_seconds": baseline["mean_seconds"], "baseline": True}]
    round_number = 0
    while True:
        round_number += 1
        next_frontier = []
        for offset in range(0, len(frontier), 2):
            sources = frontier[offset:offset + 2]
            if len(sources) == 1 and len(frontier) > 1:
                next_frontier.append(sources[0])  # Odd input advances unchanged, without a model call.
                continue
            merge = {"round": round_number, "pair": offset // 2 + 1,
                     "step": len(state["steps"]) + 1, "final": len(frontier) <= 2}
            mission, outcome, mother = _integrate(controller, epoch, baseline, state, sources=sources, merge=merge)
            if merge["final"]:
                state.update(outcome=outcome, mother=mother)
                state["steps"][-1]["selected_id"] = mission.id
                return
            candidate = next((row for row in controller.db.archive(epoch["id"]) if row["id"] == mission.id), None)
            selected = min([*sources, *([candidate] if candidate else [])], key=lambda row: row["mean_seconds"])
            state["steps"][-1]["selected_id"] = selected["id"]
            next_frontier.append(selected)
            controller.db.set(f"postprocess:{epoch['id']}", state)
            controller.db.event("mother_pairwise_integration", state["steps"][-1])
        frontier = next_frontier


def finalize(controller, epoch: dict, baseline: dict) -> dict:
    """Called under the campaign lock; a claimed finalization is never replayed."""
    db = controller.db
    key = f"postprocess:{epoch['id']}"
    previous = db.get(key)
    if previous is not None:
        if previous["status"] == "started":
            controller.search.recover_pending()
            if previous.get("slot_id"):
                db.settle_tokens(previous["slot_id"], None)
            previous.update(status="interrupted", completed_at=time.time(),
                            error="Finalization was interrupted; model calls are not replayed")
            if previous.get("steps") and previous["steps"][-1]["status"] == "started":
                previous["steps"][-1]["status"] = "interrupted"
            db.set(key, previous)
            db.set("status", previous["search_stop_reason"])
        return previous
    search_status = db.get("status")
    if search_status in {"checkpointed", "running", "ready", "postprocessing"}:
        search_status = "search_closed"
    db.set(f"search_closed:{epoch['id']}", time.time())
    state = {"status": "started", "started_at": time.time(),
             "search_stop_reason": search_status, "budget_phase": "postprocess",
             "mother_required": bool(getattr(controller, "mother_enabled", False)),
             "unlimited_wall_time": True, "unlimited_tokens": unlimited_tokens(controller.config)}
    db.set(key, state)
    db.set("status", "postprocessing")
    controller.evaluator.deadline = None
    controller.backend = wrap_backend(controller.backend, controller.config)
    try:
        if guided(controller.config):
            from .integration_policy import integrate_memory

            integrate_memory(controller, epoch, baseline, state)
        elif pairwise_mother(controller.config):
            _pairwise(controller, epoch, baseline, state)
        else:
            _, outcome, mother = _integrate(controller, epoch, baseline, state)
            state.update(outcome=outcome, mother=mother)
        state["status"] = "complete"
    except (ForestError, OSError, ValueError) as exc:
        controller.search.recover_pending()
        if state.get("slot_id"):
            db.settle_tokens(state["slot_id"], None)
        state.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        if state.get("steps") and state["steps"][-1]["status"] == "started":
            state["steps"][-1].update(status="failed", error=state["error"])
    state.update(completed_at=time.time())
    state["elapsed_seconds"] = state["completed_at"] - state["started_at"]
    record_timing(db, "postprocess", state["elapsed_seconds"])
    db.set(key, state)
    db.event("postprocess_finished", state)
    db.set("status", search_status if search_status != "postprocessing" else "budget_exhausted")
    return state
