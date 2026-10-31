"""Native Codex generation with explicit identity and optional ROMEO MCP access."""
from __future__ import annotations

import copy
import json
import shutil
import time
from pathlib import Path

from .codex_conversation import run_turn, workspace_for
from .codex_mailbox import (
    EFFORT,
    MODEL,
    TOKEN_CEILING,
    bounded_json,
    response_envelope,
    sha256,
)
from .core import CandidateRejected, InfrastructureError, atomic_json, run_process
from .diagnostics_mcp import INSTRUCTIONS as DIAGNOSTIC_INSTRUCTIONS
from .diagnostics_mcp import DiagnosticsMCP
from .documentation_mcp import DOCUMENTATION_INSTRUCTIONS, DOCUMENTATION_TOOLS, DocumentationMCP
from .model_mcp import DISABLED_MODEL_TOOLS, RomeoMCP
from .model_policy import DSH_MODEL, require_identity, require_request_identity
from .model_runtime import environment as model_environment
from .model_runtime import overrides as provider_overrides
from .model_runtime import (
    structured_output_args,
    structured_output_instructions,
    validate_structured_output,
)
from .model_skills import consume_report, usage_trace, verify_binding
from .support.budgets import FINISH_STARTED, OBSERVE_TOKENS, time_left


def check_dependencies(receipt: Path, required_jobs: set[str]) -> dict:
    gate = bounded_json(receipt, 65536)
    if gate.get("schema") == "forest-app-authorization-v1":
        from .webapp.runner_support import validate_authorization

        return validate_authorization(receipt, gate, required_jobs)
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


def command_for(request: dict, output: Path, executable: str = "codex", *,
                romeo_mcp: RomeoMCP | None = None,
                documentation_mcp: DocumentationMCP | None = None,
                diagnostics_mcp: DiagnosticsMCP | None = None,
                dsh_settings: dict | None = None) -> list[str]:
    require_identity(request)
    executable = shutil.which(executable)
    if not executable:
        raise InfrastructureError("The authenticated Codex CLI is unavailable locally")
    output.mkdir(parents=True, exist_ok=True)
    messages = request["messages"]
    if [m.get("role") for m in messages] != ["system", "user"]:
        raise InfrastructureError("Expected the frozen neutral system/user prompt")
    verify_binding(request)
    system = messages[0]["content"]
    if romeo_mcp is not None:
        system = romeo_mcp.instructions(system)
    if documentation_mcp is not None:
        system += DOCUMENTATION_INSTRUCTIONS
    if diagnostics_mcp is not None:
        system += DIAGNOSTIC_INSTRUCTIONS
    system += structured_output_instructions(request["model"], request["schema"])
    (output / "instructions.txt").write_text(system, encoding="utf8")
    atomic_json(output / "output-schema.json", wire_schema(request["schema"]))
    persistent = request.get("conversation") is not None
    workspace = workspace_for(request, output) if persistent else output
    workspace.mkdir(parents=True, exist_ok=True)
    args = [executable, "exec", "--sandbox", "read-only", "--color", "never", "-C", str(workspace)]
    if persistent and request["conversation"]["turn"] > 0:
        args += ["resume", request["conversation"]["thread_id"]]
    # Resume has its own schema, model and config options. Pass them directly to
    # that subcommand so the planning schema cannot survive into code assembly.
    args += ["--ignore-user-config", "--strict-config", "--skip-git-repo-check", "--json",
             "--model", request["model"],
             *structured_output_args(request["model"], output / "output-schema.json",
                                     tools_enabled=any(m is not None for m in
                                         (romeo_mcp, documentation_mcp, diagnostics_mcp))),
             "--output-last-message", str(output / "agent-result.json")]
    if not persistent:
        args.append("--ephemeral")
    overrides = {
        "model_reasoning_effort": request["reasoning_effort"],
        "model_instructions_file": str(output / "instructions.txt"),
        "project_doc_max_bytes": 0,
        "skills.max_context_tokens": 1,
        "approval_policy": "never",
        **provider_overrides(request["model"], dsh_settings),
        "web_search": "disabled",
        "features.skip_host_skill_discovery": True,
        "features.code_mode_host": any(m is not None for m in (romeo_mcp, documentation_mcp, diagnostics_mcp)),
        **{f"features.{name}": False for name in [
            "shell_tool", "unified_exec", "apps", "plugins", "memories", "multi_agent",
            "multi_agent_v2", "hooks", "skill_search", "browser_use", "computer_use",
            "image_generation", "view_image", "workspace_dependencies",
            "sleep_tool", "unbounded_connection_retries", "shell_snapshot", "goals",
        ]},
    }
    if request.get("token_policy") != OBSERVE_TOKENS:
        overrides["model_context_window"] = 65536
    if romeo_mcp is not None:
        overrides.update(romeo_mcp.overrides())
    if documentation_mcp is not None:
        overrides.update(documentation_mcp.overrides(request["nonce"]))
    if diagnostics_mcp is not None:
        overrides.update(diagnostics_mcp.overrides())
    for key, value in overrides.items():
        args.extend(["--config", f"{key}={json.dumps(value, ensure_ascii=False)}"])
    return [*args, "-"]


