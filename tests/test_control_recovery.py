"""Known terminal failures can continue; uncertain calls and real tools cannot."""
import copy
import json
import time

import pytest
from test_active_architecture import campaign, decision  # noqa: F401
from test_active_corrections import analyze, corrected, trial  # noqa: F401
from test_mother_conversation import complete_turn, receipt_for, request_for

from hpc_forest import active_control as controls
from hpc_forest import active_lifecycle as life
from hpc_forest import codex_mailbox as mailbox
from hpc_forest.active_state import state
from hpc_forest.codex_conversation import OUTPUT_LIMIT, first_turn, next_turn, run_turn
from hpc_forest.codex_process import usage_from_events
from hpc_forest.core import InfrastructureError


@pytest.mark.parametrize("mutation,allowed", [
    ({}, True), ({"receiver_thread_ids": ["actual-agent"]}, False),
    ({"receiver_thread_ids": None}, False), ({"agents_states": {"agent": "done"}}, False),
    ({"tool": "spawn_agent"}, False), ({"prompt": "do work"}, False),
    ({"arguments": {"command": "run"}}, False), ({"status": "unknown"}, False),
])
def test_only_exact_empty_native_wait_is_a_noop(tmp_path, mutation, allowed):
    item = {"id": "one", "type": "collab_tool_call", "tool": "wait",
            "receiver_thread_ids": [], "prompt": None, "agents_states": {}, "status": "completed"}
    item.update(mutation)
    path = tmp_path / "native.jsonl"
    path.write_text(json.dumps({"type": "item.completed", "item": item}))
    usage, forbidden = usage_from_events(path, observe_only=True, allow_empty_agent_wait=True)
    assert forbidden is not allowed
    assert bool(usage["native_noops"]) is allowed
    assert usage_from_events(path)[1]  # Still forbidden outside active Mother.


@pytest.mark.parametrize("fault", [None, "transport", "wrong_thread", "forged_text", "real_tool"])
def test_output_limit_advances_only_verified_terminal_native_turn(tmp_path, fault):
    start = request_for(first_turn())
    first = complete_turn(start, "1" * 64, tmp_path / "first")
    request = {**start, "conversation": next_turn(first["conversation"], phase="steering"),
               "active_control": {"kind": "mother"}}
    output = tmp_path / "second"
    output.mkdir()
    def invoke():
        thread = first["conversation"]["thread_id"]
        if fault == "wrong_thread":
            thread = "00000000-0000-0000-0000-000000000001"
        terminal = {"type": "turn.failed", "error": {"message": OUTPUT_LIMIT}}
        if fault == "forged_text":
            terminal = {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(terminal)}}
        (output / "codex.jsonl").write_text("\n".join(json.dumps(v) for v in [
            {"type": "thread.started", "thread_id": thread}, terminal]))
        return {"data": None, "error": "No complete proposal", "infrastructure_error": fault == "transport",
                "usage": {"tokens": None, "token_accounting": "unknown", "events": [],
                          "turn_failure_messages": [OUTPUT_LIMIT],
                          "forbidden_tool_events": ["command_execution"] if fault == "real_tool" else []}}
    result = run_turn(request, "2" * 64, output, invoke)
    assert result["data"] is None and result["usage"]["tokens"] is None
    if fault is None:
        assert result["recovery"]["reason"] == "model_output_limit"
        later = {**start, "conversation": next_turn(result["conversation"], phase="steering")}
        final = complete_turn(later, "3" * 64, tmp_path / "third")
        assert final["conversation"]["thread_id"] == first["conversation"]["thread_id"]
        assert final["conversation"]["turn"] == 2
    else:
        assert "conversation" not in result
    with pytest.raises(InfrastructureError, match="matching"):
        run_turn(request, "2" * 64, tmp_path / "replay", lambda: pytest.fail("Never replay"))


@pytest.mark.parametrize("reason", ["model_output_limit", "invalid_structured_output"])
def test_terminal_control_failure_is_billed_and_retried_within_same_allowance(campaign, reason):  # noqa: F811
    job = controls.create(campaign, 1, "mother")
    request, sha, _ = controls.begin_call(campaign, job)
    response = mailbox.response_envelope(request, sha, data=None, error="No complete proposal",
        infrastructure_error=False, conversation=receipt_for(request, sha),
        recovery={"reason": reason, "continuation": "same_native_thread"},
        usage={"tokens": None, "token_accounting": "unknown"})
    controls.finish_call(campaign, job, response, time.time())
    assert job["status"] == "ready" and job["calls"][0]["status"] == "failed"
    assert not campaign.db.get("active_mother_broken:1")
    assert campaign.db.costs()["unknown_usage_calls"] == 1
    second, sha2, _ = controls.begin_call(campaign, job)
    assert second["nonce"] != request["nonce"]
    assert second["conversation"]["thread_id"] == response["conversation"]["thread_id"]
    assert second["conversation"]["turn"] == request["conversation"]["turn"] + 1
    assert second["conversation"]["previous_request_sha256"] == sha
    assert json.loads(second["messages"][1]["content"])["must_finish"]
    result = mailbox.response_envelope(second, sha2, data=decision(controls.snapshot(campaign, job)),
        conversation=receipt_for(second, sha2), usage={"tokens": 9, "token_accounting": "exact"})
    controls.finish_call(campaign, job, result, time.time())
    assert job["status"] == "complete" and len(job["calls"]) == job["maximum"]


