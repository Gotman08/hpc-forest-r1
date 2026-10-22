"""Memory protocol tests; invented measurements are fixtures, never benchmark claims."""
import copy
from dataclasses import asdict

import pytest

from hpc_forest.config import validate
from hpc_forest.core import CandidateRejected, ForestError, Mission, Outcome, canonical
from hpc_forest.integration_policy import limits, validate_decision
from hpc_forest.memory_context import bounded_history, source_view
from hpc_forest.memory_contract import empty_read, extract_memory, memory_contract
from hpc_forest.memory_retrieval import MemoryReader, bounded_page, evidence_ids
from hpc_forest.memory_store import MemoryStore, rebuild_memory, sync_memory
from hpc_forest.proposal_contract import SOURCE_SCHEMA
from hpc_forest.registry import Registry
from hpc_forest.search import Search


@pytest.fixture
def memory_db(tmp_path, config):
    config["memory"] = {"mode": "record-only", "context_characters": 6000, "page_size": 4}
    db = Registry(tmp_path / "registry.sqlite3")
    db.set("config", config)
    db.set("current_epoch", 1)
    db.set("deadline", None)
    db.connection.execute("INSERT INTO epochs(id,base_commit,protocol_id,created) VALUES(1,'base','p',0)")
    db.connection.execute("INSERT INTO epochs(id,base_commit,protocol_id,created) VALUES(2,'other','q',1)")
    db.connection.commit()
    store = MemoryStore(db, tmp_path)
    yield db, store, config, tmp_path
    db.close()


def fact(store, identity, *, role="T1", epoch=1, protocol="p", seconds=4, correct=True,
         claim="layout experiment", kind="experiment"):
    mission = {"id": identity, "tree_id": f"e{epoch}:{role}", "epoch": epoch, "role": role}
    with store.db.connection:
        store._put(mission, protocol, 1, identity, kind, {
            "facts": {"commit": "commit-" + identity, "base_commit": "base", "parent_id": None,
                      "outcome": {"status": "ok" if correct else "incorrect", "correct": correct,
                                  "mean_seconds": seconds, "score": None if correct is None else 0}},
            "model_interpretation": {"hypothesis": claim}})


def mission(role="T1", epoch=1):
    return Mission("next", f"e{epoch}:{role}", "trial", epoch, role, "base", None, "Mother", 1, 1, "")


def test_retrieval_includes_slow_incorrect_and_infrastructure_evidence_without_sibling_leaks(memory_db):
    db, store, config, root = memory_db
    fact(store, "fast", seconds=1, claim="simple arithmetic")
    fact(store, "slow", seconds=9, claim="transposition opens vectorization")
    fact(store, "incorrect", seconds=None, correct=False, claim="transposition boundary error")
    fact(store, "infra", seconds=None, correct=None, claim="transposition compiler unavailable")
    fact(store, "sibling", role="T2", claim="transposition")
    fact(store, "old-epoch", epoch=2, protocol="q", claim="transposition")
    fact(store, "other-protocol", protocol="other", claim="transposition")
    with MemoryReader(root, mission(), config, "p") as reader:
        page = reader.search("transposition")
        assert set(evidence_ids(page)) == {"slow", "incorrect", "infra", "fast"}
        assert page["items"][0]["id"] != "fast"
        for identity in ("sibling", "old-epoch", "other-protocol", "unknown"):
            with pytest.raises(CandidateRejected):
                reader.exact(identity)
        assert reader.exact("infra")["facts"]["outcome"]["score"] is None
        assert reader.exact("incorrect")["facts"]["outcome"]["score"] == 0
    with MemoryReader(root, mission("G"), config, "p") as reader:
        assert reader.exact("sibling")["role"] == "T2"
        with pytest.raises(CandidateRejected):
            reader.exact("old-epoch")


@pytest.mark.parametrize("width", [2, 3, 5, 7, 20, 56, 78, 500, 600])
def test_n_tree_catalogue_and_discoveries_are_paged_without_losing_coverage(memory_db, width):
    db, store, config, root = memory_db
    children = [{"role": f"T{i}", "subject": f"Subject {i}", "objective": "x" * 2000} for i in range(1, width + 1)]
    db.set("forest_plan:1", {"children": children})
    for child in children:
        fact(store, "trial-" + child["role"], role=child["role"], claim="different transformation " + child["role"])
    seen, roles = set(), set()
    with MemoryReader(root, mission("G"), config, "p") as reader:
        for query, output in ((reader.search, seen), (reader.catalog, roles)):
            offset = 0
            while offset is not None:
                page = query(offset=offset)
                assert len(canonical(page)) <= 6000
                output.update(item["id"] if "id" in item else item["role"] for item in page["items"])
                offset = page["next_offset"]
        assert len(seen) == len(roles) == width


def test_source_pages_reconstruct_exact_program_and_large_current_program_is_not_silently_clipped(memory_db):
    _, _, config, root = memory_db
    worktree = root / "work"
    (worktree / "src").mkdir(parents=True)
    content = ('const char *s = "\\n";\n' * 3000) + "// final line é"
    (worktree / "src/large.c").write_text(content, encoding="utf8", newline="")
    current = mission()
    current.worktree = str(worktree)
    context = {"memory": {"enabled": True, "max_result_characters": 6000}}
    files, view = source_view(worktree, context)
    assert files == {} and view["memory"]["source_read_required"]
    chunks, offset = [], 0
    with MemoryReader(root, current, config, "p") as reader:
        while offset is not None:
            page = reader.source("current", "src/large.c", offset)
            assert len(canonical(page)) <= 6000
            chunks.append(page["text"])
            offset = page["next_offset"]
        with pytest.raises(CandidateRejected):
            reader.source("current", "../trusted/check.py", 0)
    assert "".join(chunks) == content


