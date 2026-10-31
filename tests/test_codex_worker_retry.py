"""Local file-transport regressions; these tests never invoke a model or ROMEO."""

import asyncio
import json
import shutil
import time
from types import SimpleNamespace

import pytest

from hpc_forest import codex_worker
from hpc_forest.codex_mailbox import (
    EFFORT,
    MODEL,
    PROTOCOL,
    initialize_channel,
    publish_request,
    response_envelope,
    sha256,
    wait_response,
)
from hpc_forest.core import InfrastructureError

REMOTE = "/scratch/hpc-forest-gpt61sol-max-test/results-1/mailbox"


class Transfer:
    def __init__(self, channel, *, fail_suffix=None, failures=0):
        self.channel, self.fail_suffix, self.failures = channel, fail_suffix, failures
        self.downloads, self.uploads = [], []

    def local(self, remote):
        return self.channel / remote.split("/mailbox/", 1)[1]

    async def download(self, remote, local):
        self.downloads.append(remote)
        shutil.copyfile(self.local(remote), local)
        return {"ok": True, "verifie": True, "remote_sha256": sha256(local.read_bytes())}

    async def upload(self, local, remote):
        self.uploads.append((remote, local.read_bytes()))
        if self.fail_suffix and remote.endswith(self.fail_suffix) and self.failures:
            self.failures -= 1
            raise InfrastructureError("Synthetic transient SCP failure")
        shutil.copyfile(local, self.local(remote))
        return {"ok": True, "verifie": True}


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    channel = tmp_path / "mailbox"
    initialize_channel(channel, "a" * 32, "test")
    request = {"protocol": PROTOCOL, "kind": "source-proposal", "nonce": "b" * 32,
               "session_id": "a" * 32, "model": MODEL, "reasoning_effort": EFFORT,
               "expires_at": time.time() + 30}
    request_sha = publish_request(channel, request)
    calls = []

    def model(request, request_sha, *args):
        calls.append(request["nonce"])
        return response_envelope(request, request_sha, data={"fixture": True}, error=None,
                                 infrastructure_error=False,
                                 usage={"tokens": 17, "token_accounting": "exact", "llm_calls": 1})

    monkeypatch.setattr(codex_worker, "run_codex", model)
    return channel, request, request_sha, calls, tmp_path / "worker"


def worker(transfer, output):
    return codex_worker.Worker(transfer, REMOTE, "a" * 32, output, None, set(),
                               defer_diagnostics=True)


@pytest.mark.parametrize("suffix", [".response.json", ".ready.json"])
def test_transient_upload_recovers_with_identical_bytes_and_one_generation(fixture, suffix):
    channel, request, request_sha, calls, output = fixture
    transfer = Transfer(channel, fail_suffix=suffix, failures=1)
    instance = worker(transfer, output)
    assert asyncio.run(instance.handle(request["nonce"] + ".request.json"))
    response = wait_response(channel, request, request_sha)
    assert response["usage"]["tokens"] == 17
    assert len(calls) == 1
    retried = [raw for remote, raw in transfer.uploads if remote.endswith(suffix)]
    assert len(retried) == 2 and retried[0] == retried[1]
    assert not asyncio.run(instance.handle(request["nonce"] + ".request.json"))


def test_finish_started_response_can_be_delivered_after_search_time_and_restart(fixture, monkeypatch):
    channel, request, _, calls, output = fixture
    old_expiry = request["expires_at"]
    request.update(expires_at=None, deadline_policy="finish-started", budget_phase="postprocess")
    path = channel / "requests" / (request["nonce"] + ".request.json")
    path.write_bytes(codex_worker.json_bytes(request))
    request_sha = sha256(path.read_bytes())
    clock = [old_expiry + 3600]
    monkeypatch.setattr(codex_worker, "time", SimpleNamespace(time=lambda: clock[0]))
    transfer = Transfer(channel, fail_suffix=".ready.json", failures=1)
    assert asyncio.run(worker(transfer, output).handle(path.name))
    assert wait_response(channel, request, request_sha)["usage"]["tokens"] == 17
    assert calls == [request["nonce"]]
    assert not (output / request["nonce"] / "expired.json").exists()
    assert not asyncio.run(worker(Transfer(channel), output).handle(path.name))
    assert calls == [request["nonce"]]