def authorized_discovery(item: dict, *, romeo: bool, documentation: bool, diagnostics: bool = False) -> bool:
    """Allow built-in metadata discovery only for explicitly bound MCP servers."""
    servers = (({"romeo"} if romeo else set()) | ({"hpc_docs"} if documentation else set())
               | ({"hpc_diagnostics"} if diagnostics else set()))
    if (not servers or item.get("server") != "codex"
            or item.get("tool") not in {"list_mcp_resources", "list_mcp_resource_templates"}):
        return False
    arguments = item.get("arguments")
    if not isinstance(arguments, dict) or set(arguments) - {"server", "cursor"}:
        return False
    server, cursor = arguments.get("server"), arguments.get("cursor")
    return ((server is None or isinstance(server, str) and server in servers)
            and (cursor is None or isinstance(cursor, str)))


def usage_from_events(path: Path, *, observe_only: bool = False,
                      allow_romeo_mcp: bool = False, allow_documentation: bool = False,
                      diagnostic_tools: tuple[str, ...] = (),
                      allow_empty_agent_wait: bool = False) -> tuple[dict, bool]:
    usage_events, tool_events = [], []
    mcp_calls, forbidden_tools, runtime_errors = {}, [], []
    turn_failures = []
    native_noops = {}
    for line in path.read_text(encoding="utf8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage_events.append(event["usage"])
        failure = event.get("error")
        if (event.get("type") == "turn.failed" and isinstance(failure, dict)
                and isinstance(failure.get("message"), str)):
            turn_failures.append(failure["message"])
        item = event.get("item", {})
        if event.get("type") in {"item.started", "item.completed", "item.updated"}:
            if item.get("type") == "error" and (allow_romeo_mcp or allow_documentation or diagnostic_tools):
                message = str(item.get("message", ""))
                if "Code Mode is unavailable" in message or "code-mode host is disabled" in message:
                    runtime_errors.append(message)
            if item.get("type") not in {"agent_message", "reasoning", "error", None}:
                tool_events.append(item.get("type"))
                # Some CLI versions emit a wait with no recipients even when
                # multi-agent tools are disabled. Recognize only that exact
                # no-op; delegation, a missing recipient list and other tools
                # remain forbidden.
                empty_wait = (allow_empty_agent_wait and item.get("type") == "collab_tool_call"
                    and item.get("tool") == "wait" and item.get("receiver_thread_ids") == []
                    and item.get("agents_states") == {}
                    and item.get("prompt") is None
                    and item.get("status") in {"in_progress", "completed"}
                    and not set(item) - {"id", "type", "tool", "status", "sender_thread_id",
                                         "receiver_thread_ids", "agents_states", "prompt"})
                if empty_wait:
                    native_noops[item.get("id") or f"event-{len(tool_events)}"] = {
                        "type": "empty_agent_wait", "status": item["status"]}
                allowed = empty_wait or (item.get("type") == "mcp_tool_call" and isinstance(item.get("tool"), str)
                           and bool(item["tool"]) and (
                               (allow_romeo_mcp and item.get("server") == "romeo"
                                and item["tool"] not in DISABLED_MODEL_TOOLS)
                               or (allow_documentation and item.get("server") == "hpc_docs"
                                   and item["tool"] in DOCUMENTATION_TOOLS)
                               or (item.get("server") == "hpc_diagnostics" and item["tool"] in diagnostic_tools)
                               or authorized_discovery(item, romeo=allow_romeo_mcp,
                                                       documentation=allow_documentation,
                                                       diagnostics=bool(diagnostic_tools))))
                if not allowed:
                    forbidden_tools.append(item.get("type"))
                if item.get("type") == "mcp_tool_call":
                    identifier = item.get("id") or f"event-{len(tool_events)}"
                    mcp_calls[identifier] = {"id": identifier, "server": item.get("server"),
                                             "tool": item.get("tool"), "status": item.get("status"),
                                             "allowed": bool(allowed)}
    known = bool(usage_events) and all(
        all(type(u.get(k)) is int and u[k] >= 0 for k in ["input_tokens", "output_tokens"])
        for u in usage_events
    )
    return {
        "tokens": sum(u["input_tokens"] + u["output_tokens"] for u in usage_events)
        if known else None if observe_only else TOKEN_CEILING,
        "token_accounting": "exact" if known else "unknown" if observe_only else "upper_bound",
        "observed_tokens": sum(u["input_tokens"] + u["output_tokens"] for u in usage_events
                               if all(type(u.get(k)) is int and u[k] >= 0
                                      for k in ["input_tokens", "output_tokens"])),
        "events": usage_events, "llm_calls": max(1, len(usage_events)),
        "model_requested": MODEL, "reasoning_effort_requested": EFFORT,
        "cached_tokens_included_in_input": True, "tool_events": tool_events,
        "mcp_tool_calls": list(mcp_calls.values()), "forbidden_tool_events": forbidden_tools,
        "tool_runtime_errors": list(dict.fromkeys(runtime_errors)),
        "turn_failure_messages": list(dict.fromkeys(turn_failures)),
        "native_noops": list(native_noops.values()),
        "codex_jsonl_sha256": sha256(path.read_bytes()),
    }, bool(forbidden_tools)


def run_codex(request: dict, request_sha: str, output: Path, dependency_receipt: Path,
              required_jobs: set[str], executable="codex", *, romeo_mcp: RomeoMCP | None = None,
              documentation_mcp: DocumentationMCP | None = None,
              diagnostics_mcp: DiagnosticsMCP | None = None,
              dsh_settings: dict | None = None) -> dict:
    gate = check_dependencies(dependency_receipt, required_jobs)
    if gate.get("schema") == "forest-app-authorization-v1":
        if request.get("session_id") != gate.get("session_id"):
            raise InfrastructureError("Request differs from the authorized application mission")
        require_request_identity(request, {"model": gate["next_model"],
            "reasoning_effort": gate["reasoning_effort"], "generator_pool": gate.get("generator_pool", [])})
        if dsh_settings != gate.get("dsh_romeo"):
            raise InfrastructureError("dsh-romeo connection differs from the authorized mission")
    if "active_control" in request:
        from .active_contract import validate_request

        validate_request(request)
        romeo_mcp = documentation_mcp = None  # Only the separately scoped diagnostic service is allowed.
    if request.get("model") == DSH_MODEL and request.get("meta_role") == "mother-plan-review":
        # The critique uses its persisted planning context. Keep this bounded
        # report tool-free so ROMEO can enforce its original JSON schema.
        romeo_mcp = documentation_mcp = None
    if request.get("meta_role") == "mother-plan-repair":
        turn = request.get("conversation") or {}
        if turn.get("phase") != "plan-review" or turn.get("turn") != 1 or request.get("diagnostics") is not None:
            raise InfrastructureError("Plan format repair requires the first native continuation without tools")
        romeo_mcp = documentation_mcp = None
    if request.get("diagnostics") is not None:
        if diagnostics_mcp is None:
            raise InfrastructureError("The controller requested diagnostics but the native worker did not bind them")
        from .diagnostics_contract import load_grant

        load_grant(diagnostics_mcp.root, diagnostics_mcp.binding, request)
    elif diagnostics_mcp is not None:
        raise InfrastructureError("Diagnostic tools require a controller request grant")
    if (gate.get("status") in {"parallel_pilot_explicitly_authorized",
                               "harness_comparison_explicitly_authorized"}
            and request.get("session_id") != gate.get("session_id")):
        raise InfrastructureError("Generation belongs to another explicitly authorized session")
    if request["expires_at"] is None and request.get("deadline_policy") != FINISH_STARTED:
        raise InfrastructureError("An unlimited request requires the finish-started contract")
    if request["expires_at"] is None and gate.get("completion", {}).get("policy") != FINISH_STARTED:
        raise InfrastructureError("The authorization does not cover unlimited completion time")
    observe_only = request.get("token_policy") == OBSERVE_TOKENS
    if observe_only and gate.get("completion", {}).get("token_policy") != OBSERVE_TOKENS:
        raise InfrastructureError("The authorization does not cover unlimited token consumption")
    timeout = time_left(request["expires_at"], now=time.time())
    if timeout is not None:
        timeout -= 5
    if timeout is not None and timeout <= 0:
        return response_envelope(
            request,
            request_sha,
            error="Request expired before generation",
            infrastructure_error=False,
            usage={
                "tokens": 0,
                "token_accounting": "exact",
                "llm_calls": 0,
                "generation_not_started": "search_deadline",
            },
        )
    def invoke():
        return _invoke(request, request_sha, output, executable, timeout, observe_only,
                       romeo_mcp, documentation_mcp, diagnostics_mcp, dsh_settings)
    if request.get("conversation") is not None:
        return run_turn(request, request_sha, output, invoke)
    return invoke()


def _invoke(request, request_sha, output, executable, timeout, observe_only,
            romeo_mcp=None, documentation_mcp=None, diagnostics_mcp=None, dsh_settings=None):
    from .model_policy import provider

    options = {"romeo_mcp": romeo_mcp}
    if dsh_settings is not None:
        options["dsh_settings"] = dsh_settings
    if documentation_mcp is not None:
        options["documentation_mcp"] = documentation_mcp
    if diagnostics_mcp is not None:
        options["diagnostics_mcp"] = diagnostics_mcp
    argv = command_for(request, output, executable, **options)
    atomic_json(output / "invocation.json", {
        "argv": argv, "model": request["model"], "reasoning_effort": request["reasoning_effort"],
        "request_sha256": request_sha, "hosted_inference": provider(request["model"]) == "openai",
        "provider": provider(request["model"]),
        "source_execution_allowed": romeo_mcp is not None or bool(diagnostics_mcp and diagnostics_mcp.can_collect),
        "local_source_execution_allowed": False,
        "diagnostic_execution_allowed": bool(diagnostics_mcp and diagnostics_mcp.can_collect),
        "remote_experiments_allowed": romeo_mcp is not None,
        "model_mcp": romeo_mcp.receipt() if romeo_mcp is not None else None,
        "documentation_mcp": documentation_mcp.receipt() if documentation_mcp is not None else None,
        "diagnostics_mcp": diagnostics_mcp.receipt() if diagnostics_mcp is not None else None,
        "model_skills": request.get("model_skills"),
        "effective_instructions_sha256": sha256((output / "instructions.txt").read_bytes()),
        "deadline_policy": request.get("deadline_policy", "hard"),
        "budget_phase": request.get("budget_phase", "search"),
        "token_policy": request.get("token_policy", "limited"),
        "conversation": request.get("conversation"),
    })
    atomic_json(output / "request.json", request)
    result = run_process(argv, output, output / "codex.jsonl", timeout,
                         env=model_environment(request["model"], dsh_settings),
                         stdin=request["messages"][1]["content"])
    usage, tools = usage_from_events(Path(result.log), observe_only=observe_only,
                                    allow_romeo_mcp=romeo_mcp is not None,
                                    allow_documentation=documentation_mcp is not None,
                                    diagnostic_tools=diagnostics_mcp.tools if diagnostics_mcp is not None else (),
                                    allow_empty_agent_wait=request.get("active_control", {}).get("kind") == "mother")
    usage.update(model_requested=request["model"], reasoning_effort_requested=request["reasoning_effort"],
                 provider=provider(request["model"]))
    error = None
    infra = False
    data = None
    rejection = None
    reported, report_error = None, None
    if result.returncode or result.timed_out or usage.get("turn_failure_messages"):
        output_limit = usage.get("turn_failure_messages") == [
            "Incomplete response returned, reason: max_output_tokens"]
        if output_limit and not result.timed_out and not tools and not usage.get("tool_runtime_errors"):
            # A known incomplete proposal is a generation failure, not a lost
            # transport. Do not stop every independent tree or accept partial code.
            error = "Codex generation exceeded the model output limit; no complete proposal"
        else:
            error, infra = "Codex failed or exceeded the generation deadline; inspect its log", True
    elif usage.get("tool_runtime_errors"):
        error, infra = "The native MCP tool runtime is unavailable; inspect its log", True
    elif tools:
        error, infra = "Codex attempted a tool call outside the authorized MCP access", True
    else:
        try:
            proposal = bounded_json(output / "agent-result.json", allow_json_fence=request["model"] == DSH_MODEL)
            if request["model"] == DSH_MODEL:
                validate_structured_output(request["model"], proposal, request["schema"])
            data, reported = consume_report(proposal, request.get("model_skills"))
        except CandidateRejected as exc:
            report_error = str(exc)
            error = f"Codex returned an invalid project skills report: {exc}"
        except (OSError, ValueError, InfrastructureError) as exc:
            error = f"Codex returned no valid structured proposal: {exc}"
            if isinstance(exc, ValueError):
                rejection = {"reason": "invalid_structured_output"}
    trace = usage_trace(request, request_sha, usage,
                        sha256((output / "instructions.txt").read_bytes()),
                        reported=reported, report_error=report_error)
    if trace is not None:
        usage["model_skills"] = trace
        atomic_json(output / "skills-usage.json", trace)
    response = response_envelope(request, request_sha, data=data, usage=usage,
                                 error=error, infrastructure_error=infra)
    if rejection is not None:
        response["rejection"] = rejection
    atomic_json(output / "response.json", response)
    return response


def run_observer(request: dict, output: Path, executable="codex") -> dict:
    """Explicit post-confirmation analysis, with no tools or source execution.

    This separate entry point cannot dispatch a search or assembly request and
    does not use the historical experiment authorization gates.
    """
    from .observer_contract import validate_request

    validate_request(request)
    from .codex_mailbox import json_bytes

    return _invoke(request, sha256(json_bytes(request)), output, executable, None, True)
