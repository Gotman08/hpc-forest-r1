import asyncio
import copy
import json
import shutil
import threading
import time

import pytest

from hpc_forest import ollama_backend
from hpc_forest.codex_mailbox import (
    EFFORT,
    MODEL,
    TOKEN_CEILING,
    CodexMailboxBackend,
    bounded_json,
    initialize_channel,
    make_request,
    publish_request,
    publish_response,
    response_envelope,
    sha256,
    wait_response,
)
from hpc_forest.codex_process import check_dependencies, command_for, usage_from_events
from hpc_forest.codex_worker import Worker
from hpc_forest.core import InfrastructureError, Mission, atomic_json
from hpc_forest.source_request import proposal_messages


@pytest.fixture
def setup(tmp_path, config):
    worktree = tmp_path / "tree"
    (worktree / "src").mkdir(parents=True)
    (worktree / "src/main.c").write_text("int original;\n", encoding="utf8")
    mission = Mission("trial", "e1:A", "local-1", 1, "A", "base", None, "R/A", 1, 1, str(worktree))
    channel = tmp_path / "mailbox"
    initialize_channel(channel, "a" * 32, "test")
    config["codex"] = {"model": MODEL, "reasoning_effort": EFFORT,
                       "mailbox_dir": str(channel), "session_id": "a" * 32}
    config["budget"].update(mission_tokens=TOKEN_CEILING, generation_seconds=2)
    context = {"deadline": time.time() + 3}
    return mission, context, config, channel


def data():
    return {"hypothesis": "protocol fixture", "transformations": [], "sources_kept": [],
            "files": [{"path": "src/main.c", "content": "int received;\n"}], "notes": "fixture"}


def result(request, request_sha, candidate=None):
    return response_envelope(request, request_sha, data=data() if candidate is None else candidate,
                             error=None, infrastructure_error=False,
                             usage={"tokens": 150, "token_accounting": "exact", "llm_calls": 1})


@pytest.mark.parametrize("mixed", [False, True])
def test_same_messages_and_schema_as_the_existing_neutral_adapter(setup, tmp_path, monkeypatch, mixed):
    mission, context, config, _ = setup
    if mixed:
        context["node_research"] = {"enabled": True}
    captured = {}
    expected = proposal_messages(tmp_path / "tree", mission, context)
    config["ollama"]["model_digest"] = "b" * 64
    config["ollama"]["server_version"] = "0.40.4"
    monkeypatch.setattr(ollama_backend, "resolve_model", lambda settings: settings)

    def capture(url, endpoint, payload, timeout):
        captured.update(payload)
        return {"model": config["ollama"]["model"], "done": True, "done_reason": "length",
                "prompt_eval_count": 1, "eval_count": 1}

    monkeypatch.setattr(ollama_backend, "request_json", capture)
    ollama_backend.OllamaBackend().generate(mission, context, config, tmp_path)
    assert captured["messages"] == expected["messages"]
    assert captured["format"] == expected["schema"]


def test_every_native_invocation_pins_model_max_and_disables_external_tools(setup, tmp_path, monkeypatch):
    mission, context, config, _ = setup
    request = make_request(mission, context, config)
    monkeypatch.setattr("hpc_forest.codex_process.shutil.which", lambda _: "codex.exe")
    command = command_for(request, tmp_path / "generation")
    assert command[command.index("--model") + 1] == MODEL
    assert 'model_reasoning_effort="max"' in command
    assert 'forced_login_method="chatgpt"' in command
    assert "--ignore-user-config" in command and "--strict-config" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    for value in ["features.shell_tool=false", "features.apps=false", "features.memories=false",
                  "features.plugins=false", "features.multi_agent=false", "project_doc_max_bytes=0"]:
        assert value in command
    assert (tmp_path / "generation/instructions.txt").read_text(encoding="utf8") == request["messages"][0]["content"]


@pytest.mark.parametrize("field,value", [("model", "another-model"), ("reasoning_effort", "xhigh")])
def test_never_substitute_model_or_effort(setup, tmp_path, field, value):
    mission, context, config, _ = setup
    request = make_request(mission, context, config)
    request[field] = value
    with pytest.raises(InfrastructureError):
        command_for(request, tmp_path / "generation")


def test_no_model_without_received_deepseek_archive_receipts(tmp_path):
    gate = tmp_path / "gate.json"
    atomic_json(gate, {"status": "waiting", "next_model": MODEL, "reasoning_effort": EFFORT})
    with pytest.raises(InfrastructureError):
        check_dependencies(gate, {"1", "2"})
    archives = []
    for job in ["1", "2"]:
        p = tmp_path / f"{job}.tar.gz"
        p.write_bytes(b"transport fixture")
        archives.append({"job_id": job, "path": str(p), "sha256": sha256(p.read_bytes())})
    atomic_json(gate, {"status": "deepseek_results_received_and_audited", "next_model": MODEL,
                      "reasoning_effort": EFFORT, "finished_job_ids": ["1", "2"], "archives": archives})
    check_dependencies(gate, {"1", "2"})
    (tmp_path / "1.tar.gz").write_bytes(b"changed")
    with pytest.raises(InfrastructureError):
        check_dependencies(gate, {"1", "2"})


