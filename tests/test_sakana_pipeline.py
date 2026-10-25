"""Offline recipe fixtures: real compile/test/search/confirmation, no hosted model calls."""
import json

import pytest

from hpc_forest.controller import Controller, create_workspace
from hpc_forest.reporting import package, report


@pytest.mark.parametrize("policy", [
    {"algorithm": "ab-mcts-a", "distribution": "gaussian"},
    {"algorithm": "ab-mcts-a", "distribution": "beta"},
    {"algorithm": "standard-mcts"}, {"algorithm": "repeated-sampling"},
    {"algorithm": "sequential-refinement"},
])
def test_policy_to_confirmed_delivery(config, tmp_path, need_compiler, policy):
    config["search"] = policy
    config["evolution"] = {"enabled": True}
    root = create_workspace(tmp_path / "campaign", config)
    with Controller(root) as controller:
        controller.run()
        best = controller.confirm()
        assert best and best["evaluation_digest"]
        assert not controller.db.rows("SELECT id FROM trials WHERE state='pending'")
    report(root)
    result = json.loads((root / "report/experiments.json").read_text())
    assert result["search_topology"]["policy"] == policy["algorithm"]
    assert result["diversity_archive"]["entries"]
    assert (root / "report/search-generators.csv").is_file()
    assert package(root, tmp_path / "confirmed.zip").is_file()
