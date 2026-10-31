"""Offline native-turn fixtures, actual AB-MCTS, C checks and independent confirmation."""
import copy
import json
import re
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_mother_forest import decomposition, settings

from hpc_forest import codex_mailbox as mailbox
from hpc_forest import codex_process
from hpc_forest.codex_conversation import first_turn, next_turn, run_turn, verify_receipt
from hpc_forest.codex_mailbox import CodexMailboxBackend
from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import BudgetExhausted, InfrastructureError, atomic_json, digest
from hpc_forest.mother import plan_for
from hpc_forest.reporting import package, report


def persistent_settings(tmp_path):
    config = settings(tmp_path)
    config["forest"]["conversation"] = "persistent"
    config["schedule"].update(trials_per_role_per_cycle=1, integrations_per_cycle=0)
    return config


def receipt_for(request, sha, thread=None):
    turn = request["conversation"]
    return {**{key: turn[key] for key in ("id", "phase", "turn")},
            "request_sha256": sha, "thread_id": thread or turn["thread_id"] or str(uuid.uuid4())}


def request_for(turn):
    return {"conversation": turn, "session_id": "a" * 32,
            "model": mailbox.MODEL, "reasoning_effort": mailbox.EFFORT}


def complete_turn(request, sha, output, thread=None):
    output.mkdir(parents=True, exist_ok=True)
    thread = thread or request["conversation"]["thread_id"] or str(uuid.uuid4())
    def invoke():
        (output / "codex.jsonl").write_text(json.dumps({"type": "thread.started", "thread_id": thread}))
        return {"data": {"fixture": True}, "error": None}
    return run_turn(request, sha, output, invoke)


def test_native_turn_resumes_exact_uuid_and_chain_without_ephemeral_or_last(tmp_path, monkeypatch):
    monkeypatch.setattr(codex_process, "shutil", SimpleNamespace(which=lambda _: "codex.exe"))
    start = request_for(first_turn())
    start["messages"] = [{"role": "system", "content": "Planning turn."}, {"role": "user", "content": "Subject"}]
    start["schema"] = {"type": "object"}
    response = complete_turn(start, "1" * 64, tmp_path / "first")
    resume = {**start, "conversation": next_turn(response["conversation"])}
    first = codex_process.command_for(start, tmp_path / "first")
    second = codex_process.command_for(resume, tmp_path / "second")
    assert "--ephemeral" not in first + second and "--last" not in second
    assert "resume" not in first
    assert second[second.index("resume") + 1] == response["conversation"]["thread_id"]
    assert second.index("--output-schema") > second.index("resume")
    assert first[first.index("-C") + 1] == second[second.index("-C") + 1]
    assert "features.multi_agent=false" in second and "features.shell_tool=false" in second
    resumed = complete_turn(resume, "2" * 64, tmp_path / "second")
    assert verify_receipt(resume, "2" * 64, resumed)["thread_id"] == response["conversation"]["thread_id"]


@pytest.mark.parametrize("fault", ["missing", "different_session", "different_uuid", "previous_hash", "replay", "planning_again"])
def test_missing_or_mismatched_history_never_starts_a_fresh_mother(tmp_path, fault):
    start = request_for(first_turn())
    original = complete_turn(start, "1" * 64, tmp_path / "first")
    request = {**start, "conversation": next_turn(original["conversation"])}
    if fault == "missing":
        request["conversation"]["id"] = "f" * 32
    elif fault == "different_session":
        request["session_id"] = "b" * 32
    elif fault == "different_uuid":
        request["conversation"]["thread_id"] = str(uuid.uuid4())
    elif fault == "previous_hash":
        request["conversation"]["previous_request_sha256"] = "f" * 64
    elif fault == "replay":
        complete_turn(request, "2" * 64, tmp_path / "second")
    else:
        request = start
    with pytest.raises(InfrastructureError):
        run_turn(request, "3" * 64, tmp_path / "rejected", lambda: pytest.fail("Native call must be blocked"))


def test_interrupted_turn_is_not_replayed_and_wrong_native_thread_is_rejected(tmp_path):
    start = request_for(first_turn())
    original = complete_turn(start, "1" * 64, tmp_path / "first")
    resume = {**start, "conversation": next_turn(original["conversation"])}
    failed = complete_turn(resume, "2" * 64, tmp_path / "second", thread=str(uuid.uuid4()))
    assert failed["infrastructure_error"] and "receipt" in failed["error"]
    with pytest.raises(InfrastructureError, match="matching"):
        run_turn(resume, "2" * 64, tmp_path / "retry", lambda: pytest.fail("Never replay"))


