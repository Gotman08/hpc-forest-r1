"""Submission idempotency, immutable inputs and model identity across the application."""
import asyncio
import io
import json
import shutil
import time
import zipfile
from pathlib import Path

import pytest

from hpc_forest.codex_mailbox import (
    check_channel,
    initialize_channel,
    make_request,
    response_envelope,
)
from hpc_forest.codex_process import command_for
from hpc_forest.codex_worker import validate_request
from hpc_forest.core import InfrastructureError, Mission, atomic_json, file_digest
from hpc_forest.evaluator import create_evaluator
from hpc_forest.model_policy import catalog
from hpc_forest.webapp.campaigns import Campaigns
from hpc_forest.webapp.execution import Missions, freeze_bundle, job_arguments
from hpc_forest.webapp.paths import AppError
from hpc_forest.webapp.projects import Projects
from hpc_forest.webapp.runner_support import (
    ProjectEvaluator,
    editable_files,
    executable,
    extract_verified,
    prepare_project,
    validate_authorization,
)
from hpc_forest.webapp.store import Store


@pytest.fixture
def application(tmp_path):
    store = Store(tmp_path / "app")
    settings = {"codex_config": str(tmp_path / "codex.toml"), "base_dir": "/scratch/test",
                "codex_home": "/home/test/.codex", "profiles": {"cpu": {
                    "python": "/runtime/python", "codex": "/runtime/codex",
                    "architecture": "x86_64", "spack_packages": ["/gcc-hash"]}}}
    Path(settings["codex_config"]).write_text("configuration fixture")
    atomic_json(store.root / "romeo.json", settings)
    projects = Projects(store)
    project = projects.import_files("Application fixture", [
        ("main.cpp", b"int main(){return 0;}"), ("tests/check.py", b"assert True")])
    projects.update(project["id"], {**project["contract"], "build_command": "g++ main.cpp -o program",
                    "test_command": "python3 tests/check.py", "benchmark_command": "./program 123",
                    "expected_result": "Correct on every test", "duration_minutes": 10,
                    "statement": "Keep the contract", "model": "gpt-6.1-sol", "reasoning_effort": "ultra"})
    projects.attach(project["id"], "statement", "spec.md", b"Preserve all integer input values.")
    projects.attach(project["id"], "test_data", "cases.txt", b"123")
    prepared = projects.prepare(project["id"])
    missions = Missions(store, Campaigns(store))
    return store, settings, projects, prepared, missions


def test_bundle_restores_layout_and_protected_contract(application, tmp_path):
    store, settings, projects, prepared, missions = application
    mission = missions.launch(prepared["id"])
    bundle, launch = freeze_bundle(store, mission, settings)
    root = tmp_path / ("forest-app-" + mission["id"])
    extract_verified(bundle, root)
    assert all(file_digest(root / "engine" / name) == sha for name, sha in launch["engine_files"].items())
    config = prepare_project(root, launch)
    assert config["codex"]["model"] == "gpt-6.1-sol"
    assert config["codex"]["reasoning_effort"] == "ultra"
    assert "Preserve all integer" in config["forest"]["statement"]
    assert (root / "source/src/main.cpp").read_bytes() == b"int main(){return 0;}"
    assert not (root / "source/tests").exists()
    assert (root / "validation/attachments/cases.txt").read_bytes() == b"123"
    assert (root / "validation/original/tests/check.py").read_bytes() == b"assert True"
    assert isinstance(create_evaluator(root, config, {}, "test"), ProjectEvaluator)
    # Updating the draft cannot change a prepared input or an already frozen campaign.
    project = projects.store.get(prepared["project_id"])
    projects.update(project["id"], {**project["contract"], "model": "gpt-6-luna", "reasoning_effort": "max"})
    assert missions.get(mission["id"])["model"] == "gpt-6.1-sol"
    arguments = job_arguments(mission, settings, launch, file_digest(bundle))
    assert arguments["arch"] == "x64cpu" and arguments["cpus_per_task"] == 2
    assert arguments["time_limit"] == "00:40:00"
    assert "PYTHONPATH=" in arguments["command"] and "sha256sum -c" in arguments["command"]


