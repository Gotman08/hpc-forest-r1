import asyncio
import copy
import threading

import pytest
import test_codex_worker_retry as local_transport

from hpc_forest import codex_worker
from hpc_forest.codex_mailbox import publish_request, response_envelope, wait_response
from hpc_forest.request_pool import RequestPool

relay_fixture = local_transport.fixture


@pytest.mark.parametrize("count", [8, 40])
def test_native_relay_starts_all_n_calls_together_and_delivers_once(relay_fixture, monkeypatch, count):
    channel, original, _, _, output = relay_fixture
    barrier = threading.Barrier(count, timeout=10)
    calls, requests = [], []
    for index in range(count):
        request = copy.deepcopy(original)
        request.update(nonce=f"{index + 1:032x}", expires_at=None,
                       deadline_policy="finish-started", budget_phase="search")
        requests.append((request, publish_request(channel, request)))
    (channel / "requests" / (original["nonce"] + ".request.json")).unlink()
    def model(request, request_sha, *args):
        calls.append(request["nonce"])
        barrier.wait()
        return response_envelope(request, request_sha, data={"fixture": True}, error=None,
            infrastructure_error=False, usage={"tokens": 7, "token_accounting": "exact", "llm_calls": 1})
    monkeypatch.setattr(codex_worker, "run_codex", model)
    async def exercise():
        instance = local_transport.worker(local_transport.Transfer(channel), output)
        pool = RequestPool(instance)
        names = [request["nonce"] + ".request.json" for request, _ in requests]
        await pool.pump(names + names, count)
        await pool.drain()
        assert len(instance.completed) == count
        await pool.pump(names, count)
        assert not pool.active
        await pool.close()
    asyncio.run(exercise())
    assert len(calls) == count and len(set(calls)) == count
    for request, sha in requests:
        response = wait_response(channel, request, sha)
        assert response["error"] is None and response["usage"]["tokens"] == 7


def test_relay_failure_waits_for_other_started_models_before_raising():
    async def exercise():
        release = asyncio.Event()
        finished = []
        class Worker:
            completed, retired = set(), set()
            async def handle(self, name):
                if name == "bad":
                    raise ValueError("synthetic transfer failure")
                await release.wait()
                finished.append(name)
        pool = RequestPool(Worker())
        await pool.pump(["bad", "slow"], 2)
        await asyncio.sleep(0)
        propagation = asyncio.create_task(pool.pump([], 2))
        await asyncio.sleep(0)
        assert not propagation.done()
        release.set()
        with pytest.raises(ValueError, match="synthetic"):
            await propagation
        assert finished == ["slow"] and not pool.active
        await pool.close()
    asyncio.run(exercise())
