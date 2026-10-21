"""Versioned preparation/authorization only; no allocation or model invocation."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest
from test_depth_campaign import load_tool, write_receipt

from hpc_forest.config import validate
from hpc_forest.core import InfrastructureError


@pytest.fixture
def forest_native(monkeypatch):
    smoke = load_tool("native_smoke", monkeypatch)
    session = "a" * 32
    plan = {"scope": smoke.FOREST_SCOPE, "session_id": session, "model": smoke.MODEL,
            "effort": smoke.EFFORT, "subject": "2023-count", "seed": 23,
            "mother_calls": 3, "cores": 4, "gpus": 0, "depth_comparison": True,
            "max_depth": 0, "binary_tree": {"enabled": False},
            "historical_candidates_imported": False, "created_at": 0,
            "remote_root": "/scratch_p/nimarano/hpc-forest-r1-mother-forest-" + session,
            "preparation_manifest": {"path": smoke.OFFICIAL_SHARED_ROOT +
                                     "/prepared/prepared-manifest.json", "sha256": "b" * 64},
            "statement": {"path": smoke.OFFICIAL_SHARED_ROOT + "/statements/2023.txt", "sha256": "c" * 64},
            **smoke.forest_contract(1800)}
    return smoke, plan


@pytest.mark.parametrize("duration", [1800, 7200, 18000, 86400])
def test_native_forest_chooses_count_at_runtime_without_parallelism_setting(forest_native, duration):
    smoke, plan = forest_native
    plan.update(smoke.forest_contract(duration))
    smoke.validate_depth_plan(plan)
    assert plan["forest"] == {"policy": "mother", "conversation": "persistent", "integration": "pairwise"}
    assert plan["schedule"]["integrations_per_cycle"] == 0 and plan["mother_calls"] is None
    assert plan["budget"]["tokens"] is plan["budget"]["search_slots"] is plan["schedule"]["cycles"] is None
    assert "parallelism" not in plan and "children" not in plan
    assert smoke.worker_lifetime_seconds(smoke.FOREST_SCOPE, plan) is None


def test_native_forest_authorization_cannot_reuse_a_fixed_tree_or_binary_scope(tmp_path, forest_native):
    smoke, plan = forest_native
    receipt, value = write_receipt(tmp_path, smoke, plan)
    assert smoke.authorize(receipt, {smoke.FOREST_SCOPE}) == value
    with pytest.raises(InfrastructureError):
        smoke.authorize(receipt, {smoke.ADAPTIVE_SCOPE})
    for changes in ({"forest": {"policy": "fixed"}}, {"binary_tree": {"enabled": True}}):
        with pytest.raises(InfrastructureError):
            smoke.validate_depth_plan({**plan, **changes})


def test_v6_contract_stays_single_assembly_and_cannot_be_reinterpreted_as_v7(tmp_path, forest_native):
    smoke, current = forest_native
    legacy = {**current, **smoke.forest_contract(1800, pairwise=False), "scope": smoke.CONVERSATION_SCOPE}
    receipt, value = write_receipt(tmp_path, smoke, legacy)
    assert smoke.authorize(receipt, {smoke.CONVERSATION_SCOPE}) == value
    assert legacy["mother_calls"] == 2 and legacy["postprocess_missions"] == 1
    assert "integration" not in legacy["forest"]
    with pytest.raises(InfrastructureError):
        smoke.validate_depth_plan({**legacy, "scope": smoke.FOREST_SCOPE})
    with pytest.raises(InfrastructureError):
        smoke.validate_depth_plan({**current, "scope": smoke.CONVERSATION_SCOPE})


def test_romeo_model_access_is_frozen_in_new_plan_and_never_added_to_historical_scope(tmp_path, forest_native):
    from hpc_forest.model_mcp import MODEL_MCP_POLICY

    smoke, plan = forest_native
    assert not smoke.model_mcp_enabled(plan)
    plan["model_mcp"] = dict(MODEL_MCP_POLICY)
    receipt, value = write_receipt(tmp_path, smoke, plan)
    assert smoke.authorize(receipt, {smoke.FOREST_SCOPE}) == value
    assert smoke.model_mcp_enabled(plan)
    for changed in ({**plan, "scope": smoke.LEGACY_FOREST_SCOPE},
                    {**plan, "model_mcp": {**MODEL_MCP_POLICY, "server": "unrelated"}}):
        with pytest.raises(InfrastructureError, match="ROMEO profile"):
            smoke.validate_depth_plan(changed)


def test_documentation_plan_keeps_romeo_and_pins_its_official_catalogue(tmp_path, forest_native):
    from hpc_forest.documentation_mcp import DOCUMENTATION_POLICY
    from hpc_forest.model_mcp import MODEL_MCP_POLICY

    smoke, plan = forest_native
    assert not smoke.documentation_enabled(plan)
    plan.update(model_mcp=dict(MODEL_MCP_POLICY), documentation=dict(DOCUMENTATION_POLICY))
    receipt, value = write_receipt(tmp_path, smoke, plan)
    assert smoke.authorize(receipt, {smoke.FOREST_SCOPE}) == value
    assert smoke.documentation_enabled(plan)
    for changes in ({"model_mcp": None}, {"scope": smoke.LEGACY_FOREST_SCOPE},
                    {"documentation": {**DOCUMENTATION_POLICY, "catalogue_sha256": "0" * 64}}):
        with pytest.raises(InfrastructureError):
            smoke.validate_depth_plan({**plan, **changes})


def test_official_factory_carries_mother_plan_and_exact_luna_identity(forest_native, monkeypatch, tmp_path):
    smoke, plan = forest_native
    official = load_tool("official_pilot", monkeypatch)
    examples = Path(__file__).resolve().parents[1] / "examples/marathon22"
    monkeypatch.syspath_prepend(str(examples))
    spec = importlib.util.spec_from_file_location("romeo_codex_forest_test", examples / "romeo_codex.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    monkeypatch.setattr(runner, "MODEL", smoke.MODEL)
    monkeypatch.setattr(runner, "CHANNEL", tmp_path / "owned-mailbox")
    monkeypatch.setattr(runner, "SESSION_ID", plan["session_id"])
    for dictionary in (runner.reference.SCHEDULE, runner.reference.LIMITS):
        for key in tuple(dictionary):
            monkeypatch.setitem(dictionary, key, dictionary[key])
    harness = json.loads((examples / "harness-mixed.json").read_text())
    settings = official.official_settings(plan, runner, "owned-target",
                                         {"protocol_timeout_seconds": 40}, harness)
    validate(settings)
    assert settings["forest"] == plan["forest"] and settings["budget"] == {**settings["budget"], **plan["budget"]}
    assert settings["codex"]["model"] == "gpt-6-luna" and settings["codex"]["reasoning_effort"] == "max"
    assert settings["harness"]["call_token_ceiling"] is None


def test_completion_requires_every_chosen_tree_and_final_g(forest_native):
    smoke, _ = forest_native
    roles = [f"T{i}" for i in range(1, 9)]
    result = {"scope": smoke.FOREST_SCOPE, "search": {"status": "budget_exhausted"},
              "completion": {"policy": "finish-started", "confirm_final_g": True},
              "forest_plan": {"status": "complete", "children": [{"role": role} for role in roles]},
              "best_confirmed": {"commit": "winner"},
              "mother": {"preparation": {"status": "complete"}, "synthesis": None},
              "postprocess": {"status": "complete", "mission_id": "final", "mother": {"status": "complete"}},
              "final_g_confirmation": {"status": "confirmed", "experiment_id": "final", "outcome": {"correct": True}},
              "trials": [{"id": role, "role": role, "mission": {}, "result": json.dumps({"status": "valid"})}
                         for role in roles] + [{"id": "final", "role": "G", "mission": {"budget_phase": "postprocess"},
                                               "result": json.dumps({"status": "valid"})}]}
    original = {"id": "a" * 32, "thread_id": "12345678-1234-1234-1234-123456789abc", "turn": 0,
                "phase": "planning", "request_sha256": "b" * 64}
    result["forest_plan"]["conversation"] = original
    result["postprocess"]["mother"]["conversation"] = {**original, "turn": 1, "phase": "assembly"}
    # v7 records every measured pair, ending in the final program.
    result["postprocess"].update(integration_policy="pairwise", leaf_program_ids=roles,
        steps=[{"mission_id": f"merge{i}", "status": "complete", "input_ids": ["left", "right"], "final": False}
               for i in range(6)] + [{"mission_id": "final", "status": "complete",
                                    "input_ids": ["left", "right"], "final": True}])
    result["trials"][-1:-1] = [
        {"id": f"merge{i}", "role": "G", "mission": {"budget_phase": "postprocess"},
         "result": json.dumps({"status": "valid"})} for i in range(6)]
    for index, step in enumerate(result["postprocess"]["steps"], 1):
        step["mother"] = {"status": "complete", "conversation": {**original, "turn": index, "phase": "assembly"}}
    result["postprocess"]["mother"] = result["postprocess"]["steps"][-1]["mother"]
    assert smoke.depth_completion(result, trials_per_role=None)["pipeline_complete"]
    missing_tree = copy.deepcopy(result)
    missing_tree["trials"] = missing_tree["trials"][1:]
    assert not smoke.depth_completion(missing_tree, trials_per_role=None)["pipeline_complete"]
    different_mother = copy.deepcopy(result)
    different_mother["postprocess"]["steps"][0]["mother"]["conversation"]["thread_id"] = "unrelated"
    assert not smoke.depth_completion(different_mother, trials_per_role=None)["pipeline_complete"]


def test_cli_accepts_mother_choice_without_a_parallelism_knob(tmp_path, monkeypatch):
    from test_mother_forest import settings

    from hpc_forest import cli

    config = settings(tmp_path)
    config["forest"] = {"policy": "fixed"}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    statement = tmp_path / "statement.txt"
    statement.write_text("The complete problem text.", encoding="utf-8")
    captured = {}
    def create(destination, settings, source, validation):
        validate(settings)
        captured.update(settings)
        return destination
    monkeypatch.setattr(cli, "create_workspace", create)
    assert cli.main(["init", str(tmp_path / "new"), "--config", str(path), "--duration", "5h",
                     "--mother-trees", "--statement", str(statement)]) == 0
    assert captured["forest"] == {"policy": "mother", "conversation": "persistent", "integration": "pairwise",
                                  "statement": "The complete problem text."}
    assert captured["budget"]["wall_seconds"] == 18000
    from hpc_forest.model_skills import policy as skills_policy

    assert captured["skills"] == skills_policy()


def test_official_observer_never_flattens_mothers_n_tree_passes(tmp_path, monkeypatch, need_compiler):
    from test_mother_forest import ConcurrentModel, campaign

    from hpc_forest.mother import MotherContext

    examples = Path(__file__).resolve().parents[1] / "examples/marathon22"
    monkeypatch.syspath_prepend(str(examples))
    import romeo_harness_comparison as observers

    root, original, calls = campaign(tmp_path, monkeypatch, 5)
    original.db.close()
    class OfficialController(MotherContext, observers.ObservedController):
        pass
    with OfficialController(root, "Offline official-controller fixture") as controller:
        controller.backend = ConcurrentModel(5)
        state = controller.run(max_batches=1)
        roles = [f"T{i}" for i in range(1, 6)]
        assert state["research_roles"] == roles and controller.plan()[0] == roles
        assert controller.backend.peak == 5
        assert len(controller.backend.calls) == 5 and len(calls) == 1