def test_unlimited_request_requires_explicit_policy_and_phase(fixture):
    _, request, _, _, _ = fixture
    request["expires_at"] = None
    with pytest.raises(InfrastructureError, match="completion phase"):
        codex_worker.validate_request(request, request["session_id"], request["nonce"])
    request.update(deadline_policy="finish-started", budget_phase="search")
    codex_worker.validate_request(request, request["session_id"], request["nonce"])


def test_finish_started_relay_publishes_identity_bound_liveness_while_running(fixture):
    channel, _, _, calls, output = fixture
    async def alive():
        published = asyncio.Event()
        class ObservedTransfer(Transfer):
            async def upload(self, local, remote):
                receipt = await super().upload(local, remote)
                if remote.endswith("/worker-heartbeat.json"):
                    published.set()
                return receipt
        instance = worker(ObservedTransfer(channel), output)
        async with instance.keepalive(True):
            # One event-loop tick does not guarantee retry_transfer has published.
            await asyncio.wait_for(published.wait(), timeout=5)
            beat = json.loads((channel / "worker-heartbeat.json").read_text())
            assert beat["session_id"] == "a" * 32 and beat["model"] == MODEL
    asyncio.run(alive())
    assert not calls


def test_heartbeat_reconnects_its_own_session_without_poisoning_model_delivery(fixture, monkeypatch):
    channel, _, _, calls, output = fixture
    sessions, published = [], []
    original_atomic = codex_worker.atomic_json
    def atomic(path, data):
        if path == output / "worker-heartbeat.json":
            raise PermissionError("fixture: a local monitor holds the latest marker")
        original_atomic(path, data)
    monkeypatch.setattr(codex_worker, "atomic_json", atomic)
    monkeypatch.setattr(codex_worker, "HEARTBEAT_INTERVAL_SECONDS", 0.001)
    class Files:
        def __init__(self, config, *, model=False):
            self.config, self.model = config, model
        async def __aenter__(self):
            sessions.append(self)
            return self
        async def __aexit__(self, *args):
            return False
        async def upload(self, path, remote):
            assert not self.model, "The model response connection must remain untouched"
            if len(sessions) == 1:
                raise ExceptionGroup("fixture: a cancelled pulse RPC", [BrokenPipeError("closed pulse stream")])
            published.append((path, path.read_bytes()))
    monkeypatch.setattr(codex_worker, "RomeoFiles", Files)
    instance = worker(Files(output / "config.toml", model=True), output)
    async def alive():
        async with instance.keepalive(True):
            async with asyncio.timeout(2):
                while len(published) < 2:
                    await asyncio.sleep(0.001)
    asyncio.run(alive())
    assert len(sessions) >= 3 and not calls
    assert published[0][0] != published[1][0]
    assert all(path.read_bytes() == raw for path, raw in published)
    assert json.loads(published[-1][1])["session_id"] == "a" * 32
    assert (output / "heartbeat-error.json").exists()


def test_exception_groups_only_retry_transport_errors():
    assert codex_worker._transfer_failure(ExceptionGroup("transport", [TimeoutError(), OSError()]))
    assert not codex_worker._transfer_failure(ExceptionGroup("programming", [TimeoutError(), ValueError()]))


def test_heartbeat_stops_even_if_sdk_cleanup_swallows_cancellation(fixture, monkeypatch):
    _, _, _, calls, output = fixture
    entered, closed = asyncio.Event(), []
    class Files:
        def __init__(self, config):
            self.config = config
        async def __aenter__(self):
            return self
        async def __aexit__(self, kind, value, traceback):
            closed.append(kind)
            return kind is asyncio.CancelledError and len(closed) == 1
        async def upload(self, *args):
            entered.set()
            await asyncio.Event().wait()
    monkeypatch.setattr(codex_worker, "RomeoFiles", Files)
    instance = worker(Files(output / "config.toml"), output)
    async def exercise():
        async with instance.keepalive(True):
            await entered.wait()
    started = time.monotonic()
    asyncio.run(asyncio.wait_for(exercise(), timeout=0.5))
    assert time.monotonic() - started < 0.25
    assert len(closed) == 1 and not calls


