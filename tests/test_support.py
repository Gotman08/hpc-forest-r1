import json
import math
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from hpc_forest.config import validate
from hpc_forest.core import ForestError, InfrastructureError
from hpc_forest.mother import PLANNING_SOURCE_CHARACTERS, plan_for
from hpc_forest.ollama_backend import OllamaBackend
from hpc_forest.support.budgets import generation_deadline, search_deadline
from hpc_forest.support.sources import SourceLimitExceeded, source_snapshot
from hpc_forest.support.validation import require_finite_number, require_integer


def test_source_snapshot_is_ordered_bounded_and_preserves_contents(tmp_path):
    source = tmp_path / "src"
    (source / "nested").mkdir(parents=True)
    (source / "z.c").write_bytes(b"one\r\ntwo\r\n")
    (source / "nested" / "a.c").write_text("é", encoding="utf-8")
    (tmp_path / "private.txt").write_text("outside source")
    files = source_snapshot(tmp_path)
    assert list(files) == ["src/nested/a.c", "src/z.c"]
    assert files["src/z.c"] == "one\r\ntwo\r\n"
    assert files["src/nested/a.c"] == "é"


def test_snapshot_limits_count_bytes_and_characters_separately(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.c").write_text("éé", encoding="utf-8")
    assert source_snapshot(tmp_path, max_bytes=4, max_characters=2)["src/main.c"] == "éé"
    with pytest.raises(SourceLimitExceeded):
        source_snapshot(tmp_path, max_bytes=3)
    with pytest.raises(SourceLimitExceeded):
        source_snapshot(tmp_path, max_characters=1)
    assert (tmp_path / "src" / "main.c").read_bytes() == "éé".encode()


def test_snapshot_character_limit_is_cumulative_across_files(tmp_path):
    (tmp_path / "src").mkdir()
    for name in ["a.c", "b.c"]:
        (tmp_path / "src" / name).write_text("123")
    with pytest.raises(SourceLimitExceeded):
        source_snapshot(tmp_path, max_characters=5)


def test_snapshot_decoding_policy_is_explicit(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.c").write_bytes(b"\xff")
    with pytest.raises(UnicodeDecodeError):
        source_snapshot(tmp_path)
    assert source_snapshot(tmp_path, errors="replace")["src/main.c"] == "\ufffd"


def test_snapshot_rejects_missing_source_directory(tmp_path):
    with pytest.raises(InfrastructureError, match="does not exist"):
        source_snapshot(tmp_path)


@pytest.mark.parametrize("linked_path", ["src", "src/main.c"])
def test_source_link_is_refused_before_it_can_supply_context(tmp_path, monkeypatch, linked_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.c").write_text("source")
    original = Path.is_symlink
    linked = tmp_path / linked_path
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == linked or original(path))
    with pytest.raises(InfrastructureError, match="links"):
        source_snapshot(tmp_path)


@pytest.mark.parametrize("value", [-1, True, False, 1.5, math.nan, "1", None])
def test_integer_validation_rejects_invalid_accounting_values(value):
    with pytest.raises(ForestError):
        require_integer(value, "tokens")


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, True, "1", None, 10**400])
def test_nonfinite_and_ambiguous_numbers_are_rejected(value):
    with pytest.raises(ForestError):
        require_finite_number(value, "duration")


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("budget", "wall_seconds", math.nan),
        ("budget", "generation_seconds", math.inf),
        ("budget", "search_slots", True),
        ("budget", "infrastructure_retries", False),
        ("protocol", "timeout_seconds", math.inf),
        ("protocol", "repetitions", True),
        ("protocol", "warmups", False),
        ("schedule", "cycles", True),
    ],
)
def test_config_rejects_values_that_could_bypass_limits(config, section, key, value):
    config[section][key] = value
    with pytest.raises(ForestError):
        validate(config)


@pytest.mark.parametrize("roles", [["AB"], [""], [None], "ABC"])
def test_config_accepts_only_individual_role_names(config, roles):
    config["roles"] = roles
    with pytest.raises(ForestError):
        validate(config)


@pytest.mark.parametrize("tokens", [-1, True, 1.5])
def test_invalid_reservation_does_not_change_registry(db, tokens):
    before = db.costs()
    with pytest.raises(ForestError):
        db.reserve("search", "invalid", tokens)
    assert db.costs() == before


def test_unknown_budget_phase_is_refused_without_writes(db):
    with pytest.raises(ForestError, match="phase"):
        db.reserve("other", "invalid")
    assert not db.rows("SELECT * FROM slots")


@pytest.mark.parametrize("tokens", [-1, True, 1.5])
def test_invalid_settlement_keeps_original_reservation(db, tokens):
    slot = db.reserve("search", "source", 70)
    before = db.costs()
    with pytest.raises(ForestError):
        db.settle_tokens(slot, tokens)
    assert db.costs() == before


