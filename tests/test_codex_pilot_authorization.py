import json
import time

import pytest

from hpc_forest.codex_process import check_dependencies, usage_from_events
from hpc_forest.core import InfrastructureError


def test_parallel_pilot_does_not_require_or_claim_deepseek_receipt(tmp_path):
    gate = {"schema": "hpc-forest-explicit-parallel-pilot-v1",
            "status": "parallel_pilot_explicitly_authorized",
            "scope_id": "gpt61sol-max-pilot-20261015-r1",
            "next_model": "gpt-6.1-sol", "reasoning_effort": "max",
            "deepseek_completion_claimed": False,
            "expires_at": time.time() + 60, "user_message": "Launch a pilot now"}
    receipt = tmp_path / "authorization.json"
    receipt.write_text(json.dumps(gate))
    assert check_dependencies(receipt, {gate["scope_id"]}) == gate
    with pytest.raises(InfrastructureError):
        check_dependencies(receipt, {"747504", "747505"})
    gate["expires_at"] = time.time() - 1
    receipt.write_text(json.dumps(gate))
    with pytest.raises(InfrastructureError):
        check_dependencies(receipt, {gate["scope_id"]})


def test_native_startup_error_items_are_not_model_tool_calls(tmp_path):
    log = tmp_path / "native.jsonl"
    events = [
        {"type": "item.completed", "item": {"type": "error", "message": "Startup warning"}},
        {"type": "turn.completed", "usage": {"input_tokens": 11, "output_tokens": 3}},
    ]
    log.write_text("\n".join(json.dumps(event) for event in events))
    usage, tools = usage_from_events(log)
    assert not tools and usage["tool_events"] == [] and usage["tokens"] == 14
    events.insert(1, {"type": "item.started", "item": {"type": "command_execution"}})
    log.write_text("\n".join(json.dumps(event) for event in events))
    assert usage_from_events(log)[1]
