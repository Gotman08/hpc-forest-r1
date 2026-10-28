"""Admission estimates for independent trees sharing an exclusive evaluator."""
from __future__ import annotations

import time
from statistics import median

from hpc_forest.memory.contract import guided

from .forest import pairwise_mother, research_roles
from .support.budgets import mandatory_final_g


def forecast_independent(db, roles=(), *, now=None):
    config, epoch = db.get("config"), db.get("current_epoch")
    history = db.get("timing_samples", {})
    observed = time.time() if now is None else now
    settings, protocol = config.get("completion", {}), config["protocol"]
    bootstrap = settings.get("initial_model_seconds", 120)
    safety = settings.get("reserve_safety_factor", 1.25)

    def typical(stage, default):
        values = history.get(stage)
        return median(values[-5:]) if values else default

    baseline = typical("evaluation_work:baseline", typical("baseline", 1.0))
    measured_evaluations = [v for key, values in history.items()
                            if key.startswith("evaluation_work:T") for v in values[-5:]]
    generic_evaluation = median(measured_evaluations) if measured_evaluations else baseline

    def evaluation(role):
        if role.startswith("@"):
            return 0.0  # Analyst and steering calls never evaluate a program.
        return typical("evaluation_work:" + role, generic_evaluation)

    def generation(role):
        # Whole mission wall times used to contain the wait for every other tree.
        # New observations time the worker itself and the exclusive evaluator separately.
        return typical("generation:" + role, bootstrap)

    def confirmation_cost(role):
        work = baseline if role == "baseline" else evaluation(role)
        benchmark = typical("evaluation_benchmark:" + role, None)
        if benchmark is None:
            # No stage timings yet: retain a conservative conversion of whole work.
            return work * max(1, protocol["confirmation_repetitions"] / protocol["repetitions"])
        warmups = protocol["warmups"]
        ratio = (protocol["confirmation_repetitions"] + warmups) / (protocol["repetitions"] + warmups)
        # Compilation and correctness happen once, rather than once per timing repeat.
        return max(0, work - benchmark) + benchmark * ratio

    if history.get("generation:G"):
        final_g = generation("G") + evaluation("G")
        integration_source = "generation:G+evaluation_work:G"
    elif history.get("mission:G"):
        final_g = typical("mission:G", bootstrap + generic_evaluation)
        integration_source = "mission:G"
    else:
        final_g = bootstrap + generic_evaluation
        integration_source = "initial_model_seconds+exclusive_evaluation"
    integration_steps = max(1, len(research_roles(db)) - 1) if pairwise_mother(config) else 1
    integration = integration_steps * final_g
    selection_seconds = 0.0
    selection_estimate = {}
    if guided(config):
        from .integration_policy import limits

        bounds = limits(config, len(research_roles(db)))
        integration_steps = min(bounds["rounds"], settings.get("initial_integration_rounds", 2))
        # Limits permit retries and pagination; they are not expected work. A code
        # generation sample already includes that mission's reads and repairs.
        call_seconds = typical("memory_selection", settings.get("initial_selection_seconds", 30))
        counts = db.get("memory_selection_call_counts", [])
        calls = median(counts[-5:]) if counts else settings.get("initial_selection_calls", 2)
        calls = min(bounds["selection_calls_per_round"], max(1, calls))
        selection_seconds = integration_steps * calls * call_seconds
        integration = integration_steps * final_g + selection_seconds
        integration_source = "memory-guided-typical-selection+code+evaluation"
        selection_estimate = {"selection_call_seconds": call_seconds,
            "selection_calls_per_round": calls,
            "integration_step_limit": bounds["rounds"],
            "selection_call_limit": bounds["selection_calls_per_round"],
            "code_call_limit": bounds["code_calls_per_round"]}

    slots = config["budget"]["confirmation_slots"] + int(mandatory_final_g(config))
    finalists, seen = [], set()
    for candidate in db.archive(epoch):
        if candidate["commit"] not in seen and len(finalists) < slots - 1:
            finalists.append(candidate["role"])
            seen.add(candidate["commit"])
    finalists += ["G"] * (slots - 1 - len(finalists))
    confirmation = typical("confirmation", confirmation_cost("baseline")
                           + sum(confirmation_cost(role) for role in finalists))
    archive = typical("archive", 5.0)
    reserve = safety * (integration + confirmation + archive) + 10

    # Jobs can generate simultaneously but their evaluations occupy the target one
    # at a time. Schedule predicted releases instead of charging another whole wave.
    jobs = []
    active = db.get(f"research_pending:{epoch}", [])
    for node in active:
        role = node["role"]
        remaining_generation = 0.0
        if node["phase"] == "generation":
            nominal = generation(role)
            elapsed = max(0, observed - node["started_at"])
            remaining_generation = max(nominal * 0.1, nominal - elapsed)
        jobs.append((remaining_generation, evaluation(role)))
    jobs.extend((generation(role), evaluation(role)) for role in roles)
    tail = 0.0
    for release, service in sorted(jobs):
        tail = max(tail, release) + service
    next_work = safety * tail
    deadline = db.get("deadline")
    remaining = deadline - observed if deadline is not None else None
    return {
        "observed_at": observed, "target_deadline": deadline,
        "remaining_seconds": remaining, "reserve_seconds": reserve,
        "mother_seconds": typical("mother", bootstrap) if db.get("mother_enabled", False) else 0,
        "final_g_seconds": final_g, "integration_steps": integration_steps,
        "integration_seconds": integration, "integration_estimate_source": integration_source,
        **({"selection_seconds": selection_seconds, **selection_estimate} if guided(config) else {}),
        "research_estimate_source": "generation_and_exclusive_evaluation",
        "estimation_policy": "independent_phase_medians",
        "confirmation_seconds": confirmation, "archive_seconds": archive,
        "safety_factor": safety, "next_work_seconds": next_work,
        "candidate_work_seconds": safety * sum(generation(role) + evaluation(role) for role in roles),
        "pending_roles": list(roles), "inflight_roles": [node["role"] for node in active],
        "predicted_drain_seconds": tail,
        "sample_counts": {key: len(values) for key, values in history.items()},
        "search_admission_deadline": deadline - reserve if deadline is not None else None,
        "can_admit": remaining is None or remaining >= reserve + next_work,
    }


def assembly_admission(db, *, now=None):
    """Admit optional work while preserving one code turn and confirmation.

    This is an admission forecast, never a timeout: an admitted generation,
    repair, evaluation or mandatory first integration always finishes.
    """
    estimate = forecast_independent(db, now=now)
    safety = estimate["safety_factor"]
    remaining = estimate["remaining_seconds"]
    finish = safety * (estimate["final_g_seconds"] + estimate["confirmation_seconds"]
                       + estimate["archive_seconds"]) + 10
    call = estimate["selection_call_seconds"]
    read_required = finish + safety * 2 * call  # This read, then a selection decision.
    # A new round needs one decision. Additional reads are admitted separately;
    # reserving their nominal count here would reject a round that must_decide
    # can complete without those reads.
    round_required = finish + safety * call
    nominal_round = finish + safety * estimate["selection_calls_per_round"] * call
    return {"remaining_seconds": remaining, "finish_seconds": finish,
            "read_required_seconds": read_required, "round_required_seconds": round_required,
            "nominal_round_required_seconds": nominal_round,
            "can_read": remaining is None or remaining >= read_required,
            "can_start_round": remaining is None or remaining >= round_required}
