"""Admission deadlines and the separate lifetime of already admitted work."""

from __future__ import annotations

import time

FINISH_STARTED = "finish-started"
OBSERVE_TOKENS = "observe-only"
NATIVE_TOKEN_CEILING = 65536 + 131072


def finish_started(config: dict) -> bool:
    # A frozen campaign without this explicit policy keeps its original contract.
    return config.get("completion", {}).get("policy") == FINISH_STARTED


def adaptive(config: dict) -> bool:
    return config.get("completion", {}).get("reserve_policy") == "adaptive"


def mandatory_final_g(config: dict) -> bool:
    return config.get("completion", {}).get("confirm_final_g", False)


def time_driven(config: dict) -> bool:
    return config["schedule"]["cycles"] is None


def unlimited_tokens(config: dict) -> bool:
    """Only an explicit null quota disables application token admission limits."""
    return config.get("budget", {}).get("tokens", 0) is None


def postprocess_token_limit(config: dict) -> int | None:
    return None if unlimited_tokens(config) else config.get("completion", {}).get("postprocess_tokens")


def mission_token_reservation(config: dict) -> int:
    if config["backend"] == "recipe" or unlimited_tokens(config):
        return 0
    return config["budget"]["mission_tokens"]


def expired(deadline: float | None, *, now: float | None = None) -> bool:
    return deadline is not None and (time.time() if now is None else now) >= deadline


def time_left(deadline: float | None, limit: float | None = None, *, now: float | None = None) -> float | None:
    if deadline is None:
        return limit
    remaining = deadline - (time.time() if now is None else now)
    return remaining if limit is None else min(limit, remaining)


def search_deadline(deadline: float, confirmation_seconds: float) -> float:
    """The admission cutoff; legacy campaigns also use it to cancel work."""
    return deadline - confirmation_seconds


def generation_deadline(
    context: dict, seconds: float | None = None, *, now: float | None = None
) -> float | None:
    """Admitted finish-started work has no timer; legacy requests keep their caps."""
    if context.get("deadline_policy") == FINISH_STARTED:
        return None
    limits = [context["deadline"], context.get("generation_deadline", context["deadline"])]
    if seconds is not None:
        limits.append((time.time() if now is None else now) + seconds)
    return min(limits)
