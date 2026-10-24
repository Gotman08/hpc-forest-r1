"""Isolation, bounded access, failures and replay protection of offline analysts."""
import copy
import json
import sqlite3

import pytest

from hpc_forest import codex_process, observer_snapshot
from hpc_forest.cli import main
from hpc_forest.codex_mailbox import json_bytes, response_envelope, sha256
from hpc_forest.core import ForestError, InfrastructureError, atomic_json, digest, file_digest
from hpc_forest.model_policy import EFFORT, MODEL
from hpc_forest.observer_contract import (
    CHUNK_SIZE,
    empty_read,
    request_for,
    validate_request,
    validate_response,
)
from hpc_forest.registry import SCHEMA
from hpc_forest.tree_observer import run, view


def fixture_campaign(tmp_path, monkeypatch):
    root = tmp_path / "campaign"
    root.mkdir()
    db = sqlite3.connect(root / "registry.sqlite3")
    db.executescript(SCHEMA)
    metadata = {"config": {"backend": "codex", "codex": {"model": MODEL, "reasoning_effort": EFFORT},
                            "forest": {"policy": "mother"}, "protocol": {"repetitions": 3}},
                "current_epoch": 1, "status": "confirmed", "protocol_id": "target-protocol",
                "confirmation_finished:1": 123, "best_confirmed": {"epoch": 1, "commit": "winner"},
                "postprocess:1": {"status": "complete"}, "final_g_confirmation:1": {"status": "confirmed"},
                "forest_plan:1": {"status": "complete", "children": [
                    {"role": role, "objective": "Explore " + role} for role in ("T1", "T2")]}}
    db.executemany("INSERT INTO metadata VALUES(?,?)", ((k, json.dumps(v)) for k, v in metadata.items()))
    baseline = {"status": "ok", "correct": True, "commit": "base", "mean_seconds": 2, "score": 0.0}
    db.execute("INSERT INTO evaluations(experiment_id,epoch,phase,payload,created) VALUES(?,1,?,?,1)",
               ("baseline-e1", "search", json.dumps(baseline)))
    for role in ("T1", "T2"):
        db.execute("INSERT INTO trees VALUES(?,1,?,?,?,?,0)", (role, role, b"opaque checkpoint", role, "test"))
        outcome = {"status": "ok", "correct": True, "commit": role, "mean_seconds": 3, "score": -0.5}
        mission = {"id": role + "-trial", "parent_id": "baseline-e1", "delegation_parent": "mother"}
        db.execute("INSERT INTO trials VALUES(?,?,?,1,?,?,?,?,?,?,1)",
                   (role + "-trial", role, "1", role, "slot", json.dumps(mission), b"opaque before",
                    "completed", json.dumps(outcome)))
    db.commit()
    db.close()
    monkeypatch.setattr(observer_snapshot, "committed_source_snapshot", lambda repo, commit: {
        "src/main.c": f"/* {commit} */\n" + "int evidence;\n" * 1500})
    return root


def response(request, data, usage=None):
    return response_envelope(request, sha256(json_bytes(request)), data=data, error=None,
                             infrastructure_error=False, usage=usage or {"tokens": 9, "token_accounting": "exact"})


def report(evidence="baseline-e1"):
    return {"action": "report", "read": empty_read(),
            "observations": [{"claim": "The reference is measured", "evidence_ids": [evidence]}],
            "hypotheses": [{"claim": "A slower idea may be useful", "evidence_ids": [evidence],
                            "proposed_test": "Measure an isolated variant", "stop_condition": "No measured gain"}],
            "uncertainties": ["No claim of future speedup"]}


def read(operation, evidence_id="", path="", offset=0):
    return {"action": "read", "read": {"operation": operation, "evidence_id": evidence_id,
                                          "path": path, "offset": offset},
            "observations": [], "hypotheses": [], "uncertainties": []}


def test_read_only_snapshot_one_fresh_analyst_per_tree_and_idempotent_run(tmp_path, monkeypatch):
    root = fixture_campaign(tmp_path, monkeypatch)
    before = file_digest(root / "registry.sqlite3")
    output = tmp_path / "observations"
    observer_snapshot.prepare(root, output, max_calls=3)
    calls = []
    def invoke(request, directory):
        payload = json.loads(request["messages"][1]["content"])
        calls.append(request)
        assert request["model"] == MODEL and request["reasoning_effort"] == EFFORT
        assert request["budget_phase"] == "observation" and "conversation" not in request
        other = "T2-trial" if request["tree_id"] == "T1" else "T1-trial"
        assert other not in request["messages"][1]["content"]
        if payload["call_number"] == 1:
            assert len(payload["history"]) == 1  # Empty model history for every tree.
            return response(request, read("source", "baseline-e1", "src/main.c"))
        assert len(payload["history"][-1]["view"]["text"]) == CHUNK_SIZE
        assert payload["history"][-1]["view"]["next_offset"] == CHUNK_SIZE
        return response(request, report(request["tree_id"] + "-trial"))
    monkeypatch.setattr(codex_process, "run_observer", invoke)
    result = run(output)
    assert result["complete"] and len(calls) == 4 and len(result["trees"]) == 2
    assert result["usage"]["total_tokens"] == 36
    assert file_digest(root / "registry.sqlite3") == before
    assert run(output) == result and len(calls) == 4
    assert (output / "REPORT.md").is_file()


