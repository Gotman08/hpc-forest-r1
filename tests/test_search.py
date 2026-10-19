import hashlib

import pytest

from hpc_forest.core import InfrastructureError, Outcome
from hpc_forest.search import Search, unpack


def ask(search, db, role="A", ordinal=1):
    tree = search.initialize(1, role, 23)
    slot = db.reserve("search", role)
    return search.ask(tree, [role], 1, "base", ordinal, "unused", slot)


def test_transactional_tell_is_idempotent_after_restart(db):
    mission = ask(Search(db), db)
    result = Outcome(
        "valid",
        commit="abc",
        tree_hash="def",
        correct=True,
        times=[1.0],
        mean_seconds=1.0,
        score=0.5,
    )
    assert Search(db).finish(mission, result)
    checkpoint = db.one("SELECT checkpoint FROM trees WHERE id=?", (mission.tree_id,))["checkpoint"]
    assert not Search(db).finish(mission, result)
    assert (
        checkpoint
        == db.one("SELECT checkpoint FROM trees WHERE id=?", (mission.tree_id,))["checkpoint"]
    )
    assert len(db.evaluations()) == 1


def test_integration_reward_updates_g_only(db):
    search = Search(db)
    a = ask(search, db)
    search.finish(a, Outcome("valid", commit="a", correct=True, mean_seconds=1, score=0.5))
    a_checkpoint = db.one("SELECT checkpoint FROM trees WHERE id=?", (a.tree_id,))["checkpoint"]
    g = ask(search, db, "G")
    g.sources = [a.id]
    search.finish(g, Outcome("valid", commit="g", correct=True, mean_seconds=0.7, score=0.6))
    assert (
        db.one("SELECT checkpoint FROM trees WHERE id=?", (a.tree_id,))["checkpoint"]
        == a_checkpoint
    )
    assert len(db.rows("SELECT * FROM interactions")) == 1


def test_infrastructure_error_is_unscored_and_pending_ask_is_rolled_back(db):
    search = Search(db)
    mission = ask(search, db)
    search.finish(mission, Outcome("infrastructure_error", reason="target disconnected"))
    row = db.one("SELECT * FROM trees WHERE id=?", (mission.tree_id,))
    state, _ = unpack(row["checkpoint"], row["sha256"])
    assert not state.all_rewards_store
    assert db.evaluations()[0]["outcome"]["score"] is None


def test_interrupted_mission_does_not_refund_slot_or_add_reward(db):
    mission = ask(Search(db), db)
    assert Search(db).recover_pending() == 1
    assert Search(db).recover_pending() == 0
    assert db.costs()["slots"] == 1
    assert (
        db.one("SELECT state FROM trials WHERE id=?", (mission.id,))["state"]
        == "cancelled_interrupted"
    )


def test_corrupt_checkpoint_fails_closed(db):
    search = Search(db)
    tree = search.initialize(1, "A", 23)
    with db.connection:
        db.connection.execute("UPDATE trees SET checkpoint=? WHERE id=?", (b"invalid", tree))
    with pytest.raises(InfrastructureError, match="Corrupt"):
        search.ask(tree, ["A"], 1, "base", 1, "unused", db.reserve("search", "A"))


def test_new_epoch_has_fresh_statistics(db):
    search = Search(db)
    mission = ask(search, db)
    search.finish(mission, Outcome("valid", commit="a", correct=True, mean_seconds=1, score=0.5))
    with db.connection:
        db.connection.execute("INSERT INTO epochs VALUES(2,'new-base','p',NULL,0,NULL)")
    tree = search.initialize(2, "A", 24)
    row = db.one("SELECT * FROM trees WHERE id=?", (tree,))
    assert hashlib.sha256(row["checkpoint"]).hexdigest() == row["sha256"]
    state, _ = unpack(row["checkpoint"])
    assert not state.all_rewards_store
    assert len(db.evaluations(epoch=1)) == 1


def test_enumeration_has_no_adaptive_g_observation(db):
    search = Search(db)
    tree = search.initialize(1, "G", 23)
    mission = search.ask_enumeration(tree, 1, "base", 1, "unused", db.reserve("search", "G"))
    search.finish(mission, Outcome("valid", commit="g", correct=True, mean_seconds=1, score=0.5))
    state, _ = unpack(db.one("SELECT checkpoint FROM trees WHERE id=?", (tree,))["checkpoint"])
    assert not state.all_rewards_store
    assert len(db.archive(1, "G")) == 1
