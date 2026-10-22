"""Read preserved evidence without changing the engine or campaign databases."""
import difflib
import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[1]
WORK = (PROJECT / "../../work").resolve()
RUNS = {
    "776048": WORK / "cuda-memory-budget-final-20261022-5f2930cb",
    "776290": WORK / "cuda-memory-budget-decision-20261022-402d6d6d-run",
}


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def small_card(item):
    return {key: item.get(key) for key in ("id", "role", "kind", "measured_outcome")}


def campaign(job):
    delivery = PROJECT / f"experiments/cuda-nbody-memory-budget-20261022-{job}"
    path = delivery / "registry.sqlite3"
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    metadata = {row["key"]: json.loads(row["value"])
                for row in connection.execute("SELECT * FROM metadata")}
    post = metadata["postprocess:1"]
    timings = metadata["timing_samples"]["memory_selection"]
    assert len(timings) == len(post["selections"])
    usage = [json.loads(row["payload"]) for row in connection.execute(
        "SELECT payload FROM events WHERE kind='memory_selection_usage' ORDER BY id")]
    decisions = {entry["selection_id"]: entry["assembly_decision"] for entry in usage}
    selections = []
    for entry, elapsed in zip(post["selections"], timings):
        selections.append({
            "id": entry["id"], "round": entry["round"], "status": entry["status"],
            "seconds": elapsed, "error": entry.get("error"),
            "raw_decision": decisions[entry["id"]],
            "read_cards": [small_card(item) for item in entry.get("read_result", {}).get("items", [])],
        })
    pages = {}
    for number in (1, 2):
        page = read(WORK / f"m{job}/logs/memory-select-e1-r{number}/memory-context.json")
        pages[str(number)] = [small_card(item) for item in page["page"]["items"]]
    trials = []
    for row in connection.execute("SELECT * FROM trials ORDER BY created"):
        mission, result = json.loads(row["mission"]), json.loads(row["result"])
        trials.append({"id": row["id"], "role": row["role"],
            "ordinal": mission["ordinal"], "depth": mission["depth"],
            "admitted_seconds": row["created"] - metadata["started"],
            "result": {key: result.get(key) for key in (
                "status", "correct", "mean_seconds", "reason", "commit", "tree_hash")}})
    integrations = []
    for step in post["steps"]:
        result = next(t["result"] for t in trials if t["id"] == step["mission_id"])
        difference = subprocess.run([
            "git", "-C", str(WORK / f"m{job}/repo"), "diff", step["input_commits"][0],
            result["commit"], "--", "src/nbody_kernel.cu", "src/launch.json",
        ], capture_output=True, text=True, encoding="utf8", check=True).stdout
        integrations.append({"id": step["mission_id"], "selection": step["selection"],
            "result": result, "diff_from_base": difference})
    connection.close()
    return {"job": job, "registry_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "planning_analysis": metadata["mother_plan:preparation:1"]["plan"]["analysis"],
        "children": metadata["forest_plan:1"]["children"], "trials": trials,
        "initial_selection_pages": pages, "selections": selections,
        "selection_seconds": sum(timings),
        "rejected_selection_seconds": sum(s["seconds"] for s in selections if s["status"] == "rejected"),
        "integrations": integrations, "audit": read(delivery / "audit.json")}


manifests = {job: read(run / "runtime-manifest.json") for job, run in RUNS.items()}
changed = [name for name in sorted(set(manifests["776048"]) | set(manifests["776290"]))
           if manifests["776048"].get(name) != manifests["776290"].get(name)]
diffs = {}
for name in changed:
    contents = [(run / "payload" / name).read_text(encoding="utf8").splitlines(True)
                for run in RUNS.values()]
    diffs[name] = "".join(difflib.unified_diff(*contents, fromfile="776048", tofile="776290"))
requests = {}
for job, run in RUNS.items():
    requests[job] = next(request for path in (run / "worker").glob("*/request.json")
        if (request := read(path))["mission_id"].startswith("mother-preparation-"))
a, b = requests.values()
ua, ub = [json.loads(request["messages"][1]["content"]) for request in (a, b)]
comparison = read(PROJECT / "experiments/cuda-nbody-memory-budget-20261022-776290/comparison.json")
old, new = comparison["campaigns"][-2:]
result = {
    "scope": "Read-only comparison of preserved campaigns; no new GPU measurement or engine edit",
    "payload_changed_files": changed, "payload_diffs": diffs,
    "initial_input": {"system_identical": a["messages"][0] == b["messages"][0],
        "schema_identical": a["schema"] == b["schema"],
        "skills_identical": a["model_skills"] == b["model_skills"],
        "components_identical": {key: ua.get(key) == ub.get(key) for key in sorted(ua.keys() | ub.keys())},
        "remaining_differences": "Measured baseline, campaign IDs/commits/paths and target label differ; same source tree, baseline binary and GH200/CUDA specification."},
    "metrics": {"final_time_ratio": new["best_confirmed_seconds"] / old["best_confirmed_seconds"],
        "preintegration_time_ratio": min(t["best_search_seconds"] for t in new["tree_details"]) /
                                     min(t["best_search_seconds"] for t in old["tree_details"]),
        "baseline_change_percent": 100 * (new["baseline_seconds"] / old["baseline_seconds"] - 1),
        "research_closure_difference_seconds": new["research_closed_seconds"] - old["research_closed_seconds"]},
    "campaigns": [campaign(job) for job in RUNS],
    "limitations": ["One independent run per version does not estimate outcome probabilities.",
        "Structural kernel comparison is not a hardware profiling study.",
        "Correcting retrieval/selection does not establish that the missing optimization will be rediscovered.",
        "Recommendations are generic system changes, not implemented by this analysis."],
}
(OUT / "evidence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
print(json.dumps({"file": str(OUT / "evidence.json"), "metrics": result["metrics"],
                  "changed": changed, "input": result["initial_input"]}, ensure_ascii=False))
