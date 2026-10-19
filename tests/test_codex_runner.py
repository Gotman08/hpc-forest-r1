import importlib.util
import sys
from pathlib import Path

from hpc_forest.codex_mailbox import EFFORT, MODEL, TOKEN_CEILING
from hpc_forest.controller import Controller


def load_runner(monkeypatch):
    examples = Path(__file__).parents[1] / "examples/marathon22"
    monkeypatch.syspath_prepend(str(examples))
    spec = importlib.util.spec_from_file_location("romeo_codex_test", examples / "romeo_codex.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_preserves_preparation_protocol_and_controller_context(monkeypatch, tmp_path):
    module = load_runner(monkeypatch)
    module.CHANNEL, module.SESSION_ID = tmp_path / "mailbox", "a" * 32
    prepared = {"protocol_timeout_seconds": 40}
    old = module.reference.config_for("unused", "knn", "target", prepared)
    actual = module.config_for("unused", "knn", "target", prepared)
    assert actual["protocol"] == old["protocol"]
    assert actual["seed"] == old["seed"] and actual["roles"] == old["roles"]
    assert actual["codex"]["model"] == MODEL and actual["codex"]["reasoning_effort"] == EFFORT
    assert actual["budget"]["mission_tokens"] == TOKEN_CEILING
    assert "ollama" not in actual
    assert module.CodexController._context is module.reference.AutonomousController._context


def test_runner_schedule_keeps_72_proposals_and_24_integration_opportunities(monkeypatch, tmp_path):
    module = load_runner(monkeypatch)
    module.CHANNEL, module.SESSION_ID = tmp_path / "mailbox", "a" * 32
    monkeypatch.setitem(module.reference.SCHEDULE, "cycles", 4)
    monkeypatch.setitem(module.reference.SCHEDULE, "trials_per_role_per_cycle", 6)
    monkeypatch.setitem(module.reference.SCHEDULE, "integrations_per_cycle", 6)
    settings = module.config_for("unused", "sum", "target", {"protocol_timeout_seconds": 40})
    controller = Controller.__new__(Controller)
    controller.config = settings
    roles = [role for batch in controller.plan() for role in batch]
    assert roles.count("G") == 24 and sum(roles.count(role) for role in "ABC") == 72
    assert settings["budget"]["search_slots"] == 97
    assert "romeo_codex_test" not in sys.modules


def test_short_pilot_preserves_roles_and_bounds_all_24_slots(monkeypatch, tmp_path):
    module = load_runner(monkeypatch)
    module.CHANNEL, module.SESSION_ID = tmp_path / "mailbox", "b" * 32
    for name, value in {"cycles": 2, "trials_per_role_per_cycle": 3,
                        "integrations_per_cycle": 3}.items():
        monkeypatch.setitem(module.reference.SCHEDULE, name, value)
    settings = module.config_for("unused", "knn", "pilot", {"protocol_timeout_seconds": 40})
    controller = Controller.__new__(Controller)
    controller.config = settings
    roles = [role for batch in controller.plan() for role in batch]
    assert {role: roles.count(role) for role in "ABCG"} == dict.fromkeys("ABCG", 6)
    assert settings["budget"]["search_slots"] == 25
    assert settings["protocol"]["repetitions"] == 3
    assert settings["protocol"]["confirmation_repetitions"] == 5
