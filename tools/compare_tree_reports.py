"""Compare two completed policy reports; never starts a campaign or calls a model."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from hpc_forest.binary_search import enabled
from hpc_forest.core import atomic_json, digest
from hpc_forest.support.budgets import finish_started, mandatory_final_g, postprocess_token_limit


def confirmation_verified(report: dict) -> bool:
    best = report.get("best_confirmed") or {}
    seconds, reference = best.get("mean_seconds"), best.get("reference_seconds")
    if any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0
           for x in (seconds, reference)):
        return False
    confirmations = [r for r in report.get("evaluations", []) if r.get("phase") == "confirmation"]
    winner = next((r["outcome"] for r in confirmations
                   if r["experiment_id"] == best.get("experiment_id")), {})
    baseline = next((r["outcome"] for r in confirmations
                     if r["experiment_id"] == f"baseline-e{best.get('epoch')}"), {})
    improvement = 0.0 if best.get("is_baseline") else 1 - seconds / reference
    return (winner.get("correct") is True and winner.get("commit") == best.get("commit")
            and digest(winner) == best.get("evaluation_digest")
            and winner.get("mean_seconds") == seconds and baseline.get("correct") is True
            and baseline.get("mean_seconds") == reference
            and math.isclose(best.get("improvement_fraction", -1), improvement, abs_tol=1e-12))


def _mother_clean(report: dict) -> bool:
    for event in report.get("events", []):
        if event.get("kind") != "mother_usage":
            continue
        payload = event.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except ValueError:
                return False
        if not isinstance(payload, dict) or payload.get("status") != "complete":
            return False
    mother = report.get("mother")
    if isinstance(mother, dict):
        for phase in ("preparation", "synthesis"):
            entry = mother.get(phase)
            if isinstance(entry, dict) and entry.get("status") != "complete":
                return False
    return True


def compare(reference: dict, binary: dict) -> dict:
    left, right = reference["config"], binary["config"]
    checks = {key: left.get(key) == right.get(key) for key in
              ("problem", "method", "backend", "seed", "roles", "budget", "schedule",
               "protocol", "compiler", "harness", "minimum_gain", "completion")}
    checks["forest"] = left.get("forest", {"policy": "fixed"}) == right.get("forest", {"policy": "fixed"})
    backend = left["backend"]
    if backend in ("codex", "ollama"):
        def model_settings(config):
            return {k: v for k, v in config.get(backend, {}).items()
                    if k not in {"channel", "mailbox_dir", "session_id"}}
        checks["model_settings"] = model_settings(left) == model_settings(right)
    def initial_trees(report):
        return [r["outcome"].get("tree_hash") for r in report.get("evaluations", [])
                if r.get("phase") == "search" and r["experiment_id"].startswith("baseline-e")]
    initial = initial_trees(reference)
    checks["initial_source"] = bool(initial) and all(initial) and initial == initial_trees(binary)
    checks["policies"] = not enabled(left) and enabled(right)
    checks["binary_topology"] = (binary.get("search_topology", {}).get("policy") == "binary-greedy"
                                 and binary["search_topology"].get("max_children", 3) <= 2)
    for name, report in (("reference", reference), ("binary", binary)):
        checks[name + "_confirmation"] = confirmation_verified(report)
        costs = report.get("costs", {})
        if finish_started(report["config"]):
            phase_costs = report.get("phase_costs", {})
            costs = phase_costs.get("search", {})
            post_costs = phase_costs.get("postprocess", {})
            post_limit = postprocess_token_limit(report["config"])
            post = report.get("postprocess") or {}
            final_trial = next((trial for trial in report.get("experiments", [])
                                if trial.get("id") == post.get("mission_id")), {})
            checks[name + "_postprocess"] = (
                post.get("status") == "complete"
                and final_trial.get("role") == "G" and final_trial.get("budget_phase") == "postprocess"
                and (not post.get("mother_required") or (post.get("mother") or {}).get("status") == "complete")
                and post_costs.get("unknown_usage_calls", 1) == 0
                and (post_limit is None or post_costs.get("tokens_used", math.inf) <= post_limit
                     * max(1, len(report.get("epochs", []))))
            )
            checks[name + "_phase_accounting"] = (
                report.get("costs", {}).get("tokens_used") == sum(
                    phase_costs.get(phase, {}).get("tokens_used", math.inf)
                    for phase in ("search", "postprocess", "confirmation")))
            if mandatory_final_g(report["config"]):
                final = report.get("final_g_confirmation") or {}
                evaluation = next((row["outcome"] for row in report.get("evaluations", [])
                                   if row.get("phase") == "confirmation"
                                   and row["experiment_id"] == post.get("mission_id")), None)
                checks[name + "_final_g_confirmation"] = (
                    final.get("status") in {"confirmed", "rejected"}
                    and final.get("experiment_id") == post.get("mission_id")
                    and evaluation is not None and evaluation == final.get("outcome")
                    and evaluation.get("correct") in {True, False}
                    and evaluation.get("commit") == post.get("outcome", {}).get("commit"))
        token_limit = report["config"]["budget"]["tokens"]
        checks[name + "_budget"] = (costs.get("unknown_usage_calls", 1) == 0
            and (token_limit is None or costs.get("tokens_used", math.inf) <= token_limit))
        checks[name + "_transport"] = (
            not any(r.get("state") == "infrastructure_error" for r in report.get("experiments", []))
            and _mother_clean(report)
        )
    admissible = all(checks.values())
    gains = {name: (report.get("best_confirmed") or {}).get("improvement_fraction")
             for name, report in (("reference", reference), ("binary", binary))}
    winner = None
    if admissible:
        winner = ("tie" if gains["reference"] == gains["binary"] else
                  max(gains, key=gains.get))
    return {"comparison_admissible": admissible, "checks": checks,
            "winner_for_this_pair": winner, "gain_fractions": gains,
            "interpretation": "One pair only; compare native model receipts and repeat seeds before generalizing."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="AB-MCTS report/experiments.json")
    parser.add_argument("binary", type=Path, help="Binary report/experiments.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare(*(json.loads(p.read_text(encoding="utf8"))
                       for p in (args.reference, args.binary)))
    if args.output:
        atomic_json(args.output, result)
    print(json.dumps(result, indent=2))
    return 0 if result["comparison_admissible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
