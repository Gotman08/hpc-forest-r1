"""Report validation with fixture data, not a scientific policy comparison."""

import copy
import importlib.util
from pathlib import Path

import pytest

from hpc_forest.core import digest

spec = importlib.util.spec_from_file_location(
    "compare_tree_reports", Path(__file__).resolve().parents[1] / "tools/compare_tree_reports.py")
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def report(config, binary, seconds):
    config = copy.deepcopy(config)
    config["binary_tree"] = {"enabled": binary}
    outcome = {"correct": True, "commit": "candidate", "mean_seconds": seconds}
    return {"config": config, "best_confirmed": {
        "experiment_id": "candidate", "epoch": 1, "commit": "candidate",
        "mean_seconds": seconds, "reference_seconds": 10.0,
        "evaluation_digest": digest(outcome), "improvement_fraction": 1-seconds/10,
        "is_baseline": False}, "evaluations": [
            {"phase": "search", "experiment_id": "baseline-e1", "outcome": {"tree_hash": "source"}},
            {"phase": "confirmation", "experiment_id": "baseline-e1", "outcome": {
                "correct": True, "mean_seconds": 10.0}},
            {"phase": "confirmation", "experiment_id": "candidate", "outcome": outcome}],
        "costs": {"unknown_usage_calls": 0, "tokens_used": 100},
        "experiments": [{"state": "valid"}],
        "search_topology": {"policy": "binary-greedy" if binary else "ab-mcts-a", "max_children": 2}}


def test_matched_reports_compare_confirmed_gain(config):
    result = comparison.compare(report(config, False, 3.0), report(config, True, 2.0))
    assert result["comparison_admissible"] and result["winner_for_this_pair"] == "binary"
    assert result["gain_fractions"] == {"reference": 0.7, "binary": 0.8}


def test_native_session_paths_differ_without_changing_model_settings(config):
    config["backend"] = "codex"
    config["codex"] = {"model": "gpt-6-luna", "reasoning_effort": "max",
                       "transport": "codex-mailbox", "mailbox_dir": "/new/one", "session_id": "one"}
    left, right = report(config, False, 3.0), report(config, True, 2.0)
    right["config"]["codex"].update(mailbox_dir="/new/two", session_id="two")
    assert comparison.compare(left, right)["comparison_admissible"]
    right["config"]["codex"]["reasoning_effort"] = "low"
    result = comparison.compare(left, right)
    assert not result["comparison_admissible"]
    assert result["winner_for_this_pair"] is None


@pytest.mark.parametrize("changed", ["budget", "seed", "initial_source", "confirmation", "topology", "transport"])
def test_unmatched_or_unconfirmed_reports_cannot_declare_a_winner(config, changed):
    left, right = report(config, False, 3.0), report(config, True, 2.0)
    if changed == "budget":
        right["config"]["budget"]["tokens"] += 1
    elif changed == "seed":
        right["config"]["seed"] += 1
    elif changed == "initial_source":
        right["evaluations"][0]["outcome"]["tree_hash"] = "different"
    elif changed == "confirmation":
        right["evaluations"][-1]["outcome"]["correct"] = False
    elif changed == "topology":
        right["search_topology"]["max_children"] = 3
    elif changed == "transport":
        right["experiments"][0]["state"] = "infrastructure_error"
    result = comparison.compare(left, right)
    assert not result["comparison_admissible"]
    assert result["winner_for_this_pair"] is None
