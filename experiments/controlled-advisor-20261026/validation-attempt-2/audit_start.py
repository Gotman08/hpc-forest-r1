"""Read-only checks of the first six fresh attempt-2 searches."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOTS = [
    "/scratch_p/nimarano/forest-romeo-oauth-20261025-51ab9260/controlled-advisor-gemm_cpu-search-r1-76b710a27d",
    "/scratch_p/nimarano/forest-romeo-oauth-20261025-51ab9260/controlled-advisor-gemm_cpu-search-r2-c472fbe9b7",
    "/scratch_p/nimarano/forest-romeo-oauth-20261025-51ab9260/controlled-advisor-gemm_cpu-search-r3-0ff2b9e7da",
    "/scratch_p/nimarano/forest-romeo-oauth-20261025-51ab9260/controlled-advisor-blackscholes-search-r1-23f99cfc14",
    "/scratch_p/nimarano/forest-romeo-oauth-20261025-51ab9260/controlled-advisor-blackscholes-search-r2-15f5a2b668",
    "/scratch_p/nimarano/forest-romeo-oauth-20261025-51ab9260/controlled-advisor-blackscholes-search-r3-7ba59293a2"
]

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

records = []
pending = []
for name in ROOTS:
    block = Path(name)
    if not (block / "allocation.json").is_file():
        pending.append({"block": block.name, "reason": "allocation not recorded"})
        continue
    plan = read(block / "frozen-plan.json")
    allocation = read(block / "allocation.json")
    campaigns = sorted(block.glob("forest-app-*"))
    if not campaigns:
        pending.append({"block": block.name, "reason": "campaign not created"})
    for root in campaigns:
        database = root / "campaign/registry.sqlite3"
        if not database.is_file() or not (root / "launch.json").is_file():
            pending.append({"block": block.name, "reason": "campaign initializing"})
            continue
        launch = read(root / "launch.json")
        fresh = read(root / "fresh-memory.json")
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=2) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            values = dict(db.execute("SELECT key,value FROM metadata WHERE key IN ('forest_plan:1','config')"))
            actual = json.loads(values.get("forest_plan:1", "{}"))
            config = json.loads(values.get("config", "{}"))
            trials = db.execute("SELECT role,count(*) FROM trials GROUP BY role").fetchall()
            states = db.execute("SELECT state,count(*) FROM trials GROUP BY state").fetchall()
        state_path = Path("/home/nimarano/forest-controlled-attempt2-20261026/state") / block.name.removeprefix("controlled-advisor-") / "storage.json"
        records.append({
            "block": block.name, "condition": launch["condition"], "case": launch["case"],
            "initial_plan_matches": actual.get("plan_sha256") == plan["plan_sha256"],
            "plan_sha256": actual.get("plan_sha256"),
            "thread_id": actual.get("conversation", {}).get("thread_id"),
            "common_planning_thread": plan["planning_receipt"]["thread_id"],
            "session_id": launch["session_id"],
            "model": launch["model"], "effort": launch["effort"],
            "generator_pool": launch["generator_pool"], "advisor": config.get("advisor"),
            "fresh_memory": fresh, "trials_by_role": dict(trials), "trial_states": dict(states),
            "allocation": allocation, "storage": read(state_path) if state_path.is_file() else None,
        })
threads = [record["thread_id"] for record in records]
sessions = [record["session_id"] for record in records]
unique_blocks = {record["block"]: record["allocation"] for record in records}
allocations = list(unique_blocks.values())
disjoint = all(
    left["host"] != right["host"] or not set(left["affinity"]) & set(right["affinity"])
    for i, left in enumerate(allocations) for right in allocations[i + 1:]
)
checks = {
    "all_six_first_searches_started": len(records) == 6 and len(unique_blocks) == 6 and not pending,
    "initial_plans_match": bool(records) and all(record["initial_plan_matches"] for record in records),
    "separate_mother_threads": len(set(threads)) == len(threads) and bool(threads) and all(threads),
    "separate_planning_thread": all(record["thread_id"] != record["common_planning_thread"] for record in records),
    "separate_sessions": len(set(sessions)) == len(sessions),
    "all_luna_max": all(record["model"] == "gpt-6-luna" and record["effort"] == "max" and not record["generator_pool"] for record in records),
    "fresh_memory_at_start": all(
        all(record["fresh_memory"][key] == 0 for key in ("trials", "documents", "advisor_samples"))
        and not record["fresh_memory"]["imported_candidates"] for record in records
    ),
    "distinct_allocated_cpus": disjoint,
    "five_cpus_per_block": all(len(alloc["affinity"]) == 5 for alloc in allocations),
    "working_roots_persistent": all(not Path(name).resolve().is_relative_to(Path("/tmp")) for name in ROOTS),
    "independent_storage_status": all(record["storage"] is not None for record in records),
}
print(json.dumps({"timestamp_utc": datetime.now(timezone.utc).isoformat(), "checks": checks, "pending": pending, "records": records}, indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