def test_memory_extension_preserves_legacy_schema_and_rejects_invented_evidence():
    schema = copy.deepcopy(SOURCE_SCHEMA)
    assert memory_contract("system", schema, {}) == ("system", schema)
    proposal = {"hypothesis": "test", "notes": "", "transformations": [], "sources_kept": [], "files": []}
    assert extract_memory(proposal, {}) == (proposal, None, [])
    context = {"memory": {"enabled": True, "remaining_reads": 1, "evidence_ids": ["known"]}}
    value = {**proposal, "memory_read": {**empty_read(), "operation": "search"}, "memory_lessons": []}
    stripped, request, _ = extract_memory(value, context)
    assert stripped == proposal and request["operation"] == "search"
    value["memory_lessons"] = [{"claim": "possible improvement", "evidence_ids": ["unseen"],
                                "applicability": "same target", "next_experiment": "combine"}]
    with pytest.raises(CandidateRejected, match="unseen"):
        extract_memory(value, context)
    value["memory_lessons"][0]["evidence_ids"] = ["known"]
    assert extract_memory(value, context)[2][0]["claim"] == "possible improvement"
    value["files"] = [{"path": "src/x.c", "content": "code"}]
    with pytest.raises(CandidateRejected, match="cannot contain code"):
        extract_memory(value, context)


def test_rebuild_after_committed_trial_is_idempotent_and_does_not_touch_ab_mcts(memory_db):
    db, _, _, root = memory_db
    search = Search(db)
    tree = search.initialize(1, "A", 23)
    slot = db.reserve("search", "role:A")
    trial = search.ask(tree, ["A"], 1, "base", 1, "", slot)
    trial.hypothesis = "slow layout can enable future vectorization"
    search.update_mission(trial)
    search.finish(trial, Outcome("ok", commit="real-commit-fixture", correct=True, mean_seconds=9, score=.1))
    before = db.one("SELECT checkpoint,sha256 FROM trees WHERE id=?", (tree,))
    sync_memory(db, root)
    sync_memory(db, root)
    after = db.one("SELECT checkpoint,sha256 FROM trees WHERE id=?", (tree,))
    assert before == after
    rebuild_memory(root)
    assert before == db.one("SELECT checkpoint,sha256 FROM trees WHERE id=?", (tree,))
    assert db.one("SELECT count(*) AS n FROM memory_facts")["n"] == 1
    assert db.one("SELECT count(*) AS n FROM memory_ingested")["n"] == 1
    with MemoryReader(root, mission("G"), db.get("config"), "p") as reader:
        assert reader.exact(trial.id)["facts"]["outcome"] == asdict(Outcome(
            "ok", commit="real-commit-fixture", correct=True, mean_seconds=9, score=.1))


def test_selection_can_reuse_slow_program_but_incorrect_code_is_only_inspiration(memory_db):
    _, store, config, root = memory_db
    fact(store, "fast", seconds=1)
    fact(store, "slow", seconds=10)
    fact(store, "bad", seconds=None, correct=False)
    cfg = {"sources_per_integration": 3}
    value = {"action": "integrate", "read": empty_read(), "base_id": "slow",
             "source_ids": ["slow", "fast"], "idea_ids": ["bad"], "rationale": "complementary layout"}
    with MemoryReader(root, mission("G"), config, "p") as reader:
        assert validate_decision(value, reader, {"slow", "fast", "bad"}, cfg,
                                 can_finish=False, must_decide=True) == value
        value["source_ids"].append("bad")
        with pytest.raises(CandidateRejected, match="correct measured"):
            validate_decision(value, reader, {"slow", "fast", "bad"}, cfg, can_finish=False, must_decide=True)


def test_memory_off_does_not_create_projection_tables(tmp_path, config):
    db = Registry(tmp_path / "registry.sqlite3")
    try:
        db.set("config", config)
        sync_memory(db, tmp_path)
        assert not db.one("SELECT 1 FROM sqlite_master WHERE name='memory_facts'")
        config["memory"] = {"mode": "active"}
        with pytest.raises(ForestError, match="Active memory"):
            validate(config)
    finally:
        db.close()


@pytest.mark.parametrize("width", [2, 7, 78, 500, 600])
def test_one_budget_definition_covers_selection_code_and_all_n_topics(config, width):
    config["memory"] = {"mode": "active", "assembly_rounds": 2, "page_size": 6}
    bound = limits(config, width)
    assert bound["selection_calls_per_round"] * 6 >= width + 1
    assert bound["postprocess_slots"] == bound["selection_slots"] + bound["code_slots"]
    assert bound["code_calls_per_round"] == config["harness"]["max_attempts"] + 3


def test_escaped_long_diagnostics_and_lessons_still_fit_the_smallest_view():
    history = [{"generation_id": "trial-h01", "state": "development_failed",
                "development_outcome": {"status": "build_failed", "reason": '"\\\n' * 5000,
                                        "logs": ["x" * 2000] * 5},
                "measured_diagnostics": [{"path": "build.log", "text": '"\\\n' * 5000}]}]
    original = copy.deepcopy(history)
    view = bounded_history(history, 4000)
    assert len(canonical(view)) <= 4000
    assert view[0]["development_outcome"]["status"] == "build_failed"
    assert history == original
    item = {"id": "evidence", "model_interpretation": {"claim": '"\\\n' * 20000},
            "diagnostic": '"\\\n' * 2000, "details_are_bounded": True}
    page = bounded_page([item], offset=0, total=1, maximum=4000)
    assert len(canonical(page)) <= 4000 and page["items"][0]["id"] == "evidence"
