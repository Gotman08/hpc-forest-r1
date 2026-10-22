"""The plan critic is generic, bounded and charged before any tree dispatch."""
import copy
import json
from types import SimpleNamespace

import pytest
from test_memory import memory_db as memory_fixture
from test_mother_conversation import complete_turn, persistent_settings, receipt_for, request_for
from test_mother_forest import decomposition

from hpc_forest import codex_mailbox as mailbox
from hpc_forest.codex_conversation import first_turn, next_turn, run_turn
from hpc_forest.config import validate
from hpc_forest.core import ForestError, InfrastructureError, canonical, digest
from hpc_forest.model_skills import policy, verify_binding
from hpc_forest.mother import prepare_forest
from hpc_forest.mother_review import review_messages, review_page, review_plan, revise

memory_db = memory_fixture


def test_critique_skills_remain_bound_to_planning():
    request = review_messages(review_page(decomposition(2), 0, 6, 4000), 2, "", policy())
    request["meta_role"] = "mother-plan-review"
    assert verify_binding(request)["phase"] == "planning"


def test_native_planning_review_assembly_chain_never_returns_to_research(tmp_path):
    request = request_for(first_turn())
    original = complete_turn(request, "1" * 64, tmp_path / "first")
    review = {**request, "conversation": next_turn(original["conversation"], phase="plan-review")}
    reviewed = complete_turn(review, "2" * 64, tmp_path / "review")
    assembly = {**request, "conversation": next_turn(reviewed["conversation"])}
    final = complete_turn(assembly, "3" * 64, tmp_path / "assembly")
    assert final["conversation"]["thread_id"] == original["conversation"]["thread_id"]
    with pytest.raises(InfrastructureError, match="after assembly"):
        next_turn(final["conversation"], phase="plan-review")
    forged = {**request, "conversation": {**next_turn(final["conversation"]), "phase": "plan-review"}}
    with pytest.raises(InfrastructureError, match="after assembly"):
        run_turn(forged, "4" * 64, tmp_path / "forged", lambda: pytest.fail("must not run"))


@pytest.mark.parametrize("width", [1, 2, 7, 56, 600])
def test_exact_review_pages_keep_variable_n_and_fit_context(width):
    plan = decomposition(width)
    offset = 0
    while offset < width:
        page = review_page(plan, offset, 6, 4000)
        assert page and len(canonical(page)) <= 4000
        value = {"analysis": "Consider shared assumptions", "shared_assumptions": "Unmeasured hypotheses",
                 "revisions": [{**page[0], "objective": "Contrasting experiment " + page[0]["role"]}]}
        updated = revise(plan, page, value)
        assert len(updated["children"]) == width
        assert updated["children"][offset]["objective"].startswith("Contrasting")
        assert plan["children"][offset]["objective"].startswith("Fixture")
        offset += len(page)


@pytest.mark.parametrize("revisions", [[{"role": "T3", "subject": "x", "objective": "y"}],
    [{"role": "T1", "subject": "x", "objective": "y"}] * 2,
    [{"role": "T1", "subject": "Fixture subject 2", "objective": "y"}]])
def test_critic_cannot_change_unseen_roles_or_create_duplicate_subjects(revisions):
    plan = decomposition(3)
    with pytest.raises(InfrastructureError):
        revise(plan, review_page(plan, 0, 2, 4000), {
            "analysis": "test", "shared_assumptions": "", "revisions": revisions})


def review_fixture(memory_db, monkeypatch):
    db, _, _, root = memory_db
    config = persistent_settings(root)
    config["forest"]["plan_review_calls"] = 2
    config["memory"] = {"mode": "record-only", "page_size": 1}
    db.set("config", config)
    slot = db.reserve("search", "mother:preparation")
    initial = request_for(first_turn())
    receipt = receipt_for(initial, "a" * 64)
    db.set("mother_conversation:1", receipt)
    original = {"status": "complete", "plan": decomposition(3), "conversation": receipt,
                "slot_id": slot, "request_sha256": "a" * 64}
    db.set("mother_plan:preparation:1", original)
    calls = []
    def receive(channel, request, sha):
        calls.append(copy.deepcopy(request))
        page = json.loads(request["messages"][1]["content"])["topics_as_data"]
        value = {"analysis": "Question the shared assumption", "shared_assumptions": "A tentative summary",
                 "revisions": [{**page[0], "objective": "Alternative experiment " + page[0]["role"]}]}
        return {"data": value, "conversation": receipt_for(request, sha),
                "usage": {"tokens": 9, "token_accounting": "exact", "llm_calls": 1}}
    monkeypatch.setattr(mailbox, "publish_request", lambda channel, request: digest(request))
    monkeypatch.setattr(mailbox, "wait_response", receive)
    return SimpleNamespace(db=db, config=config, root=root), original, calls


def test_review_is_charged_persisted_and_not_replayed_on_resume(memory_db, monkeypatch):
    controller, original, calls = review_fixture(memory_db, monkeypatch)
    epoch = {"id": 1, "base_commit": "base", "protocol_id": "p"}
    plan = prepare_forest(controller, epoch, {})
    assert len(calls) == 2 and plan["parallelism"] == 3
    assert plan["review_coverage"] == {"total_topics": 3, "reviewed_topics": 2, "unreviewed_topics": 1,
                                      "model_calls": 2, "stop_reason": "call_limit"}
    assert plan["children"][0]["objective"] == "Alternative experiment T1"
    assert plan["children"][2]["objective"] == "Fixture objective 3"
    assert plan["conversation"]["id"] == original["conversation"]["id"]
    assert plan["conversation"]["turn"] == 2
    assert prepare_forest(controller, epoch, {}) == plan
    assert len(calls) == 2
    slots = controller.db.rows("SELECT * FROM slots WHERE purpose LIKE 'mother:plan-review:%'")
    assert len(slots) == 2 and all(row["phase"] == "search" and row["tokens_used"] == 9 for row in slots)
    assert len(controller.db.get("timing_samples")["mother_review"]) == 2
    assert controller.db.get("mother_plan:preparation:1") == original


def test_review_skips_model_when_time_is_reserved_for_real_code(memory_db, monkeypatch):
    controller, original, calls = review_fixture(memory_db, monkeypatch)
    controller.db.set("deadline", 0)
    result = review_plan(controller, {"id": 1}, original)
    assert not calls
    assert result["plan"] == original["plan"]
    assert result["review_coverage"]["unreviewed_topics"] == 3


def test_interrupted_critique_never_restarts_native_conversation(memory_db, monkeypatch):
    controller, original, _ = review_fixture(memory_db, monkeypatch)
    def interrupted(*args):
        raise InfrastructureError("offline lost native response")
    monkeypatch.setattr(mailbox, "wait_response", interrupted)
    with pytest.raises(InfrastructureError, match="lost native"):
        review_plan(controller, {"id": 1}, original)
    with pytest.raises(InfrastructureError, match="cannot be replayed"):
        review_plan(controller, {"id": 1}, original)


@pytest.mark.parametrize("value", [-1, 1.5, True, 33])
def test_invalid_critique_budget_is_rejected(tmp_path, value):
    config = persistent_settings(tmp_path)
    config["forest"]["plan_review_calls"] = value
    with pytest.raises(ForestError, match="plan_review_calls"):
        validate(config)