def test_persistent_failure_is_bounded_and_restart_resends_cache_without_regeneration(fixture):
    channel, request, request_sha, calls, output = fixture
    transfer = Transfer(channel, fail_suffix=".response.json", failures=10)
    with pytest.raises(InfrastructureError, match="after 3 attempts"):
        asyncio.run(worker(transfer, output).handle(request["nonce"] + ".request.json"))
    assert len(transfer.uploads) == 3 and len(calls) == 1
    cached = (output / request["nonce"] / "response.json").read_bytes()
    healthy = Transfer(channel)
    assert asyncio.run(worker(healthy, output).handle(request["nonce"] + ".request.json"))
    assert len(calls) == 1
    assert healthy.uploads[0][1] == cached
    assert wait_response(channel, request, request_sha)["usage"]["tokens"] == 17
    # Already acknowledged deliveries are restored locally, with no file-tool calls.
    restarted_transfer = Transfer(channel)
    assert not asyncio.run(worker(restarted_transfer, output).handle(
        request["nonce"] + ".request.json"))
    assert not restarted_transfer.downloads and not restarted_transfer.uploads


def test_original_deadline_retires_undelivered_cache_without_late_result(fixture, monkeypatch):
    channel, request, _, calls, output = fixture
    path = channel / "requests" / (request["nonce"] + ".request.json")
    clock = [time.time()]
    monkeypatch.setattr(codex_worker, "time", SimpleNamespace(time=lambda: clock[0]))

    class ExpiringTransfer(Transfer):
        async def upload(self, local, remote):
            try:
                return await super().upload(local, remote)
            except InfrastructureError:
                clock[0] = request["expires_at"] + 1
                raise

    transfer = ExpiringTransfer(channel, fail_suffix=".response.json", failures=10)
    instance = worker(transfer, output)
    assert not asyncio.run(instance.handle(path.name))
    assert len(calls) == 1 and len(transfer.uploads) == 1
    local = output / request["nonce"]
    assert (local / "expired.json").is_file()
    assert json.loads((local / "response.json").read_text())["usage"]["tokens"] == 17
    assert not (channel / "responses" / (request["nonce"] + ".ready.json")).exists()
    restored = Transfer(channel)
    assert not asyncio.run(worker(restored, output).handle(path.name))
    assert not restored.downloads and not restored.uploads


def test_restarted_delivery_refuses_changed_cache(fixture):
    channel, request, _, _, output = fixture
    assert asyncio.run(worker(Transfer(channel), output).handle(request["nonce"] + ".request.json"))
    (output / request["nonce"] / "response.json").write_text("{}")
    with pytest.raises(InfrastructureError, match="response changed"):
        worker(Transfer(channel), output)


def test_wrong_session_is_not_retried_or_served(fixture):
    channel, request, _, calls, output = fixture
    request["session_id"] = "c" * 32
    path = channel / "requests" / (request["nonce"] + ".request.json")
    path.write_text(json.dumps(request), encoding="utf8")
    transfer = Transfer(channel)
    with pytest.raises(InfrastructureError, match="another session"):
        asyncio.run(worker(transfer, output).handle(path.name))
    assert len(transfer.downloads) == 1 and not transfer.uploads and not calls


@pytest.mark.parametrize("expired", [False, True])
def test_same_nonce_and_session_with_different_claim_hash_is_fatal(fixture, expired):
    channel, request, _, calls, output = fixture
    local = output / request["nonce"]
    local.mkdir(parents=True)
    (local / "generation-claimed.json").write_text(json.dumps({"request_sha256": "c" * 64}))
    if expired:
        request["expires_at"] = time.time() - 1
        (channel / "requests" / (request["nonce"] + ".request.json")).write_text(
            json.dumps(request), encoding="utf8")
    transfer = Transfer(channel)
    with pytest.raises(codex_worker.TransferVerificationError, match="claim.*different request hash"):
        asyncio.run(worker(transfer, output).handle(request["nonce"] + ".request.json"))
    assert len(transfer.downloads) == 1 and not transfer.uploads and not calls
    assert not (local / "response.json").exists() and not (local / "expired.json").exists()


def test_expired_unclaimed_request_is_terminal_without_generation(fixture):
    channel, request, _, calls, output = fixture
    request["expires_at"] = time.time() - 1
    path = channel / "requests" / (request["nonce"] + ".request.json")
    path.write_text(json.dumps(request), encoding="utf8")
    transfer = Transfer(channel)
    assert not asyncio.run(worker(transfer, output).handle(path.name))
    assert not calls and not transfer.uploads
    assert not (output / request["nonce"] / "generation-claimed.json").exists()
    restarted = Transfer(channel)
    assert not asyncio.run(worker(restarted, output).handle(path.name))
    assert not restarted.downloads and not restarted.uploads


