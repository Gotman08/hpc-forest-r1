"""Remeasure delivered winners after all paired searches have stopped."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
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
    parser.add_argument("--heldout-protocol", type=Path)
    parser.add_argument("--heldout-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    affinity = sorted(os.sched_getaffinity(0))
    if len(affinity) != 5 or not os.environ.get("SLURM_JOB_ID") or platform.machine() != "x86_64":
        raise RuntimeError("A five-CPU x86 ROMEO allocation is required")
    args.output.mkdir(exist_ok=False)
    heldout = None
    if args.heldout_protocol:
        if not args.heldout_sha256 or file_digest(args.heldout_protocol) != args.heldout_sha256:
            raise RuntimeError("Reserved-input registration changed")
        heldout = read(args.heldout_protocol)
    distribution = "reserved" if heldout else "registered"
    plans = [(p, read(p / "pair.json"), read(p / "pair-results.json"), "") for p in args.pairs]
    if any(len(results) != 2 or not (p / "exit-code.txt").exists() for p, _, results, _ in plans):
        raise RuntimeError("All study pairs must have terminated before common remeasurement")
    atomic_json(args.output / "allocation.json", {"job_id": os.environ["SLURM_JOB_ID"],
        "host": platform.node(), "affinity": affinity, "machine": platform.machine(),
        "shared_node_not_exclusive": True, "concurrent_study_searches": 0,
        "distribution": distribution, "heldout_sha256": args.heldout_sha256})
    output = {}
    for case in sorted({plan["case"] for _, plan, _, _ in plans}):
        members = [(p, plan, results, prefix) for p, plan, results, prefix in plans if plan["case"] == case]
        pair, plan, _, _ = members[0]
        public_case = read(pair / "inputs/validation/case.json")
        os.sched_setaffinity(0, affinity[:public_case["threads"]])
        for _, other, _, _ in members:
            if other["protected_inputs"] != plan["protected_inputs"]:
                raise RuntimeError("Compared pairs have different protected inputs")
        for name, sha in plan["protected_inputs"].items():
            if file_digest(pair / "inputs" / name) != sha:
                raise RuntimeError("Protected comparison input changed")
        cfg = load_config(pair / "settings.json")
        cfg["advisor"]["enabled"] = False
        cfg["target_id"] = "diversified-" + distribution + "-" + case + "-" + os.environ["SLURM_JOB_ID"]
        cfg["seed"] = 20261025
        validation = pair / "inputs/validation"
        if heldout:
            validation = args.output / ("reserved-validation-" + case)
            shutil.copytree(pair / "inputs/validation", validation)
            atomic_json(validation / "case.json", heldout[case])
        root = create_workspace(args.output / case, cfg, pair / "inputs/source", validation)
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
            "program_affinity": sorted(os.sched_getaffinity(0)), "protected_inputs": plan["protected_inputs"],
            "evaluation_case": read(validation / "case.json"), "distribution": distribution,
            "no_reselection_on_reserved_results": True}
        atomic_json(args.output / "common-measurements.json", output)
    print(json.dumps({case: {key: {"seconds": value["mean_seconds"], "speedup": value["speedup"]}
                     for key, value in data["outcomes"].items()} for case, data in output.items()}))


if __name__ == "__main__":
    main()