class NativeFixture:
    def __init__(self, count):
        self.count, self.calls = count, []
        self.barrier = threading.Barrier(count, timeout=10)
        self.controller = None
        self.expire_in_planning = True
        self.invalid_assembly, self.repair_assembly = False, False
        self.assembly_calls, self.saved_header = 0, None
        self.romeo_mcp = None
        self.documentation_mcp = None
        self.repair_research = False

    def process(self, argv, output, log, timeout, **kwargs):
        # This replaces only hosted generation; compilation/measurement use the real process runner.
        schema = json.loads((output / "output-schema.json").read_text(encoding="utf8"))
        request = json.loads((output / "request.json").read_text(encoding="utf8"))
        self.calls.append(copy.deepcopy(request))
        turn = request.get("conversation")
        thread = (turn or {}).get("thread_id") or str(uuid.uuid4())
        if "children" in schema["properties"]:
            value = decomposition(self.count)
            if self.expire_in_planning:
                self.controller.db.set("deadline", time.time() - 1)
        else:
            payload, source_text = kwargs["stdin"].split("\n\nCURRENT SOURCE AS DATA:\n", 1)
            payload = json.loads(payload)
            if payload["role"] != "G":
                if payload["ordinal"] == 1 and not re.search(r"-h0[2-9]$", request["mission_id"]):
                    # Check concurrent initial admission, not artificial later waves.
                    self.barrier.wait()
                tile = int(payload["role"][1:]) * 8 + payload["ordinal"]
            else:
                assert turn["phase"] == "assembly" and "resume" in argv
                if payload["context_as_data"].get("integration_pair"):
                    assert 1 <= len(payload["context_as_data"]["sources"]) <= 2
                else:
                    assert len(payload["context_as_data"]["sources"]) >= self.count
                self.assembly_calls += 1
                tile = 70 + payload["ordinal"] if payload["context_as_data"].get("integration_pair") else 7
            content = source_text.split("--- BEGIN FILE src/params.h ---\n", 1)[1].split("\n--- END FILE src/params.h ---", 1)[0]
            if self.repair_research:
                content = content.replace("\nint offline_research_failure = ;\n", "\n")
            if payload["role"] == "G":
                if payload["context_as_data"].get("integration_pair"):
                    content = content.replace("\nint offline_compile_failure = ;\n", "\n")
                else:
                    self.saved_header = self.saved_header or content
                    content = self.saved_header
            content = re.sub(r"#define TILE \d+", f"#define TILE {tile}", content)
            content = content.replace("#define LAYOUT 0", "#define LAYOUT 1")
            if payload["role"] == "G":
                content = content.replace("#define SIMD 0", "#define SIMD 1")
            value = {"hypothesis": "Offline source assembly" if turn else "Offline research candidate",
                     "transformations": ["Offline fixture"], "sources_kept": payload["integration_source_ids"],
                     "files": [{"path": "src/params.h", "content": content}], "notes": "Offline fixture"}
            if payload["role"] == "G" and self.invalid_assembly:
                value = decomposition(self.count + 1)  # This must never become a dispatch request.
            elif payload["role"] == "G" and self.repair_assembly and self.assembly_calls == 1:
                value["files"][0]["content"] += "\nint offline_compile_failure = ;\n"
            elif payload["role"] == "T1" and self.repair_research and request["mission_id"].endswith("-h01"):
                value["files"][0]["content"] += "\nint offline_research_failure = ;\n"
        if request.get("model_skills"):
            value["skill_usage"] = [{"name": entry["name"], "status": "applied",
                                     "summary": "Offline fixture declaration, not hosted behavioral proof.",
                                     "references": []}
                                    for entry in request["model_skills"]["loaded"]]
        (output / "agent-result.json").write_text(json.dumps(value))
        events = [
            {"type": "thread.started", "thread_id": thread},
            {"type": "turn.completed", "usage": {"input_tokens": 2 * ((turn or {}).get("turn", 0) + 1),
                                                "output_tokens": (turn or {}).get("turn", 0) + 1}},
        ]
        if self.romeo_mcp is not None:
            assert "mcp_servers.romeo.enabled=true" in argv
            assert json.loads((output / "invocation.json").read_text())["model_mcp"] == self.romeo_mcp.receipt()
            events.insert(1, {"type": "item.completed", "item": {
                "id": "romeo-call", "type": "mcp_tool_call", "server": "romeo",
                "tool": "read_doc", "status": "completed"}})
        if self.documentation_mcp is not None:
            from hpc_forest.documentation_store import DocumentationStore

            assert "mcp_servers.hpc_docs.enabled=true" in argv
            assert json.loads((output / "invocation.json").read_text())["documentation_mcp"] == self.documentation_mcp.receipt()
            library = DocumentationStore(self.documentation_mcp.root, request["session_id"])
            library.audit(request["nonce"], "catalogue", library.catalogue())
            events.insert(1, {"type": "item.completed", "item": {
                "id": "documentation-call", "type": "mcp_tool_call", "server": "hpc_docs",
                "tool": "documentation_catalog", "status": "completed"}})
        log.write_text("\n".join(json.dumps(event) for event in events))
        return SimpleNamespace(returncode=0, timed_out=False, log=str(log))


