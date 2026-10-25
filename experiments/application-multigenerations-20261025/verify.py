"""Verify completed campaign lineage, actual source inheritance, and rendered edges."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import httpx

root = Path(__file__).resolve().parent
campaign = json.loads((root / "campaign-latest.json").read_text(encoding="utf8"))
mission = json.loads((root / "mission-latest.json").read_text(encoding="utf8"))
lineage = json.loads((root / "lineage-latest.json").read_text(encoding="utf8"))
dom = json.loads((root / "graph-dom.json").read_text(encoding="utf8"))
nodes = {n["id"]: n for t in campaign["trees"] for n in t["nodes"]}
source_dir = root / "variants"
source_dir.mkdir(exist_ok=True)
sources, inheritance, display = {}, [], []

with httpx.Client(base_url="http://127.0.0.1:8767", timeout=30) as client:
    for identity, node in nodes.items():
        result = client.get(f"/api/campaigns/{campaign['id']}/trials/{identity}/source",
                            params={"path": "src/main.cpp"}).raise_for_status().json()
        content = result["content"]
        (source_dir / (identity + ".cpp")).write_text(content, encoding="utf8")
        sources[identity] = hashlib.sha256(content.encode()).hexdigest()

for identity, node in nodes.items():
    parent = nodes.get(node["parent"])
    if parent:
        inheritance.append({"child": identity, "parent": parent["id"],
            "base_matches_parent": node["base_commit"] == parent["commit"],
            "source_changed": sources[identity] != sources[parent["id"]],
            "child_correct": node["correct"]})

def numbers(value):
    return [float(n) for n in re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", value)]

def same(first, second):
    return len(first) == len(second) and all(abs(a-b) < 1e-7 for a,b in zip(first,second))

for tree in campaign["trees"]:
    rendered = next(t for t in dom if t["title"] == "Arbre " + tree["id"])
    points = {n["id"]: numbers(n["transform"]) for n in rendered["nodes"]}
    baseline = numbers(rendered["baseline"])
    paths = [numbers(p) for p in rendered["edges"]]
    checks = []
    for node in tree["nodes"]:
        incoming = [p for p in paths if same(p[-2:], points[node["id"]])]
        expected_parent = points[node["parent"]] if node["parent"] else baseline
        checks.append({"child": node["id"], "parent": node["parent"],
            "one_incoming_edge": len(incoming) == 1,
            "correct_endpoint": len(incoming) == 1 and same(incoming[0][:2], expected_parent)})
    display.append({"tree": tree["id"], "nodes_match": set(points) == {n["id"] for n in tree["nodes"]},
        "edge_count_matches": len(paths) == len(tree["nodes"]), "edges": checks})

valid_child_counts = Counter(n["parent"] for n in nodes.values() if n["parent"] and n["correct"])
tests = {
    "mission_completed": mission["state"] == "completed",
    "pipeline_complete": campaign["pipeline_complete"],
    "multiple_generations": any(t["max_depth"] >= 2 for t in lineage["trees"]),
    "candidate_has_multiple_valid_children": any(n >= 2 for n in valid_child_counts.values()),
    "no_missing_parents_or_cycles": all(not t["missing_parents"] and not t["cycles"] for t in lineage["trees"]),
    "descendants_inherit_parent_commit": bool(inheritance) and all(i["base_matches_parent"] for i in inheritance),
    "at_least_one_changed_correct_descendant": any(i["source_changed"] and i["child_correct"] for i in inheritance),
    "display_matches_registry": all(t["nodes_match"] and t["edge_count_matches"]
        and all(e["one_incoming_edge"] and e["correct_endpoint"] for e in t["edges"]) for t in display),
    "model_and_effort": campaign["model"] == "gpt-6-luna" and campaign["effort"] == "max",
}
report = {"checks": tests, "passed": all(tests.values()), "search_nodes": len(nodes),
    "correct_search_nodes": sum(n["correct"] is True for n in nodes.values()),
    "unique_source_programs": len(set(sources.values())), "source_sha256": sources,
    "inheritance": inheritance, "display": display,
    "branching_parents": {p: count for p, count in valid_child_counts.items() if count >= 2}}
(root / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
print(json.dumps({k:v for k,v in report.items() if k not in {"source_sha256", "inheritance", "display"}}, ensure_ascii=False))
if not report["passed"]:
    raise SystemExit(1)
