"""Depth caps affect admission, without replacing either real search policy."""

import json
from itertools import cycle

import numpy as np
import pytest
import treequest

from hpc_forest.controller import Controller
from hpc_forest.core import BudgetExhausted, Outcome
from hpc_forest.search import Search
from hpc_forest.search.binary import BinaryGreedy, SearchExhausted


@pytest.mark.parametrize("binary", [False, True])
@pytest.mark.parametrize("max_depth", [0, 1])
def test_controller_supports_unlimited_and_bounded_real_search(
        db, tmp_path, monkeypatch, binary, max_depth):
    config = db.get("config")
    config["binary_tree"] = {"enabled": binary}
    config["budget"].update(max_depth=max_depth, search_slots=16)
    db.set("config", config)
    controller = object.__new__(Controller)
    controller.root, controller.db, controller.config = tmp_path, db, config
    controller.search = Search(db)
    assert isinstance(controller.search.algo, BinaryGreedy if binary else treequest.ABMCTSA)
    controller.search.initialize(1, "C", 23)
    if not binary:
        # Fix only the Gaussian draws: real TreeQuest compares GEN=0, CONT=1,
        # then its single child's sample=1. Each ask follows the existing chain.
        # This tests the cap without assuming a chance of descent in 16 draws.
        normal_samples = iter(())
        monkeypatch.setattr(np.random, "normal", lambda *args: next(normal_samples))
    monkeypatch.setattr(controller, "_sources", lambda mission: [])
    monkeypatch.setattr(controller, "_context", lambda *args: {"generate": True})
    worktrees = []
    monkeypatch.setattr("hpc_forest.controller.make_worktree",
                        lambda *args: worktrees.append(args[1]))
    epoch = {"id": 1, "base_commit": "base"}
    generated_depths = []
    for ordinal in range(16):
        normal_samples = cycle((0.0, 1.0, 1.0))
        try:
            mission, context, slot = controller._new_mission("C", epoch)
        except SearchExhausted:
            assert binary and max_depth == 1
            break
        if context:
            generated_depths.append(mission.depth)
            controller.search.finish(mission, Outcome(
                "valid", commit=mission.id, correct=True,
                mean_seconds=1.0 / (ordinal + 1), score=0.1 if ordinal % 2 == 0 else 0.9))
            db.settle_tokens(slot, 0)
    outcomes = [json.loads(row["result"])["status"]
                for row in db.rows("SELECT result FROM trials")]
    assert len(worktrees) == len(generated_depths)
    if max_depth == 0:
        assert max(generated_depths) == (8 if binary else 16)
        assert "depth_limited" not in outcomes
        assert len(generated_depths) == db.costs()["slots"] == 16
        with pytest.raises(BudgetExhausted):
            controller._new_mission("C", epoch)
    else:
        assert set(generated_depths) == {1}
        if binary:
            assert db.costs()["slots"] == len(generated_depths) == 2
        else:
            assert "depth_limited" in outcomes