def native_campaign(tmp_path, monkeypatch, count, *, harness=False, skills=False, pairwise=False):
    config = persistent_settings(tmp_path)
    if pairwise:
        config["forest"]["integration"] = "pairwise"
    if skills:
        from hpc_forest.model_skills import policy

        config["skills"] = policy()
    if harness:
        config["harness"].update(enabled=True, max_attempts=2, call_token_ceiling=None)
    mailbox.initialize_channel(Path(config["codex"]["mailbox_dir"]), config["codex"]["session_id"], "offline fixture")
    fixture = NativeFixture(count)
    monkeypatch.setattr(codex_process, "run_process", fixture.process)
    monkeypatch.setattr(codex_process, "shutil", SimpleNamespace(which=lambda _: "codex.exe"))
    monkeypatch.setattr(codex_process, "check_dependencies", lambda *args: {
        "completion": {"policy": "finish-started", "token_policy": "observe-only"}})
    def receive(channel, request, sha):
        output = tmp_path / "native-worker" / request["nonce"]
        return codex_process.run_codex(request, sha, output, tmp_path / "offline-gate", set(),
                                      romeo_mcp=fixture.romeo_mcp, documentation_mcp=fixture.documentation_mcp)
    monkeypatch.setattr(mailbox, "wait_response", receive)
    root = create_workspace(tmp_path / "campaign", config)
    fixture.controller = Controller(root)
    return root, fixture.controller, fixture


@pytest.mark.parametrize("count", [1, 5])
@pytest.mark.parametrize("with_mcp", [False, True])
def test_same_mother_assembles_g_after_timer_without_dispatch_then_confirmed(
    tmp_path, monkeypatch, need_compiler, count, with_mcp,
):
    root, controller, fixture = native_campaign(tmp_path, monkeypatch, count)
    if with_mcp:
        pytest.importorskip("mcp")
        pytest.importorskip("pypdf")
        from hpc_forest.documentation_mcp import DocumentationMCP
        from hpc_forest.model_mcp import RomeoMCP

        config = tmp_path / "codex.toml"
        config.write_text('[mcp_servers.romeo]\ncommand="offline-fixture"')
        fixture.romeo_mcp = RomeoMCP.bind(config)
        fixture.documentation_mcp = DocumentationMCP.bind(tmp_path / "references", "a" * 32)
    with controller:
        state = controller.run()
        assert state["postprocess"]["status"] == "complete"
        assert len(fixture.calls) == count + 2  # One planning turn, N research calls, one resumed assembly.
        first, final = fixture.calls[0], fixture.calls[-1]
        assert first["conversation"]["id"] == final["conversation"]["id"]
        original = state["forest_plan"]["conversation"]
        assert final["conversation"]["thread_id"] == original["thread_id"]
        assert state["mother_conversation"]["thread_id"] == original["thread_id"]
        assert final["conversation"]["previous_request_sha256"] == original["request_sha256"]
        assert final["meta_role"] == "mother-final-assembly"
        assert "children" not in final["schema"]["properties"] and "files" in final["schema"]["properties"]
        assert "restart" in final["messages"][0]["content"]
        assert final["expires_at"] is None and final["token_ceiling"] is None
        assert all("G" not in batch for batch in controller.plan())
        assert controller.db.one("SELECT count(*) AS n FROM trials WHERE role='G'")["n"] == 1
        assert controller.db.get("mother_plan:synthesis:1") is None
        assert controller.db.costs()["tokens_used"] == 3 * (count + 2)
        if with_mcp:
            from hpc_forest.documentation_store import DocumentationStore

            library = DocumentationStore(fixture.documentation_mcp.root, "a" * 32)
            with library.connection() as db:
                assert {row[0] for row in db.execute("SELECT request_id FROM accesses")} == {
                    call["nonce"] for call in fixture.calls}
        with pytest.raises(BudgetExhausted, match="assembling"):
            controller._new_mission("T1", controller.epoch())
        with pytest.raises(BudgetExhausted, match="closed"):
            controller.db.reserve_research_wave(state["research_roles"], 999)
        with pytest.raises(InfrastructureError, match="planning"):
            plan_for(controller, SimpleNamespace(epoch=1), {}, "synthesis")
        controller.confirm()
        assert controller.status()["final_g_confirmation"]["status"] == "confirmed"
        before = len(fixture.calls)
        controller.run()
        controller.confirm()
        assert len(fixture.calls) == before
    report(root)
    package(root, root / "submission.zip")
    payload = json.loads((root / "report/experiments.json").read_text())
    assert payload["mother_conversation"]["thread_id"] == original["thread_id"]


