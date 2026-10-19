"""Native Codex generation with an explicit model/effort and no candidate execution."""
from __future__ import annotations

import copy
import json
import shutil
import time
from pathlib import Path

from .codex_mailbox import (
    EFFORT,
    MODEL,
    TOKEN_CEILING,
    bounded_json,
    response_envelope,
    sha256,
)
from .core import InfrastructureError, atomic_json, run_process


def check_dependencies(receipt: Path, required_jobs: set[str]) -> dict:
    gate = bounded_json(receipt, 65536)
    if gate.get("status") == "harness_comparison_explicitly_authorized":
        if (gate.get("schema") != "hpc-forest-explicit-harness-comparison-v1"
                or gate.get("scope_id") != "gpt61sol-max-harness-20261015-r2"
                or required_jobs != {gate.get("scope_id")}
                or gate.get("next_model") != MODEL or gate.get("reasoning_effort") != EFFORT
                or gate.get("problems") != ["knn", "sum", "nbody"]
                or gate.get("arms") != ["reference", "mixed-harness"]
                or gate.get("harness_enabled") is not True
                or gate.get("max_calls_per_harness_mission") != 3
                or gate.get("planned_slots_per_problem_per_arm") != 24
                or gate.get("wall_seconds_per_problem_per_arm") != 7200
                or gate.get("token_budget_per_problem_per_arm") != 1500000
                or gate.get("deepseek_completion_claimed") is not False
                or not isinstance(gate.get("user_message"), str)
                or not gate["user_message"].strip()
                or gate.get("expires_at", 0) <= time.time()):
            raise InfrastructureError("The explicit harness comparison authorization is invalid or expired")
        return gate
    if gate.get("status") == "parallel_pilot_explicitly_authorized":
        if (gate.get("schema") != "hpc-forest-explicit-parallel-pilot-v1"
                or gate.get("scope_id") != "gpt61sol-max-pilot-20261015-r1"
                or required_jobs != {gate.get("scope_id")}
                or gate.get("next_model") != MODEL or gate.get("reasoning_effort") != EFFORT
                or gate.get("deepseek_completion_claimed") is not False
                or not isinstance(gate.get("user_message"), str)
                or not gate["user_message"].strip()
                or gate.get("expires_at", 0) <= time.time()):
            raise InfrastructureError("The explicit parallel pilot authorization is invalid or expired")
        return gate
    if (gate.get("status") != "deepseek_results_received_and_audited"
            or gate.get("next_model") != MODEL or gate.get("reasoning_effort") != EFFORT
            or set(gate.get("finished_job_ids", [])) != required_jobs):
        raise InfrastructureError("DeepSeek completion and receipt have not been established")
    archives = gate.get("archives", [])
    if len(archives) != len(required_jobs) or {a.get("job_id") for a in archives} != required_jobs:
        raise InfrastructureError("Missing DeepSeek archive receipts")
    for item in archives:
        archive = Path(item["path"])
        if archive.is_symlink() or not archive.is_file():
            raise InfrastructureError("A received DeepSeek archive is unavailable")
        if sha256(archive.read_bytes()) != item.get("sha256"):
            raise InfrastructureError("A received DeepSeek archive changed")
    return gate


def wire_schema(schema: dict) -> dict:
    """Drop provider-specific array keywords; the source validator keeps enforcing them."""
    schema = copy.deepcopy(schema)

    def visit(value):
        if isinstance(value, dict):
            value.pop("uniqueItems", None)
            value.pop("maxItems", None)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    return schema


