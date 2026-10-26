"""Describe measurement dispersion without treating timing rounds as search replicates."""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    summaries = {}
    for section in ("registered", "reserved"):
        groups = defaultdict(list)
        with (args.results / section / "common-raw-samples.csv").open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                key = tuple(row[k] for k in ("case", "candidate", "n", "threads", "seed", "pattern"))
                value = float(row["seconds"])
                if not math.isfinite(value) or value <= 0:
                    raise ValueError("Invalid timing value")
                groups[key].append(value)
        for key, values in sorted(groups.items()):
            if len(values) != 5:
                raise ValueError("Expected five registered timing rounds")
            mean = statistics.mean(values)
            cv = statistics.stdev(values) / mean
            rows.append(dict(zip(("case", "candidate", "n", "threads", "seed", "pattern"), key, strict=True))
                        | {"distribution": section, "rounds": len(values), "mean_seconds": mean,
                           "stdev_seconds": statistics.stdev(values), "cv": cv,
                           "min_seconds": min(values), "max_seconds": max(values),
                           "max_over_min": max(values) / min(values)})
            summaries[(section, key[0])] = max(summaries.get((section, key[0]), 0), cv)
    with (args.results / "timing-dispersion.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for (section, case), cv in sorted(summaries.items()):
        print(f"{section} {case}: largest within-regime coefficient of variation = {cv:.1%}")
    print("Descriptive dispersion only; five timing rounds are not five independent searches.")


if __name__ == "__main__":
    main()
