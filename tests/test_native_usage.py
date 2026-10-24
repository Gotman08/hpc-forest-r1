"""Regression from native ROMEO pilots: resumed usage was counted repeatedly."""
import json
import uuid

import pytest

from hpc_forest.codex_conversation import first_turn, next_turn, run_turn, workspace_for
from hpc_forest.native_usage import conversation_usage


def response(input_tokens, output_tokens):
    return {"usage":{"token_accounting":"exact","tokens":input_tokens+output_tokens,
                     "events":[{"input_tokens":input_tokens,"output_tokens":output_tokens}]}}


def test_native_observed_counters_charge_only_each_resumed_turn():
    # Numeric counters from two actual pilot calls; no prompt or model text.
    first = response(203698, 8019)
    saved = conversation_usage(first, None, 0)
    second = response(249876, 11395)
    next_saved = conversation_usage(second, {"usage_cumulative":saved}, 1)
    assert first["usage"]["tokens"] == 211717
    assert second["usage"]["tokens"] == 49554
    assert first["usage"]["tokens"]+second["usage"]["tokens"] == 261271
    assert second["usage"]["native_cumulative_events"][0]["input_tokens"] == 249876
    assert next_saved == {"input_tokens":249876,"output_tokens":11395}


@pytest.mark.parametrize("before,current", [
    (None,response(10,2)),
    ({"usage_cumulative":{"input_tokens":20,"output_tokens":2}},response(10,3)),
    ({"usage_cumulative":{"input_tokens":10,"output_tokens":2}},{"usage":{"events":[],"token_accounting":"unknown"}}),
])
def test_missing_or_reset_counters_remain_unknown(before,current):
    conversation_usage(current,before,1)
    assert current["usage"]["tokens"] is None
    assert current["usage"]["token_accounting"] == "unknown"


def test_counter_is_persisted_with_exact_native_chain_and_recovered_without_recharging(tmp_path):
    request = {"conversation":first_turn(),"session_id":"a"*32,"model":"gpt-6-luna","reasoning_effort":"max"}
    thread = str(uuid.uuid4())
    def invoke(output, input_tokens, output_tokens):
        output.mkdir(parents=True)
        (output/'codex.jsonl').write_text(json.dumps({"type":"thread.started","thread_id":thread}))
        return {"error":None,**response(input_tokens,output_tokens)}
    start = tmp_path/'first'
    result = run_turn(request,'1'*64,start,lambda:invoke(start,10,2))
    state_file = workspace_for(request,start).parent/'state.json'
    assert json.loads(state_file.read_text())["usage_cumulative"] == {"input_tokens":10,"output_tokens":2}
    request = {**request,"conversation":next_turn(result["conversation"],phase="steering")}
    end = tmp_path/'second'
    result = run_turn(request,'2'*64,end,lambda:invoke(end,30,5))
    assert result["usage"]["tokens"] == 23
    assert json.loads((end/'response.json').read_text())["usage"]["tokens"] == 23
