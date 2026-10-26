"""Remeasure delivered winners after all paired searches have stopped."""
from __future__ import annotations

import argparse
import json
import os
import platform
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from run_pair import evaluator_class

from hpc_forest.config import load_config
from hpc_forest.controller import create_workspace
from hpc_forest.core import atomic_json, file_digest
from hpc_forest.gitops import git
from hpc_forest.registry import Registry


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, nargs="+", required=True)
    parser.add_argument("--previous-pairs", type=Path, nargs="*", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    affinity = sorted(os.sched_getaffinity(0))
    if len(affinity) != 5 or not os.environ.get("SLURM_JOB_ID") or platform.machine() != "x86_64":
        raise RuntimeError("A five-CPU x86 ROMEO allocation is required")
    args.output.mkdir(exist_ok=False)
    plans = [(p, read(p / "pair.json"), read(p / "pair-results.json"), prefix)
             for prefix, paths in (("", args.pairs), ("prior-", args.previous_pairs)) for p in paths]
    if any(len(results) != 2 or not (p / "exit-code.txt").exists() for p, _, results, _ in plans):
        raise RuntimeError("All study pairs must have terminated before common remeasurement")
    atomic_json(args.output / "allocation.json", {"job_id": os.environ["SLURM_JOB_ID"],
        "host": platform.node(), "affinity": affinity, "machine": platform.machine(),
        "shared_node_not_exclusive": True, "concurrent_study_searches": 0})
    output = {}
    for case in ("utf8", "mandelbrot"):
        members = [(p, plan, results, prefix) for p, plan, results, prefix in plans if plan["case"] == case]
        pair, plan, _, _ = members[0]
        os.sched_setaffinity(0, affinity[:1] if case == "utf8" else affinity[:4])
        for _, other, _, _ in members:
            if other["protected_inputs"] != plan["protected_inputs"]:
                raise RuntimeError("Compared pairs have different protected inputs")
        for name, sha in plan["protected_inputs"].items():
            if file_digest(pair / "inputs" / name) != sha:
                raise RuntimeError("Protected comparison input changed")
        cfg = load_config(pair / "settings.json")
        cfg["advisor"]["enabled"] = False
        cfg["target_id"] = "tabpfn-common-remeasure-" + case + "-" + os.environ["SLURM_JOB_ID"]
        cfg["seed"] = 20261025
        root = create_workspace(args.output / case, cfg, pair / "inputs/source", pair / "inputs/validation")
        candidates = [{"id": "naive", "worktree": str(root / "repo"),
                       "commit": git(root / "repo", "rev-parse", "HEAD"), "baseline": True}]
        excluded = []
        for source_pair, member, results, prefix in members:
            for result in results:
                identity = prefix + "r" + str(member["repeat"]) + "-" + result["condition"]
                if not result.get("pipeline_complete") or not result.get("finished_within_cap"):
                    excluded.append({"id": identity, "reason": result.get("error", "no confirmed delivery within cap")})
                    continue
                arm_root = source_pair / ("forest-app-" + result["id"])
                commit = result["best_confirmed"]["commit"]
                target = args.output / ("source-" + case + "-" + identity)
                git(arm_root / "campaign/repo", "worktree", "add", "--detach", str(target), commit)
                candidates.append({"id": identity, "worktree": str(target), "commit": commit,
                                   "source_pair": member["pair_id"], "prior_study": bool(prefix)})
        with closing(Registry(root / "registry.sqlite3")) as db:
            evaluator = evaluator_class(pair / "inputs")(root, db.get("config"), db.get("manifest"),
                                                         db.get("protocol_id"), None)
            outcomes = {key: asdict(value) for key, value in evaluator.confirm(candidates, 1).items()}
        naive = outcomes["naive"]
        for result in outcomes.values():
            result["speedup"] = (naive["mean_seconds"] / result["mean_seconds"]
                if naive["status"] == result["status"] == "valid" and result["correct"] is True else None)
        output[case] = {"outcomes": outcomes, "candidates": candidates, "excluded": excluded,
            "program_affinity": sorted(os.sched_getaffinity(0)), "protected_inputs": plan["protected_inputs"]}
        atomic_json(args.output / "common-measurements.json", output)
    print(json.dumps({case: {key: {"seconds": value["mean_seconds"], "speedup": value["speedup"]}
                     for key, value in data["outcomes"].items()} for case, data in output.items()}))


if __name__ == "__main__":
    main()

