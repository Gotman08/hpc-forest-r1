"""Compare termination and consumed resources, without imputing failed deliveries."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def key(row):
    return row["case"], int(row["repeat"]), row["condition"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-arms", type=Path, required=True)
    parser.add_argument("--previous-control", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    previous = {key(row): row for row in read(args.previous_arms)}
    current = {key(row): row for row in read(args.results / "arms.csv")}
    for row in read(args.previous_control):
        previous[key(row)].update(row)
    for row in read(args.results / "control-recovery.csv"):
        current[key(row)].update(row)
    fields = ("pipeline_complete", "elapsed_seconds", "stop_reason", "closed", "mother_broken",
              "initial_mother_status", "initial_mother_error", "initial_mother_calls",
              "research_trials", "correct_trials", "trees", "max_depth", "mother_calls",
              "code_analyses_complete", "advisor_calls", "advisor_reorders", "advisor_seconds",
              "terminal_output_limit_continuations", "empty_native_waits", "idle_reopenings",
              "unavailable_mother_jobs", "protected_trials_remaining",
              "native_receipts_missing_or_invalid", "error")
    rows = []
    for identity, now in sorted(current.items()):
        old = previous[identity]
        row = {"case": identity[0], "repeat": identity[1], "condition": identity[2]}
        for field in fields:
            row["previous_" + field], row["current_" + field] = old.get(field), now.get(field)
        rows.append(row)
    with (args.results / "historical-stops.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"compared_arms": len(rows)}))


if __name__ == "__main__":
    main()
