"""Audit stop/recovery events and Mother receipt chains directly in preserved archives."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import tarfile
from collections import Counter
from pathlib import Path

from hpc_forest.codex_conversation import verify_receipt
from hpc_forest.codex_mailbox import response_envelope
from hpc_forest.core import InfrastructureError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("output_prefix", type=Path)
    args = parser.parse_args()
    with sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        meta = {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM metadata")}
        events = [(k, json.loads(v), t) for k, v, t in db.execute(
            "SELECT kind,payload,created FROM events WHERE kind LIKE 'active_%' ORDER BY id")]
    active = meta.get("active_forest:1", {})
    jobs = [v for k, v in meta.items() if k.startswith("active_control:")]
    calls = [(job, call) for job in jobs if job["kind"] == "mother" for call in job["calls"]]
    calls.sort(key=lambda pair: pair[1]["request"]["conversation"]["turn"])
    errors, receipt_rows = [], []
    for (_, previous), (_, current) in zip(calls, calls[1:]):
        a, b = previous["request"]["conversation"], current["request"]["conversation"]
        if (a["id"] != b["id"] or a["thread_id"] != b["thread_id"]
                or b["turn"] != a["turn"] + 1
                or b["previous_request_sha256"] != previous["request_sha256"]):
            errors.append("Nonconsecutive Mother receipt chain at turn " + str(b["turn"]))
    needed = {f"campaign/logs/{job['id']}/call-{call['number']:02d}/response.json": (job, call)
              for job, call in calls}
    seen = set()
    with tarfile.open(args.archive, "r|gz") as archive:
        for member in archive:
            name = member.name.removeprefix("./")
            if not member.isfile() or name not in needed:
                continue
            seen.add(name)
            job, call = needed[name]
            response = json.load(archive.extractfile(member))
            row = {"job_id": job["id"], "call": call["number"], "status": call["status"],
                   "turn": call["request"]["conversation"]["turn"], "valid": False}
            try:
                expected = response_envelope(call["request"], call["request_sha256"])
                if not all(response.get(k) == v for k, v in expected.items()):
                    raise ValueError("Response envelope mismatch")
                verify_receipt(call["request"], call["request_sha256"], response)
                row["valid"] = True
            except (InfrastructureError, ValueError, KeyError, TypeError) as exc:
                row["reason"] = str(exc)
            receipt_rows.append(row)
    for name in sorted(set(needed) - seen):
        job, call = needed[name]
        receipt_rows.append({"job_id": job["id"], "call": call["number"], "status": call["status"],
                             "turn": call["request"]["conversation"]["turn"], "valid": False,
                             "reason": "Missing response member"})
    deadline = meta.get("deadline")
    origin = deadline - 5400 if deadline is not None else None
    rows = [{"kind": kind, "created_at": created,
             "charged_seconds": created - origin if origin is not None else None,
             "details": json.dumps(payload, ensure_ascii=False)} for kind, payload, created in events]
    action_counts = Counter()
    for kind, payload, _ in events:
        if kind != "active_decision":
            continue
        for action in payload.get("actions", []):
            action_counts[(action["action"]["kind"], action["status"])] += 1
    summary = {"stop_reason": meta.get("research_scheduler:1", {}).get("stop_reason"),
               "closed": active.get("closed"), "suspended_at_end": active.get("suspended", []),
               "mother_broken": bool(meta.get("active_mother_broken:1")),
               "mother_calls": len(calls), "request_chain_verified": not errors,
               "receipts_verified": sum(r["valid"] for r in receipt_rows),
               "receipts_missing_or_invalid": sum(not r["valid"] for r in receipt_rows),
               "event_counts": dict(Counter(kind for kind, _, _ in events)),
               "action_counts": [{"action": kind, "status": status, "count": count}
                                 for (kind, status), count in sorted(action_counts.items())],
               "closure_history": active.get("lifecycle", {}).get("closure_history", []),
               "unavailable_jobs": [{"id": j["id"], "kind": j["kind"], "role": j["role"]}
                                    for j in jobs if j["status"] == "unavailable"]}
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with args.output_prefix.with_suffix(".csv").open("w", encoding="utf8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    with args.archive.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    report = {"archive": str(args.archive), "archive_sha256": sha,
              "summary": summary, "receipts": receipt_rows, "errors": errors,
              "interpretation": "Receipt checks concern the native conversation binding, not provider internals. "
                                "A refused or cancelled call is retained separately from successful calls."}
    args.output_prefix.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(summary))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
