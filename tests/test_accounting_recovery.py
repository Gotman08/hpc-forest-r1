"""Settlement state distinguishes an exact zero charge from an unused reservation."""

import sqlite3

import pytest

from hpc_forest.registry import Registry
from hpc_forest.search import Search


@pytest.mark.parametrize("binary", [False, True])
@pytest.mark.parametrize("used,upper_bound", [(0, False), (42, False), (0, True), (42, True),
                                              (None, False)])
def test_recovery_preserves_every_settled_charge(db, binary, used, upper_bound):
    config = db.get("config")
    config["backend"] = "codex"
    config["binary_tree"] = {"enabled": binary}
    db.set("config", config)
    search = Search(db)
    tree = search.initialize(1, "A", 23)
    slot = db.reserve("search", "A", 1000)
    search.ask(tree, ["A"], 1, "base", 1, "unused", slot)
    db.settle_tokens(slot, used, upper_bound=upper_bound)
    before = db.costs()
    assert search.recover_pending() == 1
    assert search.recover_pending() == 0
    assert db.costs() == before
    assert db.one("SELECT tokens_settled FROM slots WHERE id=?", (slot,))["tokens_settled"] == 1
    db.settle_tokens(slot, None)
    assert db.costs() == before


def test_unsettled_zero_reservation_remains_distinct_from_exact_zero(db):
    first = db.reserve("search", "not-settled", 0)
    second = db.reserve("search", "exact-zero", 0)
    db.settle_tokens(second, 0)
    assert db.one("SELECT tokens_settled FROM slots WHERE id=?", (first,))["tokens_settled"] == 0
    assert db.one("SELECT tokens_settled FROM slots WHERE id=?", (second,))["tokens_settled"] == 1
    db.settle_tokens(first, None)
    db.settle_tokens(second, None)
    assert db.costs()["unknown_usage_calls"] == 1


def test_legacy_slot_migration_preserves_zero_and_unknown_settlements(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE slots(id TEXT PRIMARY KEY,phase TEXT NOT NULL,"
                           "purpose TEXT NOT NULL,tokens_reserved INTEGER NOT NULL,"
                           "tokens_used INTEGER NOT NULL DEFAULT 0,"
                           "usage_known INTEGER NOT NULL DEFAULT 1,created REAL NOT NULL)")
        connection.executemany("INSERT INTO slots VALUES(?,?,?,?,?,?,?)", [
            ("exact-zero", "search", "A", 0, 0, 1, 0.0),
            ("unknown", "search", "B", 0, 70, 0, 0.0),
            ("reserved", "search", "C", 80, 0, 1, 0.0),
        ])
    db = Registry(path)
    try:
        assert {row["id"]: row["tokens_settled"] for row in db.rows("SELECT * FROM slots")} == {
            "exact-zero": 1, "unknown": 1, "reserved": 0}
        before = db.costs()
        db.settle_tokens("exact-zero", None)
        db.settle_tokens("unknown", None)
        assert db.costs() == before
        db.settle_tokens("reserved", None)
        assert db.costs()["tokens_used"] == 150
        assert db.costs()["unknown_usage_calls"] == 2
    finally:
        db.close()
    reopened = Registry(path)
    try:
        assert all(row["tokens_settled"] == 1 for row in reopened.rows("SELECT * FROM slots"))
    finally:
        reopened.close()