def test_checkpoint_keeps_original_conversation_until_assembly_and_no_g_research(tmp_path, monkeypatch, need_compiler):
    root, controller, fixture = native_campaign(tmp_path, monkeypatch, 2)
    fixture.expire_in_planning = False
    with controller:
        state = controller.run(max_batches=1)
        assert state["status"] == "checkpointed"
        original = state["mother_conversation"]
        # Subsequent native turns must progress independently of this one-off rendezvous.
        fixture.barrier.abort()
    with Controller(root) as controller:
        fixture.controller = controller
        state = controller.run(max_batches=2)
        assert state["status"] == "checkpointed" and state["completed_batches"] == 3
        assert state["mother_conversation"] == original
        assert len(fixture.calls) == 7 and all(call.get("meta_role") != "mother-final-assembly" for call in fixture.calls)
        controller.db.set("deadline", time.time() - 1)
        controller.run()
        assert fixture.calls[-1]["conversation"]["thread_id"] == original["thread_id"]
        assert controller.status()["postprocess"]["status"] == "complete"


def test_deleted_native_history_fails_without_launching_any_replacement(tmp_path, monkeypatch, need_compiler):
    _, controller, fixture = native_campaign(tmp_path, monkeypatch, 1)
    fixture.expire_in_planning = False
    with controller:
        controller.run(max_batches=1)
        original = controller.status()["mother_conversation"]
        path = tmp_path / "native-worker/conversations" / original["id"] / "state.json"
        saved = json.loads(path.read_text())
        atomic_json(path, {**saved, "status": "interrupted"})
        controller.db.set("deadline", time.time() - 1)
        state = controller.run()
        assert state["postprocess"]["status"] == "failed"
        assert len(fixture.calls) == 2  # No fresh Mother, G model or new research invocation.
        assert controller.status()["mother_conversation"] == original


def test_source_backend_cannot_dispatch_research_after_assembly(tmp_path, monkeypatch, need_compiler):
    _, controller, fixture = native_campaign(tmp_path, monkeypatch, 1)
    with controller:
        controller.run()
        row = controller.db.one("SELECT mission FROM trials WHERE role='T1'")
        from hpc_forest.core import Mission

        mission = Mission(**json.loads(row["mission"]))
        with pytest.raises(InfrastructureError, match="relaunch"):
            CodexMailboxBackend().generate(mission, {}, controller.config, controller.root)
        assert len(fixture.calls) == 3


def test_mother_cannot_replace_assembly_with_a_new_children_plan(tmp_path, monkeypatch, need_compiler):
    _, controller, fixture = native_campaign(tmp_path, monkeypatch, 1)
    fixture.invalid_assembly = True
    with controller:
        state = controller.run()
        assert state["postprocess"]["status"] == "failed"
        assert len(fixture.calls) == 3 and state["research_roles"] == ["T1"]
        assert not controller.db.one("SELECT id FROM trials WHERE role='T2'")
        controller.run()
        assert len(fixture.calls) == 3  # Neither replanning nor replacement calls on recovery.


