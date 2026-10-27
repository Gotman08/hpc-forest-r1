"""Export the separate common remeasurement, including each thread regime."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--common", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    data = read(args.common / "common-measurements.json")
    allocation = read(args.common / "allocation.json")
    comparison, samples = [], []
    inputs, affinities, grouped = defaultdict(set), defaultdict(set), defaultdict(list)
    for case, result in data.items():
        outcomes = result["outcomes"]
        for repeat in (1, 2):
            off = outcomes.get(f"r{repeat}-advisor_off", {})
            on = outcomes.get(f"r{repeat}-advisor_on", {})
            off_speedup, on_speedup = off.get("speedup"), on.get("speedup")
            comparison.append({"case": case, "repeat": repeat, "job_id": allocation["job_id"],
                "host": allocation["host"], "naive_seconds": outcomes["naive"]["mean_seconds"],
                "off_seconds": off.get("mean_seconds"), "on_seconds": on.get("mean_seconds"),
                "off_speedup": off_speedup, "on_speedup": on_speedup,
                "on_over_off_speedup": on_speedup / off_speedup if on_speedup and off_speedup else None})
        for path in sorted((args.common / case / "logs").rglob("sample-*.log")):
            relative = path.relative_to(args.common / case / "logs")
            candidate = relative.parts[1]
            payload = read(path)
            if payload.get("correct") is not True or payload.get("metric") != "protected_kernel_seconds":
                raise ValueError("Invalid common timing log: " + str(path))
            for detail in payload["details"]:
                if detail["correct"] is not True or not math.isfinite(detail["seconds"]) or detail["seconds"] <= 0:
                    raise ValueError("Invalid timed program: " + str(path))
                key = (case, detail["n"], detail["threads"], detail["seed"], detail["pattern"])
                inputs[key].add(detail["input_sha256"])
                affinities[key].add(tuple(detail["affinity"]))
                grouped[(case, candidate, detail["threads"])].append(detail["seconds"])
                samples.append({"case": case, "candidate": candidate, "sample": path.stem,
                    **{key: detail[key] for key in ("n", "threads", "seed", "pattern", "seconds",
                                                   "repetitions", "warmups", "input_sha256")},
                    "reported_main_thread_affinity": json.dumps(detail["affinity"]), "log": str(relative)})
    if any(len(values) != 1 for values in inputs.values()) or any(len(values) != 1 for values in affinities.values()):
        raise ValueError("Compared programs used different inputs or CPU affinities")
    thread_rows = []
    for (case, candidate, threads), values in sorted(grouped.items()):
        naive = grouped[(case, "naive", threads)]
        if len(values) != 5:
            raise ValueError("Expected five timing rounds per candidate")
        thread_rows.append({"case": case, "candidate": candidate, "threads": threads, "samples": len(values),
            "mean_seconds": statistics.mean(values), "min_seconds": min(values), "max_seconds": max(values),
            "speedup": statistics.mean(naive) / statistics.mean(values)})
    write_csv(args.output / "common-comparison.csv", comparison)
    write_csv(args.output / "common-thread-times.csv", thread_rows)
    write_csv(args.output / "common-raw-samples.csv", samples)
    (args.output / "common-input-audit.json").write_text(json.dumps({"allocation": allocation,
        "all_input_hashes_match": True, "all_reported_main_thread_affinities_match": True,
        "program_allowed_cpus": {case: value["program_affinity"] for case, value in data.items()},
        "affinity_note": "The driver reports its main thread affinity after OpenMP binding, not the affinities of every worker thread.",
        "detail_rows": len(samples), "regimes": [{"case": key[0], "n": key[1], "threads": key[2],
            "seed": key[3], "pattern": key[4], "input_sha256": next(iter(inputs[key])),
            "reported_main_thread_affinity": list(next(iter(affinities[key])))} for key in sorted(inputs)]}, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"comparison": comparison, "thread_rows": thread_rows, "input_rows_checked": len(samples)}))


if __name__ == "__main__":
    main()
