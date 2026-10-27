"""Read-only prequential audit. Unchosen children have NO counterfactual outcome."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def audit(root):
    with closing(sqlite3.connect((root / "campaign/registry.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)) as db:
        meta = {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM metadata")}
        events = [(kind, json.loads(value), created)
                  for kind, value, created in db.execute("SELECT kind,payload,created FROM events ORDER BY id")]
        trials = {i: {"mission": json.loads(m), "outcome": json.loads(r or "{}")}
                  for i, m, r in db.execute("SELECT id,mission,result FROM trials")}
    submitted = {e["experiment_id"]: e.get("submitted_at", created)
                 for kind, e, created in events if kind == "research_node_submitted"}
    samples = [v for k, v in meta.items() if k.startswith("advisor_sample:")]
    for sample in samples:
        identity = sample["id"]
        if identity not in trials or sample["feature_stage"] != "before_generation":
            raise ValueError("Training example does not name an admitted transition")
        if not sample["captured_at"] <= submitted[identity] <= sample["observed_at"]:
            raise ValueError("Training features were captured after generation or outcome")
        runtime = sample.get("target_kind") == "child_minus_parent_log1p_speedup"
        measured_key, parent_key = ("measured_value", "parent_value") if runtime else ("measured_score", "parent_score")
        if sample["target"] != sample[measured_key] - sample[parent_key]:
            raise ValueError("Training target is not the measured transition")
    rows, errors, calls = [], [], 0
    for kind, d, _ in events:
        if kind != "advisor_decision":
            continue
        chosen = d["chosen_id"]
        index = d["candidate_ids"].index(chosen)
        row = {"decision_id": d["id"], "tree": d.get("tree_id"), "status": d["status"],
               "context_scope": d.get("context_scope"), "validation_policy": d.get("validation_policy"),
               "decision_guard": d.get("decision_guard"), "preflight_reason": d.get("preflight_reason"),
               "prediction_target": d.get("prediction_target"),
               "proposal_count": len(d["candidate_ids"]), "chosen_trial": chosen,
               "default_parent": d.get("parent_ids", [None])[0],
               "chosen_parent": d.get("parent_ids", [None])[index],
               "called": d["called"], "changed": d.get("reordered", False), "seconds": d["seconds"],
               "context_size": len(d.get("context_ids", [])), "predicted_child_value": None,
               "validation_fit_samples": None, "validation_holdout_samples": None,
               "validation_pairwise_accuracy": None, "validation_mae_child_value": None,
               "validation_pair_count": None, "validation_parent_disjoint": None,
               "validation_decision_margin": None, "validation_parent_baseline_mae": None,
               "worker_status": None, "worker_reason": None,
               "observed_child_value": None, "prediction_absolute_error": None,
               "observed_status": trials.get(chosen, {}).get("outcome", {}).get("status"),
               "counterfactual_outcome_available": False}
        if d["called"]:
            calls += 1
            directory = root / "campaign/advisor" / d["id"]
            request = read(directory / "request.json")
            candidates = request["candidates"]
            cutoff = min(c["captured_at"] for c in candidates)
            if any("target" in c or "mean_seconds" in c for c in candidates):
                raise ValueError("Future child label appears in candidate request")
            if any(e["observed_at"] >= cutoff for e in request["context"]):
                raise ValueError("Future observation appears in prediction context")
            response_path = directory / "response.json"
            if response_path.is_file():
                response = read(response_path)
                validation = response.get("validation", {})
                row.update(worker_status=response.get("status"),
                           worker_reason=response.get("reason") or validation.get("reason"),
                           validation_fit_samples=len(validation.get("fit_ids", [])),
                           validation_holdout_samples=len(validation.get("held_out_ids", [])),
                           validation_pairwise_accuracy=validation.get("pairwise_accuracy"),
                           validation_mae_child_value=validation.get("mae_child_value", validation.get("mae_child_score", validation.get("mae_score_gain"))),
                           validation_pair_count=validation.get("pair_count"),
                           validation_parent_disjoint=validation.get("parent_disjoint"),
                           validation_decision_margin=validation.get("decision_margin"),
                           validation_parent_baseline_mae=validation.get("parent_baseline_mae"))
            if d["status"] == "advised":
                runtime = d.get("validation_policy") == "runtime_calibrated_v2"
                predicted = d["expected_child_values" if runtime else "expected_child_scores"][index]
                row["predicted_child_value"] = predicted
                sample = meta.get("advisor_sample:" + chosen)
                if sample:
                    actual = sample["measured_value" if runtime else "measured_score"]
                    error = abs(predicted - actual)
                    row.update(observed_child_value=actual, prediction_absolute_error=error)
                    errors.append(error)
        rows.append(row)
    summary = {"samples": len(samples), "parent_sources": len({s["source_sha256"] for s in samples}),
               "decisions": len(rows), "multiple_proposal_decisions": sum(r["proposal_count"] > 1 for r in rows),
               "calls": calls, "changed_parents": sum(r["changed"] for r in rows),
               "holdout_predictions_completed": sum(r["validation_mae_child_value"] is not None for r in rows),
               "parent_predictions_completed": sum(r["worker_status"] == "validated" for r in rows),
               "statuses": dict(Counter(r["status"] for r in rows)),
               "scored_predictions": len(errors), "selected_child_mae": sum(errors) / len(errors) if errors else None,
               "selected_child_rmse": math.sqrt(sum(e * e for e in errors) / len(errors)) if errors else None,
               "chronology_checked": True, "unchosen_children_not_generated": True,
               "interpretation": "Prediction errors concern selected children only. No outcome is invented for unchosen proposals."}
    return rows, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    all_rows, summaries = [], []
    for pair in args.pairs:
        plan = read(pair / "pair.json")
        for arm in plan["arms"]:
            if not arm["advisor"]["enabled"]:
                continue
            prefix = {"pair": plan["pair_id"], "case": plan["case"], "repeat": plan["repeat"], "condition": arm["condition"]}
            rows, summary = audit(pair / ("forest-app-" + arm["id"]))
            all_rows.extend({**prefix, **r} for r in rows)
            summaries.append({**prefix, **summary})
    if all_rows:
        with (args.output / "parent-decisions.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(all_rows[0]))
            writer.writeheader()
            writer.writerows(all_rows)
    (args.output / "advice-audit.json").write_text(json.dumps(summaries, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print(json.dumps(summaries))


if __name__ == "__main__":
    main()
