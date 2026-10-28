"""Fresh independent-tree CUDA campaign; never replay a historical payload."""

import argparse
import importlib.metadata
import json
import os
import platform
import sys
import time
import traceback
from pathlib import Path

from cuda_evaluator import CudaEvaluator

from hpc_forest import codex_mailbox
from hpc_forest.adaptive_budget import record_timing
from hpc_forest.config import load_config
from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import BudgetExhausted, InfrastructureError, atomic_json, file_digest
from hpc_forest.memory.contract import guided
from hpc_forest.memory.store import memory_summary
from hpc_forest.native_matrix import install_identity
from hpc_forest.reporting import package, report


def verify(root, manifest):
    for name, expected in manifest.items():
        if file_digest(root / name) != expected:
            raise InfrastructureError("Frozen payload changed: " + name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    plan = json.loads((root / "plan.json").read_text())
    verify(root, json.loads((root / "runtime-manifest.json").read_text()))
    job = os.environ.get("SLURM_JOB_ID", "")
    if (
        not job.isdigit()
        or platform.machine() != "aarch64"
        or not os.environ.get("CUDA_VISIBLE_DEVICES")
        or int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) != 4
        or str(root) != str(Path(plan["remote_root"]).resolve(strict=True))
        or plan["scope"] not in {"cuda-nbody-luna-max-independent-v2", "cuda-nbody-luna-max-memory-v1"}
        or importlib.metadata.version("treequest") != "0.3.2"
    ):
        raise InfrastructureError("Not the owned one-GPU ARM campaign")
    install_identity(plan["model"], plan["effort"])
    import hpc_forest.controller as module

    module.Evaluator = CudaEvaluator
    output = root / ("results-" + job)
    output.mkdir(exist_ok=False)
    channel = output / "mailbox"
    codex_mailbox.initialize_channel(channel, plan["session_id"], job)
    result = {k: plan[k] for k in ("scope", "session_id", "model", "effort", "subject")}
    result.update(
        job_id=job,
        pipeline_complete=False,
        old_candidates_imported=False,
        search_policy="ab-mcts-a",
        metric="geomean_cuda_event_seconds",
        source_sha256=plan["source_sha256"],
        target_seconds=plan["wall_seconds"],
    )
    atomic_json(output / "channel.json", {**result, "channel": str(channel)})
    print("CUDA_CHANNEL_READY", str(channel), flush=True)
    try:
        settings = load_config(root / "settings.json")
        if settings["budget"]["wall_seconds"] != plan["wall_seconds"]:
            raise InfrastructureError("CUDA plan duration differs from the protected settings")
        if (plan["scope"] == "cuda-nbody-luna-max-memory-v1") != guided(settings):
            raise InfrastructureError("CUDA scope differs from its integration policy")
        settings["codex"].update(mailbox_dir=str(channel))
        settings["target_id"] = "romeo-cuda-nbody-" + job
        campaign = create_workspace(
            output / plan["subject"],
            settings,
            source=root / "source",
            validation=root / "validation",
        )
        atomic_json(
            output / "allocation.json",
            {
                "job_id": job,
                "machine": platform.machine(),
                "cpus": int(os.environ["SLURM_CPUS_PER_TASK"]),
                "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
                "python": sys.executable,
                "treequest": importlib.metadata.version("treequest"),
                "preflight": json.loads((root / "cache/preflight.json").read_text()),
                "harness_sha256": file_digest(Path(os.environ["FOREST_CUDA_HARNESS"])),
                "runtime_manifest_sha256": file_digest(root / "runtime-manifest.json"),
            },
        )
        end = time.monotonic() + 600
        while not (channel / "worker-ready.json").exists():
            if time.monotonic() > end:
                raise InfrastructureError("The authorized Luna worker did not connect")
            time.sleep(0.5)
        worker = codex_mailbox.bounded_json(channel / "worker-ready.json", 16384)
        if any(
            worker.get(k) != v
            for k, v in {
                "model": plan["model"],
                "reasoning_effort": plan["effort"],
                "session_id": plan["session_id"],
                "mode": "codex",
            }.items()
        ):
            raise InfrastructureError("Wrong native worker identity")
        with Controller(campaign) as controller:
            with controller.db.connection:
                controller.db.connection.execute("DELETE FROM documents")
            controller.db.event("cuda_nbody_fresh_campaign", result)

            def progress(state):
                result["search"] = state
                result["trials"] = controller.db.rows(
                    "SELECT id,role,state,mission,result FROM trials ORDER BY created,id"
                )
                atomic_json(output / "progress.json", result)
                print("CUDA_PROGRESS", json.dumps(state), flush=True)

            while True:
                try:
                    result["search"] = controller.run(on_progress=progress)
                except BudgetExhausted as exc:
                    controller.db.set("status", "budget_exhausted")
                    controller.db.event("budget_stop", {"reason": str(exc)})
                    result["search"] = controller.status()
                result["trials"] = [
                    dict(row)
                    for row in controller.db.rows(
                        "SELECT id,role,state,mission,result FROM trials ORDER BY created,id"
                    )
                ]
                atomic_json(output / "progress.json", result)
                print("CUDA_PROGRESS", json.dumps(result["search"]), flush=True)
                if result["search"]["status"] != "checkpointed":
                    break
            result["best_confirmed"] = controller.confirm()
            status = controller.status()
            for field in (
                "postprocess",
                "final_g_confirmation",
                "forest_plan",
                "mother_conversation",
                "research_scheduler",
            ):
                result[field] = status.get(field)
            result["costs"] = controller.db.costs()
            result["memory"] = memory_summary(controller.db)
            result["phase_costs"] = {
                phase: controller.db.costs(phase)
                for phase in ("search", "postprocess", "confirmation")
            }
            result["trials"] = [
                dict(row)
                for row in controller.db.rows(
                    "SELECT id,role,state,mission,result FROM trials ORDER BY created,id"
                )
            ]
            start_archive = time.monotonic()
            report(campaign)
            package(campaign, campaign / "submission.zip")
            record_timing(controller.db, "archive", time.monotonic() - start_archive)
            now = time.time()
            result["timing"] = {
                "samples": controller.db.get("timing_samples", {}),
                "admission": controller.db.get("last_admission"),
                "started_at": controller.db.get("started"),
                "target_deadline": controller.db.get("deadline"),
                "confirmation_finished": controller.db.get("confirmation_finished:1"),
                "finished_at": now,
                "overrun_seconds": max(0, now - controller.db.get("deadline")),
            }
            controller.db.set("pipeline_finished:1", now)
        post = result.get("postprocess") or {}
        final = result.get("final_g_confirmation") or {}
        selected = result.get("forest_plan") or {}
        original = selected.get("conversation") or {}
        steps = post.get("steps") or []
        result["verification"] = {
            "forest_chosen": selected.get("status") == "complete",
            "memory_integration_complete" if guided(settings) else "pairwise_complete": post.get("status") == "complete"
            and bool(steps)
            and all(
                step.get("status") == "complete" and 1 <= len(step.get("input_ids", [])) <= (
                    settings["memory"]["sources_per_integration"] if guided(settings) else 2)
                for step in steps
            ),
            "same_mother": bool(original)
            and all(
                (step.get("mother", {}).get("conversation") or {}).get("thread_id")
                == original.get("thread_id")
                for step in steps
            ),
            "final_g_independently_confirmed": final.get("status") == "confirmed"
            and final.get("experiment_id") == post.get("mission_id"),
            "confirmed_winner": bool(result.get("best_confirmed")),
        }
        result["pipeline_complete"] = all(result["verification"].values())
    except Exception as exc:
        result.update(error=type(exc).__name__ + ": " + str(exc), traceback=traceback.format_exc())
    finally:
        atomic_json(output / "results.json", result)
        atomic_json(
            channel / "DONE.json",
            {
                "session_id": plan["session_id"],
                "pipeline_complete": result["pipeline_complete"],
                "error": result.get("error"),
                "timing": result.get("timing"),
            },
        )
        print("CUDA_DONE", result["pipeline_complete"], result.get("error"), flush=True)
    return 0 if result["pipeline_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
