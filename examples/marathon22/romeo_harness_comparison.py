"""Matched reference/mixed-harness runs; observation never enters model context."""
from __future__ import annotations

import argparse
import copy
import importlib.metadata
import json
import os
import platform
import shutil
import socket
import time
import traceback
from pathlib import Path

import evidence_pack
import romeo_base as base
import romeo_codex as runner

from hpc_forest.codex_mailbox import EFFORT, MODEL, bounded_json, initialize_channel
from hpc_forest.core import atomic_json

ORDER = [("reference", "knn"), ("mixed-harness", "knn"),
         ("mixed-harness", "sum"), ("reference", "sum"),
         ("reference", "nbody"), ("mixed-harness", "nbody")]
SCHEDULE = {"cycles": 2, "trials_per_role_per_cycle": 3, "integrations_per_cycle": 3}
LIMITS = {"wall_seconds": 7200, "tokens": 1500000, "generation_seconds": 600}


class ObservedController(runner.CodexController):
    """Export existing records after batches, without influencing proposals or rewards."""

    def plan(self):
        # The comparison owns one sequential worker. Admit and settle each mission
        # before reserving the next, retaining the exact role order and slot count.
        return [[role] for batch in super().plan() for role in batch]

    def _export_observations(self):
        records = []
        for row in self.db.rows("SELECT id,role,mission,result FROM trials ORDER BY created,id"):
            mission = json.loads(row["mission"])
            record = {"id": row["id"], "role": row["role"], "mission": mission,
                      "outcome": json.loads(row["result"]) if row["result"] else None}
            journal = self.root / "logs" / row["id"] / "node-harness.json"
            if journal.is_file():
                record["harness"] = json.loads(journal.read_text(encoding="utf8"))
            records.append(record)
        path = self.root.parent / f"{self.root.name}-observations-detaillees.json"
        atomic_json(path, {"scope": "passive_post_batch_observation", "never_model_input": True,
                          "problem": self.root.name, "arm": self.root.parent.name,
                          "trials": records, "costs": self.db.costs()})

    def run(self, *args, **kwargs):
        result = super().run(*args, **kwargs)
        self._export_observations()
        return result

    def confirm(self, *args, **kwargs):
        result = super().confirm(*args, **kwargs)
        self._export_observations()
        return result


class MatchedPreparation:
    """Reuse only official-source preparation so both arms receive identical fixed inputs."""

    def __init__(self, prepare):
        self.prepare, self.receipts = prepare, {}

    def __call__(self, slug, official, output):
        destination = output / "preparation" / slug
        if slug not in self.receipts:
            receipt = self.prepare(slug, official, output)
            self.receipts[slug] = (destination, copy.deepcopy(receipt))
            return receipt
        original, receipt = self.receipts[slug]
        shutil.copytree(original, destination)

        def rebase(value):
            if isinstance(value, dict):
                return {k: rebase(v) for k, v in value.items()}
            if isinstance(value, list):
                return [rebase(v) for v in value]
            if isinstance(value, str) and (value == str(original) or value.startswith(str(original) + os.sep)):
                return str(destination) + value[len(str(original)):]
            return value

        receipt = rebase(copy.deepcopy(receipt))
        receipt["matched_official_preparation_origin"] = str(original)
        atomic_json(destination / "operator-preparation.json", receipt)
        return receipt


