"""Adviser-only runtime value; the evaluator's measured TreeQuest score is unchanged."""
import math

POLICY = "runtime_calibrated_v2"
TARGET = "child_minus_parent_log1p_speedup"
MIN_MARGIN = math.log1p(.01)


def from_log_ratio(log_runtime_ratio):
    # Stable log(1 + baseline / runtime), even for extreme ratios.
    value = -float(log_runtime_ratio)
    if not math.isfinite(value):
        raise ValueError("A runtime value requires a finite measured log ratio")
    return max(value, 0) + math.log1p(math.exp(-abs(value)))


def measured(baseline, seconds, correct):
    if correct is False:
        return 0.0
    if (correct is not True or any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0
                                  for x in (baseline, seconds))):
        raise ValueError("A runtime value requires correct, positive, measured times")
    return from_log_ratio(math.log(seconds) - math.log(baseline))