def test_one_forest_keeps_luna_and_rejects_retired_advisor(application, tmp_path):
    store, settings, projects, old_prepared, missions = application
    project = store.get(old_prepared["project_id"])
    for enabled in (False, True):
        with pytest.raises(AppError, match="TabPFN"):
            projects.update(project["id"], {**project["contract"], "advisor": {"enabled": enabled}})
    projects.update(project["id"], {**project["contract"], "model": "gpt-6-luna",
                    "reasoning_effort": "max"})
    prepared = projects.prepare(project["id"])
    mission = missions.launch(prepared["id"])
    bundle, launch = freeze_bundle(store, mission, settings)
    root = tmp_path / ("forest-app-" + mission["id"])
    extract_verified(bundle, root)
    config = prepare_project(root, launch)
    assert "advisor" not in config and "advisor_runtime" not in launch
    with zipfile.ZipFile(bundle) as archive:
        assert not any("advisor" in name for name in archive.namelist())
    assert config["codex"]["model"] == "gpt-6-luna" and config["codex"]["reasoning_effort"] == "max"
    assert config["codex"]["generator_pool"] == []
    assert config["search"]["algorithm"] == "ab-mcts-a"
    assert '"advisor"' not in config["forest"]["statement"]
    other = tmp_path / "tampered"
    extract_verified(bundle, other)
    from hpc_forest.core import ForestError
    with pytest.raises(ForestError, match="TabPFN"):
        prepare_project(other, {**launch, "advisor": {"enabled": False}})


@pytest.mark.parametrize("entry", catalog(), ids=lambda m: m["id"])
def test_model_choice_pins_native_argv_requests_responses_and_channels(application, tmp_path, monkeypatch, entry):
    store, settings, projects, prepared, missions = application
    project = store.get(prepared["project_id"])
    for effort in entry["efforts"]:
        projects.update(project["id"], {**project["contract"], "model": entry["id"], "reasoning_effort": effort})
        selected = projects.prepare(project["id"])
        mission = missions.launch(selected["id"])
        bundle, launch = freeze_bundle(store, mission, settings)
        root = tmp_path / ("forest-app-" + mission["id"])
        extract_verified(bundle, root)
        config = prepare_project(root, launch)
        config["codex"]["mailbox_dir"] = str(root / "mailbox")
        channel = root / "mailbox"
        initialize_channel(channel, launch["session_id"], "test", model=entry["id"], effort=effort)
        check_channel(channel, launch["session_id"], model=entry["id"], effort=effort)
        with pytest.raises(InfrastructureError):
            check_channel(channel, launch["session_id"], model="gpt-6-luna", effort="ultra")
        task = Mission("m", "t", "q", 1, "A", "base", None, "R/A", 1, 1, str(root / "source"))
        request = make_request(task, {"deadline": time.time() + 300}, config)
        validate_request(request, launch["session_id"], request["nonce"], model=entry["id"], effort=effort)
        envelope = response_envelope(request, "a" * 64)
        assert envelope["model"] == entry["id"] and envelope["reasoning_effort"] == effort
        monkeypatch.setattr(shutil, "which", lambda _: "codex")
        argv = command_for(request, root / "generation")
        assert argv[argv.index("--model") + 1] == entry["id"]
        assert f'model_reasoning_effort="{effort}"' in argv
        with pytest.raises(InfrastructureError):
            validate_request({**request, "reasoning_effort": "wrong"}, launch["session_id"], request["nonce"],
                             model=entry["id"], effort=effort)


class Connector:
    def __init__(self, fail_submit=False):
        self.calls = []
        self.fail_submit = fail_submit
        self.listing = []

    async def upload(self, local, remote):
        assert local.is_file() and remote.endswith(".zip")

    async def call(self, name, /, **kwargs):
        self.calls.append(name)
        if name == "job_prepare":
            return {"ok": True, "plan_id": "p", "submittable": True,
                    "script": "#SBATCH --job-name=" + kwargs["name"] + "\n" + kwargs["command"],
                    "resolved": {"arch": kwargs["arch"], "workdir": kwargs["workdir"],
                                 "total_cpus": 2, "total_gpus": 0, "time": "00:40:00", "mem_gb": 8}}
        if name == "job_submit":
            if self.fail_submit:
                raise TimeoutError("Unknown outcome")
            return {"ok": True, "job_id": "123"}
        if name == "list_jobs":
            return {"ok": True, "submitted_via_mcp": self.listing}
        raise AssertionError(name)