@pytest.mark.parametrize("fault", [None, "transport", "wrong_thread", "forged_text", "forbidden_tool",
                                  "runtime_error", "not_rejected", "failed_turn", "multiple_terminals",
                                  "partial_data", "assembly", "analyst"])
def test_rejected_json_keeps_only_a_verified_completed_steering_turn(tmp_path, fault):
    start = request_for(first_turn())
    initial = tmp_path / "first"
    initial.mkdir()
    thread = "00000000-0000-0000-0000-000000000010"

    def plan():
        usage = {"input_tokens": 2, "output_tokens": 1}
        (initial / "codex.jsonl").write_text("\n".join(json.dumps(v) for v in [
            {"type": "thread.started", "thread_id": thread}, {"type": "turn.completed", "usage": usage}]))
        return {"data": {"fixture": True}, "error": None,
                "usage": {"tokens": 3, "token_accounting": "exact", "events": [usage]}}

    first = run_turn(start, "1" * 64, initial, plan)
    request = {**start, "conversation": next_turn(first["conversation"], phase="steering"),
               "active_control": {"kind": "mother"}}
    if fault == "assembly":
        request["conversation"]["phase"] = "assembly"
    if fault == "analyst":
        request["active_control"]["kind"] = "analyst"
    output = tmp_path / "second"
    output.mkdir()

    def invoke():
        thread = first["conversation"]["thread_id"]
        if fault == "wrong_thread":
            thread = "00000000-0000-0000-0000-000000000001"
        terminal = {"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 3}}
        if fault == "forged_text":
            terminal = {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(terminal)}}
        if fault == "failed_turn":
            terminal = {"type": "turn.failed", "error": {"message": "Connection interrupted"}}
        events = [{"type": "thread.started", "thread_id": thread}, terminal]
        if fault == "multiple_terminals":
            events.append(terminal)
        (output / "codex.jsonl").write_text("\n".join(json.dumps(v) for v in events))
        return {"data": {"partial": True} if fault == "partial_data" else None,
                "error": "Response violates the requested JSON schema",
                "infrastructure_error": fault == "transport",
                "rejection": None if fault == "not_rejected" else {"reason": "invalid_structured_output"},
                "usage": {"tokens": 10, "token_accounting": "exact",
                          "events": [{"input_tokens": 7, "output_tokens": 3}],
                          "forbidden_tool_events": ["command_execution"] if fault == "forbidden_tool" else [],
                          "tool_runtime_errors": ["Runtime unavailable"] if fault == "runtime_error" else []}}

    result = run_turn(request, "2" * 64, output, invoke)
    assert result["error"] and result["usage"]["tokens"] == 7  # Only this turn, never cumulative usage twice.
    if fault is None:
        assert result["data"] is None
        assert result["recovery"] == {"reason": "invalid_structured_output", "continuation": "same_native_thread"}
        later = {**start, "conversation": next_turn(result["conversation"], phase="steering")}
        final = complete_turn(later, "3" * 64, tmp_path / "third")
        assert final["conversation"]["thread_id"] == first["conversation"]["thread_id"]
        assert final["conversation"]["turn"] == 2
    else:
        assert "conversation" not in result and "recovery" not in result
    with pytest.raises(InfrastructureError, match="matching"):
        run_turn(request, "2" * 64, tmp_path / "replay", lambda: pytest.fail("Never replay"))


def test_idle_review_cannot_abandon_protected_trials_or_loop_without_evidence(corrected):  # noqa: F811
    for role in ("T1", "T2"):
        node = trial(corrected, role)
        life.observe(corrected.db, 1, node.id)
        analyze(corrected, role)
    before = copy.deepcopy(state(corrected.db, 1)["lifecycle"]["protections"])
    assert life.idle_review(corrected.db, 1)
    assert life.resume_after_idle_review(corrected.db, 1, ["T1", "T2"])
    current = state(corrected.db, 1)
    assert not current["closed"] and current["lifecycle"]["closing"] is None
    assert current["lifecycle"]["protections"] == before
    assert current["lifecycle"]["closure_history"][-1]["resumed_roles"] == ["T1", "T2"]
    assert not life.idle_review(corrected.db, 1)  # No unbounded model-only loop.
    assert not life.resume_after_idle_review(corrected.db, 1, ["T1", "T2"])


def test_idle_recovery_respects_final_reserve_and_exhausted_trees(corrected):  # noqa: F811
    assert life.idle_review(corrected.db, 1)
    corrected.db.set("active_unavailable:1", {"T1": "exhausted", "T2": "checkpoint_limit"})
    assert not life.resume_after_idle_review(corrected.db, 1, ["T1", "T2"])
    corrected.db.set("active_unavailable:1", {})
    corrected.db.set("deadline", time.time() + 1)
    assert not life.resume_after_idle_review(corrected.db, 1, ["T1", "T2"])
