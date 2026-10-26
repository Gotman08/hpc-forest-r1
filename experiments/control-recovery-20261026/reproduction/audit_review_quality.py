"""Export analyst failures and close decisions without changing campaign state."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from analyze import database, read


def write(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    jobs, closures = [], []
    prefix_fields = ["pair", "case", "repeat", "condition"]
    for pair in args.pairs:
        plan = read(pair / "pair.json")
        for arm in plan["arms"]:
            prefix = dict(zip(prefix_fields, [plan["pair_id"], plan["case"], plan["repeat"], arm["condition"]], strict=True))
            db = database((pair / ("forest-app-" + arm["id"]) / "campaign/registry.sqlite3").resolve())
            for key, job in db["metadata"].items():
                if not key.startswith("active_control:") or job.get("kind") != "analyst":
                    continue
                calls, coverage = job.get("calls", []), job.get("coverage", {})
                jobs.append({**prefix, "job_id": job["id"], "tree": job.get("role"),
                    "status": job.get("status"), "calls": len(calls),
                    "failed_calls": sum(c.get("status") == "failed" for c in calls),
                    "code_analysis_complete": bool(coverage.get("code_analysis_complete")),
                    "source_citations": len(coverage.get("cited_sources", [])),
                    "source_reads": len(coverage.get("reads", [])),
                    "elapsed_model_seconds": sum(float(c.get("elapsed_seconds", 0)) for c in calls),
                    "final_error": job.get("error"),
                    "call_errors": json.dumps([{"number": c["number"], "error": c.get("error")}
                        for c in calls if c.get("error")], ensure_ascii=False)})
            for event in db["events"]:
                if event["kind"] != "active_decision":
                    continue
                for decision in event["payload"].get("actions", []):
                    action = decision.get("action", {})
                    if action.get("kind") != "close":
                        continue
                    reviews = action.get("hypothesis_review", [])
                    closures.append({**prefix, "created": event["created"],
                        "decision_id": decision.get("id"), "status": decision.get("status"),
                        "closure_confirmed": bool(decision.get("closure_confirmed")),
                        "closure_pending": bool(decision.get("closure_pending")),
                        "hypotheses_reviewed": decision.get("hypotheses_reviewed"),
                        "review_entries": len(reviews),
                        "unavailable_analyses": json.dumps(decision.get("unavailable_analyses", [])),
                        "reason": decision.get("reason"), "rationale": action.get("rationale"),
                        "hypothesis_review": json.dumps(reviews, ensure_ascii=False)})
    args.output.mkdir(parents=True, exist_ok=True)
    write(args.output / "analyst-quality.csv", jobs, prefix_fields + [
        "job_id", "tree", "status", "calls", "failed_calls", "code_analysis_complete",
        "source_citations", "source_reads", "elapsed_model_seconds", "final_error", "call_errors"])
    write(args.output / "closure-quality.csv", closures, prefix_fields + [
        "created", "decision_id", "status", "closure_confirmed", "closure_pending",
        "hypotheses_reviewed", "review_entries", "unavailable_analyses", "reason", "rationale", "hypothesis_review"])
    print(json.dumps({"analyst_jobs": len(jobs),
        "unavailable_analyst_jobs": sum(j["status"] == "unavailable" for j in jobs),
        "close_decisions": len(closures),
        "confirmed_closures_with_unavailable_analyses": sum(
            c["closure_confirmed"] and c["unavailable_analyses"] != "[]" for c in closures)}))


if __name__ == "__main__":
    main()
