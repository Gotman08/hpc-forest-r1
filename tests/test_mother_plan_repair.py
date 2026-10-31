"""Rejected initial JSON may be corrected, never replayed or accepted as a plan."""
import json
import time

import pytest
from test_mother_conversation import first_turn, native_campaign, request_for

from hpc_forest import codex_process
from hpc_forest.codex_conversation import run_turn
from hpc_forest.core import InfrastructureError


@pytest.mark.parametrize("fault", [None, "transport", "forbidden_tool", "runtime", "failed_turn",
                                   "two_terminals", "unproven", "partial", "not_initial"])
def test_rejected_planning_receipt_requires_safe_completed_turn(tmp_path, fault):
    request = {**request_for(first_turn()), "meta_role": "mother-preparation"}
    if fault == "not_initial":
        request["meta_role"] = "mother-investigation"

    def invoke():
        terminal = {"type": "turn.completed", "usage": {"input_tokens": 2, "output_tokens": 1}}
        if fault == "failed_turn":
            terminal = {"type": "turn.failed"}
        events = [{"type": "thread.started", "thread_id": "00000000-0000-0000-0000-000000000010"}, terminal]
        if fault == "two_terminals":
            events.append(terminal)
        (tmp_path / "codex.jsonl").write_text("\n".join(json.dumps(v) for v in events))
        return {"error": "Invalid structured JSON", "data": {} if fault == "partial" else None,
                "infrastructure_error": fault == "transport",
                "rejection": None if fault == "unproven" else {"reason": "invalid_structured_output"},
                "usage": {"tokens": 3, "token_accounting": "exact",
                          "events": [{"input_tokens": 2, "output_tokens": 1}],
                          "forbidden_tool_events": ["shell"] if fault == "forbidden_tool" else [],
                          "tool_runtime_errors": ["Error"] if fault == "runtime" else []}}

    result = run_turn(request, "1" * 64, tmp_path, invoke)
    assert result["error"] and result["usage"]["tokens"] == 3
    assert ("conversation" in result) == (fault is None)
    assert ("recovery" in result) == (fault is None)
    with pytest.raises(InfrastructureError, match="already claimed"):
        run_turn(request, "1" * 64, tmp_path, lambda: pytest.fail("Never replay"))


@pytest.mark.parametrize("failed_repair", [False, True])
def test_initial_plan_correction_precedes_dispatch_and_preserves_native_chain(
    tmp_path, monkeypatch, need_compiler, failed_repair,
):
    root, controller, fixture = native_campaign(tmp_path, monkeypatch, 1, skills=True)
    fixture.expire_in_planning = False

    def process(argv, output, log, timeout, **kwargs):
        request = json.loads((output / "request.json").read_text())
        result = fixture.process(argv, output, log, timeout, **kwargs)
        if request.get("meta_role") == "mother-preparation" or (
                failed_repair and request.get("meta_role") == "mother-plan-repair"):
            (output / "agent-result.json").write_text('{"children": [')
        if request.get("meta_role") == "mother-plan-repair":
            assert "resume" in argv and "--ephemeral" not in argv and "--output-schema" in argv
            assert request["conversation"]["turn"] == 1 and request.get("diagnostics") is None
            assert not controller.db.get("forest_plan:1")
            invocation = json.loads((output / "invocation.json").read_text())
            assert not invocation["source_execution_allowed"]
        return result

    monkeypatch.setattr(codex_process, "run_process", process)
    with controller:
        if failed_repair:
            with pytest.raises(InfrastructureError, match="correction failed"):
                controller.run(max_batches=1)
            assert not controller.db.get("forest_plan:1")
            with pytest.raises(InfrastructureError):
                controller.run(max_batches=1)
            assert len(fixture.calls) == 2  # No loop and no fresh conversation.
        else:
            assert controller.run(max_batches=1)["status"] == "checkpointed"
            result = controller.db.get("mother_plan:preparation:1")
            assert result["repaired_initial_plan"] and result["model_calls"] == 2
            assert result["conversation"]["turn"] == 1
            first, repair = fixture.calls[:2]
            assert first["nonce"] != repair["nonce"] and first["schema"] == repair["schema"]
            assert repair["conversation"]["id"] == first["conversation"]["id"]
            original = json.loads((root / "logs" / first["mission_id"] / "result.json").read_text())
            assert original["status"] == "model_or_interface_failure"
            assert original["response"]["data"] is None
            correction = controller.db.get("mother_plan_repair:1")
            assert original["response"]["usage"]["tokens"] == correction["response"]["usage"]["tokens"] == 3
            controller.db.set("deadline", time.time() - 1)
            state = controller.run()
            assert state["postprocess"]["status"] == "complete"
            assert fixture.calls[-1]["conversation"]["thread_id"] == result["conversation"]["thread_id"]
            assert fixture.calls[-1]["conversation"]["turn"] == 2
            before = len(fixture.calls)
            controller.run()
            assert len(fixture.calls) == before