def test_assembly_repair_resumes_next_turn_of_same_mother_without_relaunch(tmp_path, monkeypatch, need_compiler):
    _, controller, fixture = native_campaign(tmp_path, monkeypatch, 1, harness=True)
    fixture.repair_assembly = True
    with controller:
        state = controller.run()
        assert state["postprocess"]["status"] == "complete"
        assemblies = [call for call in fixture.calls if call.get("meta_role") == "mother-final-assembly"]
        assert len(assemblies) == 2
        assert [call["conversation"]["turn"] for call in assemblies] == [1, 2]
        assert assemblies[0]["conversation"]["thread_id"] == assemblies[1]["conversation"]["thread_id"]
        assert assemblies[1]["conversation"]["previous_request_sha256"] != assemblies[0]["conversation"]["previous_request_sha256"]
        assert len([call for call in fixture.calls if "conversation" not in call]) == 1
        controller.confirm()
        assert controller.status()["final_g_confirmation"]["status"] == "confirmed"


def test_rejected_assembly_json_keeps_native_chain_for_admitted_repair(tmp_path, monkeypatch, need_compiler):
    _, controller, fixture = native_campaign(tmp_path, monkeypatch, 1, harness=True)
    original_process = fixture.process
    rejected = []

    def process(argv, output, log, timeout, **kwargs):
        result = original_process(argv, output, log, timeout, **kwargs)
        request = json.loads((output / "request.json").read_text(encoding="utf-8"))
        if request.get("meta_role") == "mother-final-assembly" and not rejected:
            rejected.append(request)
            path = output / "agent-result.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["forbidden_extra_property"] = "must remain rejected"
            atomic_json(path, value)
        return result

    monkeypatch.setattr(codex_process, "run_process", process)
    with controller:
        state = controller.run()
        assert state["postprocess"]["status"] == "complete" and len(rejected) == 1
        calls = [r for r in fixture.calls if r.get("meta_role") == "mother-final-assembly"]
        assert len(calls) == 2
        assert [r["conversation"]["turn"] for r in calls] == [1, 2]
        assert len({r["nonce"] for r in calls}) == 2
        assert calls[0]["conversation"]["thread_id"] == calls[1]["conversation"]["thread_id"]
        assert state["costs"]["tokens_used"] == 12
        controller.confirm()
        assert controller.status()["final_g_confirmation"]["status"] == "confirmed"


@pytest.mark.parametrize("fault", ["transport", "unknown", "tool_error", "forbidden_tool", "failed_turn", "wrong_thread"])
def test_assembly_continuity_recovery_does_not_hide_other_failures(tmp_path, fault):
    start = request_for(first_turn())
    original = complete_turn(start, "1" * 64, tmp_path / "first")
    request = {**start, "conversation": next_turn(original["conversation"]),
               "meta_role": "mother-final-assembly"}
    output = tmp_path / "rejected"
    output.mkdir()
    response = {"data": None, "error": "Schema rejected", "infrastructure_error": False,
                "rejection": {"reason": "invalid_structured_output"}, "usage": {}}
    terminal = "turn.completed"
    thread = request["conversation"]["thread_id"]
    if fault == "transport":
        response["infrastructure_error"] = True
    elif fault == "unknown":
        response.pop("rejection")
    elif fault == "tool_error":
        response["usage"]["tool_runtime_errors"] = ["failure"]
    elif fault == "forbidden_tool":
        response["usage"]["forbidden_tool_events"] = ["exec"]
    elif fault == "failed_turn":
        terminal = "turn.failed"
    else:
        thread = str(uuid.uuid4())
    (output / "codex.jsonl").write_text("\n".join(map(json.dumps, [
        {"type": "thread.started", "thread_id": thread}, {"type": terminal}])), encoding="utf-8")
    result = run_turn(request, "2" * 64, output, lambda: response)
    assert result.get("conversation") is None and result.get("recovery") is None
    with pytest.raises(InfrastructureError, match="matching completed"):
        run_turn(request, "3" * 64, tmp_path / "retry", lambda: pytest.fail("Do not replay"))


def test_new_version_cannot_reinterpret_frozen_v5_forest_contract(monkeypatch):
    from test_depth_campaign import load_tool

    smoke = load_tool("native_smoke", monkeypatch)
    old = smoke.forest_contract(1800, persistent=False)
    new = smoke.forest_contract(1800, pairwise=False)
    assert smoke.LEGACY_FOREST_SCOPE.endswith("v5") and smoke.CONVERSATION_SCOPE.endswith("v6")
    assert old["forest"] == {"policy": "mother"} and old["mother_calls"] == 3
    assert new["forest"]["conversation"] == "persistent" and new["mother_calls"] == 2
    assert digest(old) != digest(new)
