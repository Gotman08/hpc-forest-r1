"""One definition of search and generation deadlines, including queued calls."""

from __future__ import annotations

import time


def search_deadline(deadline: float, confirmation_seconds: float) -> float:
    """Keep the confirmation reserve inside the original campaign wall budget."""
    return deadline - confirmation_seconds


def generation_deadline(
    context: dict, seconds: float | None = None, *, now: float | None = None
) -> float:
    """A queued request never extends either the campaign or its search window."""
    limits = [context["deadline"], context.get("generation_deadline", context["deadline"])]
    if seconds is not None:
        limits.append((time.time() if now is None else now) + seconds)
    return min(limits)