def test_double_click_and_restart_never_submit_twice(application):
    store, settings, _, prepared, missions = application
    record = missions.launch(prepared["id"])
    assert missions.launch(prepared["id"])["id"] == record["id"]
    client = Connector(fail_submit=True)
    with pytest.raises(TimeoutError):
        asyncio.run(missions.start(client, record, settings))
    assert missions.get(record["id"])["state"] == "submitting"
    restarted = Missions(Store(store.root), Campaigns(Store(store.root)))
    asyncio.run(restarted.reconcile(client, restarted.get(record["id"])))
    assert restarted.get(record["id"])["state"] == "submitting"
    client.listing = [{"name": "fa-" + record["id"][:20], "job_id": 123}]
    asyncio.run(restarted.reconcile(client, restarted.get(record["id"])))
    assert restarted.get(record["id"])["job_id"] == "123"
    assert client.calls.count("job_submit") == 1
    assert restarted.launch(prepared["id"])["id"] == record["id"]


def test_launch_authorization_binds_model_session_digest_and_expiry(application, tmp_path):
    store, settings, _, prepared, missions = application
    mission = missions.launch(prepared["id"])
    bundle, launch = freeze_bundle(store, mission, settings)
    root = tmp_path / ("forest-app-" + mission["id"])
    extract_verified(bundle, root)
    gate = {"mission_id": mission["id"], "session_id": launch["session_id"],
            "next_model": launch["model"], "reasoning_effort": launch["effort"],
            "expires_at": time.time() + 60, "manifest_sha256": file_digest(root / "launch.json")}
    path = root / "authorization.json"
    validate_authorization(path, gate, {mission["id"]})
    for changes in ({"expires_at": 1}, {"next_model": "gpt-6-astra"}, {"session_id": "a" * 32}):
        with pytest.raises(InfrastructureError):
            validate_authorization(path, {**gate, **changes}, {mission["id"]})


@pytest.mark.parametrize("command", ["/usr/bin/program", "../program", "python3 script.py", ""])
def test_benchmark_requires_a_project_executable(command):
    with pytest.raises(AppError):
        executable({"benchmark_command": command})


def test_source_scope_and_remote_archive_paths_are_checked(tmp_path):
    with pytest.raises(AppError):
        editable_files({"contract": {"editable_paths": ["tests"]}, "files": [{"path": "tests/test.cpp"}]})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../outside", "bad")
    archive = tmp_path / "view.zip"
    archive.write_bytes(buffer.getvalue())
    with pytest.raises(AppError):
        extract_verified(archive, tmp_path / "view")


def test_failed_snapshot_download_does_not_claim_completion(application):
    _, _, _, prepared, missions = application
    mission = missions.launch(prepared["id"])
    mission = missions.update(mission["id"], job_id="123", state="running", remote_root="/scratch/mission")
    class Pending:
        async def call(self, name, **kwargs):
            if name == "job_status":
                return {"finished": True, "state": "COMPLETED"}
            return {"content": json.dumps({"job_id": "123", "state": "completed", "pipeline_complete": True})}

        async def download(self, *args):
            raise OSError("network")
    asyncio.run(missions.refresh(Pending(), mission))
    assert missions.get(mission["id"])["state"] == "collecting"
    assert missions.get(mission["id"])["sync_error"]


