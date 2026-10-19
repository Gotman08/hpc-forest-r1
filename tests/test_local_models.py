"""Local model import plumbing, with synthetic bytes and no optimization hints."""

import hashlib
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

MODULE = Path(__file__).parents[1] / "examples/marathon22/local_model.py"
SPEC = importlib.util.spec_from_file_location("marathon_local_model", MODULE)
local = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(local)


def test_import_verifies_content_addressed_manifest_without_legacy_path(tmp_path):
    blobs = tmp_path / "models/blobs"
    blobs.mkdir(parents=True)
    raw = b'{"schemaVersion":2,"layers":[]}\n'
    digest = hashlib.sha256(raw).hexdigest()
    path = blobs / ("sha256-" + digest)
    path.write_bytes(raw)
    identity = {"model": "local-example:q4", "model_digest": digest}
    loaded_raw, decoded = local.installed_manifest(tmp_path, identity)
    assert loaded_raw == raw and decoded["schemaVersion"] == 2
    assert not (tmp_path / "models/manifests").exists()
    path.write_bytes(b"{}")
    with pytest.raises(RuntimeError, match="resolved identity"):
        local.installed_manifest(tmp_path, identity)


def test_launcher_reserves_both_context_and_reasoning_output(monkeypatch):
    monkeypatch.syspath_prepend(str(MODULE.parent))
    module_spec = importlib.util.spec_from_file_location(
        "marathon_budget_launcher", MODULE.parent / "romeo_marathon.py"
    )
    launcher = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(launcher)
    prepared = {"protocol_timeout_seconds": 30}
    before = launcher.config_for("http://127.0.0.1:12345", "knn", "test-target", prepared)
    assert before["budget"]["mission_tokens"] == 40960
    monkeypatch.setattr(launcher, "DECODING", {"context_tokens": 65536, "max_output_tokens": 32768})
    after = launcher.config_for("http://127.0.0.1:12345", "knn", "test-target", prepared)
    assert after["budget"]["mission_tokens"] == 98304
    assert (
        after["ollama"]["context_tokens"] == 65536 and after["ollama"]["max_output_tokens"] == 32768
    )
    assert before["protocol"] == after["protocol"] and before["schedule"] == after["schedule"]


def test_spec_requires_immutable_files_and_declared_source(tmp_path):
    spec = {
        "model": "local-example:q4",
        "upstream": "example/model",
        "revision": "a" * 40,
        "files": [
            {
                "name": "model.gguf",
                "bytes": 12,
                "sha256": "b" * 64,
                "url": f"https://huggingface.co/example/model/resolve/{'a' * 40}/model.gguf",
            }
        ],
    }
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    assert local.read_spec(path) == spec
    spec["files"][0]["url"] = "https://huggingface.co/example/model/resolve/main/model.gguf"
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="immutable revision"):
        local.read_spec(path)
    spec["files"][0]["name"] = "../outside.gguf"
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="shard name"):
        local.read_spec(path)


def test_disjoint_download_preserves_bytes_and_rejects_wrong_hash(tmp_path, monkeypatch):
    data = b"0123456789abcdef" * 1007
    observed = []
    mode = {"honor_range": True}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            start, end = map(int, self.headers["Range"][6:].split("-"))
            observed.append((start, end))
            if mode["honor_range"]:
                body = data[start : end + 1]
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
            else:
                body = data
                self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(local, "RANGE_THRESHOLD", 100)
    monkeypatch.setattr(local, "RANGE_BYTES", len(data) // 4)
    try:
        spec = {
            "bytes": len(data),
            "url": f"http://127.0.0.1:{http.server_port}/blob",
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        target = tmp_path / "pinned"
        receipt = local.download(spec, target)
        assert target.read_bytes() == data and receipt["verified_sha256"] == spec["sha256"]
        ranges = sorted(observed)
        assert len(ranges) == 4 and ranges[0][0] == 0 and ranges[-1][1] == len(data) - 1
        assert all(a[1] + 1 == b[0] for a, b in zip(ranges, ranges[1:], strict=False))
        with pytest.raises(RuntimeError, match="identity mismatch"):
            local.download({**spec, "sha256": "0" * 64}, tmp_path / "wrong")
        mode["honor_range"] = False
        with pytest.raises(RuntimeError, match="honor bounded range"):
            local.download(spec, tmp_path / "ignored-range")
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=2)


def test_download_resumes_from_last_received_byte_after_connection_drop(tmp_path, monkeypatch):
    data = b"abcdefghijklmnopqrstuvwxyz" * 700
    ranges = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            start, end = map(int, self.headers["Range"][6:].split("-"))
            ranges.append((start, end))
            body = data[start : end + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body[:3000] if len(ranges) == 1 else body)
            self.close_connection = True

        def log_message(self, *args):
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(local, "RETRY_DELAYS", (0, 0))
    try:
        spec = {
            "bytes": len(data),
            "url": f"http://127.0.0.1:{http.server_port}/blob",
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        path = tmp_path / "resumed"
        receipt = local.download(spec, path)
        assert path.read_bytes() == data
        assert ranges == [(0, len(data) - 1), (3000, len(data) - 1)]
        assert receipt["ranges"][0]["attempts"] == 2
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=2)
