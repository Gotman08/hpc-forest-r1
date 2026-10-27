"""Read-only comparison export from completed, preserved paired campaigns."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path


def read(path, default=None):
    return json.loads(path.read_text(encoding="utf8")) if path.exists() else default


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def valid(outcome):
    return outcome.get("status") == "valid" and outcome.get("correct") is True and positive(outcome.get("mean_seconds"))


def database(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        result = {table: [dict(row) for row in connection.execute("SELECT * FROM " + table)]
                  for table in ("metadata", "trials", "evaluations", "events", "slots")}
    result["metadata"] = {r["key"]: json.loads(r["value"]) for r in result["metadata"]}
    for row in result["trials"]:
        row["mission"], row["result"] = json.loads(row["mission"]), json.loads(row["result"] or "{}")
    for table in ("evaluations", "events"):
        for row in result[table]:
            row["payload"] = json.loads(row["payload"])
    return result


def arm_summary(pair, arm, measured):
    plan, allocation = read(pair / "pair.json"), read(pair / "allocation.json")
    root = pair / ("forest-app-" + arm["id"])
    result, fresh = read(root / "arm-result.json", {}), read(root / "fresh-memory.json", {})
    db = database((root / "campaign/registry.sqlite3").resolve())
    meta, cfg = db["metadata"], db["metadata"]["config"]
    if cfg["advisor"]["enabled"] is not arm["enabled"]:
        raise ValueError("Arm condition does not match frozen configuration")
    if cfg["codex"]["model"] != "gpt-6-luna" or cfg["codex"]["reasoning_effort"] != "max" or cfg["codex"].get("generator_pool"):
        raise ValueError("Unexpected LLM configuration")
    if any(fresh.get(key) != 0 for key in ("trials", "documents", "advisor_samples")) or fresh.get("imported_candidates") is not False:
        raise ValueError("Fresh-memory receipt missing or inconsistent")
    baseline = next(r["payload"] for r in db["evaluations"]
                    if r["phase"] == "search" and r["experiment_id"] == "baseline-e1")
    research = [t for t in db["trials"] if t["mission"].get("kind", "research") == "research"
                and t["mission"].get("budget_phase", "search") == "search" and t["role"] != "G"]
    totals = meta.get("advisor_totals", {})
    decisions = [e for e in db["events"] if e["kind"] == "advisor_decision"]
    samples = [v for k, v in meta.items() if k.startswith("advisor_sample:") and v["epoch"] == meta["current_epoch"]]
    final = measured.get(arm["condition"], {})
    on_time = result.get("pipeline_complete") is True and result.get("finished_within_cap") is True
    speedup = final.get("speedup") if on_time and valid(final) else None
    settled_ids = {t["id"] for t in db["trials"] if t["state"] != "pending"}
    before = [r for r in db["evaluations"] if r["phase"] == "search"
              and r["experiment_id"] in settled_ids | {"baseline-e1"}
              and r["created"] <= meta["deadline"] and valid(r["payload"])]
    best_before = min(before, key=lambda r: r["payload"]["mean_seconds"]) if before else None
    state = meta.get("active_forest:1", {})
    controls = [v for k, v in meta.items() if k.startswith("active_control:")]
    calls = [c for j in controls for c in j.get("calls", [])]
    row = {"case": plan["case"], "repeat": plan["repeat"], "condition": arm["condition"],
        "cohort": plan.get("cohort", "primary"), "retry_of": plan.get("retry_of"),
        "pair_id": plan["pair_id"], "job_id": allocation["job_id"], "host": allocation["host"],
        "seed": plan["seed"], "model": "gpt-6-luna", "effort": "max",
        "target_seconds": plan["target_seconds"], "cap_seconds": plan["cap_seconds"],
        "elapsed_seconds": result.get("elapsed_seconds"), "pipeline_complete": result.get("pipeline_complete", False),
        "finished_within_cap": result.get("finished_within_cap", False),
        "delivery_valid": on_time and valid(final), "naive_common_seconds": measured.get("naive", {}).get("mean_seconds"),
        "selected_common_seconds": final.get("mean_seconds"), "speedup_common": speedup,
        "research_trials": len(research), "correct_trials": sum(valid(t["result"]) for t in research),
        "incorrect_trials": sum(t["result"].get("correct") is False for t in research),
        "infrastructure_failures": sum(t["result"].get("status") == "infrastructure_error" for t in research),
        "unscored_trials": sum(t["result"].get("score") is None for t in research),
        "trees": len({t["tree_id"] for t in research}),
        "initial_trees": len(meta.get("forest_plan:1", {}).get("children", [])),
        "max_depth": max((t["mission"].get("depth", 0) for t in research), default=0),
        "advisor_unique_samples": len({s.get("commit") or s["id"] for s in samples}),
        "advisor_unique_parent_sources": len({s["source_sha256"] for s in samples}),
        "advisor_multi_proposal_opportunities": sum(len(e["payload"].get("candidate_ids", [])) > 1 for e in decisions),
        "advisor_opportunities": totals.get("opportunities", 0), "advisor_calls": totals.get("calls", 0),
        "advisor_validated_calls": sum(e["payload"]["status"] == "advised" for e in decisions),
        "advisor_reorders": totals.get("reorders", 0), "advisor_seconds": totals.get("seconds", 0),
        "advisor_context_seconds": totals.get("context_seconds", 0),
        "stop_reason": meta.get("research_scheduler:1", {}).get("stop_reason"),
        "search_status": meta.get("research_scheduler:1", {}).get("status"),
        "forest_closed": state.get("closed"), "control_calls": len(calls),
        "code_analyses_complete": sum(j.get("kind") == "analyst" and j.get("status") == "complete"
            and j.get("coverage", {}).get("code_analysis_complete", False) for j in controls),
        "analyst_jobs_unavailable": sum(j.get("kind") == "analyst" and j.get("status") == "unavailable" for j in controls),
        "control_jobs_code_coverage_complete": sum(j.get("coverage", {}).get("code_analysis_complete", False) for j in controls),
        "code_source_citations": sum(len(j.get("coverage", {}).get("cited_sources", [])) for j in controls),
        "known_tokens": sum(s["tokens_used"] for s in db["slots"] if s["usage_known"]),
        "unknown_usage_slots": sum(not s["usage_known"] for s in db["slots"]),
        "fresh_memory_verified": True, "pc_relay": allocation["pc_relay"],
        "best_measured_before_target_seconds": best_before["payload"]["mean_seconds"] if best_before else None,
        "best_measured_before_target_speedup": baseline["mean_seconds"] / best_before["payload"]["mean_seconds"]
            if best_before and valid(baseline) else None,
        "error": result.get("error")}
    details = {"summary": row, "search_statuses": dict(Counter(t["result"].get("status", t["state"]) for t in research)),
        "advisor_statuses": dict(Counter(e["payload"]["status"] for e in decisions)),
        "advisor_decisions": decisions, "closure_history": state.get("lifecycle", {}).get("closure_history", []),
        "protections": state.get("lifecycle", {}).get("protections", {}),
        "actions": [a for d in state.get("decisions", {}).values() for a in d["actions"]],
        "trees": [], "initial_forest": meta.get("forest_plan:1"), "created_trees": state.get("children", []),
        "latest_analyst_status": {role: value.get("status") for role, value in state.get("analysts", {}).items()},
        "unavailable_control_jobs": [{k: j.get(k) for k in ("id", "kind", "role", "status", "error")}
                                     for j in controls if j.get("status") == "unavailable"],
        "fresh_memory": fresh, "allocation": allocation, "elapsed_not_equal": True,
        "arm_directory": str(root), "best_before_target_id": best_before["experiment_id"] if best_before else None,
        "target_metric_scope": "settled tree trials and baseline; development-only harness checks excluded"}
    for role in sorted({t["role"] for t in research}):
        trials = [t for t in research if t["role"] == role]
        details["trees"].append({"role": role, "trials": len(trials),
            "correct": sum(valid(t["result"]) for t in trials),
            "root_trials": sum(t["mission"]["parent_id"] is None for t in trials),
            "max_depth": max(t["mission"].get("depth", 0) for t in trials)})
    trial_by_id = {t["id"]: t for t in db["trials"]}
    trajectory = [{"case": plan["case"], "repeat": plan["repeat"], "condition": arm["condition"],
        "id": e["experiment_id"], "phase": e["phase"], "seconds_since_start": e["created"] - meta["started"],
        "settled_search_or_baseline": e["phase"] == "search" and e["experiment_id"] in settled_ids | {"baseline-e1"},
        "before_search_target": e["created"] <= meta["deadline"],
        "role": trial_by_id.get(e["experiment_id"], {}).get("role"),
        "parent": trial_by_id.get(e["experiment_id"], {}).get("mission", {}).get("parent_id"),
        "depth": trial_by_id.get(e["experiment_id"], {}).get("mission", {}).get("depth"),
        "status": e["payload"]["status"], "correct": e["payload"].get("correct"),
        "mean_seconds": e["payload"].get("mean_seconds"), "score": e["payload"].get("score")}
        for e in db["evaluations"]]
    return row, details, trajectory


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows, details, trajectory, paired = [], [], [], []
    for pair in args.pairs:
        plan = read(pair / "pair.json")
        measured = read(pair / "paired-measurements.json", {}).get("outcomes", {})
        if len(read(pair / "pair-results.json", [])) != 2:
            raise ValueError("Both arms must be settled before final analysis: " + str(pair))
        arm_rows = {}
        for arm in plan["arms"]:
            row, detail, points = arm_summary(pair, arm, measured)
            rows.append(row)
            details.append(detail)
            trajectory.extend(points)
            arm_rows[arm["condition"]] = row
        off, on = arm_rows["advisor_off"], arm_rows["advisor_on"]
        paired.append({"case": plan["case"], "repeat": plan["repeat"], "pair_id": plan["pair_id"],
            "cohort": plan.get("cohort", "primary"), "retry_of": plan.get("retry_of"),
            "off_speedup": off["speedup_common"], "on_speedup": on["speedup_common"],
            "on_over_off_speedup": on["speedup_common"] / off["speedup_common"]
                if positive(on["speedup_common"]) and positive(off["speedup_common"]) else None,
            "off_elapsed_seconds": off["elapsed_seconds"], "on_elapsed_seconds": on["elapsed_seconds"],
            "advisor_calls": on["advisor_calls"], "advisor_reorders": on["advisor_reorders"],
            "advisor_role_exercised": on["advisor_reorders"] > 0})
    write_csv(args.output / "arms.csv", rows)
    write_csv(args.output / "paired-comparison.csv", paired)
    write_csv(args.output / "measured-trajectory.csv", trajectory)
    (args.output / "analysis.json").write_text(json.dumps({"arms": details, "pairs": paired,
        "interpretation": "Exploratory paired search replicates; equal allowed budgets, not equal time consumed. "
            "No predictive benefit is established when the advisor never changes a parent choice."},
        indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print(json.dumps({"arms": len(rows), "pairs": paired}, ensure_ascii=False))


if __name__ == "__main__":
    main()

