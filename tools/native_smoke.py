"""One explicitly authorized Luna MAX smoke; no historical campaign admission."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import re
import time
import traceback
from pathlib import Path, PurePosixPath

from hpc_forest import codex_mailbox, codex_process, codex_worker
from hpc_forest.config import load_config
from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import FileLock, InfrastructureError, atomic_json, file_digest
from hpc_forest.mother import MotherContext
from hpc_forest.native_matrix import install_identity
from hpc_forest.reporting import report

SCOPE = "r1-reconstruction-luna-smoke-v1"
OFFICIAL_SCOPE = "r1-official-count-luna-max-v1"
MODEL, EFFORT = "gpt-6-luna", "max"
PILOTS = {SCOPE: ("matmul", 4, "hpc-forest-r1-pilot-"),
          OFFICIAL_SCOPE: ("2023-count", 8, "hpc-forest-r1-official-")}


def verify_files(root: Path, manifest: dict) -> None:
    for relative, expected in manifest.items():
        path = root / relative
        if (not path.resolve().is_relative_to(root.resolve()) or path.is_symlink()
                or not path.is_file() or file_digest(path) != expected):
            raise InfrastructureError("The smoke payload changed: " + relative)


def authorize(path: Path, required: set[str]) -> dict:
    value = codex_mailbox.bounded_json(path, 65536)
    scope = value.get("scope")
    if (scope not in PILOTS or required != {scope}
            or value.get("model") != MODEL or value.get("effort") != EFFORT
            or value.get("expires_at", 0) <= time.time()
            or value.get("historical_campaign_resumption") is not False
            or not value.get("user_request")):
        raise InfrastructureError("Missing, unrelated or expired smoke authorization")
    session = value.get("session_id", "")
    if not re.fullmatch(r"[a-f0-9]{32}", session):
        raise InfrastructureError("Invalid smoke session")
    for key in ("payload", "plan"):
        item = value[key]
        target = Path(item["path"])
        if target.is_symlink() or file_digest(target) != item["sha256"]:
            raise InfrastructureError("The authorized smoke artifact changed")
    plan = codex_mailbox.bounded_json(Path(value["plan"]["path"]), 65536)
    subject, missions, prefix = PILOTS[scope]
    if (plan.get("scope") != scope or plan.get("session_id") != session
            or plan.get("model") != MODEL or plan.get("effort") != EFFORT
            or plan.get("subject") != subject or plan.get("child_missions") != missions
            or plan.get("mother_calls") != 2):
        raise InfrastructureError("The smoke plan does not match its authorization")
    if scope == OFFICIAL_SCOPE and (plan.get("wall_seconds") != 1800
            or plan.get("token_budget") != 1500000 or plan.get("seed") != 23):
        raise InfrastructureError("The official pilot must retain the historical R1 budgets")
    root = PurePosixPath(plan["remote_root"])
    channel = PurePosixPath(value["channel"])
    if (root != PurePosixPath("/scratch_p/nimarano") / (prefix + session)
            or channel.parent.parent != root or channel.name != "mailbox"
            or not re.fullmatch(r"results-[0-9]+", channel.parent.name)):
        raise InfrastructureError("The smoke channel is not owned by this session")
    return value


def install_worker_identity(receipt: Path, scope=SCOPE) -> dict:
    value = authorize(receipt, {scope})
    install_identity(MODEL, EFFORT)

    def gate(path, required):
        fresh = authorize(path, required)
        if fresh["session_id"] != value["session_id"] or fresh["channel"] != value["channel"]:
            raise InfrastructureError("The smoke worker identity changed")
        return fresh

    def channel_guard(channel):
        if channel != value["channel"]:
            raise InfrastructureError("This worker only serves its authorized smoke channel")

    original_run = codex_process.run_codex

    def scoped_run(request, *args, **kwargs):
        if request.get("session_id") != value["session_id"]:
            raise InfrastructureError("The request belongs to another smoke session")
        return original_run(request, *args, **kwargs)

    codex_process.check_dependencies = codex_worker.check_dependencies = gate
    codex_worker.validate_remote_channel = channel_guard
    codex_worker.run_codex = scoped_run
    return value


async def serve(args):
    scope = getattr(args, "scope", SCOPE)
    identity = install_worker_identity(args.receipt, scope)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with FileLock(output / "worker.lock"):
        async with codex_worker.RomeoFiles(args.codex_config) as files:
            worker = codex_worker.Worker(files, identity["channel"], identity["session_id"],
                output, args.receipt, {scope}, executable=args.executable, defer_diagnostics=True)
            await worker.hello()
            end = time.monotonic() + (2700 if scope == OFFICIAL_SCOPE else 1200)
            while time.monotonic() < end:
                for name in sorted(await files.requests(identity["channel"])):
                    await worker.handle(name)
                listing = await files.call("list_dir", path=identity["channel"], limit=30)
                if any(item["name"] == "DONE.json" for item in listing["entries"]):
                    await files.download(identity["channel"] + "/DONE.json", output / "DONE.json")
                    done = codex_mailbox.bounded_json(output / "DONE.json", 65536)
                    if done.get("session_id") != identity["session_id"]:
                        raise InfrastructureError("Mismatched smoke completion")
                    await worker.flush_diagnostics()
                    return 0 if done.get("pipeline_complete") else 1
                await asyncio.sleep(2)
    raise InfrastructureError("The single smoke worker reached its time limit")


class SmokeController(MotherContext, Controller):
    def __init__(self, root, statement):
        super().__init__(root)
        self.statement = statement
        self.backend = codex_mailbox.CodexMailboxBackend()

    def plan(self):
        return [[role] for batch in super().plan() for role in batch]


def smoke_complete(result: dict, *, trials_per_role=1) -> bool:
    trials = result.get("trials", [])
    if sorted(trial["role"] for trial in trials) != sorted("ABCG" * trials_per_role):
        return False
    # A confirmed fallback cannot hide a failed transport on another tree.
    outcomes = [json.loads(trial["result"]) if trial.get("result") else {} for trial in trials]
    return (bool(result.get("best_confirmed"))
            and result.get("search", {}).get("status") == "search_complete"
            and all(outcome.get("status") not in (None, "infrastructure_error")
                    for outcome in outcomes)
            and set(result.get("mother", {})) == {"preparation", "synthesis"}
            and all(item["status"] == "complete" for item in result["mother"].values()))


def run_remote(args):
    import importlib.metadata

    root = args.root.resolve(strict=True)
    project = Path(__file__).resolve().parent.parent
    plan = codex_mailbox.bounded_json(root / "plan.json", 65536)
    verify_files(project, codex_mailbox.bounded_json(root / "runtime-manifest.json"))
    job = os.environ.get("SLURM_JOB_ID", "")
    if (not job.isdigit() or platform.machine() != "aarch64"
            or int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) != 4
            or os.environ.get("CUDA_VISIBLE_DEVICES")
            or importlib.metadata.version("treequest") != "0.3.2"
            or root != Path(plan["remote_root"]).resolve(strict=True)):
        raise InfrastructureError("Expected the owned four-core ARM64 CPU allocation")
    install_identity(MODEL, EFFORT)
    output = root / ("results-" + job)
    output.mkdir(exist_ok=False)
    channel = output / "mailbox"
    codex_mailbox.initialize_channel(channel, plan["session_id"], job)
    result = {"scope": SCOPE, "session_id": plan["session_id"], "model": MODEL,
              "effort": EFFORT, "subject": "matmul", "job_id": job,
              "pipeline_complete": False, "purpose": "mechanical smoke; no R1 comparison"}
    atomic_json(output / "channel.json", {**result, "channel": str(channel)})
    print("SMOKE_CHANNEL_READY", flush=True)
    try:
        settings = load_config()
        settings.update(backend="codex", target_id="romeo-r1-smoke-" + job)
        settings["codex"] = {"model": MODEL, "reasoning_effort": EFFORT,
                             "transport": "codex-mailbox", "session_id": plan["session_id"],
                             "mailbox_dir": str(channel)}
        settings["schedule"].update(cycles=1, trials_per_role_per_cycle=1,
                                    integrations_per_cycle=1)
        ceiling = codex_mailbox.TOKEN_CEILING
        settings["budget"].update(search_slots=7, confirmation_slots=2, wall_seconds=900,
            confirmation_seconds=120, tokens=1500000, mission_tokens=3 * ceiling,
            max_workers=1, generation_seconds=120, infrastructure_retries=0)
        settings["protocol"]["environment"]["OMP_NUM_THREADS"] = "4"
        settings["harness"].update(enabled=True, max_attempts=3, call_token_ceiling=ceiling)
        campaign = create_workspace(output / "matmul", settings)
        atomic_json(output / "allocation.json", {
            "job_id": job, "machine": platform.machine(), "python": os.sys.executable,
            "treequest": importlib.metadata.version("treequest"),
            "cpu_affinity": sorted(os.sched_getaffinity(0)), "gpus": 0,
            "source_package": str(project / "src/hpc_forest"),
            "runtime_manifest_sha256": file_digest(root / "runtime-manifest.json")})
        end = time.monotonic() + 180
        while not (channel / "worker-ready.json").exists():
            if time.monotonic() >= end:
                raise InfrastructureError("The local Luna smoke worker did not connect")
            time.sleep(0.5)
        ready = codex_mailbox.bounded_json(channel / "worker-ready.json", 16384)
        if any(ready.get(k) != v for k, v in {"model": MODEL, "reasoning_effort": EFFORT,
                "session_id": plan["session_id"], "mode": "codex"}.items()):
            raise InfrastructureError("Wrong worker identity")
        statement = (project / "examples/matmul/README.md").read_text(encoding="utf8")
        with SmokeController(campaign, statement) as controller:
            while True:
                result["search"] = controller.run(max_batches=1)
                result["costs"] = controller.db.costs()
                atomic_json(output / "progress.json", result)
                print("SMOKE_PROGRESS", json.dumps(result["search"]), flush=True)
                if result["search"]["status"] != "checkpointed":
                    break
            result["best_confirmed"] = controller.confirm()
            result["costs"] = controller.db.costs()
            result["mother"] = {phase: controller.db.get("mother_plan:" + phase)
                                for phase in ("preparation", "synthesis")}
            result["trials"] = [dict(row) for row in controller.db.rows(
                "SELECT id,role,state,mission,result FROM trials ORDER BY created,id")]
            result["trees"] = [dict(row) for row in controller.db.rows(
                "SELECT id,role,version,stopped FROM trees ORDER BY role")]
        report(campaign)
        result["pipeline_complete"] = smoke_complete(result)
    except Exception as exc:
        result.update(error=type(exc).__name__ + ": " + str(exc),
                      traceback=traceback.format_exc())
    finally:
        atomic_json(output / "results.json", result)
        atomic_json(channel / "DONE.json", {"session_id": plan["session_id"],
                    "pipeline_complete": result["pipeline_complete"], "error": result.get("error")})
        print("SMOKE_DONE", result["pipeline_complete"], flush=True)
    return 0 if result["pipeline_complete"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    remote = sub.add_parser("remote")
    remote.add_argument("--root", type=Path, required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("--receipt", type=Path, required=True)
    worker.add_argument("--output", type=Path, required=True)
    worker.add_argument("--codex-config", type=Path, required=True)
    worker.add_argument("--executable", required=True)
    worker.add_argument("--scope", choices=tuple(PILOTS), default=SCOPE)
    args = parser.parse_args()
    return run_remote(args) if args.mode == "remote" else asyncio.run(serve(args))


if __name__ == "__main__":
    raise SystemExit(main())
