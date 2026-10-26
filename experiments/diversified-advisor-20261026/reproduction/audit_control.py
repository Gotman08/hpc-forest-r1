"""Export control recovery and terminal decisions from immutable campaign ledgers."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from analyze import database, read

from hpc_forest.codex_conversation import verify_receipt
from hpc_forest.codex_mailbox import response_envelope
from hpc_forest.core import InfrastructureError


def audit(root):
    db = database((root / "campaign/registry.sqlite3").resolve())
    meta = db["metadata"]
    active = meta.get("active_forest:1", {})
    jobs = [v for k, v in meta.items() if k.startswith("active_control:")]
    calls = [c for j in jobs if j["kind"] == "mother" for c in j["calls"]]
    calls.sort(key=lambda c: c["request"]["conversation"]["turn"])
    for previous, current in zip(calls, calls[1:], strict=False):
        a, b = previous["request"]["conversation"], current["request"]["conversation"]
        if (a["id"] != b["id"] or a["thread_id"] != b["thread_id"]
                or b["turn"] != a["turn"] + 1
                or b["previous_request_sha256"] != previous["request_sha256"]):
            raise ValueError("Steering conversation was replaced, forked or replayed")
    receipt_counts = {"verified": 0, "missing_or_invalid": 0}
    for job in jobs:
        if job["kind"] != "mother":
            continue
        for call in job["calls"]:
            response = read(root / "campaign/logs" / job["id"] / f"call-{call['number']:02d}/response.json", {})
            try:
                expected = response_envelope(call["request"], call["request_sha256"])
                if not all(response.get(k) == v for k, v in expected.items()):
                    raise ValueError("Unbound response")
                verify_receipt(call["request"], call["request_sha256"], response)
                receipt_counts["verified"] += 1
            except (InfrastructureError, ValueError, KeyError, TypeError):
                receipt_counts["missing_or_invalid"] += 1
    events = [e for e in db["events"] if e["kind"] in {
        "active_idle_recovery", "active_protected_admission", "active_unprotected_followup",
        "active_idle_review", "active_decision"}]
    result = read(root / "arm-result.json")
    initial = meta.get("mother_plan:preparation:1", {})
    protections = active.get("lifecycle", {}).get("protections", {})
    summary = {
        "pipeline_complete": result.get("pipeline_complete"),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "closed": active.get("closed"),
        "stop_reason": meta.get("research_scheduler:1", {}).get("stop_reason"),
        "mother_broken": bool(meta.get("active_mother_broken:1")),
        "initial_mother_status": initial.get("status"),
        "initial_mother_error": initial.get("error"),
        "initial_mother_calls": initial.get("model_calls"),
        "request_chain_verified": True,
        "native_receipts_verified": receipt_counts["verified"],
        "native_receipts_missing_or_invalid": receipt_counts["missing_or_invalid"],
        "mother_calls": len(calls),
        "terminal_output_limit_continuations": sum(
            c.get("recovery", {}).get("reason") == "model_output_limit" for c in calls),
        "empty_native_waits": sum(len(c.get("usage", {}).get("native_noops", [])) for c in calls),
        "unavailable_mother_jobs": sum(j["kind"] == "mother" and j["status"] == "unavailable" for j in jobs),
        "idle_reopenings": sum(e["kind"] == "active_idle_recovery" for e in events),
        "protected_admissions": sum(e["kind"] == "active_protected_admission" for e in events),
        "protected_trials_remaining": sum(p["remaining"] for p in protections.values()),
        "error": result.get("error"),
    }
    return summary, [{"created": e["created"], "kind": e["kind"],
                      "details": json.dumps(e["payload"], ensure_ascii=False)} for e in events]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summaries, events = [], []
    for pair in args.pairs:
        plan = read(pair / "pair.json")
        for arm in plan["arms"]:
            prefix = {"pair": plan["pair_id"], "case": plan["case"],
                      "repeat": plan["repeat"], "condition": arm["condition"]}
            summary, rows = audit(pair / ("forest-app-" + arm["id"]))
            summaries.append({**prefix, **summary})
            events.extend({**prefix, **row} for row in rows)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, rows in (("control-recovery.csv", summaries), ("control-events.csv", events)):
        if rows:
            with (args.output / name).open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
    print(json.dumps(summaries))


if __name__ == "__main__":
    main()
