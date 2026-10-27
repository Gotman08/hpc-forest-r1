"""Experimental decision validation; the historical policy remains the default.

The error margin is an empirical guard, not a statistical confidence interval.
It never replaces a measured TreeQuest reward.
"""
from __future__ import annotations

import math

POLICY = "decision_calibrated_v1"
MIN_PAIRS = 3
MIN_PARENTS = 3


def validation_split(context, role):
    """Hold out recent same-objective transitions with unseen parent code."""
    available = [i for i, e in enumerate(context) if e.get("role") == role]
    held = available[-max(6, len(available) // 3):]
    if len(held) < 6:
        return [], held, {"reason": "insufficient_same_tree_validation", "policy": POLICY}
    cutoff = min(context[i]["captured_at"] for i in held)
    parent_groups = {context[i]["source_sha256"] for i in held}
    fit = [i for i, e in enumerate(context)
           if i not in held and e["observed_at"] < cutoff and e["source_sha256"] not in parent_groups]
    info = {"policy": POLICY, "cutoff": cutoff, "fit_ids": [context[i]["id"] for i in fit],
            "held_out_ids": [context[i]["id"] for i in held], "held_out_role": role,
            "fit_parent_count": len({context[i]["source_sha256"] for i in fit}),
            "held_out_parent_count": len(parent_groups), "parent_disjoint": True}
    if len(fit) < 5 or info["fit_parent_count"] < MIN_PARENTS or len(parent_groups) < MIN_PARENTS:
        info["reason"] = "insufficient_independent_parent_context"
    return fit, held, info


def decision_validation(held, predicted_gains, info):
    """Evaluate the child value used for decisions, against a zero-gain baseline."""
    predicted = [e["parent_score"] + float(g) for e, g in zip(held, predicted_gains, strict=True)]
    actual = [e["measured_score"] for e in held]
    if not all(math.isfinite(v) for v in predicted):
        raise ValueError("Non-finite validation predictions")
    pairs = [(i, j) for i in range(len(held)) for j in range(i)
             if held[i]["source_sha256"] != held[j]["source_sha256"]
             and abs(actual[i] - actual[j]) > .005]
    accuracy = sum(1.0 if (actual[i] - actual[j]) * (predicted[i] - predicted[j]) > 0
                   else .5 if predicted[i] == predicted[j] else 0 for i, j in pairs) / len(pairs) if pairs else None
    mae = sum(abs(a - p) for a, p in zip(actual, predicted, strict=True)) / len(held)
    baseline = sum(abs(e["measured_score"] - e["parent_score"]) for e in held) / len(held)
    result = {**info, "pair_count": len(pairs), "pairwise_accuracy": accuracy,
              "mae_child_score": mae, "parent_baseline_mae": baseline,
              "predicted_child_scores": predicted, "measured_child_scores": actual,
              "decision_margin": max(.005, 2 * mae), "margin_is_confidence_bound": False}
    if len(pairs) < MIN_PAIRS:
        result["reason"] = "insufficient_same_tree_parent_pairs"
    elif accuracy <= .5:
        result["reason"] = "child_value_ranking_not_better_than_chance"
    elif mae >= baseline:
        result["reason"] = "calibration_not_better_than_parent_baseline"
    return result


def calibrated_choice(candidates, gains, validation):
    scores = [e["parent_score"] + gain for e, gain in zip(candidates, gains, strict=True)]
    margin = validation.get("decision_margin")
    if (validation.get("policy") != POLICY or validation.get("reason")
            or type(margin) not in (float, int) or not math.isfinite(margin) or margin < .005):
        raise ValueError("Missing decision calibration evidence")
    # Do not turn impossible forecasts into an artificial tie at one.
    if any(not math.isfinite(s) or not 0 <= s <= 1 for s in scores):
        return 0, scores, "out_of_range_child_value"
    chosen = max(range(len(scores)), key=lambda i: scores[i])
    if scores[chosen] <= scores[0] + margin:
        return 0, scores, "insufficient_margin"
    return chosen, scores, "margin_passed"
