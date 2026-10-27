"""Export existing adviser preflight evidence; never changes a search or raw data.

Usage: python export_adviser_preflight.py <study>/results
The frozen original exporter used the wrong key for preflight_reason.
This supplement reads payload.validation.reason from the preserved raw audit.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    source = args.results / "analysis.json"
    original = source.read_bytes()
    data = json.loads(original)
    rows = []
    counts = Counter()
    for arm in data["arms"]:
        summary = arm["summary"]
        for event in arm.get("advisor_decisions", []):
            decision = event["payload"]
            if decision["status"] != "validation_preflight_rejected":
                continue
            validation = decision.get("validation", {})
            reason = validation.get("reason", "")
            if not reason:
                raise ValueError(f"Missing preflight reason in {decision['id']}")
            rows.append({
                "case": summary["case"], "repeat": summary["repeat"], "condition": summary["condition"],
                "job_id": summary["job_id"], "decision_id": decision["id"],
                "tree_id": decision["tree_id"], "reason": reason,
                "called": decision["called"],
                "context_count": len(decision.get("context_ids", [])),
                "fit_count": len(validation.get("fit_ids", [])),
                "held_out_count": len(validation.get("held_out_ids", [])),
                "fit_parent_count": validation.get("fit_parent_count", ""),
                "held_out_parent_count": validation.get("held_out_parent_count", ""),
                "available_pair_count": validation.get("available_pair_count", ""),
                "seconds": decision.get("seconds", ""),
            })
            counts[f"{summary['case']} / r{summary['repeat']} / {summary['condition']} / {reason}"] += 1
    columns = ["case", "repeat", "condition", "job_id", "decision_id", "tree_id", "reason",
               "called", "context_count", "fit_count", "held_out_count",
               "fit_parent_count", "held_out_parent_count", "available_pair_count", "seconds"]
    output = args.results / "adviser-preflight.csv"
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    provenance = {
        "source": source.name, "source_sha256": hashlib.sha256(original).hexdigest(),
        "source_key": "arms[].advisor_decisions[].payload.validation.reason",
        "output": output.name, "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "rows": len(rows), "counts": dict(counts),
        "raw_source_unchanged": source.read_bytes() == original,
        "search_changed": False,
    }
    (args.results / "adviser-preflight-provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(provenance, ensure_ascii=False))


if __name__ == "__main__":
    main()
