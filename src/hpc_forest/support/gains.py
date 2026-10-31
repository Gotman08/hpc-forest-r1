"""Median gains with a bootstrap confidence bound, for protocol 2 promotions."""
from __future__ import annotations

import random
from statistics import median


def gain(reference: list[float], candidate: list[float]) -> float:
    return 1 - median(candidate) / median(reference)


def gain_lower_bound(reference: list[float], candidate: list[float], *, seed: int,
                     resamples: int = 2000, confidence: float = 0.95) -> float:
    """One-sided lower confidence bound of the median gain, resampling both series.

    A seeded generator keeps the decision reproducible from the recorded samples.
    """
    if not reference or not candidate:
        raise ValueError("A gain interval needs samples from both programs")
    rng = random.Random(seed)
    gains = sorted(gain(rng.choices(reference, k=len(reference)), rng.choices(candidate, k=len(candidate)))
                   for _ in range(resamples))
    return gains[int((1 - confidence) * resamples)]
