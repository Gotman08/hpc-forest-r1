import copy
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from hpc_forest.core import CandidateRejected, InfrastructureError, Mission
from hpc_forest.ollama_backend import (
    OllamaBackend,
    local_url,
    request_json,
    resolve_model,
    validate_files,
)


@pytest.fixture
def server():
    state = {
        "digest": "a" * 64,
        "response": {
            "model": "qwen2.5-coder:7b",
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 200,
            "eval_count": 60,
            "message": {
                "content": json.dumps(
                    {
                        "hypothesis": "Try memory blocking",
                        "transformations": ["blocking"],
                        "sources_kept": [],
                        "files": [{"path": "src/params.h", "content": "#define TILE 16\n"}],
                        "notes": "to evaluate independently",
                    }
                )
            },
        },
        "requests": [],
        "http_status": 200,
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/tags":
                value = {
                    "models": [
                        {
                            "name": "qwen2.5-coder:7b",
                            "digest": state["digest"],
                            "details": {"quantization_level": "Q4_K_M"},
                        }
                    ]
                }
            else:
                value = {"version": "0.40.4"}
            self.send(value)

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(data)
            self.send(state["response"])

        def send(self, value):
            data = json.dumps(value).encode()
            self.send_response(state.get("chat_http_status",state["http_status"]) if self.command=="POST" else state["http_status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    state["url"] = f"http://127.0.0.1:{http.server_port}"
    yield state
    http.shutdown()
    thread.join(timeout=2)
    http.server_close()


def mission_and_config(tmp_path, config, server):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "params.h").write_text("original", encoding="utf-8")
    config["backend"] = "ollama"
    config["ollama"]["base_url"] = server["url"]
    config["ollama"] = resolve_model(config["ollama"])
    mission = Mission("trial", "e1:A", "local-1", 1, "A", "base", None, "R/A", 1, 1, str(tmp_path))
    return mission, config


def test_real_http_adapter_pins_digest_records_usage_and_applies_source(tmp_path, config, server):
    mission, config = mission_and_config(tmp_path, config, server)
    result = OllamaBackend().generate(mission, {"deadline": time.time() + 20}, config, tmp_path)
    assert result.error is None and result.tokens == 260
    assert result.usage["llm_calls"] == 1 and result.usage["model_digest"] == "a" * 64
    assert (tmp_path / "src" / "params.h").read_text() == "#define TILE 16\n"
    assert server["requests"][0]["stream"] is False
    assert server["requests"][0]["options"]["num_predict"] == 4096
    assert server["requests"][0]["options"]["num_thread"] == 4
    assert server["requests"][0]["format"]["properties"]["sources_kept"]["maxItems"] == 0
    assert (
        "--- BEGIN FILE src/params.h ---\noriginal"
        in server["requests"][0]["messages"][1]["content"]
    )
    assert (tmp_path / "logs" / "trial" / "ollama-response.json").is_file()


def test_unlimited_tokens_keep_the_configured_context_window(tmp_path, finish_started_config, server):
    mission, config = mission_and_config(tmp_path, finish_started_config, server)
    result = OllamaBackend().generate(mission, {"deadline": time.time() + 20}, config, tmp_path)
    assert result.error is None
    options = server["requests"][0]["options"]
    assert options["num_predict"] == -1
    assert options["num_ctx"] == config["ollama"]["context_tokens"]


def test_http_failure_preserves_server_diagnostic_and_does_not_replay(server):
    server["http_status"] = 500
    server["response"] = {"error": "inference runner rejected response"}
    with pytest.raises(InfrastructureError, match="HTTP 500 at /api/chat.*runner rejected"):
        request_json(server["url"], "/api/chat", {"model": "test"}, 3)
    assert len(server["requests"]) == 1


def test_http_failure_diagnostic_is_bounded(server):
    server["http_status"] = 500
    server["response"] = {"error": "x" * 10000}
    with pytest.raises(InfrastructureError) as caught:
        request_json(server["url"], "/api/chat", {"model": "test"}, 3)
    assert "HTTP 500" in str(caught.value) and len(str(caught.value)) < 4200


def test_repetition_abort_is_bounded_without_applying_source_or_replaying(tmp_path,config,server):
    mission,config=mission_and_config(tmp_path,config,server)
    server["chat_http_status"]=500
    server["response"]={"error":"prediction aborted, token repeat limit reached"}
    result=OllamaBackend().generate(mission,{"deadline":time.time()+20},config,tmp_path)
    assert result.infrastructure_error and result.tokens_upper_bound
    assert result.tokens==8192+4096
    assert result.usage["exact_tokens"] is None and result.usage["token_accounting"]=="upper_bound"
    assert len(server["requests"])==1
    assert (tmp_path/"src/params.h").read_text()=="original"
    assert not (tmp_path/"logs/trial/agent-result.json").exists()
    assert json.loads((tmp_path/"logs/trial/ollama-error.json").read_text())["token_ceiling"]==result.tokens


def test_other_engine_failures_still_abort_without_claiming_a_bound(tmp_path,config,server):
    mission,config=mission_and_config(tmp_path,config,server)
    server["chat_http_status"]=500
    server["response"]={"error":"unexpected GPU runner failure"}
    with pytest.raises(InfrastructureError,match="GPU runner failure"):
        OllamaBackend().generate(mission,{"deadline":time.time()+20},config,tmp_path)
    assert len(server["requests"])==1 and (tmp_path/"src/params.h").read_text()=="original"


def test_source_string_escapes_survive_one_json_decode(tmp_path, config, server):
    mission, config = mission_and_config(tmp_path, config, server)
    source = '#include <stdio.h>\nvoid output(void) { puts("line\\nquoted \\\"text\\\""); }\n'
    data = json.loads(server["response"]["message"]["content"])
    data["files"] = [{"path": "src/output.c", "content": source}]
    server["response"]["message"]["content"] = json.dumps(data)
    result = OllamaBackend().generate(mission, {"deadline": time.time()+20}, config, tmp_path)
    assert result.error is None
    assert (tmp_path/"src/output.c").read_bytes() == source.encode("utf-8")
    system = server["requests"][0]["messages"][0]["content"]
    assert "src/params.h" not in system
    assert "Preserve backslashes" in system


def test_configured_repetition_controls_reach_the_local_server(tmp_path, config, server):
    config["ollama"].update(repeat_penalty=1.1, repeat_last_n=64)
    mission, config = mission_and_config(tmp_path, config, server)
    result = OllamaBackend().generate(mission, {"deadline": time.time()+20}, config, tmp_path)
    assert result.error is None
    assert server["requests"][0]["options"]["repeat_penalty"] == 1.1
    assert server["requests"][0]["options"]["repeat_last_n"] == 64


@pytest.mark.parametrize(
    "path",
    [
        "../oracle.py",
        "src/../../oracle.py",
        "/tmp/oracle.py",
        "src\\escape.c",
        "C:/outside.c",
        "src/.git/config",
    ],
)
def test_all_edits_are_rejected_before_any_write(tmp_path, path):
    (tmp_path / "src").mkdir()
    data = {
        "hypothesis": "x",
        "transformations": [],
        "sources_kept": [],
        "notes": "x",
        "files": [{"path": "src/good.c", "content": "safe"}, {"path": path, "content": "bad"}],
    }
    with pytest.raises(CandidateRejected):
        validate_files(tmp_path, data, [])
    assert not (tmp_path / "src" / "good.c").exists()


def test_changed_weights_abort_before_generation(tmp_path, config, server):
    mission, config = mission_and_config(tmp_path, config, server)
    server["digest"] = "b" * 64
    with pytest.raises(InfrastructureError, match="digest changed"):
        OllamaBackend().generate(mission, {"deadline": time.time() + 20}, config, tmp_path)
    assert not server["requests"]


@pytest.mark.parametrize("condition", ["truncated", "invalid_json", "unknown_usage"])
def test_no_fabricated_success_for_partial_or_unaccounted_reply(
    tmp_path, config, server, condition
):
    mission, config = mission_and_config(tmp_path, config, server)
    if condition == "truncated":
        server["response"]["done_reason"] = "length"
    elif condition == "invalid_json":
        server["response"]["message"]["content"] = "not JSON"
    else:
        del server["response"]["eval_count"]
    result = OllamaBackend().generate(mission, {"deadline": time.time() + 20}, config, tmp_path)
    if condition == "unknown_usage":
        assert result.tokens is None
    else:
        assert result.error and result.tokens == 260
        assert (tmp_path / "src" / "params.h").read_text() == "original"


@pytest.mark.parametrize(
    "url",
    [
        "https://remote.example",
        "http://remote.example:11434",
        "http://user:password@localhost:11434",
        "http://localhost:11434/?x=1",
    ],
)
def test_local_model_cannot_silently_use_a_cloud_endpoint(url):
    with pytest.raises(InfrastructureError):
        local_url(url)


def test_unknown_integration_source_is_rejected(tmp_path):
    (tmp_path / "src").mkdir()
    data = {
        "hypothesis": "x",
        "transformations": [],
        "sources_kept": ["unknown"],
        "notes": "x",
        "files": [{"path": "src/params.h", "content": "x"}],
    }
    with pytest.raises(CandidateRejected, match="source"):
        validate_files(tmp_path, copy.deepcopy(data), ["real"])
