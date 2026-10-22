"""Relay ONLY an explicitly authorized, frozen CUDA memory campaign to Luna Max."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import shutil
import time
from pathlib import Path

from hpc_forest import codex_mailbox, codex_process, codex_worker
from hpc_forest.core import FileLock, InfrastructureError, atomic_json, file_digest
from hpc_forest.native_matrix import install_identity
from hpc_forest.request_pool import RequestPool

SCOPE = "cuda-nbody-luna-max-memory-v1"


async def relay(artifact, authorization, codex_config):
    artifact, authorization = artifact.resolve(strict=True), authorization.resolve(strict=True)
    plan_path = artifact / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf8"))
    receipt_sha = file_digest(authorization)

    def gate(path, required):
        if Path(path).resolve() != authorization or file_digest(path) != receipt_sha:
            raise InfrastructureError("Authorization changed")
        value = codex_mailbox.bounded_json(path, 65536)
        expected = {"scope": SCOPE, "session_id": plan["session_id"], "model": "gpt-6-luna",
                    "effort": "max", "gpus": 1, "tokens": None,
                    "wall_seconds": plan["wall_seconds"], "hpc_allocation_authorized": True,
                    "plan_sha256": file_digest(plan_path), "payload_sha256": file_digest(artifact / "payload.tar.gz")}
        if (required != {SCOPE} or any(value.get(key) != item for key, item in expected.items())
                or plan.get("scope") != SCOPE or not value.get("user_request")
                or not str(value.get("job_id", "")).isdigit()
                or value.get("completion") != plan["completion"]):
            raise InfrastructureError("Not this explicitly authorized CUDA memory campaign")
        return value

    receipt = gate(authorization, {SCOPE})
    job = receipt["job_id"]
    channel = plan["remote_root"] + "/results-" + job + "/mailbox"
    if receipt.get("channel") != channel:
        raise InfrastructureError("Authorization names a different mailbox")
    install_identity("gpt-6-luna", "max")
    codex_process.check_dependencies = codex_worker.check_dependencies = gate

    def channel_guard(value):
        if value != channel:
            raise InfrastructureError("Not this authorized channel")
    codex_worker.validate_remote_channel = channel_guard
    original_run = codex_process.run_codex

    def scoped_run(request, *args, **kwargs):
        if request.get("session_id") != plan["session_id"]:
            raise InfrastructureError("Wrong request session")
        return original_run(request, *args, **kwargs)
    codex_worker.run_codex = scoped_run
    executable = shutil.which("codex")
    if not executable:
        raise InfrastructureError("The local Codex executable is unavailable")
    output = artifact / "worker"
    output.mkdir(exist_ok=True)
    async with codex_worker.RomeoFiles(codex_config) as files:
        end = time.monotonic() + 7200
        print("WAITING_FOR_AUTHORIZED_GPU_CHANNEL", job, flush=True)
        while True:
            try:
                listing = await codex_worker.retry_transfer(
                    lambda: files.call("list_dir", path=channel, limit=30), attempts=1, timeout=10)
                if any(row["name"] == "OWNER.json" for row in listing["entries"]):
                    break
            except InfrastructureError:
                pass
            if time.monotonic() > end:
                raise InfrastructureError("The authorized GPU channel did not appear")
            await asyncio.sleep(5)
        with FileLock(output / "worker.lock"):
            worker = codex_worker.Worker(files, channel, plan["session_id"], output,
                authorization, {SCOPE}, executable=executable, defer_diagnostics=True, documentation=True)
            await worker.hello()
            print("LUNA_MAX_MEMORY_WORKER_READY", flush=True)
            pool = RequestPool(worker)
            try:
                async with worker.keepalive(True):
                    while True:
                        listing = await worker.transfer_call(lambda: files.call("list_dir", path=channel, limit=40))
                        names = {row["name"] for row in listing["entries"]}
                        width = await worker.controller_forest_width() if "forest-plan.json" in names else 1
                        await pool.pump(await worker.request_names(width), width)
                        if "DONE.json" in names:
                            await pool.drain()
                            await worker.transfer_call(lambda: files.download(channel + "/DONE.json", output / "DONE.json"))
                            done = codex_mailbox.bounded_json(output / "DONE.json", 65536)
                            if done.get("session_id") != plan["session_id"]:
                                raise InfrastructureError("Wrong completion session")
                            pending = await worker.flush_diagnostics(deadline=math.inf)
                            atomic_json(artifact / "worker-finished.json", {"job_id": job,
                                "pipeline_complete": done.get("pipeline_complete"),
                                "pending_diagnostics": pending, "at": time.time()})
                            return 0 if done.get("pipeline_complete") else 1
                        await asyncio.sleep(2)
            finally:
                await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--codex-config", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(relay(args.artifact, args.authorization, args.codex_config)))
