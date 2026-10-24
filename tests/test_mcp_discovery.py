"""Native discovery must not abort a valid research trial or widen its tools."""
import json

import pytest

from hpc_forest.codex_process import usage_from_events


@pytest.mark.parametrize("tool", ["list_mcp_resources", "list_mcp_resource_templates"])
@pytest.mark.parametrize("romeo,documentation,arguments,allowed", [
    (False, True, {}, True),
    (True, False, {}, True),
    (False, False, {}, False),
    (False, True, {"server": "hpc_docs"}, True),
    (True, False, {"server": "romeo", "cursor": "next"}, True),
    (False, True, {"server": "romeo"}, False),
    (True, False, {"server": "hpc_docs"}, False),
    (True, True, {"server": "other"}, False),
    (False, True, {"server": ["hpc_docs"]}, False),
    (False, True, {"cursor": 42}, False),
    (False, True, {"uri": "file:///private"}, False),
    (False, True, None, False),
])
def test_discovery_is_limited_to_configured_servers(
    tmp_path, tool, romeo, documentation, arguments, allowed,
):
    log = tmp_path / "native.jsonl"
    item = {"id": "call", "type": "mcp_tool_call", "server": "codex",
            "tool": tool, "arguments": arguments}
    events = [{"type": "item.started", "item": {**item, "status": "in_progress"}},
              {"type": "item.completed", "item": {**item, "status": "completed"}},
              {"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 3}}]
    log.write_text("\n".join(json.dumps(event) for event in events))
    usage, forbidden = usage_from_events(log, allow_romeo_mcp=romeo,
                                        allow_documentation=documentation)
    assert forbidden is not allowed
    assert usage["mcp_tool_calls"] == [{"id": "call", "server": "codex", "tool": tool,
                                       "status": "completed", "allowed": allowed}]
    assert usage["tokens"] == 15


@pytest.mark.parametrize("kind,server,tool", [
    ("mcp_tool_call", "codex", "read_mcp_resource"),
    ("mcp_tool_call", "other", "list_mcp_resources"),
    ("mcp_tool_call", "codex", "exec_command"),
    ("command_execution", "codex", "list_mcp_resources"),
    ("file_change", "codex", "list_mcp_resource_templates"),
])
def test_discovery_permission_does_not_authorize_other_actions(tmp_path, kind, server, tool):
    log = tmp_path / "native.jsonl"
    log.write_text(json.dumps({"type": "item.completed", "item": {
        "type": kind, "server": server, "tool": tool, "arguments": {},
    }}))
    assert usage_from_events(log, allow_romeo_mcp=True, allow_documentation=True)[1]
