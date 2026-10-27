"""Pair saved timings on identical inputs, without re-running or selecting codes."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path


def samples(directory):
    rows = {}
    for path in sorted(directory.glob("sample-*.log")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            try:
                outcome = json.loads(line)
            except ValueError:
                continue
            if not isinstance(outcome, dict) or outcome.get("correct") is not True:
                continue
            for detail in outcome.get("details", []):
                if detail.get("correct") is not True or detail.get("seconds", 0) <= 0:
                    raise ValueError(f"Invalid timing in {path}")
                key = (path.name, detail["n"], detail["threads"], detail["seed"],
                       detail["pattern"], detail["input_sha256"])
                if key in rows:
                    raise ValueError(f"Duplicate timing in {path}")
                rows[key] = {**detail, "log": str(path),
                             "log_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    if not rows:
        raise ValueError(f"No timing in {directory}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extracted_archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    summaries, evidence = [], []
    for distribution in ("registered", "reserved"):
        for case_directory in sorted((args.extracted_archive / distribution).iterdir()):
            logs = case_directory / "logs/e1"
            if not logs.is_dir():
                continue
            baseline = samples(logs / "naive/confirmation/attempt-001")
            for candidate in sorted(logs.iterdir()):
                if candidate.name == "naive" or not candidate.is_dir():
                    continue
                current = samples(candidate / "confirmation/attempt-001")
                if set(current) != set(baseline):
                    raise ValueError(f"Different inputs in {candidate}")
                groups = defaultdict(list)
                for key, after in current.items():
                    before = baseline[key]
                    row = {"distribution": distribution, "case": case_directory.name,
                           "candidate": candidate.name, "sample": key[0],
                           "n": after["n"], "threads": after["threads"],
                           "seed": after["seed"], "pattern": after["pattern"],
                           "input_sha256": after["input_sha256"],
                           "baseline_seconds": before["seconds"], "candidate_seconds": after["seconds"],
                           "speedup": before["seconds"] / after["seconds"],
                           "baseline_log": before["log"], "baseline_log_sha256": before["log_sha256"],
                           "candidate_log": after["log"], "candidate_log_sha256": after["log_sha256"]}
                    evidence.append(row)
                    groups[(after["n"], after["threads"], after["pattern"])].append(row)
                for (n, threads, pattern), values in sorted(groups.items()):
                    before = statistics.mean(r["baseline_seconds"] for r in values)
                    after = statistics.mean(r["candidate_seconds"] for r in values)
                    summaries.append({"distribution": distribution, "case": case_directory.name,
                                      "candidate": candidate.name, "n": n, "threads": threads,
                                      "pattern": pattern, "samples": len(values),
                                      "baseline_seconds": before, "candidate_seconds": after,
                                      "speedup": before / after})
    if not summaries:
        raise ValueError("No delivered timings")
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "configuration-timings.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    (args.output / "configuration-timing-evidence.json").write_text(json.dumps({
        "method": "Ratio of arithmetic means for identical n/threads/pattern; each sample matched by seed and input SHA256.",
        "limit": "Timing repetitions are not independent search repetitions. No reselection, no search modification.",
        "source_archive_extracted": str(args.extracted_archive), "rows": evidence,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary_rows": len(summaries), "matched_input_rows": len(evidence)}))


if __name__ == "__main__":
    main()
