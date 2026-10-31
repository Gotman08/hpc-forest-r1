"""Admission regressions: real campaign latencies, no new GPU/model measurements."""
import copy
from types import SimpleNamespace

import pytest
from test_independent_budget import independent

from hpc_forest.adaptive_budget import forecast, record_timing
from hpc_forest.config import validate
from hpc_forest.core import ForestError
from hpc_forest.independent_budget import assembly_admission
from hpc_forest.integration_policy import integrate_memory, limits
from hpc_forest.memory.contract import POLICY


def memory_budget(db, width=3):
    independent(db, count=width)
    config = db.get("config")
    config["forest"]["integration"] = POLICY
    config["memory"] = {"mode": "active", "assembly_rounds": 2, "selection_calls": 4,
                        "reads_per_mission": 3, "page_size": 6}
    config["harness"].update(enabled=True, max_attempts=3)
    config["protocol"].update(repetitions=3, confirmation_repetitions=5, warmups=0)
    db.set("config", config)
    # Latencies observed at the premature closure of campaign 775521.
    record_timing(db, "evaluation_work:baseline", 12.7024803999811)
    record_timing(db, "confirmation", 70.11555720710507)
    for role, work in [("T1", 66.44755481090397), ("T2", 85.04441367369145),
                       ("T3", 252.3052283404395)]:
        record_timing(db, "generation:" + role, work - 11.4872054895386)
        record_timing(db, "evaluation_work:" + role, 11.4872054895386)
    db.set("started", 1000)
    db.set("deadline", 2800)
    return config


@pytest.mark.parametrize("role", ["T1", "T2", "T3"])
def test_recorded_30_minute_campaign_can_continue_after_its_first_nodes(db, role):
    memory_budget(db)
    decision = forecast(db, [role], now=1403.954247713089)
    assert decision["can_admit"]  # Old reserve: 3132.61 s with only 1396.05 s left.
    assert decision["reserve_seconds"] < 600
    assert decision["final_g_seconds"] == pytest.approx(120 + 11.4872054895386)


@pytest.mark.parametrize("width", [2, 3, 5, 7, 20, 56, 500, 600])
def test_pagination_capacity_does_not_consume_the_research_budget_up_front(db, width):
    config = memory_budget(db, width)
    decision = forecast(db, ["T1"], now=1404)
    assert decision["can_admit"]
    assert decision["selection_calls_per_round"] == 2
    assert decision["selection_call_limit"] == limits(config, width)["selection_calls_per_round"]
    # A larger authorization for conditional reads/repairs is not extra nominal work.
    config["memory"].update(selection_calls=20, reads_per_mission=12, assembly_rounds=16)
    config["harness"]["max_attempts"] = 8
    db.set("config", config)
    assert forecast(db, ["T1"], now=1404)["reserve_seconds"] == decision["reserve_seconds"]


def test_nominal_rounds_are_distinct_from_the_conditional_assembly_limit(db):
    config = memory_budget(db)
    config["memory"]["assembly_rounds"] = 16
    config["completion"]["initial_integration_rounds"] = 3
    db.set("config", config)
    decision = forecast(db, now=1404)
    assert decision["integration_steps"] == 1
    assert decision["nominal_integration_steps"] == 3
    assert decision["optional_integration_seconds"] > 0
    assert decision["integration_step_limit"] == 16
    config["memory"]["assembly_rounds"] = 1
    db.set("config", config)
    assert forecast(db, now=1404)["integration_steps"] == 1


def test_latency_replay_uses_the_target_and_leaves_room_for_actual_finalization(db):
    memory_budget(db)
    elapsed, added = 403.954247713089, 0
    while forecast(db, ["T1"], now=1000 + elapsed)["can_admit"]:
        elapsed += 66.44755481090397
        added += 1
    # Replay repeats a measured fast node; it predicts time, never speedup or quality.
    assert added >= 10
    # Mandatory finalization still fits. Extra rounds now go through their own
    # admission instead of charging all historical optional rounds to research.
    final = forecast(db, now=1000 + elapsed)
    assert elapsed + final["reserve_seconds"] <= 30 * 60
    assert not assembly_admission(db, now=1000 + elapsed + final["final_g_seconds"])["can_start_round"]


