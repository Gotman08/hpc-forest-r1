"""A scoped relay launcher using each condition's unchanged historical engine."""
from __future__ import annotations
import argparse
import asyncio
import json
import math
import os
import shutil
import time
import traceback
from pathlib import Path

from hpc_forest import codex_mailbox, codex_process, codex_worker
from hpc_forest.core import FileLock, InfrastructureError, atomic_json, file_digest
from hpc_forest.native_matrix import install_identity
from hpc_forest.request_pool import RequestPool

async def relay(artifact, config):
    if os.environ.get("FOREST_STUDY_BROKER"):
        from engine_broker_client import install
        install(codex_worker,os.environ["FOREST_STUDY_BROKER"])
    artifact = artifact.resolve(strict=True)
    plan_path = artifact / "plan.json"
    authorization = artifact / "authorization.json"
    plan = json.loads(plan_path.read_text(encoding="utf8"))
    prep = json.loads((artifact / "preparation.json").read_text(encoding="utf8"))
    scope = plan["scope"]
    receipt_sha = file_digest(authorization)
    def gate(path, required):
        if Path(path).resolve() != authorization or file_digest(path) != receipt_sha:
            raise InfrastructureError("Authorization changed")
        value = codex_mailbox.bounded_json(path, 65536)
        expected = {"scope": scope, "session_id": plan["session_id"], "model": "gpt-6-luna",
                    "effort": "max", "gpus": plan["gpus"], "tokens": None,
                    "wall_seconds": plan["wall_seconds"], "hpc_allocation_authorized": True,
                    "plan_sha256": file_digest(plan_path), "payload_sha256": file_digest(artifact / "payload.tar.gz")}
        if (required != {scope} or any(value.get(key) != item for key,item in expected.items())
            or not value.get("user_request") or not str(value.get("job_id", "")).isdigit()
            or value.get("completion") != plan["completion"]):
            raise InfrastructureError("Not this explicitly authorized historical comparison")
        return value
    receipt = gate(authorization, {scope})
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
        raise InfrastructureError("Local Codex unavailable")
    output = artifact / "worker"
    output.mkdir(exist_ok=True)
    async with codex_worker.RomeoFiles(config) as files:
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
                raise InfrastructureError("Authorized channel did not appear")
            await asyncio.sleep(5)
        with FileLock(output / "worker.lock"):
            worker = codex_worker.Worker(files, channel, plan["session_id"], output,
                authorization, {scope}, executable=executable, defer_diagnostics=True,
                model_mcp_config=config if prep["model_mcp"] else None, documentation=True)
            await worker.hello()
            print("HISTORICAL_ENGINE_WORKER_READY", prep["condition"], job, flush=True)
            pool = RequestPool(worker)
            width, width_frozen, transfer_errors = 1, False, 0
            try:
                async with worker.keepalive(True):
                    while True:
                        # This loop only handles transport. Generation errors are
                        # deliberately outside it: no hidden model retries.
                        try:
                            listing = await worker.transfer_call(lambda: files.call("list_dir", path=channel, limit=40))
                            names = {row["name"] for row in listing["entries"]}
                            if "forest-plan.json" in names and not width_frozen:
                                width = await worker.controller_forest_width()
                                width_frozen = True
                                print("FROZEN_FOREST_WIDTH", width, flush=True)
                            requests = await worker.request_names(width)
                            transfer_errors = 0
                        except InfrastructureError as exc:
                            if isinstance(exc, codex_worker.TransferVerificationError):
                                raise
                            transfer_errors += 1
                            with (artifact / "relay-transfer-errors.jsonl").open("a", encoding="utf8") as log:
                                log.write(json.dumps({"time":time.time(),"error":str(exc),"consecutive":transfer_errors}) + "\n")
                            if transfer_errors >= 3:
                                raise
                            await asyncio.sleep(2)
                            continue
                        if "DONE.json" in names:
                            await pool.drain()
                            await worker.transfer_call(lambda:files.download(channel + "/DONE.json", output / "DONE.json"))
                            done = codex_mailbox.bounded_json(output / "DONE.json", 65536)
                            if done.get("session_id") != plan["session_id"]:
                                raise InfrastructureError("Wrong completion session")
                            pending = await worker.flush_diagnostics(deadline=math.inf)
                            atomic_json(artifact / "worker-finished.json", {"job_id":job,
                                "pipeline_complete":done.get("pipeline_complete"), "pending_diagnostics":pending,"at":time.time()})
                            return 0 if done.get("pipeline_complete") else 1
                        await pool.pump(requests, width)
                        await asyncio.sleep(2)
            finally:
                await pool.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        code = asyncio.run(relay(args.artifact, args.config))
    except Exception:
        atomic_json(args.artifact / "relay-failure.json", {"at":time.time(), "traceback":traceback.format_exc()})
        raise
    atomic_json(args.artifact / "relay-exit.json", {"exit_code":code,"at":time.time()})
    raise SystemExit(code)
