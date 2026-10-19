import json
from dataclasses import replace

from hpc_forest.core import Outcome, digest
from hpc_forest.observations import measured_observations
from hpc_forest.search import Search, unpack


def ask(db, role="A", ordinal=1):
    search = Search(db)
    tree = search.initialize(1, role, 23)
    slot = db.reserve("search", role)
    return search.ask(tree, [role], 1, "base", ordinal, "unused", slot)


def broken_parent(db, tmp_path):
    db.set("protocol_id", "p")
    log = tmp_path / "logs/build.log"
    log.parent.mkdir()
    log.write_text(json.dumps({"diagnostic": {"stderr": "missing compiler token"}}))
    mission = ask(db)
    key = digest({"tree": "bad-tree", "protocol": "p", "epoch": 1})
    Search(db).finish(
        mission,
        Outcome(
            "build_failed",
            commit="bad",
            tree_hash="bad-tree",
            cache_key=key,
            score=0.0,
            correct=False,
            logs=[str(log)],
        ),
    )
    return mission


def test_cross_role_duplicate_retains_real_failure_without_adding_a_reward(db, tmp_path):
    parent = broken_parent(db, tmp_path)
    duplicate = ask(db, "C")
    Search(db).finish(duplicate, Outcome("duplicate", commit="same-code", tree_hash="bad-tree"))
    pending = ask(db, "C", 2)
    before = db.costs()
    context = measured_observations(db, tmp_path, pending)
    item = context["recent_own_role"][0]
    assert item["outcome"]["status"] == "duplicate" and item["outcome"]["score"] is None
    assert item["duplicate_of"]["experiment_id"] == parent.id
    assert item["duplicate_of"]["measured_outcome"]["status"] == "build_failed"
    assert (
        item["duplicate_of"]["raw_logs"][0]["runner_output"]["diagnostic"]["stderr"]
        == "missing compiler token"
    )
    assert db.costs() == before
    row = db.one("SELECT * FROM trials WHERE id=?", (pending.id,))
    state, _ = unpack(row["before_state"])
    assert not state.all_rewards_store


def test_selected_parent_diagnostic_survives_recent_history_window(db, tmp_path):
    parent = broken_parent(db, tmp_path)
    for ordinal in range(2, 5):
        mission = ask(db, ordinal=ordinal)
        Search(db).finish(mission, Outcome("duplicate", tree_hash="bad-tree"))
    pending = replace(ask(db, ordinal=5), parent_id=parent.id, base_commit="bad")
    context = measured_observations(db, tmp_path, pending)
    assert parent.id not in [r["experiment_id"] for r in context["recent_own_role"]]
    assert context["selected_parent"]["experiment_id"] == parent.id
    assert (
        context["selected_parent"]["raw_logs"][0]["runner_output"]["diagnostic"]["stderr"]
        == "missing compiler token"
    )
    assert context["selected_base_commit"] == "bad"


def test_feedback_includes_baseline_timing_and_confines_diagnostics(db, tmp_path):
    mission = broken_parent(db, tmp_path)
    outside = tmp_path.parent / "outside-diagnostic.log"
    outside.write_text("outside content")
    db.record_evaluation(
        "baseline-e1",
        1,
        "search",
        {
            "status": "valid",
            "correct": True,
            "mean_seconds": 0.1,
            "score": 0.5,
            "logs": [str(outside)],
        },
    )
    context = measured_observations(db, tmp_path, mission)
    assert context["baseline"]["outcome"]["mean_seconds"] == 0.1
    assert context["baseline"]["raw_logs"] == []


def test_duplicate_resolution_does_not_cross_protocol_boundaries(db, tmp_path):
    broken_parent(db, tmp_path)
    duplicate = ask(db, "C")
    Search(db).finish(duplicate, Outcome("duplicate", tree_hash="bad-tree"))
    db.set("protocol_id", "different-protocol")
    item = measured_observations(db, tmp_path, ask(db, "C", 2))["recent_own_role"][0]
    assert "duplicate_of" not in item