def test_mixed_pool_survives_freeze_mailbox_native_routing_and_restart(application, tmp_path, monkeypatch):
    from hpc_forest.codex_mailbox import publish_request, wait_response
    from hpc_forest.codex_worker import Worker
    from hpc_forest.model_policy import generator_pool, require_request_identity
    from hpc_forest.webapp.runner_support import SharedFiles

    store, settings, projects, old_prepared, missions = application
    project = store.get(old_prepared["project_id"])
    pool = [{"model": "gpt-6-luna", "reasoning_effort": "max"},
            {"model": "gpt-6.1-sol", "reasoning_effort": "high"},
            {"model": "gpt-6-astra", "reasoning_effort": "max"}]
    projects.update(project["id"], {**project["contract"], "model": "gpt-6-luna", "reasoning_effort": "max",
        "generator_pool": pool, "search": {"algorithm": "ab-mcts-a", "distribution": "beta"},
        "evolution": {"enabled": True}})
    prepared = projects.prepare(project["id"])
    mission = missions.launch(prepared["id"])
    bundle, launch = freeze_bundle(store, mission, settings)
    root = tmp_path / ("forest-app-" + mission["id"])
    extract_verified(bundle, root)
    config = prepare_project(root, launch)
    assert config["evolution"]["enabled"] and config["search"]["distribution"] == "beta"
    assert generator_pool(config["codex"]) == generator_pool({**pool[0], "generator_pool": pool})
    gate = {"schema": "forest-app-authorization-v1", "mission_id": launch["id"],
        "session_id": launch["session_id"], "next_model": launch["model"], "reasoning_effort": launch["effort"],
        "generator_pool": launch["generator_pool"], "expires_at": time.time() + 300,
        "manifest_sha256": file_digest(root / "launch.json")}
    receipt = root / "authorization.json"
    atomic_json(receipt, gate)
    validate_authorization(receipt, gate, {launch["id"]})
    with pytest.raises(InfrastructureError, match="pool"):
        validate_authorization(receipt, {**gate, "generator_pool": []}, {launch["id"]})
    channel = root / "campaign/mailbox"
    initialize_channel(channel, launch["session_id"], "test", generators=pool)
    remote_root = "/scratch/forest-app-" + launch["id"]

    class MappedFiles(SharedFiles):
        def owned(self, path):
            if str(path).startswith(remote_root + "/"):
                path = root / str(path)[len(remote_root) + 1:]
            return super().owned(path)

    worker_args = (MappedFiles(root), remote_root + "/campaign/mailbox", launch["session_id"], root / "worker", receipt, {launch["id"]})
    calls = []

    def native(request, sha, output, *_):
        require_request_identity(request, config["codex"])
        monkeypatch.setattr(shutil, "which", lambda _: "codex")
        argv = command_for(request, output)
        assert argv[argv.index("--model") + 1] == request["model"]
        assert "--ephemeral" in argv and "resume" not in argv
        calls.append(request["model"])
        return response_envelope(request, sha, data={"offline_fixture": True}, error=None,
            infrastructure_error=False, usage={"tokens": 0, "token_accounting": "exact", "llm_calls": 0})

    monkeypatch.setattr("hpc_forest.codex_worker.run_codex", native)
    worker = Worker(*worker_args, generators=pool, defer_diagnostics=True)
    for i, selected in enumerate(pool):
        task = Mission("m" + str(i), "e1:T1", "q", 1, "T1", "base", None, "R/T1", 1, i, str(root / "source"),
            generator=selected, search_action="T1|" + selected["model"] + "|" + selected["reasoning_effort"])
        request = make_request(task, {"deadline": time.time() + 60,
            "research_tree": {"role": "T1", "objective": "Offline routing fixture"}}, config)
        sha = publish_request(channel, request)
        assert asyncio.run(worker.handle(request["nonce"] + ".request.json"))
        assert wait_response(channel, request, sha)["model"] == selected["model"]
        worker = Worker(*worker_args, generators=pool, defer_diagnostics=True)
        assert not asyncio.run(worker.handle(request["nonce"] + ".request.json"))
    assert calls == [p["model"] for p in pool]


@pytest.mark.parametrize("field,value", [("generator_pool", []), ("search", {"algorithm": "sequential-refinement"}),
                                       ("evolution", {"enabled": False})])
def test_changed_frozen_search_contract_is_rejected(application, tmp_path, field, value):
    store, settings, projects, prepared, missions = application
    project = store.get(prepared["project_id"])
    primary = {"model": project["contract"]["model"], "reasoning_effort": project["contract"]["reasoning_effort"]}
    projects.update(project["id"], {**project["contract"], "generator_pool": [primary,
        {"model": "gpt-6-luna", "reasoning_effort": "max"}], "evolution": {"enabled": True}})
    prepared = projects.prepare(project["id"])
    mission = missions.launch(prepared["id"])
    bundle, launch = freeze_bundle(store, mission, settings)
    root = tmp_path / ("forest-app-" + mission["id"])
    extract_verified(bundle, root)
    with pytest.raises(InfrastructureError, match="Search policy or generator pool"):
        prepare_project(root, {**launch, field: value})


def test_optional_m_requires_an_explicit_remote_profile(application):
    store, settings, projects, prepared, missions = application
    project = store.get(prepared["project_id"])
    projects.update(project["id"], {**project["contract"], "search": {"algorithm": "ab-mcts-m"}})
    prepared = projects.prepare(project["id"])
    mission = missions.launch(prepared["id"])
    with pytest.raises(AppError, match="sakana-m"):
        freeze_bundle(store, mission, settings)
    settings["profiles"]["cpu"]["search_algorithms"] = ["ab-mcts-m"]
    _, manifest = freeze_bundle(store, mission, settings)
    assert manifest["search"]["algorithm"] == "ab-mcts-m"
