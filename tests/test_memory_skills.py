"""The selection turn must pass the same native skill checks as code turns."""
import copy
import json

import pytest

from hpc_forest.core import InfrastructureError
from hpc_forest.integration_policy import selection_messages
from hpc_forest.model_skills import policy, verify_binding


def selection_request():
    context = {"assembly_selection": {"round": 1}, "memory": {"enabled": True}}
    return {"meta_role": "mother-memory-selection",
            **selection_messages(context, {"skills": policy()})}


def test_selection_loads_assembly_skills_before_native_invocation():
    request = selection_request()
    manifest = verify_binding(request)
    assert manifest["role"] == "Mother"
    assert manifest["phase"] == "assembly"
    assert manifest["loaded"][0]["name"] == "integrer-optimisations"


@pytest.mark.parametrize("change", ["schema", "phase", "instructions"])
def test_selection_keeps_native_skill_integrity_checks(change):
    request = copy.deepcopy(selection_request())
    if change == "instructions":
        request["messages"][0]["content"] = "Missing project instructions"
    else:
        payload = json.loads(request["messages"][1]["content"])
        if change == "schema":
            payload["required_schema"] = {}
        else:
            payload["phase"] = "preparation"
        request["messages"][1]["content"] = json.dumps(payload)
    with pytest.raises(InfrastructureError, match="Project skills loading"):
        verify_binding(request)
