"""ROMEO owns TreeQuest and evaluations; the local authenticated Codex worker proposes source."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import socket
import time
import traceback
from pathlib import Path

import evidence_pack
import romeo_base as base
import romeo_marathon as reference
from prepare_problem import prepare_problem

from hpc_forest import codex_mailbox
from hpc_forest.codex_mailbox import (
    EFFORT,
    MODEL,
    TOKEN_CEILING,
    CodexMailboxBackend,
    initialize_channel,
)
from hpc_forest.controller import create_workspace
from hpc_forest.core import atomic_json
from hpc_forest.knowledge import Knowledge
from hpc_forest.reporting import package, report

ROOT = Path(__file__).resolve().parent
CHANNEL = None
SESSION_ID = None
HARNESS = None
extract_official = reference.extract_official


def config_for(url, slug, target, prepared):
    c = reference.config_for(url, slug, target, prepared)
    c["backend"] = "codex"
    c.pop("ollama", None)
    c["codex"] = {"model": MODEL, "reasoning_effort": EFFORT,
                  "transport": "codex-mailbox", "mailbox_dir": str(CHANNEL),
                  "session_id": SESSION_ID}
    c["budget"]["mission_tokens"] = TOKEN_CEILING
    if HARNESS is not None:
        c["harness"] = json.loads(json.dumps(HARNESS))
        if c["harness"].get("enabled"):
            if c["harness"].get("call_token_ceiling") != TOKEN_CEILING:
                raise ValueError("Codex harness calls must reserve the native service ceiling")
            c["budget"]["mission_tokens"] = c["harness"]["max_attempts"] * TOKEN_CEILING
    return c


class CodexController(reference.AutonomousController):
    def __init__(self, root, statement):
        super().__init__(root, statement)
        self.backend = CodexMailboxBackend()


def campaign(url, slug, output, target):
    root = output / slug
    started = time.monotonic()
    result = {"problem": slug, "model": MODEL, "campaign": str(root), "complete": False}
    try:
        official = extract_official(slug, output)
        base.emit("operator_preparation_start", problem=slug)
        prepared = prepare_problem(slug, official, output)
        result["preparation"] = prepared
        base.emit(
            "operator_preparation_ready",
            problem=slug,
            benchmark_seconds=prepared["benchmark_reference_seconds"],
            search_cases=prepared["search_cases"],
            confirmation_cases=prepared["confirmation_cases"],
        )
        settings = config_for(url, slug, target, prepared)
        result["identity"] = {
            "model": MODEL, "reasoning_effort": EFFORT,
            "transport": "codex-mailbox", "hosted_inference": True,
            "weight_digest_available": False,
        }
        statement = (ROOT / "sources-officielles/problemset.txt").read_text(
            encoding="utf-8"
        )
        create_workspace(
            root,
            settings,
            source=Path(prepared["source"]),
            validation=Path(prepared["validation"]),
        )
        with CodexController(root, statement) as controller:
            with controller.db.connection:
                controller.db.connection.execute(
                    "DELETE FROM documents WHERE url=?", ("local:matmul-training-task",)
                )
            Knowledge(controller.db).add(
                "Official problem statement",
                "http://lspd.mackenzie.br/marathon/22/problemset.pdf",
                "downloaded-2026-10-15",
                statement,
                "Official source material. Operator supplies execution only.",
            )
            controller.db.event(
                "neutral_codex_mailbox_adapter",
                {
                    "files": {
                        p.name: base.sha256(p)
                        for p in [
                            ROOT / "romeo_codex.py",
                            Path(codex_mailbox.__file__),
                            ROOT / "prepare_problem.py",
                        ]
                    },
                    "operator_algorithm_changes": 0,
                    "manual_candidate_repairs": 0,
                    "operator_prepared": True,
                },
            )
            while True:
                result["search"] = controller.run(max_batches=1)
                topology = base.tree_snapshot(controller)
                topology["problem"] = slug
                atomic_json(output / f"{slug}-progress.json", topology)
                with (output / "topology-events.jsonl").open(
                    "a", encoding="utf-8"
                ) as stream:
                    stream.write(json.dumps(topology) + "\n")
                base.emit(
                    "tree_progress",
                    problem=slug,
                    **{
                        k: topology[k]
                        for k in [
                            "status",
                            "cursor",
                            "trials",
                            "scored_nodes",
                            "max_depth",
                            "max_children",
                            "tokens_used",
                        ]
                    },
                )
                if result["search"]["status"] != "checkpointed":
                    break
            result["best_confirmed"] = controller.confirm()
            result["search_complete"] = result["search"]["status"] == "search_complete"
            result["costs"] = controller.db.costs()
            result["generation_usage"] = [
                json.loads(r["payload"])
                for r in controller.db.rows(
                    "SELECT payload FROM events WHERE kind='generation_usage' ORDER BY id"
                )
            ]
            result["trials"] = [
                {
                    "id": r["id"],
                    "role": r["role"],
                    "outcome": json.loads(r["result"]) if r["result"] else None,
                }
                for r in controller.db.rows(
                    "SELECT id,role,result FROM trials ORDER BY created,id"
                )
            ]
        result["report"] = str(report(root))
        result["package"] = str(package(root, root / "submission.zip"))
        result["package_sha256"] = base.sha256(root / "submission.zip")
        result["pipeline_complete"] = True
        result["complete"] = result["search_complete"]
    except Exception as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
        result["traceback"] = traceback.format_exc()
        if (root / "registry.sqlite3").is_file():
            try:
                report(root)
            except Exception:
                result["report_error"] = traceback.format_exc()
    finally:
        result["elapsed_seconds"] = time.monotonic() - started
        atomic_json(output / f"{slug}-summary.json", result)
        base.emit(
            "problem_end",
            problem=slug,
            complete=result["complete"],
            error=result.get("error"),
            best=result.get("best_confirmed"),
        )
    return result



def main():
    global ROOT, CHANNEL, SESSION_ID, HARNESS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--problems", nargs="+", choices=["knn", "sum", "nbody"], default=["knn", "sum", "nbody"])
    parser.add_argument("--worker-wait-seconds", type=int, default=180)
    parser.add_argument("--cycles", type=int, default=4)
    parser.add_argument("--trials-per-role", type=int, default=6)
    parser.add_argument("--integrations-per-cycle", type=int, default=6)
    parser.add_argument("--wall-seconds", type=int, default=21600)
    parser.add_argument("--tokens", type=int, default=4000000)
    parser.add_argument("--node-harness-config", type=Path,
                        help="Optional new-campaign harness JSON; never modifies an existing campaign")
    args = parser.parse_args()
    job = os.environ.get("SLURM_JOB_ID", "")
    if not job.isdigit() or platform.machine().lower() not in {"aarch64", "arm64"}:
        parser.error("This campaign requires its own ARM64 Slurm CPU allocation")
    ROOT = args.root.resolve(strict=True)
    if args.node_harness_config:
        HARNESS = json.loads(args.node_harness_config.read_text(encoding="utf8"))
        research = HARNESS.get("research", {})
        if research.get("corpus"):
            research["corpus"] = str((args.node_harness_config.parent / research["corpus"]).resolve(strict=True))
    reference.ROOT = ROOT
    if min(args.cycles, args.trials_per_role, args.integrations_per_cycle,
           args.wall_seconds, args.tokens) <= 0:
        parser.error("Campaign limits must be positive")
    reference.SCHEDULE.update(cycles=args.cycles, trials_per_role_per_cycle=args.trials_per_role,
                              integrations_per_cycle=args.integrations_per_cycle)
    reference.LIMITS.update(wall_seconds=args.wall_seconds, tokens=args.tokens, generation_seconds=600)
    SESSION_ID = args.session_id
    output = ROOT / f"results-{job}"
    output.mkdir(exist_ok=False)
    CHANNEL = output / "mailbox"
    initialize_channel(CHANNEL, SESSION_ID, job)
    atomic_json(output / "channel.json", {"channel": str(CHANNEL), "session_id": SESSION_ID,
                "job_id": job, "model": MODEL, "reasoning_effort": EFFORT})
    base.emit("codex_mailbox_ready", channel=str(CHANNEL), session_id=SESSION_ID, job_id=job)
    result = {"format": "hpc-forest-marathon22-gpt61sol-max-v1", "job_id": job,
              "model": MODEL, "reasoning_effort": EFFORT, "complete": False, "problems": []}
    try:
        if importlib.metadata.version("treequest") != "0.3.2":
            raise RuntimeError("Unexpected TreeQuest version")
        baseline = json.loads((ROOT / "runtime-baseline.json").read_text(encoding="utf8"))
        package_root = Path(codex_mailbox.__file__).parent
        for name, digest in baseline.items():
            if base.sha256(package_root / name) != digest:
                raise RuntimeError("Frozen controller/runtime fingerprint changed: " + name)
        ready = CHANNEL / "worker-ready.json"
        deadline = time.monotonic() + args.worker_wait_seconds
        while not ready.exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("No local authenticated Codex worker connected")
            time.sleep(0.5)
        worker = codex_mailbox.bounded_json(ready, 16384)
        if any(worker.get(k) != value for k, value in {
            "model": MODEL, "reasoning_effort": EFFORT, "session_id": SESSION_ID, "mode": "codex",
        }.items()):
            raise RuntimeError("Wrong model worker or transport-smoke worker")
        atomic_json(output / "model-identity.json", {**worker, "weight_digest_available": False})
        target = f"romeo:{socket.gethostname()}:slurm-{job}:cpu-marathon22"
        for slug in args.problems:
            result["problems"].append(campaign("codex-mailbox", slug, output, target))
            atomic_json(output / "results.json", result)
        result["complete"] = all(p["complete"] for p in result["problems"])
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
        base.emit("runner_error", error=result["error"])
    finally:
        atomic_json(output / "results.json", result)
        atomic_json(output / "cleanup.json", {"no_model_weights_on_romeo": True,
                    "no_local_process_started_by_remote_runner": True})
        archive = ROOT / f"results-{job}.tar.gz"
        evidence_pack.make(output, ROOT / "sources-officielles", archive)
        base.emit("runner_end", complete=result["complete"], archive=str(archive), sha256=base.sha256(archive))
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
