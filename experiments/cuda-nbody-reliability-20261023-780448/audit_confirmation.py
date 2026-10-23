"""Recompute downloaded CUDA confirmation logs without invoking any model or GPU."""
import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path, PurePosixPath
from statistics import mean


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def audit(campaign, registry=None):
    campaign = campaign.resolve(strict=True)
    database = registry.resolve(strict=True) if registry else campaign / "registry.sqlite3"
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("BEGIN")
    try:
        metadata = {r["key"]: json.loads(r["value"]) for r in connection.execute("SELECT * FROM metadata")}
        epoch = metadata["current_epoch"]
        confirmations = []
        hashes = {}
        for row in connection.execute(
            "SELECT experiment_id,payload FROM evaluations WHERE epoch=? AND phase='confirmation'", (epoch,)
        ):
            outcome = json.loads(row["payload"])
            samples = []
            correctness = None
            for name in outcome["logs"]:
                parts = PurePosixPath(name).parts
                path = campaign.joinpath(*parts[parts.index("logs"):]).resolve(strict=True)
                if campaign not in path.parents:
                    raise ValueError("Log path escapes the downloaded campaign")
                hashes[path.relative_to(campaign).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
                if path.name == "correctness.log":
                    correctness = read(path)
                    assert correctness["correct"] is True and correctness["cases"] == 11
                    assert correctness["phase"] == "confirmation"
                    assert all(r["ok"] is True and r["mass_exact"] is True for r in correctness["details"])
                if path.name.startswith("sample-"):
                    sample = read(path)
                    assert sample["correct"] is True and sample["phase"] == "confirmation"
                    assert sample["metric"] == "geomean_cuda_event_seconds" and sample["cases"] == 3
                    assert sample["warmup_launches"] == 10 and sample["timed_launches_per_size"] == 100
                    assert [r["n"] for r in sample["details"]] == [4096, 8192, 16384]
                    assert all(r["ok"] is True and r["mass_exact"] is True for r in sample["details"])
                    seconds = math.exp(mean(math.log(r["latency_ms"] / 1000) for r in sample["details"]))
                    assert math.isclose(seconds, sample["seconds"], rel_tol=1e-12, abs_tol=0)
                    samples.append(seconds)
            assert correctness is not None and len(samples) == len(outcome["times"]) == 5
            assert all(math.isclose(a, b, rel_tol=1e-12, abs_tol=0)
                       for a, b in zip(samples, outcome["times"], strict=True))
            assert math.isclose(mean(samples), outcome["mean_seconds"], rel_tol=1e-12, abs_tol=0)
            confirmations.append({"id": row["experiment_id"], "commit": outcome["commit"],
                                  "samples": samples, "mean_seconds": mean(samples), "correct": outcome["correct"]})
        assert confirmations
        trials = [dict(r) for r in connection.execute("SELECT id,role,created,result,mission FROM trials WHERE epoch=?", (epoch,))]
        for trial in trials:
            trial["result"] = json.loads(trial["result"] or "{}")
            trial["mission"] = json.loads(trial["mission"])
        closed = metadata[f"search_closed:{epoch}"]
        assert all(t["created"] <= closed for t in trials if t["role"] != "G")
        forest = metadata[f"forest_plan:{epoch}"]
        roles = [r["role"] for r in forest["children"]]
        trees = []
        for role in roles:
            own = [t for t in trials if t["role"] == role]
            valid = [t for t in own if t["result"].get("correct") is True and t["result"].get("mean_seconds")]
            trees.append({"role": role, "admitted": len(own), "valid": len(valid),
                          "incorrect": sum(t["result"].get("correct") is False for t in own),
                          "unmeasured": sum(t["result"].get("correct") is None for t in own),
                          "best_search_ms": min((t["result"]["mean_seconds"] * 1000 for t in valid), default=None),
                          "max_depth": max((t["mission"]["depth"] for t in own), default=0)})
        post = metadata[f"postprocess:{epoch}"]
        result = {"epoch": epoch, "registry_sha256": before, "confirmations": confirmations,
                  "confirmation_log_hashes": hashes, "trees": trees, "postprocess": post,
                  "plan_review": metadata.get(f"mother_plan_review:{epoch}"),
                  "search_seconds": closed - metadata["started"],
                  "total_seconds": metadata[f"pipeline_finished:{epoch}"] - metadata["started"],
                  "budget_seconds": metadata["config"]["budget"]["wall_seconds"],
                  "no_research_after_closure": True,
                  "same_mother": all(s["mother"]["conversation"]["thread_id"] == forest["conversation"]["thread_id"]
                                     for s in post["steps"])}
    finally:
        connection.close()
    assert before == hashlib.sha256(database.read_bytes()).hexdigest()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--registry", type=Path, help="Registry archived separately from the logs")
    args = parser.parse_args()
    result = audit(args.campaign, args.registry)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"confirmations": len(result["confirmations"]), "trees": result["trees"],
                      "total_seconds": result["total_seconds"]}))
