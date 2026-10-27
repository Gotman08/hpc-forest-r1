"""Export immutable control-call durations from a preserved campaign archive."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sqlite3
import statistics
import tarfile
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("evidence_directory", type=Path)
    parser.add_argument("output_prefix", type=Path)
    args = parser.parse_args()
    args.evidence_directory.mkdir(parents=True, exist_ok=True)
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    names = {"campaign/registry.sqlite3": "registry.sqlite3",
             "campaign/registry.sqlite3-wal": "registry.sqlite3-wal",
             "campaign/registry.sqlite3-shm": "registry.sqlite3-shm"}
    receipts = []
    with tarfile.open(args.archive, "r|gz") as archive:
        for member in archive:
            name = member.name.removeprefix("./")
            if not member.isfile() or name not in names:
                continue
            target = args.evidence_directory / names[name]
            # Refuse to overwrite an existing extraction from another archive.
            if target.exists():
                raise FileExistsError(target)
            with archive.extractfile(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)
            with target.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            receipts.append({"member": name, "copy": str(target), "sha256": digest})
    database = args.evidence_directory / "registry.sqlite3"
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        jobs = [json.loads(value) for (value,) in db.execute(
            "SELECT value FROM metadata WHERE key LIKE 'active_control:%'")]
    rows = []
    for job in jobs:
        for call in job["calls"]:
            usage = call.get("usage", {})
            rows.append({"job_id": job["id"], "kind": job["kind"], "role": job["role"],
                         "job_status": job["status"], "number": call["number"],
                         "call_status": call["status"], "started_at": call["started_at"],
                         "elapsed_seconds": call.get("elapsed_seconds"),
                         "model": call["request"]["model"], "effort": call["request"]["reasoning_effort"],
                         "request_sha256": call["request_sha256"],
                         "error": str(call.get("error", "")),
                         "recovery": json.dumps(call.get("recovery"), ensure_ascii=False),
                         "tool_runtime_errors": json.dumps(usage.get("tool_runtime_errors"), ensure_ascii=False),
                         "turn_failure_messages": json.dumps(usage.get("turn_failure_messages"), ensure_ascii=False),
                         "token_accounting": json.dumps(usage.get("token_accounting"), ensure_ascii=False)})
    rows.sort(key=lambda row: (row["started_at"], row["job_id"], row["number"]))
    if not rows:
        raise ValueError("No control calls in the preserved ledger")
    with args.output_prefix.with_suffix(".csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    groups = {}
    for kind in sorted({row["kind"] for row in rows}):
        subset = [row for row in rows if row["kind"] == kind]
        durations = [row["elapsed_seconds"] for row in subset if row["elapsed_seconds"] is not None]
        groups[kind] = {"calls": len(subset), "statuses": dict(Counter(row["call_status"] for row in subset)),
                        "measured_durations": len(durations), "sum_seconds": sum(durations),
                        "median_seconds": statistics.median(durations) if durations else None,
                        "max_seconds": max(durations) if durations else None,
                        "jobs_unavailable": sum(job["kind"] == kind and job["status"] == "unavailable" for job in jobs)}
    summary = {"archive": str(args.archive), "database_copies": receipts, "groups": groups,
               "longest_calls": sorted((r for r in rows if r["elapsed_seconds"] is not None),
                                       key=lambda row: row["elapsed_seconds"], reverse=True)[:10],
               "warning": "Call durations can overlap research. Their sum must not be added to campaign wall time. Missing durations remain missing."}
    args.output_prefix.with_suffix(".json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(groups, ensure_ascii=False))


if __name__ == "__main__":
    main()