def test_mailbox_applies_only_verified_full_response_and_keeps_usage(setup, tmp_path):
    mission, context, config, channel = setup

    def peer():
        while not list((channel / "requests").glob("*.json")):
            time.sleep(0.01)
        path = next((channel / "requests").glob("*.json"))
        request = bounded_json(path)
        publish_response(channel, result(request, sha256(path.read_bytes())))

    thread = threading.Thread(target=peer)
    thread.start()
    generated = CodexMailboxBackend().generate(mission, context, config, tmp_path)
    thread.join(timeout=3)
    assert generated.error is None and generated.tokens == 150
    assert generated.usage["reasoning_effort"] == "max"
    assert (tmp_path / "tree/src/main.c").read_text() == "int received;\n"


def test_mailbox_returns_model_documentation_action_without_touching_source(setup, tmp_path):
    mission, context, config, channel = setup
    context["node_research"] = {"enabled": True}

    def peer():
        while not list((channel / "requests").glob("*.json")):
            time.sleep(0.01)
        path = next((channel / "requests").glob("*.json"))
        request = bounded_json(path)
        assert "research" in request["schema"]["required"]
        candidate = data()
        candidate.update(files=[], research={"queries": ["model-selected-query"], "urls": []})
        publish_response(channel, result(request, sha256(path.read_bytes()), candidate))

    thread = threading.Thread(target=peer)
    thread.start()
    generated = CodexMailboxBackend().generate(mission, context, config, tmp_path)
    thread.join(timeout=3)
    assert generated.error is None and generated.tokens == 150
    assert generated.usage["research_request"]["queries"] == ["model-selected-query"]
    assert (tmp_path / "tree/src/main.c").read_text() == "int original;\n"


@pytest.mark.parametrize("failure", ["session", "request_hash", "partial_transfer"])
def test_mismatched_or_partial_response_is_never_applied(setup, tmp_path, failure):
    mission, context, config, channel = setup
    request = make_request(mission, context, config)
    request_sha = publish_request(channel, request)
    response = result(request, request_sha)
    if failure == "session":
        response["session_id"] = "b" * 32
    if failure == "request_hash":
        response["request_sha256"] = "b" * 64
    publish_response(channel, response)
    if failure == "partial_transfer":
        (channel / "responses" / f"{request['nonce']}.response.json").write_text("{}")
    with pytest.raises(InfrastructureError):
        wait_response(channel, request, request_sha)
    assert (tmp_path / "tree/src/main.c").read_text() == "int original;\n"


def test_incomplete_upload_without_ready_marker_times_out(setup):
    mission, context, config, channel = setup
    request = make_request(mission, context, config)
    request["expires_at"] = time.time() + 0.03
    request_sha = publish_request(channel, request)
    path = channel / "responses" / f"{request['nonce']}.response.json"
    path.write_text("{partial")
    with pytest.raises(InfrastructureError, match="deadline"):
        wait_response(channel, request, request_sha, poll_seconds=0.01)


def test_usage_includes_cached_input_and_rejects_tool_events(tmp_path):
    path = tmp_path / "codex.jsonl"
    events = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}},
        {"type": "turn.completed", "usage": {"input_tokens": 120, "cached_input_tokens": 100, "output_tokens": 30}},
    ]
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf8")
    usage, tools = usage_from_events(path)
    assert usage["tokens"] == 150 and usage["token_accounting"] == "exact" and not tools
    path.write_text(json.dumps({"type": "item.started", "item": {"type": "command_execution"}}))
    usage, tools = usage_from_events(path)
    assert usage["tokens"] == TOKEN_CEILING and tools


class LocalTransfer:
    def __init__(self, channel):
        self.channel = channel

    def local(self, remote):
        suffix = remote.split("/mailbox", 1)[1].lstrip("/")
        return self.channel / suffix

    async def download(self, remote, local):
        shutil.copyfile(self.local(remote), local)
        return {"ok": True, "verifie": True, "remote_sha256": sha256(local.read_bytes())}

    async def upload(self, local, remote):
        target = self.local(remote)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local, target)
        return {"ok": True, "verifie": True}


def test_transport_smoke_uses_zero_model_calls_and_validated_hashes(setup, tmp_path):
    mission, context, config, channel = setup
    request = make_request(mission, context, config)
    request["kind"] = "transport-smoke"
    request_sha = publish_request(channel, request)
    worker = Worker(LocalTransfer(channel), "/scratch/hpc-forest-gpt61sol-max-test/results-1/mailbox",
                    "a" * 32, tmp_path / "worker", None, set(), transport_smoke=True)

    async def execute():
        await worker.hello()
        assert await worker.handle(f"{request['nonce']}.request.json")

    asyncio.run(execute())
    response = wait_response(channel, request, request_sha)
    assert response["data"]["ack"] == request["nonce"]
    assert response["usage"]["llm_calls"] == 0


