"""Run one official R1 subject using the frozen baseline, fixtures and original budget."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import sys
import time
import traceback
from pathlib import Path

from native_smoke import EFFORT, MODEL, OFFICIAL_SCOPE, smoke_complete, verify_files

from hpc_forest import codex_mailbox
from hpc_forest.controller import create_workspace
from hpc_forest.core import InfrastructureError, atomic_json, file_digest
from hpc_forest.mother import MotherContext
from hpc_forest.native_matrix import install_identity
from hpc_forest.reporting import package, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    project = Path(__file__).resolve().parent.parent
    plan = codex_mailbox.bounded_json(root / "plan.json", 65536)
    verify_files(project, codex_mailbox.bounded_json(root / "runtime-manifest.json"))
    job = os.environ.get("SLURM_JOB_ID", "")
    if (not job.isdigit() or platform.machine() != "aarch64"
            or int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) != 4
            or os.environ.get("CUDA_VISIBLE_DEVICES")
            or importlib.metadata.version("treequest") != "0.3.2"
            or root != Path(plan["remote_root"]).resolve(strict=True)
            or plan["scope"] != OFFICIAL_SCOPE or plan["subject"] != "2023-count"):
        raise InfrastructureError("Expected this official pilot's owned ARM64 allocation")
    prepared_root = Path(plan["preparation_manifest"]["path"]).parent.resolve(strict=True)
    if file_digest(prepared_root / "prepared-manifest.json") != plan["preparation_manifest"]["sha256"]:
        raise InfrastructureError("The official preparation manifest changed")
    preparation = codex_mailbox.bounded_json(prepared_root / "prepared-manifest.json")
    selected = {name: sha for name, sha in preparation["files"].items()
                if name.startswith("preparation/2023-count/")}
    if not selected:
        raise InfrastructureError("The official subject has no frozen preparation")
    verify_files(prepared_root, selected)
    record = preparation["records"][plan["subject"]]
    if record["status"] != "ready":
        raise InfrastructureError("The official subject is not admitted")
    statement_path = Path(plan["statement"]["path"])
    if file_digest(statement_path) != plan["statement"]["sha256"]:
        raise InfrastructureError("The official statement changed")
    install_identity(MODEL, EFFORT)
    sys.path.insert(0, str(project / "examples/marathon22"))
    # Import after pinning the model so inherited bindings also select Luna MAX.
    import romeo_base as base
    import romeo_codex as runner
    from romeo_harness_comparison import ObservedController

    class OfficialController(MotherContext, ObservedController):
        pass

    output = root / ("results-" + job)
    output.mkdir(exist_ok=False)
    channel = output / "mailbox"
    codex_mailbox.initialize_channel(channel, plan["session_id"], job)
    runner.CHANNEL, runner.SESSION_ID = channel, plan["session_id"]
    runner.reference.SCHEDULE.update(cycles=1, trials_per_role_per_cycle=2,
                                     integrations_per_cycle=2)
    runner.reference.LIMITS.update(wall_seconds=1800, tokens=1500000, generation_seconds=600)
    runner.HARNESS = json.loads((project / "examples/marathon22/harness-mixed.json").read_text())
    result = {"scope": OFFICIAL_SCOPE, "session_id": plan["session_id"], "model": MODEL,
        "effort": EFFORT, "subject": plan["subject"], "title": record["title"], "job_id": job,
        "pipeline_complete": False, "old_candidates_imported": False,
        "official_preparation_sha256": plan["preparation_manifest"]["sha256"],
        "statement_sha256": plan["statement"]["sha256"]}
    result["search_policy"] = ("binary-greedy" if plan.get("binary_tree", {}).get("enabled")
                               else "ab-mcts-a")
    atomic_json(output / "channel.json", {**result, "channel": str(channel)})
    print("OFFICIAL_CHANNEL_READY", flush=True)
    try:
        target = "romeo-r1-official-" + job
        settings = runner.config_for("codex-mailbox", plan["subject"], target, record["prepared"])
        settings["budget"]["search_slots"] += 2
        settings["binary_tree"] = plan.get("binary_tree", {"enabled": False})
        campaign = create_workspace(output / plan["subject"], settings,
            source=Path(record["prepared"]["source"]), validation=Path(record["prepared"]["validation"]))
        atomic_json(output / "allocation.json", {"job_id": job, "machine": platform.machine(),
            "python": sys.executable, "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "treequest": importlib.metadata.version("treequest"), "compiler": settings.get("compiler"),
            "runtime_manifest_sha256": file_digest(root / "runtime-manifest.json")})
        ready_path = channel / "worker-ready.json"
        end = time.monotonic() + 180
        while not ready_path.exists():
            if time.monotonic() >= end:
                raise InfrastructureError("The official Luna worker did not connect")
            time.sleep(0.5)
        worker = codex_mailbox.bounded_json(ready_path, 16384)
        if any(worker.get(k) != v for k, v in {"model": MODEL, "reasoning_effort": EFFORT,
                "session_id": plan["session_id"], "mode": "codex"}.items()):
            raise InfrastructureError("Wrong official worker identity")
        with OfficialController(campaign, statement_path.read_text(encoding="utf8")) as controller:
            with controller.db.connection:
                controller.db.connection.execute("DELETE FROM documents")
            controller.db.event("official_r1_reconstruction", result)
            while True:
                result["search"] = controller.run(max_batches=1)
                result["topology"] = (controller.search.snapshot() if controller.search.binary
                                      else base.tree_snapshot(controller))
                atomic_json(output / "progress.json", result)
                print("OFFICIAL_PROGRESS", json.dumps(result["search"]), flush=True)
                if result["search"]["status"] != "checkpointed":
                    break
            result["best_confirmed"] = controller.confirm()
            result["costs"] = controller.db.costs()
            result["mother"] = {phase: controller.db.get("mother_plan:" + phase)
                                for phase in ("preparation", "synthesis")}
            result["trials"] = [dict(row) for row in controller.db.rows(
                "SELECT id,role,state,mission,result FROM trials ORDER BY created,id")]
        report(campaign)
        package(campaign, campaign / "submission.zip")
        result["pipeline_complete"] = smoke_complete(result, trials_per_role=2)
    except Exception as exc:
        result.update(error=type(exc).__name__ + ": " + str(exc), traceback=traceback.format_exc())
    finally:
        atomic_json(output / "results.json", result)
        atomic_json(channel / "DONE.json", {"session_id": plan["session_id"],
                    "pipeline_complete": result["pipeline_complete"], "error": result.get("error")})
        print("OFFICIAL_DONE", result["pipeline_complete"], flush=True)
    return 0 if result["pipeline_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