def test_measured_selection_and_whole_code_episodes_replace_initial_priors(db):
    memory_budget(db)
    record_timing(db, "generation:G", 140)  # Includes this mission's reads/repairs.
    record_timing(db, "evaluation_work:G", 12)
    record_timing(db, "memory_selection", 25)
    db.set("memory_selection_call_counts", [3, 4, 3])
    decision = forecast(db, now=1404)
    assert decision["final_g_seconds"] == 152
    assert decision["selection_seconds"] == 3 * 25
    assert decision["integration_seconds"] == 152 + 75
    assert decision["optional_integration_seconds"] == 152 + 75


def test_optional_reads_preserve_code_and_confirmation_for_large_forests(db):
    memory_budget(db, width=600)
    early = assembly_admission(db, now=1404)
    assert early["can_read"] and early["can_start_round"]
    late = assembly_admission(db, now=2799)
    assert not late["can_read"] and not late["can_start_round"]
    assert late["finish_seconds"] > 0
    db.set("deadline", None)
    assert assembly_admission(db, now=10000)["can_read"]


def test_late_round_does_not_reserve_reads_that_must_decide_would_forbid(db):
    memory_budget(db)
    record_timing(db, "memory_selection", 39.826594829559326)
    db.set("memory_selection_call_counts", [3, 4])
    early = assembly_admission(db, now=1404)
    minimum = early["finish_seconds"] + 1.25 * 39.826594829559326
    late = assembly_admission(db, now=2800 - minimum - 0.05)
    assert late["can_start_round"]
    assert not late["can_read"]  # The selector must write code after one decision.
    assert late["round_required_seconds"] == pytest.approx(minimum)
    assert late["nominal_round_required_seconds"] > late["remaining_seconds"]
    assert not assembly_admission(db, now=2800 - minimum + 0.05)["can_start_round"]


def test_overdue_campaign_preserves_first_measured_g_for_confirmation(db, tmp_path, monkeypatch):
    config = memory_budget(db, width=600)
    db.set("deadline", 0)
    calls = []
    state = {}
    def choose(*args):
        calls.append("selection")
        return {"action": "integrate", "base_id": "baseline-e1", "source_ids": ["baseline-e1"],
                "idea_ids": []}
    def integrate(controller, epoch, baseline, state, **kwargs):
        calls.append("code-and-evaluation")
        state["steps"].append({"mission_id": "measured-g", "outcome": {"correct": True}})
        return SimpleNamespace(id="measured-g"), {"correct": True}, {"status": "complete"}
    monkeypatch.setattr("hpc_forest.integration_policy._select", choose)
    monkeypatch.setattr("hpc_forest.completion._integrate", integrate)
    controller = SimpleNamespace(db=db, config=config, root=tmp_path)
    integrate_memory(controller, {"id": 1, "base_commit": "base"}, {"mean_seconds": 2}, state)
    assert calls == ["selection", "code-and-evaluation"]
    assert state["mission_id"] == "measured-g"
    assert state["stop_decision"]["controller_budget_stop"]


@pytest.mark.parametrize("key,value", [("initial_selection_seconds", 0),
    ("initial_selection_seconds", float("nan")), ("initial_selection_seconds", True),
    ("initial_selection_calls", 0), ("initial_selection_calls", 1.5), ("initial_selection_calls", True),
    ("initial_integration_rounds", 0), ("initial_integration_rounds", 1.5), ("initial_integration_rounds", True)])
def test_invalid_selection_priors_fail_before_execution(config, key, value):
    config = copy.deepcopy(config)
    config["completion"][key] = value
    with pytest.raises(ForestError):
        validate(config)
