"""Real TreeQuest admission, rollback and no-future-data regression tests."""
import json

import numpy as np
import pytest
from test_advisor import controller as controller_fixture
from test_advisor import mission, mock_response, seed_context

from hpc_forest import advisor
from hpc_forest.advisor_features import FEATURES, feature_vector, trajectory
from hpc_forest.config import validate
from hpc_forest.core import ForestError, Outcome
from hpc_forest.search import Search, unpack

controller = controller_fixture


@pytest.mark.parametrize("changes", [{"search": {"algorithm": "sequential-refinement"}},
                                    {"method": "U"}, {"binary_tree": {"enabled": True}}])
def test_incompatible_policy_cannot_silently_claim_advice(config, changes):
    config.update(changes)
    config["advisor"] = {"enabled": True}
    with pytest.raises(ForestError, match="TabPFN parent advice"):
        validate(config)


def populate(db):
    config = db.get("config")
    config["budget"]["search_slots"] = 100
    db.set("config", config)
    search = Search(db)
    tree = search.initialize(1, "T1", 23)
    for i in range(6):
        m = search.ask(tree, ["T1"], 1, "base", i + 1, "", db.reserve("search", "T1"))
        search.finish(m, Outcome("valid", commit=f"code{i}", correct=True, score=0.55 + i * .03, mean_seconds=1))
    return search, tree


def test_proposals_commit_only_the_chosen_treequest_ask(db):
    search, tree = populate(db)
    initial = db.one("SELECT * FROM trees WHERE id=?", (tree,))
    before, _ = unpack(initial["checkpoint"])
    proposed = []
    def select(items):
        assert db.one("SELECT count(*) n FROM trials WHERE state='pending'")["n"] == 0
        proposed.extend(items)
        return items[-1].id
    m = search.ask(tree, ["T1"], 1, "base", 7, "", db.reserve("search", "T1"), advisor=select)
    assert len(proposed) >= 2
    assert m.id == proposed[-1].id and m.parent_id == proposed[-1].parent_id
    assert m.selection["selected_proposal"] == len(proposed) - 1
    assert db.one("SELECT count(*) n FROM trials")["n"] == 7
    assert db.one("SELECT count(*) n FROM trials WHERE state='pending'")["n"] == 1
    pending, _ = unpack(db.one("SELECT checkpoint FROM trees WHERE id=?", (tree,))["checkpoint"])
    assert pending.all_rewards_store == before.all_rewards_store
    search.finish(m, Outcome("valid", commit="new", correct=True, score=.8, mean_seconds=.5))
    state, _ = unpack(db.one("SELECT checkpoint FROM trees WHERE id=?", (tree,))["checkpoint"])
    nodes = [n for n in state.tree.get_nodes() if n.state and n.state["experiment_id"] == m.id]
    assert len(nodes) == 1
    actual_parent = nodes[0].parent.state
    assert (actual_parent["experiment_id"] if actual_parent else None) == m.parent_id
    assert len(state.all_rewards_store["T1"]) == len(before.all_rewards_store["T1"]) + 1


def test_fallback_keeps_exact_original_parent_rng_and_rollback(db):
    search, tree = populate(db)
    initial = db.one("SELECT * FROM trees WHERE id=?", (tree,))
    plain = search.ask(tree, ["T1"], 1, "base", 7, "", db.reserve("search", "T1"))
    plain_state, plain_rng = unpack(db.one("SELECT checkpoint FROM trees WHERE id=?", (tree,))["checkpoint"])
    search.finish(plain, Outcome("infrastructure_error"))
    # Compare from exactly the same pre-admission checkpoint. Cancellation
    # intentionally retains RNG progress in Forest, so rewind only this fixture.
    with db.connection:
        db.connection.execute("UPDATE trees SET checkpoint=?,sha256=? WHERE id=?",
                              (initial["checkpoint"], initial["sha256"], tree))
    global_rng = np.random.get_state()
    advised = search.ask(tree, ["T1"], 1, "base", 7, "", db.reserve("search", "T1"),
                         advisor=lambda items: items[0].id)
    state, rng = unpack(db.one("SELECT checkpoint FROM trees WHERE id=?", (tree,))["checkpoint"])
    assert (plain.parent_id, plain.base_commit, plain.depth) == (advised.parent_id, advised.base_commit, advised.depth)
    assert plain_state.all_rewards_store == state.all_rewards_store
    assert all(np.array_equal(a, b) for a, b in zip(plain_rng, rng, strict=True))
    assert all(np.array_equal(a, b) for a, b in zip(global_rng, np.random.get_state(), strict=True))
    search.finish(advised, Outcome("infrastructure_error"))
    rolled_back, retained_rng = unpack(db.one("SELECT checkpoint FROM trees WHERE id=?", (tree,))["checkpoint"])
    before, _ = unpack(initial["checkpoint"])
    assert rolled_back.all_rewards_store == before.all_rewards_store
    assert all(np.array_equal(a, b) for a, b in zip(retained_rng, rng, strict=True))


