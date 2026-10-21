"""One explicitly authorized Luna MAX smoke; no historical campaign admission."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import platform
import re
import tarfile
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
from hpc_forest.support.budgets import FINISH_STARTED, OBSERVE_TOKENS

SCOPE = "r1-reconstruction-luna-smoke-v1"
OFFICIAL_SCOPE = "r1-official-count-luna-max-v1"
DEPTH_SCOPE = "r1-official-depth-luna-max-v1"
FINISH_SCOPE = "r1-official-depth-luna-max-finish-v3"
ADAPTIVE_SCOPE = "r1-official-luna-max-adaptive-v4"
LEGACY_FOREST_SCOPE = "r1-official-luna-max-mother-forest-v5"
CONVERSATION_SCOPE = "r1-official-luna-max-mother-conversation-v6"
FOREST_SCOPE = "r1-official-luna-max-mother-pairwise-v7"
CONVERSATION_SCOPES = {CONVERSATION_SCOPE, FOREST_SCOPE}
FOREST_SCOPES = {LEGACY_FOREST_SCOPE, *CONVERSATION_SCOPES}
ADAPTIVE_SCOPES = {ADAPTIVE_SCOPE, *FOREST_SCOPES}
COMPLETION_SCOPES = {FINISH_SCOPE, *ADAPTIVE_SCOPES}
DEPTH_SCOPES = {DEPTH_SCOPE, *COMPLETION_SCOPES}
MODEL, EFFORT = "gpt-6-luna", "max"
PILOTS = {SCOPE: ("matmul", 4, "hpc-forest-r1-pilot-"),
          OFFICIAL_SCOPE: ("2023-count", 8, "hpc-forest-r1-official-"),
          DEPTH_SCOPE: ("2023-count", None, "hpc-forest-r1-depth-"),
          FINISH_SCOPE: ("2023-count", None, "hpc-forest-r1-depth-"),
          ADAPTIVE_SCOPE: ("2023-count", None, "hpc-forest-r1-adaptive-"),
          LEGACY_FOREST_SCOPE: ("2023-count", None, "hpc-forest-r1-mother-forest-"),
          CONVERSATION_SCOPE: ("2023-count", None, "hpc-forest-r1-mother-forest-"),
          FOREST_SCOPE: ("2023-count", None, "hpc-forest-r1-mother-forest-")}
OFFICIAL_SHARED_ROOT = "/gpfs/scratch/nimarano/hpc-forest-native-matrix-20261015-r1-launchfix1"


def depth_contract(trials_per_role: int, wall_seconds: int, token_budget: int | None, *, completion=False) -> dict:
    """Keep a pair per role in each cycle so integration shares the finite budget."""
    if type(trials_per_role) is not int or trials_per_role < 2 or trials_per_role % 2:
        raise InfrastructureError("Depth trials per role must be a positive even integer")
    if type(wall_seconds) is not int or wall_seconds <= 120:
        raise InfrastructureError("Depth wall budget must exceed the confirmation reserve")
    if completion and token_budget is not None:
        raise InfrastructureError("The new completion contract has no token quota; use null")
    if not completion and (type(token_budget) is not int or token_budget < 3 * codex_mailbox.TOKEN_CEILING):
        raise InfrastructureError("Depth token budget must admit a complete harness reservation")
    contract = {
        "schedule": {"cycles": trials_per_role // 2, "trials_per_role_per_cycle": 2,
                     "integrations_per_cycle": 2},
        "budget": {"wall_seconds": wall_seconds, "tokens": token_budget, "max_depth": 0,
                   "search_slots": 4 * trials_per_role + 3, "confirmation_slots": 3,
                   "confirmation_seconds": 120, "generation_seconds": 600,
                   "mission_tokens": None if completion else 3 * codex_mailbox.TOKEN_CEILING,
                   "max_workers": 1, "infrastructure_retries": 0},
        "child_missions": 4 * trials_per_role,
        "maximum_calls_including_repairs": 12 * trials_per_role + 2,
    }
    if completion:
        contract.update(
            completion={"policy": FINISH_STARTED, "postprocess_tokens": None, "token_policy": OBSERVE_TOKENS},
            postprocess_missions=1, mother_calls=3,
            maximum_calls_including_repairs=12 * trials_per_role + 6,
            search_deadline_is_admission_only=True,
            postprocess_wall_seconds=None,
            token_budget=None,
        )
    return contract


def adaptive_contract(wall_seconds: float) -> dict:
    try:
        valid = type(wall_seconds) in {int, float} and math.isfinite(wall_seconds) and wall_seconds > 0
    except OverflowError:
        valid = False
    if not valid:
        raise InfrastructureError("The adaptive duration must be positive and finite")
    contract = depth_contract(2, max(121, math.ceil(wall_seconds)), None, completion=True)
    contract["schedule"]["cycles"] = None
    contract["budget"].update(wall_seconds=wall_seconds, search_slots=None)
    contract["completion"].update(reserve_policy="adaptive", confirm_final_g=True)
    contract.update(child_missions=None, maximum_calls_including_repairs=None,
                    trials_per_role=None, wall_seconds=wall_seconds)
    return contract


def forest_contract(wall_seconds: float, *, persistent=True, pairwise=True) -> dict:
    contract = adaptive_contract(wall_seconds)
    contract["forest"] = {"policy": "mother"}
    if persistent:
        contract["forest"]["conversation"] = "persistent"
        contract["schedule"].update(trials_per_role_per_cycle=1, integrations_per_cycle=0)
        contract["mother_calls"] = 2  # Planning, then Mother herself produces G in the same thread.
        if pairwise:
            contract["forest"]["integration"] = "pairwise"
            contract.update(mother_calls=None, postprocess_missions=None)
    return contract


def validate_depth_plan(plan: dict) -> None:
    """Validate the new contract without broadening any historical admission scope."""
    model_mcp_enabled(plan)
    documentation_enabled(plan)
    skills_enabled(plan)
    session = plan.get("session_id")
    scope = plan.get("scope")
    if (scope not in DEPTH_SCOPES or not isinstance(session, str) or not re.fullmatch(r"[a-f0-9]{32}", session)
            or plan.get("remote_root") != "/scratch_p/nimarano/" + PILOTS[scope][2] + session):
        raise InfrastructureError("The depth plan must name its own random session and remote root")
    expected = (forest_contract(plan.get("wall_seconds"), persistent=scope in CONVERSATION_SCOPES,
                               pairwise=scope == FOREST_SCOPE) if scope in FOREST_SCOPES else
                adaptive_contract(plan.get("wall_seconds")) if scope == ADAPTIVE_SCOPE else
                depth_contract(plan.get("trials_per_role"), plan.get("wall_seconds"),
                               plan.get("token_budget"), completion=scope == FINISH_SCOPE))
    fixed = {"scope": scope, "model": MODEL, "effort": EFFORT,
             "subject": "2023-count", "seed": 23, "mother_calls": 3 if scope in COMPLETION_SCOPES else 2,
             "depth_comparison": True, "max_depth": 0, "cores": 4, "gpus": 0,
             "historical_candidates_imported": False, **expected}
    if any(json.dumps(plan.get(key), sort_keys=True) != json.dumps(value, sort_keys=True)
           for key, value in fixed.items()):
        raise InfrastructureError("The depth plan does not match its explicit schedule and budget")
    binary = plan.get("binary_tree")
    if (not isinstance(binary, dict) or set(binary) != {"enabled"}
            or type(binary["enabled"]) is not bool):
        raise InfrastructureError("The depth search policy must be explicit")
    if scope in FOREST_SCOPES and binary["enabled"]:
        raise InfrastructureError("Mother-selected forests use AB-MCTS only")
    for key, relative in (("preparation_manifest", "prepared/prepared-manifest.json"),
                          ("statement", "statements/2023.txt")):
        item = plan.get(key, {})
        if (not isinstance(item, dict) or item.get("path") != OFFICIAL_SHARED_ROOT + "/" + relative
                or not isinstance(item.get("sha256"), str)
                or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])):
            raise InfrastructureError("The depth plan must pin its frozen official " + key)


def model_mcp_enabled(plan: dict) -> bool:
    """Only explicitly pinned conversation plans opt in to the existing profile."""
    from hpc_forest.model_mcp import MODEL_MCP_POLICY

    if "model_mcp" not in plan:
        return False
    if plan.get("scope") not in CONVERSATION_SCOPES or plan["model_mcp"] != MODEL_MCP_POLICY:
        raise InfrastructureError("The model MCP access must explicitly bind the existing ROMEO profile")
    return True


def documentation_enabled(plan: dict) -> bool:
    """New plans explicitly freeze references without changing historical tool access."""
    from hpc_forest.documentation_mcp import DOCUMENTATION_POLICY

    if "documentation" not in plan:
        return False
    if (plan.get("scope") not in CONVERSATION_SCOPES or plan["documentation"] != DOCUMENTATION_POLICY
            or not model_mcp_enabled(plan)):
        raise InfrastructureError("The official documentation access or catalogue does not match its frozen plan")
    return True


def skills_enabled(plan: dict) -> bool:
    """Only new, explicitly pinned plans load the project's role-specific skills."""
    from hpc_forest.model_skills import policy as skills_policy

    if "skills" not in plan:
        return False
    if plan.get("scope") not in CONVERSATION_SCOPES or plan["skills"] != skills_policy():
        raise InfrastructureError("Project skills do not match the frozen campaign plan")
    return True


