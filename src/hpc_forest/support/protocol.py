"""Evaluation protocol versions: a campaign keeps the semantics it was created with.

Version 1 is the historical behaviour, implied when a frozen configuration has no
version. Version 2 classifies candidate faults explicitly, trips a breaker only
after repeated infrastructure failures, verifies every timed output, decides on
medians with a confidence bound, measures in calm and builds from the commit.
"""
from __future__ import annotations

CURRENT = 2
SUPPORTED = (1, 2)


def version(config: dict) -> int:
    return (config.get("protocol") or {}).get("version", 1)


def v2(config: dict) -> bool:
    return version(config) >= 2
