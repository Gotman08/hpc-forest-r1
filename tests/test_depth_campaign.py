import importlib.util
import json
import tarfile
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from hpc_forest.controller import Controller
from hpc_forest.core import InfrastructureError, file_digest


def load_tool(name, monkeypatch):
    tools = Path(__file__).resolve().parents[1] / "tools"
    monkeypatch.syspath_prepend(str(tools))
    spec = importlib.util.spec_from_file_location(name + "_depth_test", tools / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def smoke(monkeypatch):
    return load_tool("native_smoke", monkeypatch)


@pytest.fixture
def depth_plan(smoke):
    session = "a" * 32
    return {"scope": smoke.DEPTH_SCOPE, "session_id": session, "model": smoke.MODEL,
            "effort": smoke.EFFORT, "subject": "2023-count", "trials_per_role": 16,
            "wall_seconds": 1800, "token_budget": 1500000, "seed": 23,
            "mother_calls": 2, "cores": 4, "gpus": 0, "depth_comparison": True,
            "max_depth": 0, "binary_tree": {"enabled": False},
            "historical_candidates_imported": False, "created_at": time.time(),
            "remote_root": "/scratch_p/nimarano/hpc-forest-r1-depth-" + session,
            "preparation_manifest": {"path": smoke.OFFICIAL_SHARED_ROOT +
                                     "/prepared/prepared-manifest.json", "sha256": "b" * 64},
            "statement": {"path": smoke.OFFICIAL_SHARED_ROOT + "/statements/2023.txt",
                          "sha256": "c" * 64},
            **smoke.depth_contract(16, 1800, 1500000)}


def write_receipt(tmp_path, smoke, plan, *, packed_plan=None):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf8")
    payload = tmp_path / "payload.tar.gz"
    packed = tmp_path / "packed-plan.json"
    packed.write_text(json.dumps(plan if packed_plan is None else packed_plan), encoding="utf8")
    with tarfile.open(payload, "w:gz") as archive:
        archive.add(packed, arcname="plan.json")
    value = {"scope": plan["scope"], "model": smoke.MODEL, "effort": smoke.EFFORT,
             "expires_at": time.time() + 5400, "historical_campaign_resumption": False,
             "session_id": plan["session_id"], "user_request": "Both policies with Luna MAX",
             "channel": plan["remote_root"] + "/results-123/mailbox",
             "remote_payload": plan["remote_root"] + ".tar.gz",
             "plan": {"path": str(plan_path), "sha256": file_digest(plan_path)},
             "payload": {"path": str(payload), "sha256": file_digest(payload)}}
    if "completion" in plan:
        value["completion"] = plan["completion"]
    receipt = tmp_path / "authorization.json"
    receipt.write_text(json.dumps(value), encoding="utf8")
    return receipt, value


def test_depth_contract_funds_baseline_children_and_two_mothers(smoke):
    contract = smoke.depth_contract(16, 1800, 1500000)
    assert contract["schedule"] == {"cycles": 8, "trials_per_role_per_cycle": 2,
                                    "integrations_per_cycle": 2}
    assert contract["child_missions"] == 64
    assert contract["budget"]["search_slots"] == 67
    assert contract["budget"]["max_depth"] == 0
    assert contract["maximum_calls_including_repairs"] == 194
    assert contract["budget"]["mission_tokens"] == 3 * smoke.codex_mailbox.TOKEN_CEILING


def test_finish_started_scope_declares_final_calls_without_token_limits(smoke, depth_plan):
    depth_plan.update(scope=smoke.FINISH_SCOPE, **smoke.depth_contract(16, 1800, None, completion=True))
    smoke.validate_depth_plan(depth_plan)
    assert depth_plan["budget"]["tokens"] is None
    assert depth_plan["budget"]["mission_tokens"] is None
    assert depth_plan["budget"]["search_slots"] == 67
    assert depth_plan["completion"]["postprocess_tokens"] is None
    assert depth_plan["mother_calls"] == 3 and depth_plan["postprocess_missions"] == 1
    assert depth_plan["maximum_calls_including_repairs"] == 198
    assert smoke.worker_lifetime_seconds(smoke.FINISH_SCOPE, depth_plan) is None


def test_running_finish_authorization_can_outlive_start_window_but_cannot_start_expired(
    tmp_path, smoke, depth_plan, monkeypatch,
):
    depth_plan.update(scope=smoke.FINISH_SCOPE, **smoke.depth_contract(16, 1800, None, completion=True))
    path, value = write_receipt(tmp_path, smoke, depth_plan)
    assert smoke.authorize(path, {smoke.FINISH_SCOPE}) == value
    monkeypatch.setattr(smoke, "time", SimpleNamespace(time=lambda: value["expires_at"] + 3600))
    with pytest.raises(InfrastructureError, match="expired"):
        smoke.authorize(path, {smoke.FINISH_SCOPE})
    assert smoke.authorize(path, {smoke.FINISH_SCOPE}, allow_running_completion=True) == value
    value.pop("completion")
    path.write_text(json.dumps(value))
    with pytest.raises(InfrastructureError, match="completion budget"):
        smoke.authorize(path, {smoke.FINISH_SCOPE}, allow_running_completion=True)


def test_finish_scope_requires_actual_final_mother_and_g_even_after_budget(smoke):
    result = {"search": {"status": "budget_exhausted"}, "best_confirmed": {"is_baseline": True},
              "completion": {"policy": "finish-started"},
              "postprocess": {"status": "complete", "mother": {"status": "complete"}},
              "mother": {"preparation": {"status": "complete"}, "synthesis": None},
              "trials": [{"role": role, "result": json.dumps({"status": "valid"})}
                         for role in "ABCABC"]}
    assert not smoke.depth_completion(result, trials_per_role=16)["pipeline_complete"]
    result["trials"].append({"role": "G", "mission": json.dumps({"budget_phase": "postprocess"}),
                             "result": json.dumps({"status": "valid"})})
    complete = smoke.depth_completion(result, trials_per_role=16)
    assert complete["pipeline_complete"] and complete["realized_trials_per_role"]["G"] == 0
    assert complete["postprocess_missions"] == 1
    result["postprocess"]["mother"]["status"] = "model_or_interface_failure"
    assert not smoke.depth_completion(result, trials_per_role=16)["pipeline_complete"]


@pytest.mark.parametrize("trials,wall,tokens", [
    (True, 1800, 1500000), (3, 1800, 1500000), (0, 1800, 1500000),
    (16.0, 1800, 1500000), (16, 120, 1500000), (16, 1800, 1),
])
def test_depth_contract_refuses_implicit_or_inadequate_limits(smoke, trials, wall, tokens):
    with pytest.raises(InfrastructureError):
        smoke.depth_contract(trials, wall, tokens)


@pytest.mark.parametrize("binary", [False, True])
def test_depth_authorization_is_frozen_owned_and_separate(tmp_path, smoke, depth_plan, binary):
    depth_plan["binary_tree"]["enabled"] = binary
    path, value = write_receipt(tmp_path, smoke, depth_plan)
    assert smoke.authorize(path, {smoke.DEPTH_SCOPE}) == value
    with pytest.raises(InfrastructureError):
        smoke.authorize(path, {smoke.OFFICIAL_SCOPE})
    assert smoke.worker_lifetime_seconds(smoke.DEPTH_SCOPE, depth_plan) == 2700
    assert smoke.worker_lifetime_seconds(smoke.OFFICIAL_SCOPE, {}) == 2700
    assert smoke.worker_lifetime_seconds(smoke.SCOPE, {}) == 1200


@pytest.mark.parametrize("key,value", [
    ("max_depth", 6), ("seed", 24), ("mother_calls", 1), ("child_missions", 8),
    ("historical_candidates_imported", True), ("model", "gpt-6.1-sol"),
    ("schedule", {"cycles": 1, "trials_per_role_per_cycle": 16, "integrations_per_cycle": 16}),
    ("schedule", {"cycles": 8, "trials_per_role_per_cycle": 2.0, "integrations_per_cycle": 2}),
    ("statement", {"path": "/unfrozen/statement.txt", "sha256": "c" * 64}),
])
def test_rehashing_cannot_broaden_the_depth_contract(tmp_path, smoke, depth_plan, key, value):
    depth_plan[key] = value
    path, _ = write_receipt(tmp_path, smoke, depth_plan)
    with pytest.raises(InfrastructureError):
        smoke.authorize(path, {smoke.DEPTH_SCOPE})


def test_depth_payload_must_embed_the_authorized_plan(tmp_path, smoke, depth_plan):
    other = {**depth_plan, "binary_tree": {"enabled": True}}
    path, _ = write_receipt(tmp_path, smoke, depth_plan, packed_plan=other)
    with pytest.raises(InfrastructureError, match="different depth plan"):
        smoke.authorize(path, {smoke.DEPTH_SCOPE})


@pytest.mark.parametrize("key,value", [
    ("expires_at", time.time() + 600), ("remote_payload", "/another/payload.tar.gz"),
    ("channel", "/scratch_p/nimarano/hpc-forest-r1-depth-" + "b" * 32 + "/results-123/mailbox"),
])
def test_depth_receipt_covers_duration_payload_and_channel(tmp_path, smoke, depth_plan, key, value):
    path, receipt = write_receipt(tmp_path, smoke, depth_plan)
    receipt[key] = value
    path.write_text(json.dumps(receipt), encoding="utf8")
    with pytest.raises(InfrastructureError):
        smoke.authorize(path, {smoke.DEPTH_SCOPE})


@pytest.mark.parametrize("binary", [False, True])
@pytest.mark.parametrize("uncapped", [False, True])
def test_official_settings_interleave_pairs_without_exceeding_frozen_budgets(
        monkeypatch, smoke, depth_plan, binary, uncapped):
    if uncapped:
        depth_plan.update(scope=smoke.FINISH_SCOPE, **smoke.depth_contract(16, 1800, None, completion=True))
    official = load_tool("official_pilot", monkeypatch)
    examples = Path(__file__).resolve().parents[1] / "examples/marathon22"
    monkeypatch.syspath_prepend(str(examples))
    spec = importlib.util.spec_from_file_location("romeo_codex_depth_test", examples / "romeo_codex.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    monkeypatch.setattr(runner, "MODEL", smoke.MODEL)
    for dictionary in (runner.reference.SCHEDULE, runner.reference.LIMITS):
        for key in tuple(dictionary):
            monkeypatch.setitem(dictionary, key, dictionary[key])
    depth_plan["binary_tree"]["enabled"] = binary
    harness = json.loads((examples / "harness-mixed.json").read_text())
    settings = official.official_settings(depth_plan, runner, "owned-target",
                                          {"protocol_timeout_seconds": 40}, harness)
    controller = Controller.__new__(Controller)
    controller.config = settings
    batches = controller.plan()
    assert batches[:4] == ([["A"], ["B"], ["C"], ["A"]] if uncapped else
                           [["A", "B", "C"], ["A", "B", "C"], ["G"], ["G"]])
    roles = [role for batch in batches for role in batch]
    assert {role: roles.count(role) for role in "ABCG"} == dict.fromkeys("ABCG", 16)
    assert settings["budget"]["wall_seconds"] == 1800
    assert settings["budget"]["tokens"] == (None if uncapped else 1500000)
    if uncapped:
        assert settings["harness"]["call_token_ceiling"] is None
        assert settings["budget"]["mission_tokens"] is None
    assert settings["budget"]["max_depth"] == 0
    assert settings["budget"]["search_slots"] == 1 + len(roles) + 2
    assert settings["binary_tree"]["enabled"] is binary
    # A subsequent historical pilot keeps its fixed two-per-role, depth-six protocol.
    historic = {"scope": smoke.OFFICIAL_SCOPE, "subject": "2023-count"}
    settings = official.official_settings(historic, runner, "historic-target",
                                          {"protocol_timeout_seconds": 40}, harness)
    assert settings["schedule"] == {"cycles": 1, "trials_per_role_per_cycle": 2,
                                    "integrations_per_cycle": 2}
    assert settings["budget"]["max_depth"] == 6
    assert settings["budget"]["search_slots"] == 11


def test_bounded_completion_does_not_claim_unexecuted_trials_or_hide_failure(smoke):
    result = {"search": {"status": "budget_exhausted"}, "best_confirmed": {"is_baseline": True},
              "mother": {"preparation": {"status": "complete"}, "synthesis": None},
              "trials": [{"role": role, "result": json.dumps({"status": "valid"})}
                         for role in "ABCABC"]}
    completion = smoke.depth_completion(result, trials_per_role=16)
    assert completion["pipeline_complete"]
    assert completion["budget_exhausted"] and not completion["schedule_completed"]
    assert completion["realized_trials_per_role"] == {"A": 2, "B": 2, "C": 2, "G": 0}
    assert completion["mother_phase_status"]["synthesis"] == "not_reached"
    result["trials"][0]["result"] = json.dumps({"status": "infrastructure_error"})
    assert not smoke.depth_completion(result, trials_per_role=16)["pipeline_complete"]
    result["trials"][0]["result"] = json.dumps({"status": "valid"})
    result["mother"]["preparation"]["status"] = "model_or_interface_failure"
    assert not smoke.depth_completion(result, trials_per_role=16)["pipeline_complete"]


def test_depth_completed_schedule_still_requires_all_roles_and_mother_phases(smoke):
    result = {"search": {"status": "search_complete"}, "best_confirmed": {"is_baseline": True},
              "mother": {phase: {"status": "complete"} for phase in ("preparation", "synthesis")},
              "trials": [{"role": role, "result": json.dumps({"status": "valid"})}
                         for role in "ABCG" * 16]}
    complete = smoke.depth_completion(result, trials_per_role=16)
    assert complete["pipeline_complete"] and complete["schedule_completed"]
    result["trials"].pop()
    complete = smoke.depth_completion(result, trials_per_role=16)
    assert not complete["pipeline_complete"] and not complete["schedule_completed"]


def test_fresh_depth_run_uses_current_checker_and_preserves_official_fixtures(
        tmp_path, monkeypatch, smoke):
    official = load_tool("official_pilot", monkeypatch)
    original = tmp_path / "official-validation"
    original.mkdir()
    (original / "contract_tool.py").write_text("old checker", encoding="utf8")
    (original / "contract.json").write_text('{"expected": "unchanged"}', encoding="utf8")
    project = Path(__file__).resolve().parents[1]
    prepared = {"validation": str(original)}
    historical, receipt = official.campaign_validation(
        {"scope": smoke.OFFICIAL_SCOPE}, project, tmp_path, prepared)
    assert historical == original and receipt is None
    validation, receipt = official.campaign_validation(
        {"scope": smoke.DEPTH_SCOPE}, project, tmp_path, prepared)
    assert validation != original
    assert (original / "contract_tool.py").read_text() == "old checker"
    assert (validation / "contract.json").read_bytes() == (original / "contract.json").read_bytes()
    assert receipt["original_tool_sha256"] == file_digest(original / "contract_tool.py")
    assert receipt["runtime_tool_sha256"] == file_digest(project / "src/hpc_forest/contracts.py")
    assert receipt["fixtures_preserved"] is True


@pytest.mark.parametrize("hours", [0.5, 2, 5, 24])
@pytest.mark.parametrize("binary", [False, True])
def test_adaptive_native_plan_has_no_hidden_finite_ceiling(smoke, depth_plan, hours, binary):
    depth_plan.update(scope=smoke.ADAPTIVE_SCOPE, **smoke.adaptive_contract(hours * 3600))
    depth_plan["remote_root"] = "/scratch_p/nimarano/hpc-forest-r1-adaptive-" + depth_plan["session_id"]
    depth_plan["binary_tree"]["enabled"] = binary
    smoke.validate_depth_plan(depth_plan)
    assert depth_plan["schedule"]["cycles"] is None
    assert depth_plan["trials_per_role"] is depth_plan["child_missions"] is None
    assert depth_plan["maximum_calls_including_repairs"] is None
    assert depth_plan["budget"]["search_slots"] is depth_plan["budget"]["tokens"] is None
    assert depth_plan["completion"]["confirm_final_g"]
    assert smoke.worker_lifetime_seconds(smoke.ADAPTIVE_SCOPE, depth_plan) is None


def test_adaptive_runtime_factory_uses_exact_plan_and_luna_max(smoke, depth_plan, monkeypatch):
    depth_plan.update(scope=smoke.ADAPTIVE_SCOPE, **smoke.adaptive_contract(86400))
    depth_plan["remote_root"] = "/scratch_p/nimarano/hpc-forest-r1-adaptive-" + depth_plan["session_id"]
    official = load_tool("official_pilot", monkeypatch)
    examples = Path(__file__).resolve().parents[1] / "examples/marathon22"
    monkeypatch.syspath_prepend(str(examples))
    spec = importlib.util.spec_from_file_location("romeo_codex_adaptive_test", examples / "romeo_codex.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    monkeypatch.setattr(runner, "MODEL", smoke.MODEL)
    for dictionary in (runner.reference.SCHEDULE, runner.reference.LIMITS):
        for key in tuple(dictionary):
            monkeypatch.setitem(dictionary, key, dictionary[key])
    harness = json.loads((examples / "harness-mixed.json").read_text())
    settings = official.official_settings(depth_plan, runner, "owned-target",
                                          {"protocol_timeout_seconds": 40}, harness)
    assert settings["schedule"] == depth_plan["schedule"]
    assert all(settings["budget"][key] == value for key, value in depth_plan["budget"].items())
    assert settings["codex"]["model"] == "gpt-6-luna" and settings["codex"]["reasoning_effort"] == "max"
    assert settings["harness"]["call_token_ceiling"] is None
    from hpc_forest.config import validate

    validate(settings)


def test_adaptive_authorization_covers_24_hours_and_only_finishes_an_already_started_run(
        tmp_path, smoke, depth_plan, monkeypatch):
    depth_plan.update(scope=smoke.ADAPTIVE_SCOPE, **smoke.adaptive_contract(86400))
    depth_plan["remote_root"] = "/scratch_p/nimarano/hpc-forest-r1-adaptive-" + depth_plan["session_id"]
    path, value = write_receipt(tmp_path, smoke, depth_plan)
    value["expires_at"] = depth_plan["created_at"] + 86400 + 3600
    path.write_text(json.dumps(value))
    assert smoke.authorize(path, {smoke.ADAPTIVE_SCOPE}) == value
    monkeypatch.setattr(smoke, "time", SimpleNamespace(time=lambda: value["expires_at"] + 1))
    with pytest.raises(InfrastructureError, match="expired"):
        smoke.authorize(path, {smoke.ADAPTIVE_SCOPE})
    assert smoke.authorize(path, {smoke.ADAPTIVE_SCOPE}, allow_running_completion=True) == value


def test_adaptive_completion_refuses_missing_final_g_confirmation(smoke):
    final_id = "final-g"
    result = {"search": {"status": "budget_exhausted"}, "best_confirmed": {"is_baseline": True},
              "completion": smoke.adaptive_contract(1800)["completion"],
              "postprocess": {"status": "complete", "mission_id": final_id,
                              "mother": {"status": "complete"}},
              "trials": [{"id": final_id, "role": "G", "mission": {"budget_phase": "postprocess"},
                          "result": json.dumps({"status": "valid"})}]}
    assert not smoke.depth_completion(result, trials_per_role=None)["pipeline_complete"]
    result["final_g_confirmation"] = {"status": "confirmed", "experiment_id": final_id,
                                       "outcome": {"correct": True, "mean_seconds": 1}}
    assert smoke.depth_completion(result, trials_per_role=None)["pipeline_complete"]