def worker_lifetime_seconds(scope: str, plan: dict) -> int | None:
    if scope in DEPTH_SCOPES:
        validate_depth_plan(plan)
        if scope in COMPLETION_SCOPES:
            return None
        return plan["wall_seconds"] + 900
    return 2700 if scope == OFFICIAL_SCOPE else 1200


def verify_files(root: Path, manifest: dict) -> None:
    for relative, expected in manifest.items():
        path = root / relative
        if (not path.resolve().is_relative_to(root.resolve()) or path.is_symlink()
                or not path.is_file() or file_digest(path) != expected):
            raise InfrastructureError("The smoke payload changed: " + relative)


def authorize(path: Path, required: set[str], *, allow_running_completion=False) -> dict:
    value = codex_mailbox.bounded_json(path, 65536)
    scope = value.get("scope")
    if (scope not in PILOTS or required != {scope}
            or value.get("model") != MODEL or value.get("effort") != EFFORT
            or (value.get("expires_at", 0) <= time.time()
                and not (scope in COMPLETION_SCOPES and allow_running_completion))
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
    model_mcp_enabled(plan)
    documentation_enabled(plan)
    subject, missions, prefix = PILOTS[scope]
    if scope in DEPTH_SCOPES:
        validate_depth_plan(plan)
        missions = plan["child_missions"]
        if (value.get("remote_payload") != plan.get("remote_root", "") + ".tar.gz"
                or not isinstance(value.get("user_request"), str)
                or not value["user_request"].strip()
                or type(plan.get("created_at")) not in {float, int}
                or not math.isfinite(plan["created_at"])
                or type(value.get("expires_at")) not in {float, int}
                or not math.isfinite(value["expires_at"])
                or value["expires_at"] < plan["created_at"] + plan["wall_seconds"] + 900):
            raise InfrastructureError("The depth receipt does not cover its owned payload and wall budget")
        try:
            with tarfile.open(value["payload"]["path"], "r:gz") as archive:
                members = [member for member in archive.getmembers() if member.name == "plan.json"]
                if len(members) != 1 or not members[0].isfile() or members[0].size > 65536:
                    raise InfrastructureError("The depth payload must contain one bounded frozen plan")
                with archive.extractfile(members[0]) as stream:
                    if codex_mailbox.sha256(stream.read()) != value["plan"]["sha256"]:
                        raise InfrastructureError("The payload contains a different depth plan")
        except (OSError, tarfile.TarError) as exc:
            raise InfrastructureError("The authorized depth payload is not readable") from exc
    mother_calls = (None if scope == FOREST_SCOPE else 2 if scope == CONVERSATION_SCOPE
                    else 3 if scope in COMPLETION_SCOPES else 2)
    if (plan.get("scope") != scope or plan.get("session_id") != session
            or plan.get("model") != MODEL or plan.get("effort") != EFFORT
            or plan.get("subject") != subject or plan.get("child_missions") != missions
            or plan.get("mother_calls") != mother_calls):
        raise InfrastructureError("The smoke plan does not match its authorization")
    if scope == OFFICIAL_SCOPE and (plan.get("wall_seconds") != 1800
            or plan.get("token_budget") != 1500000 or plan.get("seed") != 23):
        raise InfrastructureError("The official pilot must retain the historical R1 budgets")
    if scope in COMPLETION_SCOPES and value.get("completion") != plan["completion"]:
        raise InfrastructureError("The receipt must explicitly cover the separate completion budget")
    root = PurePosixPath(plan["remote_root"])
    channel = PurePosixPath(value["channel"])
    if (root != PurePosixPath("/scratch_p/nimarano") / (prefix + session)
            or channel.parent.parent != root or channel.name != "mailbox"
            or not re.fullmatch(r"results-[0-9]+", channel.parent.name)):
        raise InfrastructureError("The smoke channel is not owned by this session")
    return value


def install_worker_identity(receipt: Path, scope=SCOPE) -> dict:
    value = authorize(receipt, {scope})
    receipt_sha = file_digest(receipt)
    install_identity(MODEL, EFFORT)

    def gate(path, required):
        fresh = authorize(path, required, allow_running_completion=scope in COMPLETION_SCOPES)
        if scope in COMPLETION_SCOPES and file_digest(path) != receipt_sha:
            raise InfrastructureError("The running completion authorization changed")
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
    plan = codex_mailbox.bounded_json(Path(identity["plan"]["path"]), 65536)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with FileLock(output / "worker.lock"):
        async with codex_worker.RomeoFiles(args.codex_config) as files:
            worker = codex_worker.Worker(files, identity["channel"], identity["session_id"],
                output, args.receipt, {scope}, executable=args.executable, defer_diagnostics=True,
                model_mcp_config=args.codex_config if model_mcp_enabled(plan) else None,
                documentation=documentation_enabled(plan))
            await worker.hello()
            lifetime = worker_lifetime_seconds(scope, plan)
            end = None if lifetime is None else time.monotonic() + lifetime
            from hpc_forest.request_pool import RequestPool

            pool = RequestPool(worker)
            try:
                async with worker.keepalive(lifetime is None):
                    while end is None or time.monotonic() < end:
                        listing = await worker.transfer_call(
                            lambda: files.call("list_dir", path=identity["channel"], limit=30))
                        if scope in FOREST_SCOPES:
                            width = (await worker.controller_forest_width() if any(
                                item["name"] == "forest-plan.json" for item in listing["entries"]) else 1)
                            await pool.pump(await worker.request_names(width), width)
                        else:
                            for name in sorted(await worker.request_names()):
                                await worker.handle(name)
                        if any(item["name"] == "DONE.json" for item in listing["entries"]):
                            await pool.drain()
                            await worker.transfer_call(lambda: files.download(
                                identity["channel"] + "/DONE.json", output / "DONE.json"))
                            done = codex_mailbox.bounded_json(output / "DONE.json", 65536)
                            if done.get("session_id") != identity["session_id"]:
                                raise InfrastructureError("Mismatched smoke completion")
                            pending = await worker.flush_diagnostics(
                                deadline=math.inf if scope in FOREST_SCOPES else
                                    time.time() + (120 if end is None else min(120, max(0, end - time.monotonic()))))
                            if pending:
                                print("SMOKE_DIAGNOSTICS_PENDING", len(pending), flush=True)
                            return 0 if done.get("pipeline_complete") else 1
                        await asyncio.sleep(2)
            finally:
                await pool.close()
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


def depth_completion(result: dict, *, trials_per_role: int | None) -> dict:
    """Separate successful bounded execution from completing every planned trial."""
    all_trials = result.get("trials", [])
    soft = result.get("completion", {}).get("policy") == FINISH_STARTED
    def phase(trial):
        mission = trial.get("mission", {})
        if isinstance(mission, str):
            mission = json.loads(mission)
        return mission.get("budget_phase", "search")
    trials = [trial for trial in all_trials if phase(trial) == "search"]
    post_trials = [trial for trial in all_trials if phase(trial) == "postprocess"]
    selected = result.get("forest_plan")
    roles = [child["role"] for child in selected["children"]] if selected else list("ABC")
    counts = {role: sum(trial.get("role") == role for trial in trials) for role in [*roles, "G"]}
    outcomes = [json.loads(trial["result"]) if trial.get("result") else {} for trial in trials]
    status = result.get("search", {}).get("status")
    bounded = status == "budget_exhausted"
    schedule_completed = trials_per_role is not None and status == "search_complete" and all(
        count == trials_per_role for count in counts.values())
    mother = result.get("mother", {})
    phases = {phase: (mother.get(phase) or {}).get("status", "not_reached")
              for phase in ("preparation", "synthesis")}
    reached = {"preparation": bool(selected) or any(counts[role] for role in roles), "synthesis": counts["G"] > 0}
    clean = (len(trials) == sum(counts.values())
             and (trials_per_role is None or all(count <= trials_per_role for count in counts.values()))
             and all(outcome.get("status") not in (None, "infrastructure_error")
                     for outcome in outcomes)
             and all(value in {"complete", "not_invoked_budget"}
                     or value == "not_reached" and not reached[phase]
                     for phase, value in phases.items()))
    search_result = {**result, "trials": trials}
    complete = (smoke_complete(search_result, trials_per_role=trials_per_role) if schedule_completed
                else (bounded or trials_per_role is None and status == "search_complete")
                and bool(result.get("best_confirmed")) and clean)
    post = result.get("postprocess") or {}
    if soft:
        steps = post.get("steps") or []
        pairwise = result.get("scope") == FOREST_SCOPE
        expected_post = max(1, len(post.get("leaf_program_ids", [])) - 1) if pairwise else 1
        complete = (complete and post.get("status") == "complete"
                    and (post.get("mother") or {}).get("status") == "complete"
                    and len(post_trials) == expected_post and all(trial.get("role") == "G" for trial in post_trials))
        if pairwise:
            complete = (complete and post.get("integration_policy") == "pairwise"
                        and len(steps) == expected_post
                        and [step.get("mission_id") for step in steps] == [trial.get("id") for trial in post_trials]
                        and all(step.get("status") == "complete" and 1 <= len(step.get("input_ids", [])) <= 2
                                for step in steps)
                        and steps[-1].get("final") is True and steps[-1].get("mission_id") == post.get("mission_id"))
    elif post_trials:
        complete = False
    if result.get("completion", {}).get("confirm_final_g"):
        final = result.get("final_g_confirmation") or {}
        complete = (complete and final.get("status") in {"confirmed", "rejected"}
                    and final.get("experiment_id") == post.get("mission_id")
                    and bool(final.get("outcome")))
    if result.get("scope") in FOREST_SCOPES:
        complete = (complete and bool(selected) and selected.get("status") == "complete"
                    and all(counts[role] > 0 for role in roles)
                    and all(outcome.get("status") not in {"cancelled_budget", "cancelled_interrupted", "generation_failed"}
                            for outcome in outcomes))
    if result.get("scope") in CONVERSATION_SCOPES:
        original = (selected or {}).get("conversation") or {}
        assembled = (post.get("mother") or {}).get("conversation") or {}
        complete = (complete and bool(original) and assembled.get("id") == original.get("id")
                    and assembled.get("thread_id") == original.get("thread_id")
                    and assembled.get("phase") == "assembly" and assembled.get("turn", 0) >= 1
                    and counts["G"] == 0)
        if result.get("scope") == FOREST_SCOPE:
            previous_turn = 0
            for step in post.get("steps", []):
                receipt = (step.get("mother") or {}).get("conversation") or {}
                turn = receipt.get("turn")
                complete = (complete and receipt.get("id") == original.get("id")
                            and receipt.get("thread_id") == original.get("thread_id")
                            and receipt.get("phase") == "assembly" and type(turn) is int
                            and turn > previous_turn)
                previous_turn = turn if type(turn) is int else previous_turn
            complete = complete and bool(post.get("steps")) and (
                post["steps"][-1].get("mother") or {}).get("conversation") == assembled
    return {"pipeline_complete": bool(complete), "schedule_completed": schedule_completed,
            "budget_exhausted": bounded, "stop_reason": status,
            "requested_trials_per_role": trials_per_role, "realized_trials_per_role": counts,
            "mother_phase_status": phases, "postprocess_missions": len(post_trials),
            "postprocess_status": post.get("status", "not_configured")}


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
        settings["completion"] = {"policy": "hard"}  # Preserve this historical mechanical scope.
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