def test_worker_prioritizes_response_and_defers_diagnostics(setup, tmp_path):
    mission, context, config, channel = setup
    request = make_request(mission, context, config)
    request["kind"] = "transport-smoke"
    request_sha = publish_request(channel, request)
    output = tmp_path / "worker"
    local = output / request["nonce"]
    local.mkdir(parents=True)
    (local / "codex.jsonl").write_text("diagnostic only")
    (local / "invocation.json").write_text("{}")
    uploads = []

    class OrderedTransfer(LocalTransfer):
        async def upload(self, source, destination):
            uploads.append(destination)
            return await super().upload(source, destination)

    worker = Worker(OrderedTransfer(channel),
        "/scratch/hpc-forest-gpt61sol-max-test/results-1/mailbox", "a" * 32,
        output, None, set(), transport_smoke=True, defer_diagnostics=True)

    async def execute():
        assert await worker.handle(f"{request['nonce']}.request.json")
        assert len(uploads) == 2
        assert uploads[0].endswith(".response.json")
        assert uploads[1].endswith(".ready.json")
        assert wait_response(channel, request, request_sha)["usage"]["llm_calls"] == 0
        await worker.flush_diagnostics()
        assert len(uploads) == 4
        assert all("/logs/" in value for value in uploads[2:])
        await worker.flush_diagnostics()
        assert len(uploads) == 4
        assert not await worker.handle(f"{request['nonce']}.request.json")

    asyncio.run(execute())


def test_worker_crash_does_not_replay_a_potentially_charged_generation(setup, tmp_path, monkeypatch):
    mission, context, config, channel = setup
    request = make_request(mission, context, config)
    request_sha = publish_request(channel, request)
    output = tmp_path / "worker"
    (output / request["nonce"]).mkdir(parents=True)
    atomic_json(output / request["nonce"] / "generation-claimed.json", {"request_sha256": request_sha})
    worker = Worker(LocalTransfer(channel), "/scratch/hpc-forest-gpt61sol-max-test/results-1/mailbox",
                    "a" * 32, output, None, set())
    monkeypatch.setattr("hpc_forest.codex_worker.run_codex", lambda *_: pytest.fail("Request replayed"))
    asyncio.run(worker.handle(f"{request['nonce']}.request.json"))
    response = wait_response(channel, request, request_sha)
    assert response["infrastructure_error"] and "not replayed" in response["error"]
    assert response["usage"]["tokens"] == TOKEN_CEILING


def test_source_validation_is_atomic_when_one_file_escapes(setup, tmp_path):
    mission, context, config, channel = setup
    candidate = copy.deepcopy(data())
    candidate["files"].append({"path": "../trusted/test.py", "content": "forbidden"})

    def peer():
        while not list((channel / "requests").glob("*.json")):
            time.sleep(0.01)
        path = next((channel / "requests").glob("*.json"))
        request = bounded_json(path)
        publish_response(channel, result(request, sha256(path.read_bytes()), candidate))

    thread = threading.Thread(target=peer)
    thread.start()
    generated = CodexMailboxBackend().generate(mission, context, config, tmp_path)
    thread.join(timeout=3)
    assert generated.error and (tmp_path / "tree/src/main.c").read_text() == "int original;\n"


def test_smoke_worker_cannot_answer_an_actual_source_request(setup, tmp_path):
    mission, context, config, channel = setup
    request = make_request(mission, context, config)
    publish_request(channel, request)
    worker = Worker(LocalTransfer(channel), "/scratch/hpc-forest-gpt61sol-max-test/results-1/mailbox",
                    "a" * 32, tmp_path / "worker", None, set(), transport_smoke=True)
    with pytest.raises(InfrastructureError, match="cannot answer"):
        asyncio.run(worker.handle(f"{request['nonce']}.request.json"))


def test_exact_usage_above_reservation_is_not_hidden(setup, tmp_path):
    mission, context, config, channel = setup

    def peer():
        while not list((channel / "requests").glob("*.json")):
            time.sleep(0.01)
        path = next((channel / "requests").glob("*.json"))
        request = bounded_json(path)
        response = result(request, sha256(path.read_bytes()))
        response["usage"]["tokens"] = TOKEN_CEILING + 10
        publish_response(channel, response)

    thread = threading.Thread(target=peer)
    thread.start()
    generated = CodexMailboxBackend().generate(mission, context, config, tmp_path)
    thread.join(timeout=3)
    assert generated.tokens == TOKEN_CEILING + 10 and generated.infrastructure_error
    assert (tmp_path / "tree/src/main.c").read_text() == "int original;\n"
