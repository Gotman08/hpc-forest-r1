"""Standalone ROMEO supervisor: native model worker, search, confirmation and exports."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import signal
import subprocess
import sys
import threading
import time
from contextlib import suppress
from pathlib import Path

from ..codex_mailbox import initialize_channel
from ..codex_worker import Worker
from ..core import FileLock, InfrastructureError, atomic_json, file_digest
from ..model_runtime import authenticate
from ..request_pool import RequestPool
from .runner_support import (
    SharedFiles,
    export_view,
    package_project,
    prepare_project,
)


def phase(root: Path, state: str, **extra):
    atomic_json(root / "progress.json", {
        "state": state, "updated": time.time(), "job_id": os.environ.get("SLURM_JOB_ID"),
        "host": platform.node(), "pc_relay": False, **extra})


def control(root: Path):
    import hpc_forest.controller as module

    from ..reporting import report

    done = {"pipeline_complete": False}
    try:
        phase(root, "validating")
        with module.Controller(root / "campaign") as controller:
            def progress(value):
                phase(root, "running", search={k: value.get(k) for k in ("status", "costs", "epoch")})
            controller.run(on_progress=progress)
            phase(root, "confirming")
            best = controller.confirm()
            status = controller.status()
            complete = ((status.get("postprocess") or {}).get("status") == "complete"
                        and (status.get("final_g_confirmation") or {}).get("status") in {"confirmed", "rejected"})
            if not complete:
                raise InfrastructureError("The final assembly or confirmation is incomplete")
            report(root / "campaign")
            package_project(root, root / "campaign", best)
            controller.db.set("pipeline_finished:1", time.time())
            done.update(pipeline_complete=True, best_confirmed=best,
                        final_g_confirmation=status.get("final_g_confirmation"), finished_at=time.time())
        phase(root, "completed", **done)
        return 0
    except Exception as exc:
        done["error"] = type(exc).__name__ + ": " + str(exc)
        phase(root, "failed", **done)
        return 1
    finally:
        launch = json.loads((root / "launch.json").read_text(encoding="utf8"))
        atomic_json(root / "campaign/DONE.json", done)
        atomic_json(root / "campaign/mailbox/DONE.json", {**done, "session_id": launch["session_id"]})


async def work(root: Path):
    launch = json.loads((root / "launch.json").read_text(encoding="utf8"))
    output = root / "worker"
    with FileLock(output / "worker.lock"):
        worker = Worker(SharedFiles(root), str(root / "campaign/mailbox"), launch["session_id"],
                        output, root / "authorization.json", {launch["id"]},
                        executable=launch["codex"], model=launch["model"], effort=launch["effort"],
                        generators=launch.get("generator_pool"),
                        dsh_settings=launch.get("dsh_romeo"),
                        documentation=True, diagnostics_root=root / "campaign",
                        defer_diagnostics=True)
        await worker.hello()
        pool = RequestPool(worker)
        try:
            async with worker.keepalive(True):
                while True:
                    channel = root / "campaign/mailbox"
                    width = await worker.controller_forest_width() if (channel / "forest-plan.json").exists() else 1
                    await pool.pump(await worker.request_names(width), width)
                    if (channel / "DONE.json").is_file():
                        await pool.drain()
                        await worker.flush_diagnostics(deadline=time.time() + 60)
                        return 0
                    await asyncio.sleep(0.5)
        finally:
            await pool.close()


def supervise(root: Path):
    from ..controller import create_workspace

    launch = json.loads((root / "launch.json").read_text(encoding="utf8"))
    cpus = sorted(os.sched_getaffinity(0))
    if launch.get("execution_validation"):
        from ..execution_validation import allocation_evidence

        observation = allocation_evidence(launch["execution_validation"])
        atomic_json(root / "allocation-validation.json", observation)
        if observation["status"] != "passed":
            raise InfrastructureError("The allocation does not satisfy the frozen execution contract")
    minimum_cpus = 1 if launch.get("execution_validation") else 2
    if (not os.environ.get("SLURM_JOB_ID", "").isdigit() or len(cpus) < minimum_cpus
            or platform.machine() != launch["architecture"]):
        raise InfrastructureError("The expected ROMEO compute allocation is required")
    for name, digest in launch["engine_files"].items():
        if file_digest(root / "engine" / name) != digest:
            raise InfrastructureError("Frozen engine changed")
    auth = authenticate(launch["codex"], {"model": launch["model"], "reasoning_effort": launch["effort"],
                        "generator_pool": launch.get("generator_pool", [])},
                        dsh_settings=launch.get("dsh_romeo"), check_catalog=True)
    phase(root, "preparing", model=launch["model"], effort=launch["effort"], **auth)
    config = prepare_project(root, launch)
    from hpc_forest.search.policy import make_algorithm, settings

    make_algorithm(settings(config))  # Fail before initialization if optional dependencies are missing.
    create_workspace(root / "campaign", config, root / "source", root / "validation")
    initialize_channel(root / "campaign/mailbox", launch["session_id"], os.environ["SLURM_JOB_ID"],
                       model=launch["model"], effort=launch["effort"], generators=launch.get("generator_pool"))
    atomic_json(root / "authorization.json", {
        "schema": "forest-app-authorization-v1", "mission_id": launch["id"],
        "session_id": launch["session_id"], "next_model": launch["model"], "reasoning_effort": launch["effort"],
        "generator_pool": launch.get("generator_pool", []),
        **({"dsh_romeo": launch["dsh_romeo"]} if "dsh_romeo" in launch else {}),
        "manifest_sha256": file_digest(root / "launch.json"), "expires_at": time.time() + launch["allocation_seconds"],
        "completion": {"policy": "finish-started", "token_policy": "observe-only"},
    })
    processes, streams = [], []
    stopping = threading.Event()
    def snapshot_loop():
        while not stopping.wait(20):
            try:
                export_view(root)
            except Exception as exc:
                atomic_json(root / "export-error.json", {"error": type(exc).__name__, "at": time.time()})
    snapshot = threading.Thread(target=snapshot_loop, daemon=True)
    snapshot.start()
    deadline = time.monotonic() + launch["allocation_seconds"] - 90
    try:
        placements = (("worker", cpus[-1]), ("controller", cpus[0]))
        if launch.get("execution_validation"):
            placements = (("worker", ",".join(map(str, cpus))),
                          ("controller", ",".join(map(str, cpus))))
        for name, cpu in placements:
            stream = (root / (name + ".log")).open("ab")
            streams.append(stream)
            processes.append(subprocess.Popen(
                ["taskset", "-c", str(cpu), sys.executable, "-u", "-m", __package__ + ".remote_runner",
                 str(root), "--role", name], stdout=stream, stderr=subprocess.STDOUT, start_new_session=True))
        while processes[1].poll() is None:
            if processes[0].poll() is not None:
                raise InfrastructureError("Native model worker stopped; campaign evidence preserved")
            if time.monotonic() >= deadline:
                raise InfrastructureError("Allocation safety limit reached before final confirmation")
            time.sleep(1)
        processes[0].wait(timeout=90)
        return processes[1].returncode
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        stopping.set()
        snapshot.join(timeout=30)
        for stream in streams:
            stream.close()
        export_view(root)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--role", choices=["supervisor", "controller", "worker"], default="supervisor")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    try:
        if args.role == "controller":
            return control(root)
        if args.role == "worker":
            return asyncio.run(work(root))
        with FileLock(root / "supervisor.lock"):
            return supervise(root)
    except Exception as exc:
        if args.role == "supervisor":
            phase(root, "failed", error=type(exc).__name__ + ": " + str(exc))
            with suppress(Exception):
                export_view(root)
        raise


if __name__ == "__main__":
    raise SystemExit(main())

