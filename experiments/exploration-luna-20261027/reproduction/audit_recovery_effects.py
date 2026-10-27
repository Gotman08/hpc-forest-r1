"""Describe trials admitted after an idle reopening; no counterfactual gain is inferred."""
import argparse
import csv
import json
from pathlib import Path

from campaign_evidence import database, read, valid

parser = argparse.ArgumentParser()
parser.add_argument("--pairs", type=Path, nargs="+", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
rows = []
for pair in args.pairs:
    plan = read(pair / "pair.json")
    for arm in plan["arms"]:
        db = database((pair / ("forest-app-" + arm["id"]) / "campaign/registry.sqlite3").resolve())
        start = db["metadata"]["deadline"] - plan["target_seconds"]
        events = sorted((e for e in db["events"] if e["kind"] == "active_idle_recovery"), key=lambda e: e["created"])
        research = [t for t in db["trials"] if t["mission"].get("kind", "research") == "research"
                    and t["mission"].get("budget_phase", "search") == "search" and t["role"] != "G"]
        for index, event in enumerate(events):
            end = events[index + 1]["created"] if index + 1 < len(events) else float("inf")
            admitted = [t for t in research if event["created"] < t["created"] < end]
            earlier = [e["payload"]["mean_seconds"] for e in db["evaluations"]
                       if e["phase"] == "search" and e["created"] <= event["created"] and valid(e["payload"])]
            later = [t["result"]["mean_seconds"] for t in admitted if valid(t["result"])]
            rows.append({"case": plan["case"], "repeat": plan["repeat"], "condition": arm["condition"],
                         "reopening": index + 1, "seconds_since_start": event["created"] - start,
                         "roles": json.dumps(event["payload"].get("resumed_roles", [])),
                         "new_research_trials_until_next_reopening": len(admitted),
                         "correct_new_trials": len(later),
                         "best_measured_seconds_before": min(earlier) if earlier else None,
                         "best_new_trial_seconds": min(later) if later else None})
args.output.mkdir(parents=True, exist_ok=True)
fields = ["case", "repeat", "condition", "reopening", "seconds_since_start", "roles",
          "new_research_trials_until_next_reopening", "correct_new_trials",
          "best_measured_seconds_before", "best_new_trial_seconds"]
with (args.output / "idle-recovery-effects.csv").open("w", encoding="utf-8-sig", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
print(json.dumps(rows))
