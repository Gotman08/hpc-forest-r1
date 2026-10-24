"""Persisted wall-time forecasts. Estimates close admissions, never cancel work."""

from __future__ import annotations

import math
import re
import time
from statistics import median

from .core import BudgetExhausted, ForestError
from .forest import model_selected, pairwise_mother, persistent_mother, research_roles
from .support.budgets import adaptive, mandatory_final_g, search_deadline
from .support.validation import require_finite_number


def parse_duration(value: str) -> float:
    """Accept seconds or a sequence such as 30m, 2h, 1h30m, or 24h."""
    compact = re.sub(r"\s+", "", value.lower())
    parts = re.findall(r"(\d+(?:\.\d+)?)([smhd]?)", compact)
    if not parts or "".join(number + unit for number, unit in parts) != compact:
        raise ValueError("Duration must use seconds, minutes, hours or days (e.g. 30m, 2h, 24h)")
    if len(parts) > 1 and any(not unit for _, unit in parts):
        raise ValueError("Each part of a compound duration needs a unit")
    seconds = sum(float(number) * {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
                  for number, unit in parts)
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Duration must be positive and finite")
    return seconds


def record_timing(db, stage: str, seconds: float) -> None:
    if not adaptive(db.get("config")) or not math.isfinite(seconds) or seconds < 0:
        return
    history = db.get("timing_samples", {})
    history[stage] = (history.get(stage, []) + [seconds])[-12:]
    db.set("timing_samples", history)


def record_evaluation_timing(db, role, evaluator):
    """Keep exclusive work separate from GPU queue waits and model generation."""
    measured = getattr(evaluator, "last_wall_times", {})
    for stage in ("work", "build", "check", "benchmark", "lock_wait"):
        if stage + "_seconds" in measured:
            record_timing(db, f"evaluation_{stage}:{role}", measured[stage + "_seconds"])


def forecast(db, roles=(), *, now: float | None = None) -> dict:
    """Forecast each phase independently; never turn an estimate into a timeout.

    Persistent Mother uses recent typical wave/integration durations, with the
    configured margin. A research repair is not a sample of a Mother fusion.
    Historical fixed-tree profiles keep their maximum-based estimator.
    """
    if db.get(f"research_scheduler:{db.get('current_epoch')}", {}).get("policy") in {
        "independent-v1", "active-independent-v1",
    }:
        from .independent_budget import forecast_independent

        return forecast_independent(db, roles, now=now)
    config = db.get("config")
    history = db.get("timing_samples", {})
    settings = config.get("completion", {})
    persistent = persistent_mother(config)

    def estimate(values):
        return median(values[-5:]) if persistent else max(values)

    recipe = config["backend"] == "recipe"
    bootstrap = 0.01 if recipe else settings.get("initial_model_seconds", 120)
    attempts = config.get("harness", {}).get("max_attempts", 1) if config.get("harness", {}).get("enabled") else 1
    baseline = max(history.get("baseline", [1.0]))
    samples = [value for stage, values in history.items() if stage.startswith("mission:")
               and (not persistent or stage != "mission:G") for value in values]
    general = max(samples) if samples else bootstrap * attempts + baseline

    def mission(role):
        values = history.get("mission:" + role)
        if values:
            return estimate(values)
        # G is a sequential continuation of Mother, not another research wave.
        # Before its first observation, budget one nominal call and evaluation;
        # the margin covers uncertainty, not every possible repair at every step.
        if persistent and role == "G":
            return bootstrap + baseline
        return general

    mother = max(history.get("mother", [bootstrap])) if db.get("mother_enabled", False) else 0
    slots = config["budget"]["confirmation_slots"] + int(mandatory_final_g(config))
    protocol = config["protocol"]
    confirmation = max(history.get("confirmation", [
        baseline * max(1, protocol["confirmation_repetitions"] / protocol["repetitions"]) * slots
    ]))
    archive = max(history.get("archive", [5.0]))
    integration_steps = max(1, len(research_roles(db)) - 1) if pairwise_mother(config) else 1
    integration = (integration_steps * mission("G") if persistent else
        max(history.get("postprocess", [mother + mission("G")])))
    safety = settings.get("reserve_safety_factor", 1.25)
    reserve = safety * (integration + confirmation + archive) + 10
    next_work = safety * sum(mission(role) for role in roles)
    wave_stage = f"research_wave:{len(roles)}"
    wave_samples = history.get(wave_stage, []) if persistent and roles else []
    if model_selected(config) and roles:
        # All N model generations overlap; their external evaluations remain serialized.
        # A measured whole wave already includes all of those serial evaluations.
        next_work = safety * (estimate(wave_samples) if wave_samples else
            max(mission(role) for role in roles) + baseline * (len(roles) - 1))
    deadline = db.get("deadline")
    observed_at = time.time() if now is None else now
    remaining = deadline - observed_at if deadline is not None else None
    return {
        "observed_at": observed_at, "target_deadline": deadline,
        "remaining_seconds": remaining, "reserve_seconds": reserve,
        "mother_seconds": mother, "final_g_seconds": mission("G"),
        "integration_steps": integration_steps, "integration_seconds": integration,
        "integration_estimate_source": ("mission:G" if history.get("mission:G") else
            "initial_model_seconds") if persistent else "legacy_maximum",
        "research_estimate_source": wave_stage if wave_samples else "mission_durations",
        "estimation_policy": "recent_median_by_phase" if persistent else "recent_maximum",
        "confirmation_seconds": confirmation, "archive_seconds": archive,
        "safety_factor": safety, "next_work_seconds": next_work,
        "pending_roles": list(roles), "sample_counts": {k: len(v) for k, v in history.items()},
        "search_admission_deadline": deadline - reserve if deadline is not None else None,
        "can_admit": remaining is None or remaining >= reserve + next_work,
    }


def admission_deadline(db) -> float | None:
    deadline = db.get("deadline")
    if deadline is None:
        return None
    config = db.get("config")
    if adaptive(config):
        return forecast(db)["search_admission_deadline"]
    return search_deadline(deadline, config["budget"]["confirmation_seconds"])


def admit(db, roles) -> None:
    decision = forecast(db, roles)
    epoch = db.get("current_epoch")
    db.set(f"adaptive_budget:{epoch}", decision)
    db.event("adaptive_admission", decision)
    if not decision["can_admit"]:
        raise BudgetExhausted("Remaining time reserved for Mother, final G and independent confirmation")


def validate_adaptive(config: dict) -> None:
    settings = config.get("completion", {})
    if settings.get("reserve_policy", "fixed") not in {"fixed", "adaptive"}:
        raise ForestError("completion.reserve_policy must be fixed or adaptive")
    if type(settings.get("confirm_final_g", False)) is not bool:
        raise ForestError("completion.confirm_final_g must be a boolean")
    for key, minimum, default in (("initial_model_seconds", 0, 120),
                                  ("initial_selection_seconds", 0, 30),
                                  ("reserve_safety_factor", 1, 1.25)):
        value = require_finite_number(settings.get(key, default),
                                      f"completion.{key}")
        if value < minimum or value == 0:
            raise ForestError(f"completion.{key} must be positive and >= {minimum}")
    for key in ("initial_selection_calls", "initial_integration_rounds"):
        count = settings.get(key, 2)
        if type(count) is not int or count < 1:
            raise ForestError(f"completion.{key} must be a positive integer")
