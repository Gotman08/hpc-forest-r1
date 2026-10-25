import copy
from types import SimpleNamespace

import pytest

from hpc_forest.core import ForestError, Outcome
from hpc_forest.evolution_archive import attach, fingerprint, record, select, settings, view


def entry(identifier, code, seconds=1, role="A", epoch=1):
    return {"id": identifier, "role": role, "epoch": epoch, "commit": identifier,
            "mean_seconds": seconds, "protocol_id": "p", **fingerprint({"src/main.cpp": code})}


def enable(db):
    config = db.get("config")
    config["evolution"] = {"enabled": True}
    db.set("config", config)
    db.set("protocol_id", "p")
    return config


def test_archive_keeps_champion_and_a_slow_different_solution():
    a = entry("fast", "for(int i=0;i<n;i++) a[i]+=b[i];", 1)
    b = entry("similar", "for(int i=0;i<n;i++) a[i]+=b[i]+1;", 1.01)
    c = entry("different", "sort(begin(values),end(values)); return binary_search(values,key);", 8)
    chosen = select([b, c, a], 2)
    assert [v["id"] for v in chosen] == ["fast", "different"]
    assert chosen[1]["mean_seconds"] == 8  # No invented performance for a novel source.
    duplicate = {**a, "id": "copy", "mean_seconds": 2}
    assert len(select([a, duplicate], 12)) == 1


def test_archive_scope_and_authorized_cross_tree_reuse(db):
    config = enable(db)
    for e in [entry("a", "aaaa"), entry("b", "bbbb", role="B"), entry("old", "old", epoch=2)]:
        db.set("evolution_entry:" + e["id"], e)
    own = view(db, 1, role="A")
    assert [e["id"] for e in own["entries"]] == ["a"]
    shared = view(db, 1, role="A", authorized_ids=["b"])
    assert {e["id"] for e in shared["entries"]} == {"a", "b"}
    mission = SimpleNamespace(epoch=1, role="A", import_ids=[], sources=[])
    result = attach(SimpleNamespace(config=config, db=db), mission, {})
    assert result["diverse_measured_sources"]["eligible_count"] == 1
    db.set("protocol_id", "new")
    assert view(db, 1)["entries"] == []


def test_only_correct_measured_commits_enter_archive(db, tmp_path, monkeypatch):
    config = enable(db)
    controller = SimpleNamespace(config=config, db=db, root=tmp_path)
    mission = SimpleNamespace(id="trial", epoch=1, role="A")
    monkeypatch.setattr("hpc_forest.evolution_archive.committed_source_snapshot", lambda *_: {"src/x.c": "return 1;"})
    for result in [Outcome("incorrect", correct=False, score=0), Outcome("infrastructure_error"),
                   Outcome("duplicate", correct=True), Outcome("valid", correct=True, score=0.5)]:
        record(controller, mission, result)
        assert view(db, 1)["entries"] == []
    correct = Outcome("valid", commit="c", correct=True, mean_seconds=2, score=0.3)
    before = copy.deepcopy(correct)
    record(controller, mission, correct)
    assert correct == before and view(db, 1)["entries"][0]["commit"] == "c"


@pytest.mark.parametrize("value", [[], {"enabled": 1}, {"archive_size": 100}, {"inspirations": 0}, {"judge_model": "x"}])
def test_invalid_archive_settings(value):
    with pytest.raises(ForestError):
        settings({"evolution": value})
