"""Compare two completed policy reports; never starts a campaign or calls a model."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from hpc_forest.binary_search import enabled
from hpc_forest.core import atomic_json, digest


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


def compare(reference: dict, binary: dict) -> dict:
    left, right = reference["config"], binary["config"]
    checks = {key: left.get(key) == right.get(key) for key in
              ("problem", "method", "backend", "seed", "roles", "budget", "schedule",
               "protocol", "compiler", "harness", "minimum_gain")}
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
        checks[name + "_budget"] = (costs.get("unknown_usage_calls", 1) == 0
            and costs.get("tokens_used", math.inf) <= report["config"]["budget"]["tokens"])
        checks[name + "_transport"] = not any(
            r.get("state") == "infrastructure_error" for r in report.get("experiments", []))
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
