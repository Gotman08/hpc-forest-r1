"""Decision receipts and optional annotations must not discard evaluated work."""
from types import SimpleNamespace

import pytest
from test_memory import fact, mission
from test_memory import memory_db as memory_fixture

from hpc_forest.core import CandidateRejected, InfrastructureError
from hpc_forest.integration_policy import _select, selection_messages, validate_decision
from hpc_forest.memory.consultations import Consultations
from hpc_forest.memory.contract import empty_read, extract_memory
from hpc_forest.memory.retrieval import MemoryReader

memory_db = memory_fixture


def decision(action="integrate", base="slow"):
    return {"action": action, "read": empty_read(), "base_id": base,
            "source_ids": [base], "idea_ids": [], "rationale": "Test a complementary approach"}


def test_consultations_survive_new_round_and_connection_without_cross_campaign_access(memory_db):
    db, store, config, root = memory_db
    fact(store, "slow", seconds=10)
    fact(store, "foreign", epoch=2, protocol="q")
    db.set("forest_plan:1", {"children": [{"role": "T1", "subject": "one", "objective": "test"}]})
    with MemoryReader(root, mission("G"), config, "p") as reader:
        Consultations(db, 1, "p", "mother").remember(reader.catalog())
        resumed = Consultations(db, 1, "p", "mother")
        assert resumed.known() == {"slow"}
        assert resumed.coverage(600)["summaries_unseen"] == 599
        assert not resumed.coverage(1)["all_variants_read"]
        assert validate_decision(decision(), reader, resumed.known(), {"sources_per_integration": 3},
                                 can_finish=True, must_decide=True)["base_id"] == "slow"
        for epoch, protocol, conversation in [(2, "q", "mother"), (1, "other", "mother"), (1, "p", "new")]:
            assert not Consultations(db, epoch, protocol, conversation).known()
        with pytest.raises(InfrastructureError, match="unrelated"):
            resumed.remember({"items": [{"id": "foreign"}]})
        assert resumed.known() == {"slow"}


def test_finish_ignores_unused_legacy_ids_without_selecting_a_program(memory_db):
    _, _, config, root = memory_db
    value = decision("finish", "not-a-program")
    with MemoryReader(root, mission("G"), config, "p") as reader:
        with pytest.raises(CandidateRejected, match="before the first"):
            validate_decision(value, reader, set(), {"sources_per_integration": 3},
                              can_finish=False, must_decide=True)
        normalized = validate_decision(value, reader, set(), {"sources_per_integration": 3},
                                       can_finish=True, must_decide=True)
        assert normalized == {**value, "base_id": "", "source_ids": [], "idea_ids": []}
        with pytest.raises(CandidateRejected, match="not consulted"):
            validate_decision(decision(), reader, set(), {"sources_per_integration": 3},
                              can_finish=True, must_decide=True)


@pytest.mark.parametrize("can_finish,must_decide,actions", [
    (False, False, ["read", "integrate"]), (False, True, ["integrate"]),
    (True, True, ["integrate", "finish"]), (True, False, ["read", "integrate", "finish"])])
def test_schema_only_offers_available_actions(config, can_finish, must_decide, actions):
    context = {"assembly_selection": {"can_finish": can_finish, "must_decide": must_decide}, "memory": {}}
    assert selection_messages(context, config)["schema"]["properties"]["action"]["enum"] == actions


@pytest.mark.parametrize("prior_valid,expected", [(False, "integrate"), (True, "finish")])
def test_exhausted_selection_does_not_force_redundant_code_after_valid_integration(
    memory_db, monkeypatch, prior_valid, expected,
):
    db, store, config, root = memory_db
    fact(store, "baseline-e1")
    # Exercise the real selector with one rejected decision and no model/network calls.
    slot = db.reserve("search", "selection-fixture")
    monkeypatch.setattr(db, "reserve", lambda *args: slot)
    monkeypatch.setattr("hpc_forest.mother.mother_context", lambda c, m, x: {
        **x, "mother_conversation": {"id": "mother"}})
    monkeypatch.setattr("hpc_forest.memory.context.attach_memory", lambda c, m, x: {
        **x, "memory": {"page": {"items": []}, "catalog": {"items": [], "total": 600}}})
    monkeypatch.setattr("hpc_forest.independent_budget.assembly_admission", lambda db: {"can_read": False})
    backend = SimpleNamespace(generate=lambda *args: SimpleNamespace(
        tokens=0, tokens_upper_bound=False, error=None, usage={"assembly_decision": decision()}))
    controller = SimpleNamespace(db=db, config=config, root=root, backend=backend)
    state = {"steps": [{"mission_id": "G1", "input_ids": [], "outcome": {"correct": True}}]
             if prior_valid else [], "selections": []}
    result = _select(controller, {"id": 1, "protocol_id": "p", "base_commit": "base"},
                     {"mean_seconds": 4}, state, 1, {"rounds": 2, "selection_calls_per_round": 1})
    assert result["action"] == expected
    assert state["selections"][0]["status"] == "rejected"
    assert state["coverage"]["summaries_unseen"] == 600


@pytest.mark.parametrize("bad", [None, [{}] * 5, [{"claim": "unproven", "evidence_ids": ["invented"],
                                  "applicability": "", "next_experiment": ""}]])
def test_bad_optional_lessons_are_diagnosed_without_touching_source_or_relaxing_reads(bad):
    context = {"memory": {"enabled": True, "evidence_ids": ["known"]}}
    code = {"hypothesis": "try", "notes": "", "transformations": [], "sources_kept": [],
            "files": [{"path": "src/main.c", "content": "real code still needs validation"}]}
    rejected = []
    value = {**code, "memory_read": empty_read(), "memory_lessons": bad}
    assert extract_memory(value, context, rejected_lessons=rejected) == (code, None, [])
    assert rejected and "reason" in rejected[0]
    value["memory_read"]["operation"] = "search"
    with pytest.raises(CandidateRejected, match="cannot contain code"):
        extract_memory(value, context, rejected_lessons=[])


def test_only_invalid_lesson_is_dropped():
    good = {"claim": "a hypothesis", "evidence_ids": ["known"], "applicability": "", "next_experiment": ""}
    value = {"files": [], "memory_read": empty_read(), "memory_lessons": [good, {**good, "evidence_ids": ["fake"]}]}
    rejected = []
    assert extract_memory(value, {"memory": {"enabled": True, "evidence_ids": ["known"]}},
                          rejected_lessons=rejected)[2] == [good]
    assert rejected == [{"index": 1, "reason": "Lesson references unseen or unrelated evidence"}]


def test_missing_optional_lessons_are_reported_without_discarding_code():
    value = {"files": [{"path": "src/main.c", "content": "code awaiting controller checks"}],
             "memory_read": empty_read()}
    warnings = []
    stripped, request, lessons = extract_memory(value, {"memory": {"enabled": True}}, rejected_lessons=warnings)
    assert stripped["files"] == value["files"] and request is None and lessons == []
    assert warnings == [{"index": None, "reason": "Too many or malformed memory lessons"}]