def test_integrity_failure_is_fatal_without_retry(fixture):
    channel, request, _, calls, output = fixture

    class InvalidReceipt(Transfer):
        async def upload(self, local, remote):
            self.uploads.append((remote, local.read_bytes()))
            raise codex_worker.TransferVerificationError("Synthetic invalid hash receipt")

    transfer = InvalidReceipt(channel)
    with pytest.raises(codex_worker.TransferVerificationError):
        asyncio.run(worker(transfer, output).handle(request["nonce"] + ".request.json"))
    assert len(calls) == 1 and len(transfer.uploads) == 1
    assert not (output / request["nonce"] / "expired.json").exists()


def test_diagnostics_failure_is_preserved_without_affecting_delivered_response(fixture):
    channel, request, request_sha, _, output = fixture
    transfer = Transfer(channel, fail_suffix=".codex.jsonl", failures=10)
    instance = worker(transfer, output)
    assert asyncio.run(instance.handle(request["nonce"] + ".request.json"))
    local = output / request["nonce"]
    (local / "codex.jsonl").write_text("fixture diagnostics")
    assert asyncio.run(instance.flush_diagnostics()) == [request["nonce"]]
    assert (local / "diagnostics-pending.json").is_file()
    assert wait_response(channel, request, request_sha)["data"] == {"fixture": True}


def test_retry_helper_preserves_nontransport_errors_and_bounds_wait():
    calls = []

    async def invalid():
        calls.append(1)
        raise ValueError("Not a transport error")

    with pytest.raises(ValueError):
        asyncio.run(codex_worker.retry_transfer(invalid, retry_delay=0))
    assert len(calls) == 1

    async def stalled():
        await asyncio.sleep(60)

    started = time.monotonic()
    with pytest.raises(InfrastructureError):
        asyncio.run(codex_worker.retry_transfer(stalled, attempts=2, timeout=0.01, retry_delay=0))
    assert time.monotonic() - started < 1


def test_interrupted_response_write_leaves_no_truncated_cache(fixture, monkeypatch):
    channel, request, request_sha, calls, output = fixture
    original, armed = codex_worker.Path.write_bytes, [True]

    def interrupted(path, data):
        if armed[0] and (path.name == "response.json" or path.name.startswith(".response.json.")):
            armed[0] = False
            original(path, data[: len(data) // 2])
            raise OSError("Synthetic power loss while publishing the response")
        return original(path, data)

    monkeypatch.setattr(codex_worker.Path, "write_bytes", interrupted)
    with pytest.raises(OSError, match="power loss"):
        asyncio.run(worker(Transfer(channel), output).handle(request["nonce"] + ".request.json"))
    assert not (output / request["nonce"] / "response.json").exists()
    # The restart reports the charged request as interrupted instead of crashing on a partial cache.
    assert asyncio.run(worker(Transfer(channel), output).handle(request["nonce"] + ".request.json"))
    response = wait_response(channel, request, request_sha)
    assert response["infrastructure_error"] and "not replayed" in response["error"]
    assert calls == [request["nonce"]]


class ToolSession:
    def __init__(self, response):
        self.response, self.calls = response, 0

    async def call_tool(self, name, arguments):
        self.calls += 1
        return self.response


@pytest.mark.parametrize("error,content", [
    (True, [SimpleNamespace(type="text", text="Error executing tool upload_to_romeo: timed out")]),
    (False, []),
    (False, [SimpleNamespace(type="text", text="not JSON")]),
])
def test_romeo_tool_errors_are_retried_as_transport_failures(tmp_path, error, content):
    files = codex_worker.RomeoFiles(tmp_path / "codex.toml")
    files.session = ToolSession(SimpleNamespace(isError=error, structuredContent=None, content=content))
    with pytest.raises(InfrastructureError, match="after 2 attempts"):
        asyncio.run(codex_worker.retry_transfer(
            lambda: files.call("upload_to_romeo", local_path="x", remote_path="y"), attempts=2, retry_delay=0))
    assert files.session.calls == 2
