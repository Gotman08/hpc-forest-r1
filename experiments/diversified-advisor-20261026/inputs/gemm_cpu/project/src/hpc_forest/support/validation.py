"""Reject ambiguous or non-finite numbers at configuration and accounting boundaries."""

from __future__ import annotations

import math

from ..core import ForestError


def require_integer(value, name: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int:
        raise ForestError(f"{name} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        raise ForestError(f"{name} is outside its allowed range")
    return value


def require_finite_number(value, name: str) -> int | float:
    try:
        valid = type(value) in {int, float} and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ForestError(f"{name} must be a finite number")
    return value