@pytest.mark.parametrize("key,value", [("status", "checkpointed"), ("confirmation_finished:1", None),
                                       ("postprocess:1", {"status": "failed"}),
                                       ("final_g_confirmation:1", {"status": "unavailable"})])
def test_cannot_observe_before_complete_confirmation(tmp_path, monkeypatch, key, value):
    root = fixture_campaign(tmp_path, monkeypatch)
    with sqlite3.connect(root / "registry.sqlite3") as db:
        db.execute("UPDATE metadata SET value=? WHERE key=?", (json.dumps(value), key))
    with pytest.raises(ForestError, match="completed Mother"):
        observer_snapshot.prepare(root, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_pending_trial_and_in_campaign_output_rejected(tmp_path, monkeypatch):
    root = fixture_campaign(tmp_path, monkeypatch)
    with pytest.raises(ForestError, match="outside"):
        observer_snapshot.prepare(root, root / "observers")
    with sqlite3.connect(root / "registry.sqlite3") as db:
        db.execute("UPDATE trials SET state='pending' WHERE role='T1'")
    with pytest.raises(ForestError, match="pending"):
        observer_snapshot.prepare(root, tmp_path / "output")


def test_cross_tree_claim_fails_without_stopping_other_analyst(tmp_path, monkeypatch):
    root = fixture_campaign(tmp_path, monkeypatch)
    output = tmp_path / "observations"
    observer_snapshot.prepare(root, output)
    def invoke(request, directory):
        return response(request, report("T2-trial" if request["tree_id"] == "T1" else "baseline-e1"))
    monkeypatch.setattr(codex_process, "run_observer", invoke)
    result = run(output)
    assert [s["status"] for s in result["trees"]] == ["failed", "complete"]
    assert not result["complete"] and result["usage"]["total_tokens"] == 18


def test_call_budget_and_unknown_interruption_never_replay(tmp_path, monkeypatch):
    root = fixture_campaign(tmp_path, monkeypatch)
    output = tmp_path / "observations"
    observer_snapshot.prepare(root, output, max_calls=1)
    calls = []
    def interrupted(request, directory):
        calls.append(request)
        raise KeyboardInterrupt
    monkeypatch.setattr(codex_process, "run_observer", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run(output)
    def later(request, directory):
        calls.append(request)
        return response(request, read("evidence", "baseline-e1"))
    monkeypatch.setattr(codex_process, "run_observer", later)
    result = run(output)
    assert len(calls) == 2 and [c["tree_id"] for c in calls] == ["T1", "T2"]
    assert [s["status"] for s in result["trees"]] == ["interrupted_unknown", "failed"]
    assert result["usage"]["total_tokens"] is None and result["usage"]["unknown_usage_calls"] == 1
    assert run(output) == result and len(calls) == 2


def test_changed_snapshot_and_spoofed_response_rejected(tmp_path, monkeypatch):
    root = fixture_campaign(tmp_path, monkeypatch)
    output = tmp_path / "observations"
    observer_snapshot.prepare(root, output)
    path = output / "tree-001" / "snapshot.json"
    original = path.read_bytes()
    data = json.loads(original)
    data["records"][0]["outcome"]["score"] = 999
    atomic_json(path, data)
    with pytest.raises(ForestError, match="evidence changed"):
        run(output)
    path.write_bytes(original)
    def spoof(request, directory):
        return {**response(request, report()), "nonce": "forged"}
    monkeypatch.setattr(codex_process, "run_observer", spoof)
    result = run(output)
    assert all(s["status"] == "failed" for s in result["trees"])
    assert result["usage"]["unknown_usage_calls"] == 2


@pytest.mark.parametrize("bad", [
    {**report(), "score": 99}, {**report(), "action": "execute"},
    {**report(), "observations": [{"claim": "invented", "evidence_ids": ["missing"]}]},
    read("source", "baseline-e1", "../../secret"),
])
def test_invalid_or_escaping_model_output_never_executes(bad):
    dossier = {"records": [{"id": "baseline-e1", "source_files": {"src/a.c": "code"}}]}
    with pytest.raises(InfrastructureError):
        data = validate_response(bad, {"baseline-e1"})
        view(dossier, data["read"])


def test_native_observer_rejects_search_requests_and_tools(tmp_path, monkeypatch):
    from types import SimpleNamespace

    request = request_for("a" * 32, "T1", {"data": "untrusted"})
    original = copy.deepcopy(request)
    request["budget_phase"] = "search"
    with pytest.raises(InfrastructureError, match="observation-only"):
        codex_process.run_observer(request, tmp_path)
    request = original
    monkeypatch.setattr(codex_process, "shutil", SimpleNamespace(which=lambda _: "codex.exe"))
    def process(argv, output, log, timeout, **kwargs):
        assert "--ephemeral" in argv and "--ignore-user-config" in argv
        assert argv[argv.index("--model") + 1] == MODEL
        assert 'model_reasoning_effort="max"' in argv
        assert "features.memories=false" in argv and "features.shell_tool=false" in argv
        assert "features.multi_agent=false" in argv and "features.code_mode_host=false" in argv
        assert not any("mcp_servers" in arg for arg in argv)
        atomic_json(output / "agent-result.json", report())
        log.write_text(json.dumps({"type": "item.completed", "item": {"type": "command_execution"}}))
        return SimpleNamespace(returncode=0, timed_out=False, log=str(log))
    monkeypatch.setattr(codex_process, "run_process", process)
    result = codex_process.run_observer(request, tmp_path)
    assert result["infrastructure_error"] and result["data"] is None


def test_final_call_uses_report_only_native_schema():
    request = request_for("a" * 32, "T1", {"must_report": True})
    validate_request(request)
    properties = request["schema"]["properties"]
    assert properties["action"]["enum"] == ["report"]
    assert properties["read"]["properties"]["operation"]["enum"] == ["none"]
    request["schema"]["properties"]["action"]["enum"].append("read")
    with pytest.raises(InfrastructureError, match="observation-only"):
        validate_request(request)


def test_transient_reader_lock_does_not_reissue_model_call(tmp_path, monkeypatch):
    from hpc_forest import observer_io

    root = fixture_campaign(tmp_path, monkeypatch)
    output = tmp_path / "observations"
    observer_snapshot.prepare(root, output, max_calls=1)
    calls, locks = [], []
    original = observer_io.atomic_json
    def persist(path, value):
        if path.name == "state.json" and value.get("status") == "complete" and len(locks) < 2:
            locks.append(path)
            raise PermissionError("Transient Windows reader")
        original(path, value)
    monkeypatch.setattr(observer_io, "atomic_json", persist)
    monkeypatch.setattr(observer_io.time, "sleep", lambda seconds: None)
    def invoke(request, directory):
        calls.append(request["nonce"])
        return response(request, report())
    monkeypatch.setattr(codex_process, "run_observer", invoke)
    result = run(output)
    assert result["complete"] and len(calls) == 2 and len(locks) == 2
    assert run(output) == result and len(calls) == 2


def test_cli_preparation_does_not_call_model(tmp_path, monkeypatch, capsys):
    root = fixture_campaign(tmp_path, monkeypatch)
    def forbidden(*args):
        pytest.fail("prepare-only must never invoke a model")
    monkeypatch.setattr(codex_process, "run_observer", forbidden)
    output = tmp_path / "observations"
    assert main(["observe", str(root), str(output)]) == 0
    assert str(output / "manifest.json") == json.loads(capsys.readouterr().out)["manifest"]


def test_real_search_confirmation_frozen_before_observation(tmp_path, monkeypatch, need_compiler):
    from test_memory_integration import campaign

    root, controller, fixture = campaign(tmp_path, monkeypatch)
    with controller:
        state = controller.run()
        assert state["postprocess"]["status"] == "complete"
        winner = controller.confirm()
        model_calls = copy.deepcopy(fixture.calls)
        tables = ("metadata", "trees", "slots", "trials", "evaluations", "events", "memory_facts")
        def persisted():
            return {table: controller.db.rows(f"SELECT * FROM {table} ORDER BY rowid") for table in tables}
        before = persisted()
        output = tmp_path / "observations"
        observer_snapshot.prepare(root, output, max_calls=1)
        def observe(request, directory):
            return response(request, report())
        monkeypatch.setattr(codex_process, "run_observer", observe)
        result = run(output)
        assert result["complete"] and len(result["trees"]) == 2
        assert persisted() == before and fixture.calls == model_calls
        assert controller.db.get("best_confirmed") == winner
        snapshots = [json.loads(p.read_text()) for p in output.glob("tree-*/snapshot.json")]
        assert any(r["kind"] == "development" and r["outcome"]["correct"] is False
                   for d in snapshots for r in d["records"])
        for dossier in snapshots:
            assert all(r["source_digest"] == digest(r["source_files"]) for r in dossier["records"])
