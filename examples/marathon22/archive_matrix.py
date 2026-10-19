"""One exact model/effort, all independently prepared archive problems, fresh forests."""
from __future__ import annotations

import argparse
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

from hpc_forest.core import atomic_json, file_digest
from hpc_forest.native_matrix import install_identity


def select_subjects(records, requested=None):
    selected = list(records) if requested is None else requested
    if len(set(selected)) != len(selected) or any(key not in records for key in selected):
        raise ValueError("Unknown or repeated archive subject")
    return [key for key in selected if records[key]["status"] == "ready"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--shared", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--subjects", nargs="+")
    args = parser.parse_args()
    install_identity(args.model, args.effort)
    # Import after selecting identity: legacy imports receive the explicitly pinned values.
    import romeo_codex as runner
    from romeo_harness_comparison import ObservedController, verify_worker

    from hpc_forest.codex_mailbox import initialize_channel
    from hpc_forest.controller import create_workspace
    from hpc_forest.mother import MotherContext
    from hpc_forest.reporting import package, report

    class MotherController(MotherContext, ObservedController):
        pass

    job = os.environ.get("SLURM_JOB_ID", "")
    if not job.isdigit() or platform.machine() != "aarch64":
        parser.error("Run only inside the owned ARM64 allocation")
    if importlib.metadata.version("treequest") != "0.3.2":
        raise RuntimeError("The real pinned TreeQuest version is required")
    root, shared = args.root.resolve(), args.shared.resolve(strict=True)
    root.mkdir(parents=True, exist_ok=False)
    output = root / f"results-{job}"
    output.mkdir()
    prepared_manifest = json.loads((shared / "prepared/prepared-manifest.json").read_text())
    selected_subjects = select_subjects(prepared_manifest["records"], args.subjects)
    for name, expected in prepared_manifest["files"].items():
        p = shared / "prepared" / name
        if not p.resolve().is_relative_to(shared / "prepared") or file_digest(p) != expected:
            raise RuntimeError("The shared official preparation changed")
    for name, expected in json.loads((shared / "runtime-manifest.json").read_text()).items():
        if file_digest(shared / "project" / name) != expected:
            raise RuntimeError("The immutable experiment runtime changed")
    shutil.copyfile(shared / "matrix-plan.json", output / "matrix-plan.json")
    shutil.copyfile(shared / "prepared/prepared-manifest.json", output / "prepared-manifest.json")
    shutil.copyfile(shared / "preflight-junit.xml", output / "preflight-junit.xml")
    channel = output / "mailbox"
    initialize_channel(channel, args.session_id, job)
    atomic_json(output / "channel.json", {"channel": str(channel), "session_id": args.session_id,
                "model": args.model, "effort": args.effort})
    base.emit("matrix_mailbox_ready", channel=str(channel), session_id=args.session_id)
    verify_worker(channel, args.session_id, 600)
    runner.CHANNEL, runner.SESSION_ID = channel, args.session_id
    runner.reference.SCHEDULE.update(cycles=1, trials_per_role_per_cycle=2, integrations_per_cycle=2)
    runner.reference.LIMITS.update(wall_seconds=1800, tokens=1500000, generation_seconds=600)
    runner.HARNESS = json.loads((shared / "harness-mixed.json").read_text())
    result = {"schema": "hpc-forest-native-mother-matrix-v1", "job_id": job,
              "model": args.model, "reasoning_effort": args.effort,
              "planned_child_slots_per_subject": 8, "planned_mother_calls_per_subject": 2,
              "replicates": 1, "mother_causal_ablation": False, "problems": [],
              "requested_subjects": args.subjects, "admitted_subjects": selected_subjects,
              "unprepared": {k: v for k, v in prepared_manifest["records"].items() if v["status"] != "ready"},
              "old_candidates_imported": False, "operator_algorithm_advice": False}
    target = f"romeo:{socket.gethostname()}:slurm-{job}:archive-matrix-cpu4"
    try:
        for key, record in prepared_manifest["records"].items():
            if key not in selected_subjects:
                continue
            started = time.monotonic()
            campaign = output / key
            entry = {"subject": key, "model": args.model, "effort": args.effort,
                     "pipeline_complete": False, "title": record["title"]}
            try:
                settings = runner.config_for("codex-mailbox", key, target, record["prepared"])
                settings["budget"]["search_slots"] += 2  # Mother slots are charged and reported separately.
                statement = (shared / "statements" / (key[:4] + ".txt")).read_text(encoding="utf8")
                create_workspace(campaign, settings, source=Path(record["prepared"]["source"]),
                                 validation=Path(record["prepared"]["validation"]))
                with MotherController(campaign, statement) as controller:
                    with controller.db.connection:
                        controller.db.connection.execute("DELETE FROM documents")
                    controller.db.event("archive_protocol_identity", {
                        "model": args.model, "effort": args.effort,
                        "shared_preparation_sha256": file_digest(shared / "prepared/prepared-manifest.json"),
                        "mother_enabled": True, "operator_algorithm_advice": False})
                    while True:
                        entry["search"] = controller.run(max_batches=1)
                        topology = base.tree_snapshot(controller)
                        atomic_json(output / (key + "-progress.json"), topology)
                        base.emit("matrix_progress", subject=key, model=args.model, effort=args.effort,
                                  **{k: topology[k] for k in ["trials", "scored_nodes", "max_depth", "max_children", "tokens_used"]})
                        if entry["search"]["status"] != "checkpointed":
                            break
                    entry["best_confirmed"] = controller.confirm()
                    entry["costs"] = controller.db.costs()
                    entry["topology"] = base.tree_snapshot(controller)
                    entry["mother"] = {phase: controller.db.get("mother_plan:" + phase)
                                       for phase in ["preparation", "synthesis"]}
                report(campaign)
                package(campaign, campaign / "submission.zip")
                entry["pipeline_complete"] = True
            except Exception as exc:
                entry["error"] = type(exc).__name__ + ": " + str(exc)
                entry["traceback"] = traceback.format_exc()
            entry["elapsed_seconds"] = time.monotonic() - started
            result["problems"].append(entry)
            atomic_json(output / (key + "-summary.json"), entry)
            atomic_json(output / "results.json", result)
            base.emit("matrix_subject_end", subject=key, pipeline_complete=entry["pipeline_complete"],
                      best=entry.get("best_confirmed"), error=entry.get("error"))
            if entry.get("error"):
                # A confirmed infrastructure incident is inspected before the next configuration.
                break
    finally:
        expected = len(selected_subjects)
        result["pipeline_complete"] = len(result["problems"]) == expected and all(p["pipeline_complete"] for p in result["problems"])
        atomic_json(output / "results.json", result)
        archive = root / f"results-{job}.tar.gz"
        evidence_pack.make(output, shared / "sources-officielles", archive)
        base.emit("runner_end", complete=result["pipeline_complete"], archive=str(archive), sha256=base.sha256(archive))
    return 0 if result["pipeline_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
