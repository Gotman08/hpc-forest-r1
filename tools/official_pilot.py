"""Run one official R1 subject using the frozen baseline, fixtures and original budget."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import shutil
import sys
import time
import traceback
from pathlib import Path

from native_smoke import (
    ADAPTIVE_SCOPES,
    DEPTH_SCOPES,
    EFFORT,
    FOREST_SCOPES,
    MODEL,
    OFFICIAL_SCOPE,
    depth_completion,
    smoke_complete,
    validate_depth_plan,
    verify_files,
)

from hpc_forest import codex_mailbox
from hpc_forest.adaptive_budget import record_timing
from hpc_forest.controller import create_workspace
from hpc_forest.core import BudgetExhausted, InfrastructureError, atomic_json, file_digest
from hpc_forest.forest import persistent_mother
from hpc_forest.mother import MotherContext
from hpc_forest.native_matrix import install_identity
from hpc_forest.reporting import package, report
from hpc_forest.support.budgets import unlimited_tokens


def campaign_validation(plan, project, root, prepared):
    """Freeze the current checker for fresh depth runs, preserving official fixtures."""
    original = Path(prepared["validation"])
    if plan["scope"] not in DEPTH_SCOPES:
        return original, None
    validation = root / "validation-runtime"
    shutil.copytree(original, validation, ignore=shutil.ignore_patterns("__pycache__"))
    original_tool = validation / "contract_tool.py"
    original_sha = file_digest(original_tool)
    current_tool = project / "src/hpc_forest/contracts.py"
    shutil.copyfile(current_tool, original_tool)
    provenance = {"scope": "fresh-depth-runtime-checker",
                  "original_tool_sha256": original_sha,
                  "runtime_tool_sha256": file_digest(original_tool),
                  "fixtures_preserved": True}
    atomic_json(root / "validation-runtime-provenance.json", provenance)
    return validation, provenance


def official_settings(plan, runner, target, prepared, harness):
    """Apply only this owned plan; historical short pilots keep their original limits."""
    if plan["scope"] in DEPTH_SCOPES:
        validate_depth_plan(plan)
        schedule = plan["schedule"]
        limits = {"wall_seconds": plan["wall_seconds"], "tokens": plan["token_budget"],
                  "generation_seconds": plan["budget"]["generation_seconds"]}
    elif plan["scope"] == OFFICIAL_SCOPE:
        schedule = {"cycles": 1, "trials_per_role_per_cycle": 2, "integrations_per_cycle": 2}
        limits = {"wall_seconds": 1800, "tokens": 1500000, "generation_seconds": 600}
    else:
        raise InfrastructureError("Unrelated official campaign scope")
    # The historical factory computes a finite slot count; override the entire
    # adaptive schedule/budget afterwards, without changing frozen factories.
    runner.reference.SCHEDULE.update({**schedule, "cycles": schedule["cycles"] or 1})
    runner.reference.LIMITS.update(limits)
    runner.HARNESS = json.loads(json.dumps(harness))
    settings = runner.config_for("codex-mailbox", plan["subject"], target, prepared)
    settings["completion"] = plan.get("completion", {"policy": "hard"})
    # config_for reserves the baseline and child slots. The mother owns two more.
    settings["budget"]["search_slots"] += 2
    settings["binary_tree"] = plan.get("binary_tree", {"enabled": False})
    if plan["scope"] in ADAPTIVE_SCOPES:
        settings["schedule"] = plan["schedule"].copy()
        settings["budget"].update(plan["budget"])
    if plan["scope"] in FOREST_SCOPES:
        settings["forest"] = plan["forest"].copy()
        if "skills" in plan:
            settings["skills"] = plan["skills"].copy()
    if plan["scope"] in DEPTH_SCOPES:
        settings["budget"]["max_depth"] = 0
        if unlimited_tokens(settings):
            settings["budget"]["mission_tokens"] = None
            settings["harness"]["call_token_ceiling"] = None
        if (settings["schedule"] != plan["schedule"]
                or settings["seed"] != plan["seed"]
                or settings["codex"].get("model") != MODEL
                or settings["codex"].get("reasoning_effort") != EFFORT
                or any(settings["budget"].get(key) != value for key, value in plan["budget"].items())):
            raise InfrastructureError("Runtime settings differ from the frozen depth plan")
    return settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    project = Path(__file__).resolve().parent.parent
    plan = codex_mailbox.bounded_json(root / "plan.json", 65536)
    if plan.get("scope") in DEPTH_SCOPES:
        validate_depth_plan(plan)
    verify_files(project, codex_mailbox.bounded_json(root / "runtime-manifest.json"))
    job = os.environ.get("SLURM_JOB_ID", "")
    if (not job.isdigit() or platform.machine() != "aarch64"
            or int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) != 4
            or os.environ.get("CUDA_VISIBLE_DEVICES")
            or importlib.metadata.version("treequest") != "0.3.2"
            or root != Path(plan["remote_root"]).resolve(strict=True)
            or plan["scope"] not in {OFFICIAL_SCOPE, *DEPTH_SCOPES}
            or plan["subject"] != "2023-count"):
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
    harness = json.loads((project / "examples/marathon22/harness-mixed.json").read_text())
    result = {"scope": plan["scope"], "session_id": plan["session_id"], "model": MODEL,
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
        settings = official_settings(plan, runner, target, record["prepared"], harness)
        result["completion"] = settings["completion"]
        if plan["scope"] in DEPTH_SCOPES:
            result.update(schedule=plan["schedule"], budget=plan["budget"], max_depth=0,
                          requested_trials_per_role=plan["trials_per_role"],
                          schedule_completed=False, budget_exhausted=False)
        validation, validation_provenance = campaign_validation(
            plan, project, root, record["prepared"])
        result["validation_runtime"] = validation_provenance
        campaign = create_workspace(output / plan["subject"], settings,
            source=Path(record["prepared"]["source"]), validation=validation)
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
            def progress(state):
                result["search"] = state
                atomic_json(output / "progress.json", result)
                print("OFFICIAL_PROGRESS", json.dumps(state), flush=True)
            while True:
                try:
                    result["search"] = controller.run(
                        max_batches=None if persistent_mother(controller.config) else 1,
                        on_progress=progress)
                except BudgetExhausted as exc:
                    if plan["scope"] not in DEPTH_SCOPES:
                        raise
                    controller.db.set("status", "budget_exhausted")
                    controller.db.event("budget_stop", {"reason": str(exc)})
                    result["search"] = controller.status()
                result["topology"] = (controller.search.snapshot() if controller.search.binary
                                      else base.tree_snapshot(controller))
                atomic_json(output / "progress.json", result)
                print("OFFICIAL_PROGRESS", json.dumps(result["search"]), flush=True)
                if result["search"]["status"] != "checkpointed":
                    break
            result["best_confirmed"] = controller.confirm()
            result["postprocess"] = controller.status().get("postprocess")
            result["final_g_confirmation"] = controller.status().get("final_g_confirmation")
            result["timing"] = {"admission": controller.status().get("last_admission"),
                                "samples": controller.db.get("timing_samples", {}),
                                "target_deadline": controller.db.get("deadline"),
                                "confirmation_finished": controller.db.get("confirmation_finished:1")}
            result["costs"] = controller.db.costs()
            result["phase_costs"] = {phase: controller.db.costs(phase)
                                     for phase in ("search", "postprocess", "confirmation")}
            result["forest_plan"] = controller.status().get("forest_plan")
            result["mother_conversation"] = controller.status().get("mother_conversation")
            result["mother"] = {phase: controller.db.get("mother_plan:" + phase +
                (f":{controller.epoch()['id']}" if plan["scope"] in FOREST_SCOPES else ""))
                                for phase in ("preparation", "synthesis")}
            result["trials"] = [dict(row) for row in controller.db.rows(
                "SELECT id,role,state,mission,result FROM trials ORDER BY created,id")]
            archive_started = time.time()
            report(campaign)
            package(campaign, campaign / "submission.zip")
            record_timing(controller.db, "archive", time.time() - archive_started)
            result["timing"].update(finished_at=time.time(),
                samples=controller.db.get("timing_samples", {}),
                overrun_seconds=max(0, time.time() - controller.db.get("deadline")))
            controller.db.set("pipeline_finished:1", result["timing"]["finished_at"])
        if plan["scope"] in DEPTH_SCOPES:
            result.update(depth_completion(result, trials_per_role=plan["trials_per_role"]))
        else:
            result["pipeline_complete"] = smoke_complete(result, trials_per_role=2)
    except Exception as exc:
        result.update(error=type(exc).__name__ + ": " + str(exc), traceback=traceback.format_exc())
    finally:
        atomic_json(output / "results.json", result)
        atomic_json(channel / "DONE.json", {"session_id": plan["session_id"],
                    "pipeline_complete": result["pipeline_complete"], "error": result.get("error"),
                    "timing": result.get("timing")})
        print("OFFICIAL_DONE", result["pipeline_complete"], flush=True)
    return 0 if result["pipeline_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
