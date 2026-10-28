"""Operator commands remain idempotent and cannot relaunch a frozen job."""
import asyncio
import json
import threading
from types import SimpleNamespace

import pytest
from test_web_execution import Connector
from test_web_execution import application as application_fixture

from hpc_forest.core import InfrastructureError, atomic_json
from hpc_forest.operator_control import stop_requested
from hpc_forest.webapp.paths import AppError

application = application_fixture


def test_stop_before_submission_cancels_without_network(application):
    _, settings, _, prepared, missions = application
    stale = missions.launch(prepared["id"])
    missions.request_stop(stale["id"])
    client = Connector()
    asyncio.run(missions.start(client, stale, settings))
    assert missions.get(stale["id"])["state"] == "cancelled"
    assert not client.calls


def test_stop_during_upload_cannot_submit_cancelled_mission(application):
    _, settings, _, prepared, missions = application
    record = missions.launch(prepared["id"])
    class StopOnUpload(Connector):
        async def upload(self, local, remote):
            missions.request_stop(record["id"])
    client = StopOnUpload()
    asyncio.run(missions.start(client, record, settings))
    assert "job_submit" not in client.calls
    assert missions.get(record["id"])["state"] == "cancelled"


def test_stale_start_after_submit_is_idempotent(application):
    _, settings, _, prepared, missions = application
    stale = missions.launch(prepared["id"])
    client = Connector()
    asyncio.run(missions.start(client, stale, settings))
    asyncio.run(missions.start(client, stale, settings))
    assert client.calls.count("job_submit") == 1


def test_stop_delivery_survives_lost_response(application):
    _, settings, _, prepared, missions = application
    record = missions.launch(prepared["id"])
    asyncio.run(missions.start(Connector(), record, settings))
    record = missions.request_stop(record["id"])
    class StopTransport:
        def __init__(self):
            self.deliveries = []
        async def upload(self, local, remote):
            self.deliveries.append(json.loads(local.read_text()))
            if len(self.deliveries) == 1:
                raise TimeoutError("response lost after upload")
    client = StopTransport()
    with pytest.raises(TimeoutError):
        asyncio.run(missions.deliver_stop(client, record))
    asyncio.run(missions.deliver_stop(client, missions.get(record["id"])))
    assert client.deliveries[0] == client.deliveries[1]
    assert missions.get(record["id"])["stop_delivered_at"]


def test_historical_engine_cannot_claim_a_supported_stop(application):
    _, _, _, prepared, missions = application
    record = missions.launch(prepared["id"])
    missions.update(record["id"], state="running", launch={})
    with pytest.raises(AppError, match="historique"):
        missions.request_stop(record["id"])


def test_stop_delivery_failure_keeps_monitoring_existing_job(application, monkeypatch):
    _, settings, _, prepared, missions = application
    record = missions.launch(prepared["id"])
    asyncio.run(missions.start(Connector(), record, settings))
    missions.request_stop(record["id"])
    class QueuedConnector:
        def __init__(self, path):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def upload(self, local, remote):
            raise FileNotFoundError("job has not extracted its working directory")
    observed = []
    async def refresh(client, value):
        observed.append(value["job_id"])
    monkeypatch.setattr(missions, "connector", QueuedConnector)
    monkeypatch.setattr(missions, "refresh", refresh)
    asyncio.run(missions.tick())
    assert observed == [missions.get(record["id"])["job_id"]]
    assert missions.get(record["id"])["stop_delivery_error"]


def test_controller_stop_is_bound_and_recorded_once(tmp_path, db, config):
    config.update(problem="app-mission", app_protocol={"binary": "program"})
    config["codex"]["session_id"] = "session"
    controller = SimpleNamespace(root=tmp_path / "campaign", db=db, config=config)
    path = tmp_path / "stop-request.json"
    path.write_text('{"partial":')
    assert not stop_requested(controller)
    request = {"schema": "forest-operator-stop-v1", "mission_id": "wrong", "session_id": "session"}
    atomic_json(path, request)
    with pytest.raises(InfrastructureError):
        stop_requested(controller)
    atomic_json(path, {**request, "mission_id": "mission"})
    assert stop_requested(controller) and stop_requested(controller)
    assert len(db.rows("SELECT * FROM events WHERE kind='operator_stop_accepted'")) == 1


@pytest.mark.parametrize("active", [False, True])
def test_stop_drains_admitted_trees_then_really_confirms(tmp_path, monkeypatch, need_compiler, active):
    from test_mother_conversation import native_campaign

    from hpc_forest.control_versions import contracts

    _, controller, native = native_campaign(tmp_path, monkeypatch, 2)
    native.expire_in_planning = False
    if active:
        controller.config["forest"]["active"] = {"mode": "full", "closure_guards": False,
                                                   "code_analysis": False}
        controller.db.set("config", controller.config)
        controller.db.set("control_contracts", contracts(controller.config))
    completed = []
    original = controller._complete_generation
    observed = threading.Event()
    def complete(mission, slot, generated, baseline):
        fatal = original(mission, slot, generated, baseline)
        if mission.role != "G":
            completed.append(mission.id)
            controller.db.set("operator_stop:1", {"policy": "drain_then_confirm"})
            observed.set()
        return fatal
    controller._complete_generation = complete
    with controller:
        status = controller.run()
        assert observed.is_set() and len(completed) == 2
        assert status["research_scheduler"]["stop_reason"] == "operator_stop"
        assert not controller.db.rows("SELECT id FROM trials WHERE state='pending'")
        assert status["postprocess"]["status"] == "complete"
        controller.confirm()
        assert controller.status()["final_g_confirmation"]["status"] in {"confirmed", "rejected"}
