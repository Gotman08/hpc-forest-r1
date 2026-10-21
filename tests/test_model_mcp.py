"""Offline checks for the real local MCP launcher and native tool accounting."""
import json
import subprocess
import sys
import traceback
from types import SimpleNamespace

import pytest
from test_mother_conversation import complete_turn, request_for

from hpc_forest import codex_process
from hpc_forest.codex_conversation import first_turn, next_turn
from hpc_forest.model_mcp import DISABLED_MODEL_TOOLS, RomeoMCP, load_server


@pytest.fixture
def binding(tmp_path):
    server = tmp_path / "fake_mcp.py"
    server.write_text(
        "import json, os, sys\n"
        "line = sys.stdin.readline().strip()\n"
        "print(json.dumps({'line': line, 'cwd': os.getcwd(), "
        "'profile': os.environ.get('ROMEO_TOOL_PROFILE'), "
        "'secret': os.environ.get('FAKE_MCP_SECRET'), "
        "'ProgramData': os.environ.get('ProgramData')}))\n", encoding="utf8")
    config = tmp_path / "codex.toml"
    config.write_text(
        "[mcp_servers.romeo]\ncommand = " + json.dumps(sys.executable) +
        "\nargs = " + json.dumps([str(server)]) + "\ncwd = " + json.dumps(str(tmp_path)) +
        '\n[mcp_servers.romeo.env]\nROMEO_TOOL_PROFILE = "full"\nFAKE_MCP_SECRET = "secret-sentinel"\n'
        '[mcp_servers.unrelated]\ncommand = "must-not-inherit"\n', encoding="utf8")
    return RomeoMCP.bind(config)


def test_launcher_keeps_stdio_profile_environment_and_cwd_without_exposing_secrets(binding, monkeypatch):
    monkeypatch.setenv("ProgramData", "windows-scp-profile-fixture")
    values = binding.overrides()
    assert "secret-sentinel" not in json.dumps(values)
    assert "must-not-inherit" not in json.dumps(values)
    assert "PROGRAMDATA" in {key.upper() for key in values["mcp_servers.romeo.env_vars"]}
    process = subprocess.run([values["mcp_servers.romeo.command"], *values["mcp_servers.romeo.args"]],
                             input="stdio request\n", capture_output=True, text=True, timeout=15)
    assert process.returncode == 0, process.stderr
    response = json.loads(process.stdout)
    assert response == {"line": "stdio request", "cwd": str(binding.config.parent),
                        "profile": "full", "secret": "secret-sentinel",
                        "ProgramData": "windows-scp-profile-fixture"}
    binding.config.write_text('[mcp_servers.romeo]\ncommand = "changed"')
    with pytest.raises(ValueError, match="changed"):
        binding.overrides()
    failed = subprocess.run([values["mcp_servers.romeo.command"], *values["mcp_servers.romeo.args"]],
                            input="", capture_output=True, text=True, timeout=15)
    assert failed.returncode != 0 and "could not start" in failed.stderr


@pytest.mark.parametrize("content", [
    "[mcp_servers.other]\ncommand='other'", "not valid TOML or secret-sentinel",
    "[mcp_servers.romeo]\ncommand='server'\nenabled=false",
    "[mcp_servers.romeo]\ncommand='server'\nurl='https://other.invalid'",
    "[mcp_servers.romeo]\ncommand='server'\nargs=[1]",
    "[mcp_servers.romeo]\ncommand='server'\ntool_timeout_sec=-1",
])
def test_invalid_configuration_fails_without_secret_values_in_error(tmp_path, content):
    config = tmp_path / "bad.toml"
    config.write_text(content)
    with pytest.raises(ValueError) as failure:
        load_server(config)
    assert "secret-sentinel" not in str(failure.value)
    assert "secret-sentinel" not in "".join(traceback.format_exception(failure.value))


def test_mother_resume_retains_mcp_and_original_uuid_with_only_romeo_enabled(tmp_path, monkeypatch, binding):
    monkeypatch.setattr(codex_process, "shutil", SimpleNamespace(which=lambda _: "codex.exe"))
    start = request_for(first_turn())
    start.update(messages=[{"role": "system", "content": "Do not execute commands."},
                           {"role": "user", "content": "Subject"}], schema={"type": "object"},
                 token_policy="observe-only")
    response = complete_turn(start, "1" * 64, tmp_path / "first")
    resume = {**start, "conversation": next_turn(response["conversation"])}
    for request, name in ((start, "first"), (resume, "final")):
        output = tmp_path / name
        argv = codex_process.command_for(request, output, romeo_mcp=binding)
        assert "mcp_servers.romeo.required=true" in argv
        assert "mcp_servers.romeo.enabled=true" in argv
        assert 'mcp_servers.romeo.default_tools_approval_mode="approve"' in argv
        assert "--ignore-user-config" in argv and "--strict-config" in argv
        assert "features.shell_tool=false" in argv and "features.multi_agent=false" in argv
        assert "features.code_mode_host=true" in argv
        assert "secret-sentinel" not in json.dumps(argv)
        assert "must-not-inherit" not in json.dumps(argv)
        assert not any("model_context_window" in part for part in argv)
        instructions = (output / "instructions.txt").read_text(encoding="utf8")
        assert "Do not execute local commands" in instructions and "permanently" in instructions
        assert start["messages"][0]["content"] == "Do not execute commands."
        if name == "final":
            assert argv[argv.index("resume") + 1] == response["conversation"]["thread_id"]
            assert argv.index("mcp_servers.romeo.enabled=true") > argv.index("resume")
            assert argv.index("features.code_mode_host=true") > argv.index("resume")


