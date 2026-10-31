"""Provider contracts against a local fake gateway; no model calls or HPC jobs."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from hpc_forest import codex_process, dsh_romeo, model_runtime
from hpc_forest.config import load_config, validate
from hpc_forest.core import InfrastructureError
from hpc_forest.model_policy import DSH_MODEL, EFFORT, MODEL, catalog, efforts, generator_pool


@pytest.fixture
def gateway(monkeypatch):
    state = {"requests": [], "models": [{"id": DSH_MODEL}], "status": 200}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["requests"].append((self.path, self.headers.get("Authorization")))
            self.send_response(state["status"])
            if state["status"] == 302:
                self.send_header("Location", "/leak")
            self.end_headers()
            self.wfile.write(json.dumps({"data": state["models"]}).encode())

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("DSH_ROMEO_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setenv("ROMEO_LLM_KEY", "fixture-private-key")
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_gateway_probe_only_reads_models_and_authenticates(gateway):
    dsh_romeo.check_available()
    assert gateway["requests"] == [("/v1/models", "Bearer fixture-private-key")]


@pytest.mark.parametrize("status", [302, 401, 503])
def test_gateway_failure_is_infrastructure_and_never_leaks_credentials(gateway, status):
    gateway["status"] = status
    with pytest.raises(InfrastructureError) as error:
        dsh_romeo.check_available()
    assert "fixture-private-key" not in str(error.value)
    assert len(gateway["requests"]) == 1  # No redirected Authorization header, no retries/launches.


def test_wrong_served_model_never_falls_back(gateway):
    gateway["models"] = [{"id": "different-model"}]
    with pytest.raises(InfrastructureError, match="absent"):
        dsh_romeo.check_available()


@pytest.mark.parametrize("url", ["http://127.0.0.1:11318/v1", "http://localhost/v1", "http://[::1]/v1",
                                 "http://0.0.0.0/v1", "https://user:secret@gateway/v1",
                                 "https://gateway/v1?key=secret", "file:///v1", "http://gateway:bad/v1"])
def test_remote_config_rejects_pc_tunnels_and_credential_urls(url):
    with pytest.raises(InfrastructureError):
        dsh_romeo.validate_remote({"base_url": url, "api_key_file": "/private/key"})


def test_remote_config_and_environment_never_accept_inline_keys(tmp_path, monkeypatch):
    settings = {"base_url": "http://gateway.example:11317/v1", "api_key_file": "/private/key"}
    assert dsh_romeo.validate_remote(settings) == settings
    with pytest.raises(InfrastructureError):
        dsh_romeo.validate_remote({**settings, "api_key": "secret"})
    monkeypatch.delenv("ROMEO_LLM_KEY", raising=False)
    with pytest.raises(InfrastructureError, match="ROMEO_LLM_KEY"):
        dsh_romeo.environment()
    key = tmp_path / "key"
    key.write_text("file-fixture-key\n")
    env = dsh_romeo.environment({**settings, "api_key_file": str(key)})
    assert env["ROMEO_LLM_KEY"] == "file-fixture-key"
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:11318/v1")
    native_env = model_runtime.environment(MODEL)
    assert native_env["ROMEO_LLM_KEY"] == ""
    assert native_env["OPENAI_BASE_URL"] == "" and native_env["OPENAI_API_BASE"] == ""
    assert model_runtime.overrides(MODEL)["model_provider"] == "openai"


@pytest.mark.parametrize("effort", ["medium", "xhigh", "ultra"])
def test_deepseek_only_accepts_its_real_efforts(effort):
    config = load_config()
    config["backend"] = "codex"
    config["codex"].update(model=DSH_MODEL, reasoning_effort=effort)
    with pytest.raises(InfrastructureError):
        validate(config)


def test_catalog_and_generator_pool_include_new_models():
    entries = catalog()
    assert {"gpt-6.1-terra", "gpt-6-sol", "gpt-5.6-luna", DSH_MODEL} <= {e["id"] for e in entries}
    primary = {"model": MODEL, "reasoning_effort": EFFORT}
    pool = [{"model": e["id"], "reasoning_effort": e["default_effort"]} for e in entries]
    assert len(generator_pool({**primary, "generator_pool": pool})) == len(entries)
    assert efforts(DSH_MODEL) == ("none", "low", "high", "max")
    assert "ultra" in efforts("gpt-6.1-terra") and "ultra" not in efforts("gpt-5.6-luna")


def test_planning_context_and_report_describe_the_selected_models(tmp_path, monkeypatch):
    from hpc_forest import diagnostics_contract, mother, tree_observer

    config = load_config()
    config.update(backend="codex", forest={"policy": "mother", "conversation": "persistent",
                                         "active": {"mode": "full"}})
    primary = {"model": DSH_MODEL, "reasoning_effort": "high"}
    config["codex"].update(**primary, session_id="a" * 32, generator_pool=[
        primary, {"model": "gpt-6.1-terra", "reasoning_effort": "ultra"}])
    data = {"config": config, "deadline": time.time() + 600}
    db = SimpleNamespace(get=data.get, set=data.__setitem__, reserve=lambda *a, **kw: "slot",
                         one=lambda *a: None, rows=lambda *a: [])
    controller = SimpleNamespace(config=config, db=db, root=tmp_path, statement="Synthetic contract")
    mission = SimpleNamespace(epoch=1, id="fixture", worktree=str(tmp_path))
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.cpp").write_text("int main(){return 0;}")
    monkeypatch.setattr(mother, "research_roles", lambda *a: [])
    captured = []

    class Captured(Exception):
        pass

    def capture(root, request, **kwargs):
        captured.append(request)
        raise Captured

    monkeypatch.setattr(diagnostics_contract, "authorize", capture)
    with pytest.raises(Captured):
        mother.plan_for(controller, mission, {"deadline_policy": "finish-started"}, "preparation")
    payload = json.loads(captured[0]["messages"][1]["content"])["active_architecture_as_data"]
    assert payload["control_identity"] == primary
    assert payload["research_generators"] == generator_pool(config["codex"])
    tree_observer._summary(tmp_path, primary, [])
    report = (tmp_path / "REPORT.md").read_text(encoding="utf8")
    assert DSH_MODEL in report and "effort high" in report
    assert "GPT-6 Luna" not in report


@pytest.mark.parametrize("effort", efforts(DSH_MODEL))
@pytest.mark.parametrize("resume", [False, True])
@pytest.mark.parametrize("with_tools", [False, True])
def test_native_codex_routes_deepseek_and_keeps_effort_on_resume(tmp_path, monkeypatch, effort, resume, with_tools):
    monkeypatch.setattr(codex_process.shutil, "which", lambda _: "codex")
    request = {"nonce": "b" * 32, "model": DSH_MODEL, "reasoning_effort": effort, "schema": {"type": "object"},
               "messages": [{"role": "system", "content": "Frozen contract"}, {"role": "user", "content": "Task"}]}
    if resume:
        request["conversation"] = {"id": "a" * 32, "turn": 1, "phase": "steering",
                                   "thread_id": "12345678-1234-1234-1234-123456789abc",
                                   "previous_request_sha256": "b" * 64}
    documentation = SimpleNamespace(overrides=lambda nonce: {"mcp_servers.hpc_docs.enabled": True}) if with_tools else None
    argv = codex_process.command_for(request, tmp_path, documentation_mcp=documentation)
    assert 'model_provider="romeo"' in argv
    assert 'model_providers.romeo.wire_api="responses"' in argv
    assert 'model_providers.romeo.env_key="ROMEO_LLM_KEY"' in argv
    assert f'model_reasoning_effort="{effort}"' in argv
    assert not any("forced_login_method" in arg for arg in argv)
    assert "features.shell_tool=false" in argv and "--strict-config" in argv
    assert ("--output-schema" in argv) is (not with_tools)
    instructions = (tmp_path / "instructions.txt").read_text(encoding="utf8")
    assert instructions.startswith("Frozen contract")
    assert json.loads(instructions.splitlines()[-1]) == request["schema"]
    if resume:
        assert argv.index("resume") < argv.index('model_provider="romeo"')


def test_pure_deepseek_needs_no_chatgpt_login_or_codex_catalog(gateway, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("A DeepSeek-only mission must not check ChatGPT login")
    monkeypatch.setattr(model_runtime.subprocess, "run", unexpected)
    auth = model_runtime.authenticate("codex", {"model": DSH_MODEL, "reasoning_effort": "max"}, check_catalog=True)
    assert auth["authentication"] == "dsh-romeo API key" and auth["model_weights_on_romeo"]


@pytest.mark.parametrize("analysis,valid", [("short", True), ("too long for the original schema", False)])
@pytest.mark.parametrize("repair", [False, True])
@pytest.mark.parametrize("fenced", [False, True])
def test_deepseek_plan_critique_uses_native_grammar_and_still_validates_lengths(
    tmp_path, monkeypatch, analysis, valid, repair, fenced
):
    monkeypatch.setenv("ROMEO_LLM_KEY", "fixture-private-key")
    monkeypatch.setattr(codex_process.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(codex_process, "check_dependencies", lambda *args: {
        "completion": {"policy": "finish-started", "token_policy": "observe-only"}})
    request = {"nonce": "a" * 32, "session_id": "b" * 32, "model": DSH_MODEL,
               "reasoning_effort": "max", "meta_role": "mother-plan-review",
               "expires_at": None, "deadline_policy": "finish-started", "token_policy": "observe-only",
               "schema": {"type": "object", "required": ["analysis"], "properties": {
                   "analysis": {"type": "string", "maxLength": 8}}},
               "messages": [{"role": "system", "content": "Review the existing plan"},
                            {"role": "user", "content": "Frozen plan"}]}
    output = tmp_path / "reply"
    output.mkdir()
    if repair:
        from hpc_forest.codex_conversation import first_turn, next_turn, run_turn

        first = {**request, "conversation": first_turn()}
        initial = tmp_path / "initial"
        initial.mkdir()

        def initial_turn():
            usage = {"input_tokens": 2, "output_tokens": 1}
            (initial / "codex.jsonl").write_text("\n".join(json.dumps(v) for v in [
                {"type": "thread.started", "thread_id": "00000000-0000-0000-0000-000000000010"},
                {"type": "turn.completed", "usage": usage}]))
            return {"data": {}, "error": None,
                    "usage": {"tokens": 3, "token_accounting": "exact", "events": [usage]}}

        prior = run_turn(first, "d" * 64, initial, initial_turn)
        request.update(meta_role="mother-plan-repair", conversation=next_turn(prior["conversation"], phase="plan-review"))

    def process(argv, cwd, log, timeout, **kwargs):
        assert "--output-schema" in argv
        assert not any("mcp_servers.hpc_docs" in arg for arg in argv)
        events = [{"type": "turn.completed", "usage": {"input_tokens": 4, "output_tokens": 2}}]
        if repair:
            events.insert(0, {"type": "thread.started", "thread_id": request["conversation"]["thread_id"]})
        log.write_text("\n".join(json.dumps(v) for v in events))
        raw = json.dumps({"analysis": analysis})
        (cwd / "agent-result.json").write_text("```json\n" + raw + "\n```" if fenced else raw, encoding="utf-8")
        return SimpleNamespace(returncode=0, timed_out=False, log=str(log))

    monkeypatch.setattr(codex_process, "run_process", process)
    documentation = SimpleNamespace(overrides=lambda nonce: {"mcp_servers.hpc_docs.enabled": True})
    response = codex_process.run_codex(request, "c" * 64, output, tmp_path / "receipt.json", set(),
                                       documentation_mcp=documentation)
    assert (response["error"] is None) is valid
    assert response["data"] == ({"analysis": analysis} if valid else None)
    assert response["usage"]["tokens"] == (3 if repair else 6)
    assert not response["infrastructure_error"]
    if repair:
        assert ("conversation" in response) is valid  # No second correction loop.


def test_mixed_pool_checks_both_providers_without_looking_up_deepseek_in_codex(gateway, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(model_runtime.subprocess, "run", lambda argv, **kw:
                        calls.append((argv, kw["env"])) or
                        SimpleNamespace(returncode=0, stdout="Logged in using ChatGPT", stderr=""))
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-dsh-alias")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://fixture-dsh-alias/v1")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    (tmp_path / "models_cache.json").write_text(json.dumps({"models": [
        {"slug": MODEL, "supported_reasoning_levels": [{"effort": "max"}]}]}))
    primary = {"model": MODEL, "reasoning_effort": "max"}
    auth = model_runtime.authenticate("codex", {**primary, "generator_pool": [primary,
        {"model": DSH_MODEL, "reasoning_effort": "low"}]}, check_catalog=True)
    assert len(calls) == 1 and calls[0][0] == ["codex", "login", "status"]
    assert all(calls[0][1][name] == "" for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "ROMEO_LLM_KEY"))
    assert len(gateway["requests"]) == 1 and auth["authentication"] == "ChatGPT + dsh-romeo"


@pytest.mark.parametrize("returncode", [0, 1])
def test_invocation_passes_key_only_in_environment_and_classifies_failures(tmp_path, monkeypatch, returncode):
    monkeypatch.setenv("ROMEO_LLM_KEY", "private-invocation-key")
    monkeypatch.setattr(codex_process.shutil, "which", lambda _: "codex")
    request = {"nonce": "a" * 32, "session_id": "b" * 32, "model": DSH_MODEL, "reasoning_effort": "high",
               "schema": {"type": "object"}, "messages": [
                   {"role": "system", "content": "Frozen contract"}, {"role": "user", "content": "Task"}]}

    def process(argv, cwd, log, timeout, **kwargs):
        assert kwargs["env"]["ROMEO_LLM_KEY"] == "private-invocation-key"
        assert "private-invocation-key" not in str(argv)
        log.write_text(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 4, "output_tokens": 2}}))
        (cwd / "agent-result.json").write_text('{"fixture":true}')
        return SimpleNamespace(returncode=returncode, timed_out=False, log=str(log))

    monkeypatch.setattr(codex_process, "run_process", process)
    response = codex_process._invoke(request, "c" * 64, tmp_path, "codex", 10, False)
    assert response["infrastructure_error"] is bool(returncode)
    invocation = json.loads((tmp_path / "invocation.json").read_text())
    assert invocation["provider"] == "dsh-romeo" and invocation["hosted_inference"] is False
    assert all("private-invocation-key" not in p.read_text() for p in tmp_path.iterdir() if p.is_file())


@pytest.mark.parametrize("proposal,valid", [
    ({"action": "read", "values": [1, 2]}, True),
    ({"action": "invent", "values": [1]}, False),
    ({"action": "read", "values": [True]}, False),
    ({"action": "read", "values": [1, 1]}, False),
    ({"action": "read", "values": [1, 2, 3]}, False),
    ({"action": "read", "values": []}, False),
    ({"action": "read", "values": [1], "unexpected": "data"}, False),
    ({"action": "read"}, False),
])
@pytest.mark.parametrize("fenced", [False, True])
def test_deepseek_validates_the_full_original_schema_before_accepting_output(
    tmp_path, monkeypatch, proposal, valid, fenced
):
    monkeypatch.setenv("ROMEO_LLM_KEY", "fixture-private-key")
    monkeypatch.setattr(codex_process.shutil, "which", lambda _: "codex")
    schema = {"type": "object", "additionalProperties": False,
              "required": ["action", "values"], "properties": {
                  "action": {"type": "string", "enum": ["read"]},
                  "values": {"type": "array", "minItems": 1, "maxItems": 2,
                             "uniqueItems": True, "items": {"type": "integer"}}}}
    request = {"nonce": "a" * 32, "session_id": "b" * 32, "model": DSH_MODEL,
               "reasoning_effort": "max", "schema": schema, "messages": [
                   {"role": "system", "content": "Frozen contract"},
                   {"role": "user", "content": "Task"}]}

    def process(argv, cwd, log, timeout, **kwargs):
        assert "--output-schema" in argv
        log.write_text(json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 4, "output_tokens": 2}}))
        raw = json.dumps(proposal)
        (cwd / "agent-result.json").write_text("```json\n" + raw + "\n```" if fenced else raw, encoding="utf-8")
        return SimpleNamespace(returncode=0, timed_out=False, log=str(log))

    monkeypatch.setattr(codex_process, "run_process", process)
    response = codex_process._invoke(request, "c" * 64, tmp_path, "codex", 10, False)
    assert (response["error"] is None) is valid
    assert response["data"] == (proposal if valid else None)
    assert response["infrastructure_error"] is False
    assert response["usage"]["tokens"] == 6
    if not valid:
        assert response["rejection"] == {"reason": "invalid_structured_output"}


@pytest.mark.parametrize("model,raw,valid", [
    (DSH_MODEL, '```json\n{"answer":"ok"}\n```', True),
    (DSH_MODEL, ' \r\n```json\r\n{"answer":"ok"}\r\n```\r\n', True),
    (DSH_MODEL, '```json\n{"answer":"ok\\n```"}\n```', True),
    (MODEL, '```json\n{"answer":"ok"}\n```', False),
    (DSH_MODEL, 'Here is the result:\n```json\n{"answer":"ok"}\n```', False),
    (DSH_MODEL, '```json\n{"answer":"ok"}\n```\nMore text', False),
    (DSH_MODEL, '```json\n{"answer":"ok"}\n```\n```json\n{}\n```', False),
    (DSH_MODEL, '```python\n{"answer":"ok"}\n```', False),
    (DSH_MODEL, '```json\n{"answer":"ok"}', False),
    (DSH_MODEL, '```json\n{"answer":}\n```', False),
    (DSH_MODEL, '```json\n[]\n```', False),
])
def test_native_final_json_fence_is_bounded_to_deepseek_and_preserves_evidence(
    tmp_path, monkeypatch, model, raw, valid
):
    monkeypatch.setenv("ROMEO_LLM_KEY", "fixture-private-key")
    monkeypatch.setattr(codex_process.shutil, "which", lambda _: "codex")
    schema = {"type": "object", "additionalProperties": False, "required": ["answer"],
              "properties": {"answer": {"type": "string"}}}
    request = {"nonce": "a" * 32, "session_id": "b" * 32, "model": model,
               "reasoning_effort": "max", "schema": schema, "messages": [
                   {"role": "system", "content": "Frozen contract"}, {"role": "user", "content": "Task"}]}

    def process(argv, cwd, log, timeout, **kwargs):
        assert ("--output-schema" in argv) is (model != DSH_MODEL)
        log.write_text(json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 4, "output_tokens": 2}}), encoding="utf-8")
        (cwd / "agent-result.json").write_bytes(raw.encode("utf-8"))
        return SimpleNamespace(returncode=0, timed_out=False, log=str(log))

    monkeypatch.setattr(codex_process, "run_process", process)
    docs = SimpleNamespace(overrides=lambda nonce: {"mcp_servers.hpc_docs.enabled": True}, receipt=lambda: {})
    response = codex_process._invoke(request, "c" * 64, tmp_path, "codex", 10, False,
                                     documentation_mcp=docs)
    assert (response["error"] is None) is valid
    assert not response["infrastructure_error"]
    assert response["usage"]["tokens"] == 6
    if valid:
        assert response["data"] == json.loads(raw.strip().split("\n", 1)[1].rsplit("\n", 1)[0])
    else:
        assert response["data"] is None
    assert (tmp_path / "agent-result.json").read_bytes() == raw.encode("utf-8")


def test_json_fences_do_not_relax_mailbox_or_size_guards(tmp_path):
    from hpc_forest.codex_mailbox import bounded_json

    path = tmp_path / "output.json"
    path.write_text('```json\n{"ok":true}\n```', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        bounded_json(path)
    with pytest.raises(InfrastructureError, match="size limit"):
        bounded_json(path, 16, allow_json_fence=True)
    with pytest.raises(InfrastructureError, match="regular file"):
        bounded_json(tmp_path, allow_json_fence=True)