def verify_worker(channel, session, timeout):
    ready = channel / "worker-ready.json"
    end = time.monotonic() + timeout
    while not ready.exists():
        if time.monotonic() >= end:
            raise RuntimeError("No authenticated local worker connected")
        time.sleep(0.5)
    worker = bounded_json(ready, 16384)
    expected = {"model": MODEL, "reasoning_effort": EFFORT, "session_id": session, "mode": "codex"}
    if any(worker.get(k) != value for k, value in expected.items()):
        raise RuntimeError("The worker identity differs from this comparison")
    return worker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--worker-wait-seconds", type=int, default=600)
    args = parser.parse_args()
    job = os.environ.get("SLURM_JOB_ID", "")
    if not job.isdigit() or platform.machine().lower() not in {"aarch64", "arm64"}:
        parser.error("The comparison requires its own ARM64 Slurm allocation")
    root = args.root.resolve(strict=True)
    output = root / f"results-{job}"
    output.mkdir(exist_ok=False)
    result = {"schema": "hpc-forest-matched-gpt-harness-comparison-v1", "job_id": job,
              "model": MODEL, "reasoning_effort": EFFORT, "order": ORDER,
              "schedule": SCHEDULE, "limits_per_problem_and_arm": LIMITS,
              "seed": 23, "problems": [], "pipeline_complete": False,
              "operator_algorithm_hints": False, "manual_candidate_edits": 0,
              "historical_candidates_imported": False,
              "performance_comparison_replicates": 1,
              "causal_harness_superiority_established": False}
    current_arm = None
    original_emit = base.emit

    def contextual_emit(event, **values):
        original_emit(event, comparison_arm=current_arm, **values)

    base.emit = contextual_emit
    try:
        baseline = json.loads((root / "runtime-baseline.json").read_text(encoding="utf8"))
        package_root = Path(runner.codex_mailbox.__file__).parent
        for name, digest in baseline.items():
            if base.sha256(package_root / name) != digest:
                raise RuntimeError("Frozen runtime differs: " + name)
        if importlib.metadata.version("treequest") != "0.3.2":
            raise RuntimeError("Unexpected TreeQuest version")
        shutil.copyfile(root / "assistance-protocol.json", output / "assistance-protocol.json")
        for name in ("preflight-tests.log", "timer-probe.json", "resources-romeo.json"):
            shutil.copyfile(root / name, output / name)
        atomic_json(output / "arm-order.json", {"order": ORDER, "chosen_before_model_calls": True})
        channel = output / "mailbox"
        initialize_channel(channel, args.session_id, job)
        atomic_json(output / "channel.json", {"channel": str(channel), "session_id": args.session_id,
                    "job_id": job, "model": MODEL, "reasoning_effort": EFFORT})
        base.emit("codex_mailbox_ready", channel=str(channel), session_id=args.session_id, job_id=job)
        worker = verify_worker(channel, args.session_id, args.worker_wait_seconds)
        atomic_json(output / "model-identity.json", worker)
        runner.ROOT = runner.reference.ROOT = root
        runner.CHANNEL, runner.SESSION_ID = channel, args.session_id
        runner.reference.SCHEDULE.update(SCHEDULE)
        runner.reference.LIMITS.update(LIMITS)
        runner.CodexController = ObservedController
        runner.prepare_problem = MatchedPreparation(runner.prepare_problem)
        mixed = json.loads((root / "harness-mixed.json").read_text(encoding="utf8"))
        if (mixed.get("enabled") is not True or mixed.get("max_attempts") != 3
                or mixed.get("call_token_ceiling") != 196608
                or mixed.get("research", {}).get("corpus") is not None):
            raise RuntimeError("The declared mixed harness contract changed")
        target = f"romeo:{socket.gethostname()}:slurm-{job}:cpu-marathon22"
        for arm, slug in ORDER:
            current_arm = arm
            arm_root = output / arm
            arm_root.mkdir(exist_ok=True)
            runner.HARNESS = mixed if arm == "mixed-harness" else None
            base.emit("comparison_arm_start", problem=slug, harness_enabled=runner.HARNESS is not None)
            entry = runner.campaign("codex-mailbox", slug, arm_root, target)
            result["problems"].append({"arm": arm, **entry})
            atomic_json(output / "results.json", result)
        result["pipeline_complete"] = all(p.get("pipeline_complete") for p in result["problems"])
        result["search_complete"] = all(p.get("search_complete") for p in result["problems"])
        result["complete"] = result["pipeline_complete"]
    except Exception as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
        result["traceback"] = traceback.format_exc()
        base.emit("runner_error", error=result["error"])
    finally:
        atomic_json(output / "results.json", result)
        atomic_json(output / "cleanup.json", {"model_weights_on_romeo": False,
                    "candidate_gpus": 0, "remote_runner_starts_local_processes": False})
        archive = root / f"results-{job}.tar.gz"
        evidence_pack.make(output, root / "sources-officielles", archive)
        base.emit("runner_end", complete=result["pipeline_complete"], archive=str(archive),
                  sha256=base.sha256(archive))
    return 0 if result["pipeline_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