def command_for(request: dict, output: Path, executable: str = "codex") -> list[str]:
    if request.get("model") != MODEL or request.get("reasoning_effort") != EFFORT:
        raise InfrastructureError("A different model or reasoning effort is forbidden")
    executable = shutil.which(executable)
    if not executable:
        raise InfrastructureError("The authenticated Codex CLI is unavailable locally")
    output.mkdir(parents=True, exist_ok=True)
    messages = request["messages"]
    if [m.get("role") for m in messages] != ["system", "user"]:
        raise InfrastructureError("Expected the frozen neutral system/user prompt")
    (output / "instructions.txt").write_text(messages[0]["content"], encoding="utf8")
    atomic_json(output / "output-schema.json", wire_schema(request["schema"]))
    args = [executable, "exec", "--ignore-user-config", "--strict-config", "--ephemeral",
            "--skip-git-repo-check", "--sandbox", "read-only", "--json", "--color", "never",
            "--model", MODEL, "--output-schema", str(output / "output-schema.json"),
            "--output-last-message", str(output / "agent-result.json"), "-C", str(output)]
    overrides = {
        "model_reasoning_effort": EFFORT,
        "model_instructions_file": str(output / "instructions.txt"),
        "model_context_window": 65536,
        "project_doc_max_bytes": 0,
        "skills.max_context_tokens": 1,
        "approval_policy": "never",
        "forced_login_method": "chatgpt",
        "web_search": "disabled",
        "features.skip_host_skill_discovery": True,
        **{f"features.{name}": False for name in [
            "shell_tool", "unified_exec", "apps", "plugins", "memories", "multi_agent",
            "multi_agent_v2", "hooks", "skill_search", "browser_use", "computer_use",
            "image_generation", "view_image", "workspace_dependencies", "code_mode_host",
            "sleep_tool", "unbounded_connection_retries", "shell_snapshot", "goals",
        ]},
    }
    for key, value in overrides.items():
        args.extend(["--config", f"{key}={json.dumps(value, ensure_ascii=False)}"])
    return [*args, "-"]


def usage_from_events(path: Path) -> tuple[dict, bool]:
    usage_events, tool_events = [], []
    for line in path.read_text(encoding="utf8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage_events.append(event["usage"])
        item = event.get("item", {})
        if event.get("type") in {"item.started", "item.completed", "item.updated"}:
            if item.get("type") not in {"agent_message", "reasoning", "error", None}:
                tool_events.append(item.get("type"))
    known = bool(usage_events) and all(
        all(type(u.get(k)) is int and u[k] >= 0 for k in ["input_tokens", "output_tokens"])
        for u in usage_events
    )
    return {
        "tokens": sum(u["input_tokens"] + u["output_tokens"] for u in usage_events)
        if known else TOKEN_CEILING,
        "token_accounting": "exact" if known else "upper_bound",
        "events": usage_events, "llm_calls": max(1, len(usage_events)),
        "model_requested": MODEL, "reasoning_effort_requested": EFFORT,
        "cached_tokens_included_in_input": True, "tool_events": tool_events,
        "codex_jsonl_sha256": sha256(path.read_bytes()),
    }, bool(tool_events)


def run_codex(request: dict, request_sha: str, output: Path, dependency_receipt: Path,
              required_jobs: set[str], executable="codex") -> dict:
    gate = check_dependencies(dependency_receipt, required_jobs)
    if (gate.get("status") in {"parallel_pilot_explicitly_authorized",
                               "harness_comparison_explicitly_authorized"}
            and request.get("session_id") != gate.get("session_id")):
        raise InfrastructureError("Generation belongs to another explicitly authorized session")
    timeout = request["expires_at"] - time.time() - 5
    if timeout <= 0:
        return response_envelope(request, request_sha, error="Request expired before generation",
                                 infrastructure_error=True,
                                 usage={"tokens": 0, "token_accounting": "exact", "llm_calls": 0})
    argv = command_for(request, output, executable)
    atomic_json(output / "invocation.json", {
        "argv": argv, "model": MODEL, "reasoning_effort": EFFORT,
        "request_sha256": request_sha, "hosted_inference": True,
        "source_execution_allowed": False,
    })
    atomic_json(output / "request.json", request)
    result = run_process(argv, output, output / "codex.jsonl", timeout,
                         env={"OPENAI_API_KEY": "", "CODEX_API_KEY": ""},
                         stdin=request["messages"][1]["content"])
    usage, tools = usage_from_events(Path(result.log))
    error = None
    infra = False
    data = None
    if result.returncode or result.timed_out:
        error, infra = "Codex failed or exceeded the generation deadline; inspect its log", True
    elif tools:
        error, infra = "Codex attempted a tool call in a source-only generation", True
    else:
        try:
            data = bounded_json(output / "agent-result.json")
        except (OSError, ValueError, InfrastructureError) as exc:
            error = f"Codex returned no valid structured proposal: {exc}"
    response = response_envelope(request, request_sha, data=data, usage=usage,
                                 error=error, infrastructure_error=infra)
    atomic_json(output / "response.json", response)
    return response
