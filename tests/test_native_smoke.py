import importlib.util
import json
import time
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from hpc_forest.core import InfrastructureError, Outcome, file_digest

spec = importlib.util.spec_from_file_location(
    "native_smoke", Path(__file__).resolve().parents[1] / "tools/native_smoke.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


@pytest.fixture
def receipt(tmp_path):
    session = "a" * 32
    root = "/scratch_p/nimarano/hpc-forest-r1-pilot-" + session
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"scope": smoke.SCOPE, "session_id": session,
        "model": smoke.MODEL, "effort": "max", "subject": "matmul",
        "child_missions": 4, "mother_calls": 2, "remote_root": root}))
    payload = tmp_path / "payload.tar.gz"
    payload.write_bytes(b"owned smoke payload")
    value = {"scope": smoke.SCOPE, "model": smoke.MODEL, "effort": "max",
        "expires_at": time.time() + 600, "historical_campaign_resumption": False,
        "session_id": session, "user_request": "One Luna MAX smoke, any subject",
        "channel": root + "/results-123/mailbox",
        "payload": {"path": str(payload), "sha256": file_digest(payload)},
        "plan": {"path": str(plan), "sha256": file_digest(plan)}}
    path = tmp_path / "authorization.json"
    path.write_text(json.dumps(value))
    return path, value


def test_accept_owned_single_smoke(receipt):
    path, value = receipt
    assert smoke.authorize(path, {smoke.SCOPE}) == value


@pytest.mark.parametrize("key,value", [
    ("scope", "historical-matrix"), ("model", "gpt-6-astra"), ("effort", "low"),
    ("expires_at", 0), ("historical_campaign_resumption", True), ("user_request", ""),
    ("session_id", "bad"), ("channel", "/scratch_p/nimarano/old/results-123/mailbox"),
])
def test_refuse_unrelated_authorization(receipt, key, value):
    path, original = receipt
    original[key] = value
    path.write_text(json.dumps(original))
    with pytest.raises(InfrastructureError):
        smoke.authorize(path, {smoke.SCOPE})


def test_refuse_changed_payload_and_wrong_required_scope(receipt):
    path, value = receipt
    with pytest.raises(InfrastructureError):
        smoke.authorize(path, {"old-campaign"})
    Path(value["payload"]["path"]).write_bytes(b"different")
    with pytest.raises(InfrastructureError):
        smoke.authorize(path, {smoke.SCOPE})


def test_manifest_refuses_escape_and_changed_source(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "main.py"
    source.write_text("print(1)")
    smoke.verify_files(project, {"main.py": file_digest(source)})
    with pytest.raises(InfrastructureError):
        smoke.verify_files(project, {"../project/main.py": "wrong"})


def test_remote_guard_accepts_an_alias_of_the_owned_root(tmp_path, monkeypatch):
    root = tmp_path / "smoke"
    (root / "alias-part").mkdir(parents=True)
    alias = root / "alias-part" / ".."
    (root / "plan.json").write_text(json.dumps({"remote_root": str(alias),
        "session_id": "a" * 32}))
    (root / "runtime-manifest.json").write_text("{}")
    monkeypatch.setenv("SLURM_JOB_ID", "123")
    monkeypatch.setenv("SLURM_CPUS_PER_TASK", "4")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    monkeypatch.setattr(smoke.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(smoke, "install_identity", lambda *args: None)

    def reached_channel(*args):
        raise RuntimeError("allocation guard passed without any model call")

    monkeypatch.setattr(smoke.codex_mailbox, "initialize_channel", reached_channel)
    with pytest.raises(RuntimeError, match="allocation guard passed"):
        smoke.run_remote(SimpleNamespace(root=root))


def test_confirmed_fallback_cannot_hide_an_infrastructure_failure():
    result = {"best_confirmed": {"experiment_id": "fallback"},
        "search": {"status": "search_complete"},
        "mother": {phase: {"status": "complete"} for phase in ("preparation", "synthesis")},
        "trials": [{"role": role, "result": json.dumps(asdict(Outcome("valid")))}
                   for role in "ABCG"]}
    assert smoke.smoke_complete(result)
    result["trials"][1]["result"] = json.dumps(asdict(Outcome("infrastructure_error")))
    assert not smoke.smoke_complete(result)


def test_official_authorization_requires_the_historical_subject_and_budget(receipt):
    path, value = receipt
    plan_path = Path(value["plan"]["path"])
    plan = json.loads(plan_path.read_text())
    root = "/scratch_p/nimarano/hpc-forest-r1-official-" + value["session_id"]
    plan.update(scope=smoke.OFFICIAL_SCOPE, subject="2023-count", child_missions=8,
                wall_seconds=1800, token_budget=1500000, seed=23, remote_root=root)
    plan_path.write_text(json.dumps(plan))
    value.update(scope=smoke.OFFICIAL_SCOPE, channel=root + "/results-123/mailbox")
    value["plan"]["sha256"] = file_digest(plan_path)
    path.write_text(json.dumps(value))
    assert smoke.authorize(path, {smoke.OFFICIAL_SCOPE})["scope"] == smoke.OFFICIAL_SCOPE
    plan["wall_seconds"] = 900
    plan_path.write_text(json.dumps(plan))
    value["plan"]["sha256"] = file_digest(plan_path)
    path.write_text(json.dumps(value))
    with pytest.raises(InfrastructureError, match="historical R1 budgets"):
        smoke.authorize(path, {smoke.OFFICIAL_SCOPE})
