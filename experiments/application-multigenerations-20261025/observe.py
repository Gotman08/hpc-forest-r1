"""Read-only audit of the real application campaign; no search intervention."""
import json
import time
from collections import Counter
from pathlib import Path

import httpx

root = Path(__file__).resolve().parent
ids = json.loads((root / "identifiers.json").read_text(encoding="utf8"))
with httpx.Client(base_url="http://127.0.0.1:8767", timeout=30) as client:
    mission = client.get("/api/missions/" + ids["mission_id"]).raise_for_status().json()
    (root / "mission-latest.json").write_text(json.dumps(mission, ensure_ascii=False, indent=2), encoding="utf8")
    summary = {"observed": time.time(), "mission": mission}
    campaign_id = mission.get("campaign_id")
    if campaign_id:
        ids["campaign_id"] = campaign_id
        ids["job_id"] = mission.get("job_id")
        (root / "identifiers.json").write_text(json.dumps(ids, indent=2), encoding="utf8")
        campaign = client.get("/api/campaigns/" + campaign_id).raise_for_status().json()
        (root / "campaign-latest.json").write_text(json.dumps(campaign, ensure_ascii=False, indent=2), encoding="utf8")
        summary["campaign"] = {k: campaign.get(k) for k in (
            "state", "raw_state", "trial_count", "started", "deadline", "finished", "speedup",
            "search_stop_reason", "pipeline_complete", "downloads", "host")}
        summary["trees"] = []
        for tree in campaign["trees"]:
            aliases = {str(alias): node for node in tree["nodes"]
                       for alias in (node["id"], node["trial_id"]) if alias is not None}
            missing, cycles, edges = [], [], []

            def depth(node, seen=()):
                if node["id"] in seen:
                    cycles.append(node["id"])
                    return 0
                parent = node.get("parent")
                if parent is None:
                    return 1
                previous = aliases.get(str(parent))
                if previous is None:
                    missing.append({"child": node["id"], "parent": parent})
                    return 1
                return 1 + depth(previous, (*seen, node["id"]))

            depths = {node["id"]: depth(node) for node in tree["nodes"]}
            parents = Counter()
            for node in tree["nodes"]:
                parent = aliases.get(str(node.get("parent")))
                parent_id = parent["id"] if parent else None
                if parent:
                    parents[parent_id] += 1
                edges.append({"id": node["id"], "parent": parent_id, "raw_parent": node.get("parent"),
                              "depth": depths[node["id"]], "state": node["state"],
                              "correct": node["correct"], "seconds": node["seconds"]})
            summary["trees"].append({"id": tree["id"], "count": len(tree["nodes"]),
                "correct": tree["correct_count"], "max_depth": max(depths.values(), default=0),
                "branching_parents": {k: v for k, v in parents.items() if v >= 2},
                "missing_parents": missing, "cycles": cycles, "nodes": edges})
        summary["analyses"] = len(campaign["analyses"])
        summary["decisions"] = len(campaign["decisions"])
        summary["recent_events"] = [e.get("kind") for e in campaign["events"][:8]]
    (root / "lineage-latest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf8")
    with (root / "observations.jsonl").open("a", encoding="utf8") as out:
        out.write(json.dumps(summary, ensure_ascii=False) + "\n")
    compact = dict(summary)
    compact["mission"] = {k: mission.get(k) for k in (
        "id", "state", "job_id", "last_error", "sync_error", "synced_at")}
    compact["trees"] = [{k: v for k, v in t.items() if k != "nodes"}
                        for t in summary.get("trees", [])]
    print(json.dumps(compact, ensure_ascii=False))
