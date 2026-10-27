"""Count settled, actually measured trials at fixed charged-time checkpoints."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("--target-seconds", type=float, default=5400)
    args = parser.parse_args()
    with sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        trials = {m["id"]: (m, json.loads(result or "{}"))
                  for mission, result in db.execute("SELECT mission,result FROM trials")
                  if (m := json.loads(mission)).get("budget_phase") == "search"
                  and m.get("kind") == "research" and m["role"] != "G"}
        events = [(kind, json.loads(raw), created)
                  for kind, raw, created in db.execute(
                      "SELECT kind,payload,created FROM events "
                      "WHERE kind IN ('adaptive_admission','research_node_settled') ORDER BY id")]
        baseline = db.execute(
            "SELECT e.payload FROM evaluations e JOIN epochs p ON e.experiment_id=p.baseline_id "
            "WHERE e.phase='search' ORDER BY e.id LIMIT 1").fetchone()
        if baseline is None:
            baseline = db.execute(
                "SELECT e.payload FROM evaluations e JOIN epochs p ON e.experiment_id=p.baseline_id "
                "ORDER BY e.id LIMIT 1").fetchone()
    deadlines = {p["target_deadline"] for k, p, _ in events
                 if k == "adaptive_admission" and p.get("target_deadline") is not None}
    if len(deadlines) != 1:
        raise ValueError("Expected one unchanged target deadline, found " + str(deadlines))
    origin = next(iter(deadlines)) - args.target_seconds
    baseline_result = json.loads(baseline[0]) if baseline else None
    baseline_seconds = baseline_result.get("mean_seconds") if baseline_result else None
    if not baseline_seconds:
        raise ValueError("Missing actual baseline timing")
    settled = {}
    for kind, payload, created in events:
        if kind != "research_node_settled" or payload["experiment_id"] not in trials:
            continue
        identity = payload["experiment_id"]
        if identity in settled:
            raise ValueError("Repeated settlement event: " + identity)
        settled[identity] = payload.get("settled_at", created) - origin
    if set(settled) != set(trials):
        raise ValueError("Unsettled trials must be explained before exporting a terminal curve")
    rows = []
    for seconds in (900, 1800, 2700, 3600, 4500, 5400):
        ids = [identity for identity, elapsed in settled.items() if elapsed <= seconds]
        correct = [identity for identity in ids
                   if trials[identity][1].get("correct") is True and trials[identity][1].get("times")]
        best = min(correct, key=lambda identity: trials[identity][1]["mean_seconds"], default=None)
        best_seconds = trials[best][1]["mean_seconds"] if best else None
        rows.append({"charged_seconds": seconds, "settled_research_trials": len(ids),
                     "correct_measured_trials": len(correct),
                     "distinct_correct_source_trees": len({trials[i][1]["tree_hash"] for i in correct}),
                     "selected_parent_ids": len({trials[i][0]["parent_id"] for i in ids
                                                 if trials[i][0].get("parent_id")}),
                     "root_proposals": sum(not trials[i][0].get("parent_id") for i in ids),
                     "refinement_proposals": sum(bool(trials[i][0].get("parent_id")) for i in ids),
                     "best_trial_id": best, "best_search_seconds": best_seconds,
                     "baseline_search_seconds": baseline_seconds,
                     "best_search_speedup": baseline_seconds / best_seconds if best_seconds else None})
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    with args.output_prefix.with_suffix(".csv").open("w", encoding="utf8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with args.database.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    result = {"database": str(args.database), "database_sha256": sha,
              "charged_time_origin_epoch": origin, "rows": rows,
              "limits": "Search measurements only, not final common remeasurement. "
                        "Charged time includes the shared planning cost. Counts exclude integrations. "
                        "Later checkpoints can lie after search ended and then retain the last count."}
    args.output_prefix.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