def test_incorrect_measured_child_is_informative_but_infrastructure_is_not(controller):
    m = mission("bad", controller.root)
    advisor.capture(controller, m)
    advisor.observe(controller, m, Outcome("incorrect", correct=False, score=0, commit="bad-code"))
    rows = advisor.samples(controller.db, 1, 128)
    assert len(rows) == 1 and rows[0]["target"] == -.5
    advisor.observe(controller, m, Outcome("infrastructure_error"))
    assert advisor.samples(controller.db, 1, 128) == rows


def test_parent_source_frozen_and_later_outcomes_do_not_change_features(controller, monkeypatch):
    m = mission("child", controller.root)
    calls = []
    def source(repo, commit):
        calls.append(commit)
        return {"src/f.cpp": "int f(){ for(int i=0;i<8;i++){ if(i){return i;} } return 0;}"}
    monkeypatch.setattr(advisor, "committed_source_snapshot", source)
    frozen = advisor.capture(controller, m)
    (controller.root / "child/src/main.cpp").write_text("future child's different source")
    assert advisor.capture(controller, m) == frozen and calls == ["base"]
    assert frozen["features"][FEATURES.index("max_brace_depth")] == 3
    assert frozen["feature_stage"] == "before_generation" and "target" not in frozen
    before = json.dumps(frozen, sort_keys=True)
    advisor.observe(controller, m, Outcome("valid", correct=True, score=.9, mean_seconds=.1, commit="child-code"))
    assert json.dumps(controller.db.get("advisor_features:" + m.id), sort_keys=True) == before


def test_structure_features_distinguish_equal_keyword_counts(controller):
    m = mission("a", controller.root)
    nested = feature_vector({"f": "for(;;){for(;;){x++;}}"}, m)
    separate = feature_vector({"f": "for(;;){x++;}for(;;){}"}, m)
    assert nested[FEATURES.index("for")] == separate[FEATURES.index("for")] == 2
    assert nested != separate and len(nested) == len(FEATURES)


def test_new_tree_root_uses_its_actual_measured_base(controller):
    search = Search(controller.db)
    tree = search.initialize(1, "T1", 23)
    old = search.ask(tree, ["T1"], 1, "base", 1, "", controller.db.reserve("search", "T1"))
    outcome = Outcome("valid", commit="optimized-base", correct=True, mean_seconds=.5, score=.8)
    search.finish(old, outcome)
    new = mission("new", controller.root)
    new.base_commit = "optimized-base"
    ratio, values = trajectory(controller.db, new, 2, .5)
    assert ratio == pytest.approx(np.log(.25)) and values[0] == .8 and values[1] == 1


def test_selection_compares_expected_child_value_not_only_parent_gain(controller, monkeypatch):
    seed_context(controller)
    a, b = [mission(n, controller.root) for n in ("slow", "fast")]
    for candidate, score in ((a, .2), (b, .9)):
        entry = advisor.capture(controller, candidate)
        entry["parent_score"] = score
        entry["features"][FEATURES.index("parent_score")] = score
        controller.db.set("advisor_features:" + candidate.id, entry)
    mock_response(monkeypatch, [.6, .05])
    assert advisor.choose(controller, [a, b]) == b.id
    event = json.loads(controller.db.rows("SELECT payload FROM events WHERE kind='advisor_decision'")[-1]["payload"])
    assert event["expected_child_scores"] == pytest.approx([.8, .95])
    mock_response(monkeypatch, [.1, -.6])
    assert advisor.choose(controller, [a, b]) == a.id  # Same predicted value: preserve TreeQuest.
