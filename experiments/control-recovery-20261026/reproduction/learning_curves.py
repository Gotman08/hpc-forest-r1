"""Descriptive search curves, not counterfactual shorter-budget campaigns."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from analyze import database, read, valid


def checkpoints(db, minutes=(10, 30, 60, 90), receipt=None):
    meta = db["metadata"]
    started = meta["started"]
    samples = [v for k, v in meta.items() if k.startswith("advisor_sample:")]
    settled = {
        e["payload"]["experiment_id"]: e["payload"].get("settled_at", e["created"])
        for e in db["events"] if e["kind"] == "research_node_settled"
    }
    trial_ids = {t["id"] for t in db["trials"]
                 if t["mission"].get("budget_phase", "search") == "search"}
    baseline = next(e["payload"] for e in db["evaluations"]
                    if e["phase"] == "search" and e["experiment_id"] == "baseline-e1")
    rows = []
    stopped_at = (receipt["started_at"] + receipt["elapsed_seconds"]) if receipt else None
    for minute in minutes:
        cutoff = min(started + minute * 60, meta["deadline"])
        ready = {i for i, observed in settled.items() if observed <= cutoff} & trial_ids
        observed = [e for e in db["evaluations"] if e["phase"] == "search"
                    and e["created"] <= cutoff
                    and e["experiment_id"] in ready | {"baseline-e1"}]
        correct = [e for e in observed if valid(e["payload"])]
        best = min(correct, key=lambda e: e["payload"]["mean_seconds"]) if correct else None
        decisions = [e["payload"] for e in db["events"]
                     if e["kind"] == "advisor_decision" and e["created"] <= cutoff]
        elapsed_finish = meta.get("pipeline_finished:1")
        stopped = stopped_at is not None and stopped_at <= cutoff
        rows.append({
            "checkpoint_minutes": minute,
            "cutoff_seconds_from_search_start": cutoff - started,
            "settled_trials": len(ready),
            "correct_trials": len({e["experiment_id"] for e in correct} - {"baseline-e1"}),
            "best_trial": best["experiment_id"] if best else None,
            "best_search_seconds": best["payload"]["mean_seconds"] if best else None,
            "best_search_speedup": baseline["mean_seconds"] / best["payload"]["mean_seconds"]
            if best and valid(baseline) else None,
            "advisor_samples": sum(s["observed_at"] <= cutoff for s in samples),
            "advisor_calls": sum(d["called"] for d in decisions),
            "advisor_changed_parents": sum(d.get("reordered", False) for d in decisions),
            "advisor_validated_calls": sum(d["status"] == "advised" for d in decisions),
            "pipeline_already_finished": elapsed_finish is not None and elapsed_finish <= cutoff,
            "campaign_already_stopped": stopped if receipt else None,
            "campaign_outcome_at_checkpoint": (
                ("delivered" if receipt.get("pipeline_complete") else "failed") if stopped
                else "active" if receipt else "unknown"
            ),
            "trial_scope": "settled research and intermediate integrations in the search phase",
            "is_confirmed_delivery": False,
            "interpretation": "Observed prefix of this long search; not an independent shorter-budget run.",
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for pair in args.pairs:
        plan = read(pair / "pair.json")
        for arm in plan["arms"]:
            root = pair / ("forest-app-" + arm["id"])
            db = database((root / "campaign/registry.sqlite3").resolve())
            for row in checkpoints(db, receipt=read(root / "arm-result.json")):
                rows.append({"case": plan["case"], "repeat": plan["repeat"],
                             "cohort": plan.get("cohort", "primary"), "condition": arm["condition"], **row})
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "learning-curves.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"rows": len(rows), "cutoffs_minutes": [10, 30, 60, 90]}))


if __name__ == "__main__":
    main()
