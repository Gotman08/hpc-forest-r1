"""Replay the latest-failure blind spot without model calls or GPU measurements."""
import json

import pytest
from test_memory import fact, mission
from test_memory import memory_db as memory_fixture

from hpc_forest.core import canonical
from hpc_forest.memory.retrieval import MemoryReader, evidence_ids

memory_db = memory_fixture


def test_tree_summary_keeps_valid_slow_alternatives_after_a_failure(memory_db):
    db, store, config, root = memory_db
    db.set("forest_plan:1", {"children": [{"role": "T1", "subject": "Topic", "objective": "Explore"}]})
    fact(store, "best", seconds=1)
    fact(store, "slow", seconds=9, claim="A different program may combine well")
    fact(store, "latest-failed", seconds=None, correct=False)
    fact(store, "unmeasured", seconds=None, correct=None)
    fact(store, "development", kind="development")
    fact(store, "other-protocol", protocol="q", seconds=.01)
    fact(store, "sibling", role="T2", seconds=.001)
    with db.connection:
        db.connection.execute("UPDATE memory_facts SET created=10 WHERE id='latest-failed'")
    with MemoryReader(root, mission("G"), config, "p") as reader:
        page = reader.catalog()
    item = page["items"][0]
    assert item["results"] == {"trials": 4, "valid": 2, "incorrect": 1, "unmeasured": 1}
    assert item["records"] == 5
    assert item["best"]["id"] == "best"
    assert item["alternative"]["id"] == "slow"
    assert item["latest"]["id"] == "latest-failed"
    assert set(evidence_ids(page)) == {"best", "slow", "latest-failed"}


def test_an_identical_program_is_not_an_alternative(memory_db):
    db, store, config, root = memory_db
    db.set("forest_plan:1", {"children": [{"role": "T1", "subject": "Topic", "objective": "Explore"}]})
    fact(store, "best", seconds=1)
    fact(store, "duplicate", seconds=2)
    with db.connection:
        for row in db.rows("SELECT id,payload FROM memory_facts"):
            value = json.loads(row["payload"])
            value["facts"]["outcome"]["tree_hash"] = "same-program-and-launch"
            db.connection.execute("UPDATE memory_facts SET payload=? WHERE id=?", (canonical(value), row["id"]))
    with MemoryReader(root, mission("G"), config, "p") as reader:
        assert reader.catalog()["items"][0]["alternative"] is None


@pytest.mark.parametrize("width", [2, 20, 600])
def test_small_catalogue_budget_preserves_all_topics_and_facts(memory_db, width):
    db, store, config, root = memory_db
    config["memory"].update(page_size=20, context_characters=4000)
    db.set("forest_plan:1", {"children": [
        {"role": f"T{i}", "subject": '"\\' * 1000, "objective": "x" * 4000} for i in range(width)]})
    for i in range(width):
        fact(store, f"fast-{i}", role=f"T{i}", seconds=1)
        fact(store, f"slow-{i}", role=f"T{i}", seconds=8)
    offset, roles = 0, set()
    with MemoryReader(root, mission("G"), config, "p") as reader:
        while offset is not None:
            page = reader.catalog(offset)
            assert len(canonical(page)) <= 4000
            for item in page["items"]:
                assert item["results"]["valid"] == 2
                roles.add(item["role"])
            following = page["next_offset"]
            assert following is None or following > offset
            offset = following
    assert len(roles) == width
