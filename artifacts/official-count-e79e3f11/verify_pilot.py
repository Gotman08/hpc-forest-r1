"""Read-only evidence audit after this owned pilot has finished."""
import hashlib
import importlib.util
import json
import re
import sqlite3
import statistics
import sys
import zipfile
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parent
project = root.parent.parent
sys.path.insert(0, str(project / "src"))
from hpc_forest.core import digest

load = lambda p: json.loads(p.read_text(encoding="utf8"))
result = load(root / "romeo-results.json")
assert result["pipeline_complete"] and result["search_policy"] == "binary-greedy"
assert result["search"]["status"] == "search_complete"
assert Counter(row["role"] for row in result["trials"]) == {k: 2 for k in "ABCG"}
assert result["topology"]["max_children"] <= 2
for tree in result["topology"]["trees"]:
    assert all(not n.get("pruned") or n["child_count"] == 0 for n in tree["nodes"])
    assert len(tree["decisions"]) == 1
missions = [json.loads(row["mission"]) for row in result["trials"]]
for role in "ABCG":
    pair = [m for m in missions if m["role"] == role]
    assert pair[0]["parent_id"] == pair[1]["parent_id"]
    assert pair[0]["base_commit"] == pair[1]["base_commit"]

best = result["best_confirmed"]
with sqlite3.connect((root / "registry.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    evaluations = {r[0]: json.loads(r[1]) for r in db.execute(
        "SELECT experiment_id,payload FROM evaluations WHERE phase='confirmation'")}
winner = evaluations[best["experiment_id"]]
assert winner["correct"] is True and winner["commit"] == best["commit"]
assert digest(winner) == best["evaluation_digest"]
assert statistics.mean(winner["times"]) == best["mean_seconds"]
assert evaluations["baseline-e1"]["mean_seconds"] == best["reference_seconds"]
assert 1 - best["mean_seconds"] / best["reference_seconds"] == best["improvement_fraction"]

calls, isolated, review, diagnostics = [], [], [], []
tokens = 0
for path in sorted((root / "worker").glob("*/request.json")):
    request, response = load(path), load(path.parent / "response.json")
    invocation = load(path.parent / "invocation.json")
    assert request == load(path.parent / "downloaded-request.json")
    assert response["request_sha256"] == hashlib.sha256((path.parent / "downloaded-request.json").read_bytes()).hexdigest()
    assert request["model"] == response["model"] == invocation["model"] == "gpt-6-luna"
    assert request["reasoning_effort"] == response["reasoning_effort"] == invocation["reasoning_effort"] == "max"
    assert request["session_id"] == response["session_id"] == result["session_id"]
    assert request["nonce"] == response["nonce"] and not response.get("error")
    assert (path.parent / "delivered.json").is_file()
    assert response["usage"]["token_accounting"] == "exact"
    assert not response["usage"].get("tool_events")
    tokens += response["usage"]["tokens"]
    events = []
    for line in (path.parent / "codex.jsonl").read_text(encoding="utf8").splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            diagnostics.append({"request": path.parent.name, "line": line})
    assert not any(any(word in e.get("item", {}).get("type", "") for word in
                      ("tool", "command_execution", "web_search", "collab", "mcp", "file_change")) for e in events)
    user, _ = json.JSONDecoder().raw_decode(request["messages"][-1]["content"])
    role = user.get("role")
    if role in ("A", "B", "C"):
        context = user["context_as_data"]
        observed = context["automatic_observations"]
        assert not request["integration_source_ids"] and not context["sources"] and not context["interactions"]
        assert observed["selected_parent"] is None
        assert not observed["recent_own_role"] and not observed["own_role_history"]
        isolated.append({"role": role, "ordinal": user["ordinal"], "request": path.parent.name,
                         "sibling_sources_shared": False, "peer_feedback_shared": False})
    for source in response.get("data", {}).get("files", []):
        terms = re.findall(r"https?://|\b(?:system|popen|socket|connect|curl|wget|execve|fork)\s*\(", source["content"], re.I)
        if terms:
            review.append({"request": path.parent.name, "path": source["path"], "terms": terms})
    calls.append({"role": role or request.get("meta_role"), "mission_id": request["mission_id"],
                  "tokens": response["usage"]["tokens"], "model": request["model"],
                  "effort": request["reasoning_effort"], "tool_events": []})
assert tokens == result["costs"]["exact_tokens_used"] == result["costs"]["tokens_used"]
assert result["costs"]["unknown_usage_calls"] == result["costs"]["bounded_usage_calls"] == 0

spec = importlib.util.spec_from_file_location("tree_compare", project / "tools/compare_tree_reports.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
comparison = module.compare(load(project / "artifacts/official-count-5f1e1aa8/experiments.json"),
                            load(root / "experiments.json"))
assert comparison["comparison_admissible"], comparison
with zipfile.ZipFile(root / "submission.zip") as archive:
    manifest = json.loads(archive.read("HPC_FOREST_MANIFEST.json"))
    assert manifest["commit"] == best["commit"] and manifest["search_policy"] == "binary-greedy"
    assert digest(manifest["confirmation"]) == best["evaluation_digest"]
    (root / "winner-source.cpp").write_bytes(archive.read("src/solution.cpp"))
audit = {"pipeline_complete_rechecked": True, "sqlite_integrity": "ok",
         "confirmation_digest_verified": True, "native_calls": len(calls), "exact_tokens": tokens,
         "tool_events": 0, "all_models_luna_max": True, "ABC_contexts_isolated": True,
         "trial_statuses": dict(Counter(json.loads(r["result"])["status"] for r in result["trials"])),
         "source_review_terms": review, "native_diagnostics": diagnostics,
         "topology": result["topology"], "best_confirmed": best,
         "comparison": comparison, "calls": calls, "isolated_requests": isolated,
         "scope": "One pair per tree; deeper traversal tested locally. Provider internals are not observable."}
for name, obj in (("audit.json", audit), ("comparison.json", comparison)):
    (root / name).write_text(json.dumps(obj, indent=2) + "\n", encoding="utf8")
print(json.dumps({k: v for k, v in audit.items() if k not in ("calls", "isolated_requests", "topology")}, indent=2))