@pytest.mark.parametrize("kind,server,tool,enabled,forbidden", [
    ("mcp_tool_call", "romeo", "read_doc", True, False),
    ("mcp_tool_call", "romeo", "job_prepare", True, False),
    ("mcp_tool_call", "romeo", "job_prepare", False, True),
    ("mcp_tool_call", "other", "read_doc", True, True),
    ("mcp_tool_call", "romeo", "romeollm_launch", True, True),
    ("mcp_tool_call", "romeo", None, True, True),
    ("command_execution", "romeo", "read_doc", True, True),
])
def test_mcp_accounting_accepts_only_authorized_tools_and_deduplicates_events(
    tmp_path, kind, server, tool, enabled, forbidden,
):
    log = tmp_path / "codex.jsonl"
    item = {"id": "call-1", "type": kind, "server": server, "tool": tool}
    log.write_text("\n".join(json.dumps(event) for event in [
        {"type": "item.started", "item": {**item, "status": "in_progress"}},
        {"type": "item.completed", "item": {**item, "status": "completed"}},
        {"type": "turn.completed", "usage": {"input_tokens": 120, "cached_input_tokens": 100,
                                               "output_tokens": 30}},
    ]))
    usage, bad_tools = codex_process.usage_from_events(log, observe_only=True, allow_romeo_mcp=enabled)
    assert bad_tools is forbidden
    assert usage["tokens"] == 150 and usage["token_accounting"] == "exact"
    if kind == "mcp_tool_call":
        assert len(usage["mcp_tool_calls"]) == 1
        assert usage["mcp_tool_calls"][0]["status"] == "completed"


def test_user_tool_selection_preserved_but_model_dispatch_stays_disabled(binding):
    text = binding.config.read_text(encoding="utf8").replace(
        "[mcp_servers.romeo.env]", 'enabled_tools=["read_doc", "romeollm_launch"]\n'
        'disabled_tools=["upload_to_romeo"]\ntool_timeout_sec=300\n[mcp_servers.romeo.env]')
    binding.config.write_text(text, encoding="utf8")
    values = RomeoMCP.bind(binding.config).overrides()
    assert set(DISABLED_MODEL_TOOLS) <= set(values["mcp_servers.romeo.disabled_tools"])
    assert "upload_to_romeo" in values["mcp_servers.romeo.disabled_tools"]
    assert values["mcp_servers.romeo.enabled_tools"] == ["read_doc", "romeollm_launch"]
    assert values["mcp_servers.romeo.tool_timeout_sec"] == 300


@pytest.mark.parametrize("message,enabled,expected", [
    ("Code Mode is unavailable because code-mode host is disabled.", True, True),
    ("Code Mode is unavailable because code-mode host is disabled.", False, False),
    ("Under-development features enabled: skip_host_skill_discovery.", True, False),
    ("Exceeded skills context budget. All skill descriptions were removed.", True, False),
])
def test_unavailable_mcp_router_is_distinct_from_nonfatal_native_warnings(tmp_path, message, enabled, expected):
    log = tmp_path / "codex.jsonl"
    log.write_text(json.dumps({"type": "item.completed", "item": {
        "id": "router-error", "type": "error", "message": message}}), encoding="utf-8")
    usage, forbidden = codex_process.usage_from_events(log, observe_only=True, allow_romeo_mcp=enabled)
    assert bool(usage["tool_runtime_errors"]) is expected
    assert forbidden is False


def test_valid_json_and_zero_exit_cannot_hide_an_unavailable_mcp_router(tmp_path, monkeypatch, binding):
    monkeypatch.setattr(codex_process, "shutil", SimpleNamespace(which=lambda _: "codex.exe"))
    request = request_for(first_turn())
    request.update(nonce="b" * 32, messages=[{"role": "system", "content": "Use the configured MCP."},
                             {"role": "user", "content": "Propose a program."}],
                   schema={"type": "object"}, token_policy="observe-only")

    def native(argv, output, log, timeout, **kwargs):
        (output / "agent-result.json").write_text('{"files": []}', encoding="utf-8")
        log.write_text("\n".join(json.dumps(event) for event in [
            {"type": "item.completed", "item": {"id": "router-error", "type": "error",
                "message": "Code Mode is unavailable because code-mode host is disabled."}},
            {"type": "turn.completed", "usage": {"input_tokens": 120, "output_tokens": 30}},
        ]), encoding="utf-8")
        return SimpleNamespace(returncode=0, timed_out=False, log=str(log))

    monkeypatch.setattr(codex_process, "run_process", native)
    response = codex_process._invoke(request, "1" * 64, tmp_path / "native", "codex.exe", None, True,
                                     romeo_mcp=binding)
    assert response["infrastructure_error"] is True
    assert "MCP tool runtime is unavailable" in response["error"]
    assert response["data"] is None
    assert response["usage"]["tokens"] == 150
    assert response["usage"]["token_accounting"] == "exact"
