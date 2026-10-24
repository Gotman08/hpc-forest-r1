import json
import time

import pytest

from hpc_forest.codex_process import check_dependencies, run_codex
from hpc_forest.core import InfrastructureError
from hpc_forest.model_policy import EFFORT, MODEL


def authorization():
    return {
        "schema": "hpc-forest-explicit-harness-comparison-v1",
        "status": "harness_comparison_explicitly_authorized",
        "scope_id": "gpt61sol-max-harness-20261015-r2",
        "next_model": MODEL, "reasoning_effort": EFFORT,
        "problems": ["knn", "sum", "nbody"], "arms": ["reference", "mixed-harness"],
        "harness_enabled": True, "max_calls_per_harness_mission": 3,
        "planned_slots_per_problem_per_arm": 24, "wall_seconds_per_problem_per_arm": 7200,
        "token_budget_per_problem_per_arm": 1500000, "deepseek_completion_claimed": False,
        "user_message": "Compare the new harness on the three problems without algorithm hints",
        "session_id": "c" * 32, "expires_at": time.time() + 60,
    }


def test_explicit_comparison_does_not_claim_deepseek_completion(tmp_path):
    gate = authorization()
    receipt = tmp_path / "authorization.json"
    receipt.write_text(json.dumps(gate))
    assert check_dependencies(receipt, {gate["scope_id"]}) == gate
    with pytest.raises(InfrastructureError):
        check_dependencies(receipt, {"747504", "747505"})


@pytest.mark.parametrize("field,value", [
    ("expires_at", 0), ("next_model", "other"), ("reasoning_effort", "high"),
    ("deepseek_completion_claimed", True), ("problems", ["knn"]),
    ("arms", ["mixed-harness"]), ("max_calls_per_harness_mission", 4),
    ("token_budget_per_problem_per_arm", 4000000),
])
def test_comparison_scope_cannot_be_changed(tmp_path, field, value):
    gate = authorization()
    gate[field] = value
    receipt = tmp_path / "authorization.json"
    receipt.write_text(json.dumps(gate))
    with pytest.raises(InfrastructureError):
        check_dependencies(receipt, {gate["scope_id"]})


def test_comparison_session_checked_before_native_model_invocation(tmp_path):
    gate = authorization()
    receipt = tmp_path / "authorization.json"
    receipt.write_text(json.dumps(gate))
    with pytest.raises(InfrastructureError, match="another explicitly authorized session"):
        run_codex({"session_id": "d" * 32}, "", tmp_path / "never-called", receipt,
                  {gate["scope_id"]})
    assert not (tmp_path / "never-called").exists()