def test_unknown_slot_cannot_silently_lose_usage(db):
    with pytest.raises(ForestError, match="unknown"):
        db.settle_tokens("missing", 42)
    assert not db.rows("SELECT * FROM slots")


def test_deadlines_keep_campaign_search_and_queue_limits():
    context = {"deadline": 1000, "generation_deadline": search_deadline(1000, 120)}
    assert generation_deadline(context) == 880
    assert generation_deadline(context, 600, now=500) == 880
    assert generation_deadline(context, 100, now=500) == 600
    assert generation_deadline({"deadline": 1000}, 600, now=500) == 1000
    assert generation_deadline({"deadline": 1000, "generation_deadline": 1200}) == 1000


@pytest.fixture
def mother_setup(tmp_path, db):
    worktree = tmp_path / "tree"
    (worktree / "src").mkdir(parents=True)
    (worktree / "src" / "main.c").write_text("int main(void) { return 0; }\n")
    controller = SimpleNamespace(
        db=db, root=tmp_path / "campaign", statement="official facts",
        config={"codex": {"session_id": "a" * 32, "model": "fixture", "reasoning_effort": "max",
                          "mailbox_dir": str(tmp_path / "mailbox")}},
    )
    mission = SimpleNamespace(worktree=str(worktree), epoch=1)
    context = {"deadline": time.time() + 600, "generation_deadline": time.time() + 300}
    return controller, mission, context


def test_mother_phases_are_cached_and_accounted_without_replaying_calls(mother_setup, db, monkeypatch):
    controller, mission, context = mother_setup
    requests = []

    def publish(_channel, request):
        requests.append(request)
        return "a" * 64

    def response(_channel, _request, _sha):
        return {
            "usage": {"token_accounting": "exact", "tokens": 17, "llm_calls": 1},
            "data": dict.fromkeys(["analysis", "A", "B", "C", "G"], "bounded plan"),
        }

    monkeypatch.setattr("hpc_forest.mother.mailbox.publish_request", publish)
    monkeypatch.setattr("hpc_forest.mother.mailbox.wait_response", response)
    for phase in ["preparation", "synthesis"]:
        first = plan_for(controller, mission, context, phase)
        second = plan_for(controller, mission, context, phase)
        assert first == second and first["status"] == "complete"
    assert len(requests) == 2
    assert db.costs()["tokens_used"] == db.costs()["exact_tokens_used"] == 34
    assert db.costs()["tokens_reserved"] == 0


def test_mother_source_limit_releases_reservation_without_call(mother_setup, db, monkeypatch):
    controller, mission, context = mother_setup
    (Path(mission.worktree) / "src" / "main.c").write_text("x" * (PLANNING_SOURCE_CHARACTERS + 1))
    monkeypatch.setattr(
        "hpc_forest.mother.mailbox.publish_request",
        lambda *_: pytest.fail("Oversized source must not reach the model transport"),
    )
    result = plan_for(controller, mission, context, "preparation")
    assert result["status"] == "not_invoked_source_limit"
    assert result["model_calls"] == 0
    assert db.costs()["tokens_used"] == db.costs()["tokens_reserved"] == 0


def test_mother_accepts_complete_source_above_former_limit(mother_setup, monkeypatch):
    controller, mission, context = mother_setup
    source = "/*" + "x" * 33487 + "*/\nint main(void) { return 0; }\n"
    (Path(mission.worktree) / "src" / "main.c").write_bytes(source.encode())
    requests = []
    monkeypatch.setattr("hpc_forest.mother.mailbox.publish_request",
                        lambda _channel, request: requests.append(request) or "a" * 64)
    monkeypatch.setattr("hpc_forest.mother.mailbox.wait_response", lambda *_: {
        "usage": {"token_accounting": "exact", "tokens": 17, "llm_calls": 1},
        "data": dict.fromkeys(["analysis", "A", "B", "C", "G"], "bounded plan"),
    })
    assert plan_for(controller, mission, context, "preparation")["status"] == "complete"
    assert len(requests) == 1
    data = json.loads(requests[0]["messages"][1]["content"])
    assert data["current_sources_as_data"]["src/main.c"] == source


def test_expired_local_generation_never_contacts_metadata_or_model(tmp_path, config, monkeypatch):
    monkeypatch.setattr(
        "hpc_forest.ollama_backend.resolve_model",
        lambda *_: pytest.fail("Expired generation must not contact the local engine"),
    )
    result = OllamaBackend().generate(
        SimpleNamespace(role="A"),
        {"deadline": time.time() + 60, "generation_deadline": time.time() - 1},
        config, tmp_path,
    )
    assert result.tokens == 0 and result.usage["llm_calls"] == 0
