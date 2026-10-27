"""Read completed attempt-2 evidence; never run Forest or modify its candidates.

Usage: python analyze.py [--raw-dir PATH/TO/final-attempt-2]
The optional raw directory supplies delivered sources and common timing samples.
Subsequent runs reuse the captured measurement JSON and per-configuration CSV.
Only the standard library is required.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
COMPARISON = STUDY / "results-attempt-2" / "comparison"
CONDITIONS = ("off", "current", "data", "validation", "both")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def key(row):
    return row["case"], int(row["repeat"]), row["condition"]


def finite(value):
    return value not in (None, "") and math.isfinite(float(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path)
    args = parser.parse_args()
    dossiers = json.loads((COMPARISON / "analysis.json").read_text(encoding="utf-8"))["arms"]
    arms = {key(a["summary"]): a for a in dossiers}
    decisions = read_csv(COMPARISON / "adviser-decisions.csv")
    trajectories = read_csv(COMPARISON / "trajectory.csv")
    # A trial may also appear in final confirmation: select the search record.
    trial = {(key(t), t["id"]): t for t in trajectories if t["phase"] == "search"}
    payloads = {(k, e["payload"]["id"]): e["payload"] for k, a in arms.items()
                for e in a["advisor_decisions"]}

    def parent_score_at_decision(k, payload, index):
        # A root in a new tree can start at an integrated source, not at naive.
        # Recover the actual feature from uncensored forecasts whenever possible.
        scores, gains = payload.get("expected_child_scores", []), payload.get("predictions", [])
        if len(scores) > index and len(gains) > index:
            if payload.get("validation_policy") == "decision_calibrated_v1" or 0 < scores[index] < 1:
                return scores[index] - gains[index], "recorded_forecast_minus_gain"
        parent_id = payload.get("parent_ids", [])[index]
        parent = trial.get((k, parent_id)) if parent_id else None
        if parent is not None and finite(parent["score"]):
            return float(parent["score"]), "explicit_parent_trial"
        return None, "unresolved_censored_root"

    groups, arm_rows, diagnostics = [], [], []
    error_counts = Counter()
    for case in sorted({k[0] for k in arms}):
        for condition in CONDITIONS:
            ss = [arms[(case, r, condition)]["summary"] for r in (1, 2, 3)]
            ratios = [s["registered_speedup"] / arms[(case, s["repeat"], "off")]["summary"]["registered_speedup"] for s in ss]
            reserved_ratios = [s["reserved_speedup"] / arms[(case, s["repeat"], "off")]["summary"]["reserved_speedup"] for s in ss]
            rows = [d for d in decisions if d["case"] == case and d["condition"] == condition]
            called = [d for d in rows if d["called"] == "True"]
            contexts = [float(d["context_size"]) for d in called if finite(d["context_size"])]
            fits = [float(d["validation_fit_samples"]) for d in called if finite(d["validation_fit_samples"])]
            selected = [d for d in rows if d["changed"] == "True" and finite(d["observed_child_score"]) and finite(d["predicted_child_score"])]
            predicted_errors, parent_errors, gains = [], [], []
            for d in selected:
                payload = payloads[(key(d), d["decision_id"])]
                index = payload["candidate_ids"].index(payload["chosen_id"])
                parent_score, provenance = parent_score_at_decision(key(d), payload, index)
                if parent_score is None:
                    continue
                actual, prediction = float(d["observed_child_score"]), float(d["predicted_child_score"])
                predicted_errors.append(abs(actual - prediction))
                parent_errors.append(abs(actual - parent_score))
                gains.append(actual - parent_score)
                diagnostics.append({"case": case, "repeat": d["repeat"], "condition": condition,
                    "decision_id": d["decision_id"], "chosen_trial": d["chosen_trial"],
                    "parent_id": d["chosen_parent"], "parent_score": parent_score,
                    "parent_score_provenance": provenance,
                    "predicted_child_score": prediction, "observed_child_score": actual,
                    "score_gain": actual - parent_score, "prediction_absolute_error": abs(actual - prediction),
                    "parent_baseline_absolute_error": abs(actual - parent_score),
                    "counterfactual_available": False})
            groups.append({"case": case, "condition": condition,
                "registered_speedup_geomean": st.geometric_mean(s["registered_speedup"] for s in ss),
                "reserved_speedup_geomean": st.geometric_mean(s["reserved_speedup"] for s in ss),
                "speedup_ratio_to_off_geomean": st.geometric_mean(ratios),
                "runtime_ratio_to_off_geomean": 1 / st.geometric_mean(ratios),
                "reserved_speedup_ratio_to_off_geomean": st.geometric_mean(reserved_ratios),
                "wins_against_off": sum(r > 1 for r in ratios), "pairs": len(ratios),
                "research_trials_total": sum(s["research_trials"] for s in ss),
                "adviser_calls": sum(s["advisor_calls"] for s in ss),
                "adviser_validated_calls": sum(s["advisor_validated_calls"] for s in ss),
                "adviser_reorders": sum(s["advisor_reorders"] for s in ss),
                "adviser_seconds_mean": st.mean(s["advisor_seconds"] for s in ss),
                "adviser_seconds_total": sum(s["advisor_seconds"] for s in ss),
                "context_size_median": st.median(contexts) if contexts else None,
                "fit_size_median": st.median(fits) if fits else None,
                "overrides_with_observed_parent_and_child": len(gains),
                "override_mae_score": st.mean(predicted_errors) if gains else None,
                "override_parent_baseline_mae_score": st.mean(parent_errors) if gains else None,
                "override_gain_above_005": sum(g > .005 for g in gains),
                "override_gain_below_minus005": sum(g < -.005 for g in gains),
                "override_gain_within_005": sum(abs(g) <= .005 for g in gains)})
    for k, a in sorted(arms.items()):
        s = a["summary"]
        roots = sum(t["root_trials"] for t in a["trees"])
        arm_rows.append({**{f: s[f] for f in ("case", "repeat", "condition", "registered_speedup", "reserved_speedup", "research_trials", "trees", "initial_trees", "max_depth", "advisor_calls", "advisor_reorders", "advisor_seconds", "code_analyses_complete", "analyst_jobs_unavailable", "control_calls", "stop_reason")},
            "elapsed_minutes": s["elapsed_seconds"] / 60,
            "charged_elapsed_minutes": s["charged_elapsed_seconds"] / 60,
            "adviser_time_fraction_of_elapsed": s["advisor_seconds"] / s["elapsed_seconds"],
            "root_trials": roots,
            "root_trial_fraction": roots / s["research_trials"] if s["research_trials"] else None,
            "created_research_trees": sum(t.get("kind") != "intermediate_integration" for t in a["created_trees"]),
            "created_integration_trees": sum(t.get("kind") == "intermediate_integration" for t in a["created_trees"])})
        error_counts.update((j["kind"], j["error"]) for j in a["unavailable_control_jobs"])
    validation_stats, prediction_bounds, early = {}, [], []
    for condition in ("current", "data", "validation", "both"):
        rows = [d for d in decisions if d["condition"] == condition and d["called"] == "True"]
        validation_stats[condition] = {
            "calls": len(rows), "worker_reason": dict(Counter(d["worker_reason"] or "none" for d in rows)),
            "decision_guard": dict(Counter(d["decision_guard"] or "none" for d in rows)),
            "worker_status": dict(Counter(d["worker_status"] or "none" for d in rows)),
            "changed": sum(d["changed"] == "True" for d in rows)}
    for k, a in arms.items():
        s = a["summary"]
        if s["elapsed_seconds"] < 2700:
            confirmed = {h["decision_id"] for h in a["closure_history"] if h.get("closure_confirmed")}
            acts = [x for x in a["actions"] if x["id"] in confirmed]
            early.append({"case": k[0], "repeat": k[1], "condition": k[2],
                "elapsed_minutes": s["elapsed_seconds"] / 60, "closure": a["closure_history"], "actions": acts})
        for event in a["advisor_decisions"]:
            p = event["payload"]
            if not p.get("predictions"):
                continue
            parents = [parent_score_at_decision(k, p, i)[0] for i in range(len(p["predictions"]))]
            unbounded = [s + g for s, g in zip(parents, p["predictions"]) if s is not None]
            prediction_bounds.append({"case": k[0], "repeat": k[1], "condition": k[2],
                "decision_id": p["id"], "candidates": len(parents),
                "unresolved_censored_roots": sum(s is None for s in parents),
                "predictions_above_one": sum(x > 1 for x in unbounded),
                "predictions_below_zero": sum(x < 0 for x in unbounded), "reordered": p.get("reordered", False)})
    source_manifest = []
    per_configuration = []
    if args.raw_dir:
        for split in ("registered", "reserved"):
            shutil.copyfile(args.raw_dir / split / "common-measurements.json", HERE / f"measurements-{split}.json")
            for log in sorted((args.raw_dir / split).glob("*/logs/e1/r*/confirmation/attempt-001/sample-*.log")):
                sample = json.loads(log.read_text(encoding="utf-8"))
                tag = log.parents[2].name
                repeat, condition = tag.split("-", 1)
                case = log.parents[5].name
                for item in sample["details"]:
                    per_configuration.append({"split": split, "case": case, "repeat": int(repeat[1:]),
                        "condition": condition, "sample": log.stem, "n": item["n"],
                        "threads": item["threads"], "seconds": item["seconds"]})
        source_dir = HERE / "delivered-sources"
        source_dir.mkdir(exist_ok=True)
        for source in sorted((args.raw_dir / "registered").glob("source-*/src/candidate.cpp")):
            name = source.parents[1].name.removeprefix("source-") + ".cpp"
            data = source.read_bytes()
            (source_dir / name).write_bytes(data)
            source_manifest.append({"file": f"delivered-sources/{name}", "sha256": hashlib.sha256(data).hexdigest(),
                "origin_in_results_archive": source.relative_to(args.raw_dir).as_posix()})
        write_json(HERE / "sources-manifest.json", source_manifest)
        write_csv(HERE / "per-configuration-samples.csv", per_configuration)
    measure_cv = []
    for split in ("registered", "reserved"):
        path = HERE / f"measurements-{split}.json"
        if not path.exists():
            continue
        for case, group in json.loads(path.read_text(encoding="utf-8")).items():
            for tag, result in group["outcomes"].items():
                if tag == "naive":
                    continue
                times = result["times"]
                measure_cv.append({"split": split, "case": case, "tag": tag, "n_samples": len(times),
                    "mean_seconds": st.mean(times), "sample_cv_percent": 100 * st.stdev(times) / st.mean(times)})
    comparisons = []
    samples_path = HERE / "per-configuration-samples.csv"
    if samples_path.exists():
        samples = defaultdict(list)
        for r in read_csv(samples_path):
            samples[(r["split"], r["case"], int(r["repeat"]), r["condition"], int(r["n"]), int(r["threads"]))].append(float(r["seconds"]))
        for k, times in sorted(samples.items()):
            split, case, repeat, condition, n, threads = k
            baseline_times = samples.get((split, case, repeat, "off", n, threads))
            comparisons.append({"split": split, "case": case, "repeat": repeat, "condition": condition,
                "n": n, "threads": threads, "samples": len(times), "mean_seconds": st.mean(times),
                "runtime_ratio_to_off": st.mean(times) / st.mean(baseline_times) if baseline_times else None})
    write_csv(HERE / "condition-summary.csv", groups)
    write_csv(HERE / "arm-diagnostics.csv", arm_rows)
    write_csv(HERE / "selected-override-diagnostics.csv", diagnostics)
    write_csv(HERE / "prediction-bounds.csv", prediction_bounds)
    write_csv(HERE / "measurement-variability.csv", measure_cv)
    write_csv(HERE / "per-configuration-comparison.csv", comparisons)
    report = {"scope": "Completed attempt 2 only. Descriptive analysis, no new search or benchmark.",
        "inputs": [{"file": str(p.relative_to(STUDY)).replace("\\", "/"), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in (COMPARISON / "analysis.json", COMPARISON / "adviser-decisions.csv", COMPARISON / "trajectory.csv")],
        "arms": len(arms), "conditions": groups, "validation": validation_stats,
        "unavailable_control_jobs": [{"kind": k[0], "reason": k[1], "count": v} for k, v in sorted(error_counts.items())],
        "early_closures_under_45_minutes": early,
        "interpretation_limits": ["Chosen children only: unchosen counterfactuals are unavailable.",
            "Parent-baseline error is an observed subset diagnostic, not a randomized comparison of ranking policies.",
            "Common timing repetitions are not independent search repetitions.",
            "Same initial Mother plan and budget caps do not fix later LLM generations, decisions or elapsed time.",
            "Adviser summed call time is not an exact measurement of lost whole-Forest wall time."]}
    write_json(HERE / "diagnostic.json", report)
    print(json.dumps({"arms": len(arms), "selected_overrides": len(diagnostics),
        "control_failures": sum(error_counts.values()), "sources_captured": len(source_manifest),
        "configuration_samples": len(per_configuration), "measurement_series": len(measure_cv)}, indent=2))


if __name__ == "__main__":
    main()
