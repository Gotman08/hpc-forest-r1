"""Deterministic search-policy tests; fixture timings are not HPC measurements."""

import copy
import json
import math
import sqlite3
from types import SimpleNamespace

import numpy as np
import pytest
import treequest

from hpc_forest.backends import Generated
from hpc_forest.cli import parser
from hpc_forest.config import validate
from hpc_forest.controller import Controller
from hpc_forest.core import BudgetExhausted, ForestError, InfrastructureError, Outcome
from hpc_forest.observations import measured_observations
from hpc_forest.reporting import report
from hpc_forest.search import Search, unpack
from hpc_forest.search.binary import VERSION, BinaryGreedy, SearchExhausted


def enable(db, **budget):
    config = db.get("config")
    config["binary_tree"] = {"enabled": True}
    config["budget"].update(search_slots=40, **budget)
    db.set("config", config)
    return config


def ask(db, ordinal=1, role="C"):
    search = Search(db)
    tree = search.initialize(1, role, 23)
    search.check_admission(tree, db.get("config")["budget"]["max_depth"])
    slot = db.reserve("search", role)
    return search.ask(tree, [role], 1, "base", ordinal, "unused", slot)


def finish(db, mission, seconds, *, correct=True, status="valid", score=0.5):
    outcome = Outcome(status, commit="code-" + mission.id, correct=correct,
                      mean_seconds=seconds, score=score)
    assert Search(db).finish(mission, outcome)
    return outcome


def state(db, tree="e1:C"):
    row = db.one("SELECT * FROM trees WHERE id=?", (tree,))
    return unpack(row["checkpoint"], row["sha256"])[0]


def test_default_and_legacy_configs_keep_real_ab_mcts(db):
    for setting in (None, {"enabled": False}):
        config = db.get("config")
        config.pop("binary_tree", None)
        if setting is not None:
            config["binary_tree"] = setting
        db.set("config", config)
        search = Search(db)
        assert isinstance(search.algo, treequest.ABMCTSA)
        assert not search.binary
    mission = ask(db)
    finish(db, mission, 1.0)
    assert state(db).all_rewards_store


def test_disabled_mode_matches_independent_ab_mcts_parent_choices(db):
    config = db.get("config")
    config["budget"]["search_slots"] = 16
    db.set("config", config)
    policy = treequest.ABMCTSA()
    reference = policy.init_tree()
    old_rng = np.random.get_state()
    expected, scores = [], [0.6, 0.7, 0.55, 0.8, 0.9, 0.4, 0.85, 0.75]
    try:
        np.random.seed(23)
        for ordinal, score in enumerate(scores, 1):
            reference, trial = policy.ask(reference, ["C"])
            parent = trial.parent_state
            depth = parent["depth"] + 1 if parent else 1
            expected.append((parent["commit"] if parent else "base", depth))
            reference = policy.tell(reference, trial.trial_id, ({
                "experiment_id": str(ordinal), "commit": str(ordinal), "depth": depth}, score))
    finally:
        np.random.set_state(old_rng)
    actual = []
    for ordinal, score in enumerate(scores, 1):
        mission = ask(db, ordinal)
        actual.append((mission.base_commit, mission.depth))
        Search(db).finish(mission, Outcome("valid", commit=str(ordinal), correct=True,
                                           mean_seconds=1.0, score=score))
    assert actual == expected


def test_pairs_follow_right_then_left_and_never_expand_pruned_nodes(db):
    enable(db)
    pairs = []
    parent = None
    for pair, (left_seconds, right_seconds) in enumerate(((4.0, 2.0), (1.0, 3.0), (5.0, 0.8))):
        left = ask(db, pair * 2 + 1)
        assert left.parent_id == parent
        finish(db, left, left_seconds)
        right = ask(db, pair * 2 + 2)
        assert right.parent_id == parent
        assert right.base_commit == left.base_commit
        finish(db, right, right_seconds)
        winner = left if left_seconds <= right_seconds else right
        parent = winner.id
        pairs.append((left, right, winner))
    snapshot = Search(db).snapshot()
    assert snapshot["policy"] == "binary-greedy" and snapshot["max_children"] == 2
    assert snapshot["max_depth"] == 3 and snapshot["scored_nodes"] == 6
    nodes = {n["id"]: n for n in snapshot["trees"][0]["nodes"]}
    for left, right, winner in pairs:
        loser = right if winner is left else left
        assert nodes[loser.id]["pruned"] is True
        assert nodes[loser.id]["child_count"] == 0
        assert nodes[winner.id]["pruned"] is False
        assert nodes[left.id]["side"] == "left" and nodes[right.id]["side"] == "right"
    # Pruning retains all evaluations and correct programs for final confirmation.
    assert len(db.evaluations()) == len(db.archive(1, "C")) == 6


def test_pair_is_completed_before_descent_and_tie_keeps_left(db):
    enable(db)
    left = ask(db)
    finish(db, left, 1.0)
    assert state(db).active_parent == -1
    right = ask(db, 2)
    assert right.parent_id is None
    finish(db, right, 1.0)
    descendant = ask(db, 3)
    assert descendant.parent_id == left.id
    assert descendant.base_commit == "code-" + left.id


@pytest.mark.parametrize("seconds,correct,status,score", [
    (0.01, False, "incorrect", 0.0), (0.0, True, "valid", 0.5),
    (-1.0, True, "valid", 0.5), (math.nan, True, "valid", 0.5),
    (math.inf, True, "valid", 0.5), (None, None, "infrastructure_error", None),
    (None, None, "duplicate", None),
])
def test_invalid_or_unmeasured_faster_sibling_is_not_selected(db, seconds, correct, status, score):
    enable(db)
    left = ask(db)
    finish(db, left, seconds, correct=correct, status=status, score=score)
    right = ask(db, 2)
    finish(db, right, 1.0)
    assert ask(db, 3).parent_id == right.id
    assert state(db).tree.root.children[0].score == score


def test_two_incorrect_children_stop_only_their_tree_without_new_admission(db):
    enable(db)
    for ordinal in (1, 2):
        finish(db, ask(db, ordinal), None, correct=False, status="build_failed", score=0.0)
    before = db.costs()
    with pytest.raises(SearchExhausted, match="Neither sibling"):
        ask(db, 3)
    assert db.costs() == before
    assert state(db).stopped
    assert ask(db, role="A").role == "A"


def test_depth_limit_refuses_new_children_before_reserving_budget(db):
    enable(db, max_depth=1)
    finish(db, ask(db), 2.0)
    finish(db, ask(db, 2), 1.0)
    before = db.costs()
    with pytest.raises(SearchExhausted, match="maximum depth"):
        ask(db, 3)
    assert db.costs() == before and len(state(db).tree.root.children) == 2


def test_pending_pair_is_persistent_idempotent_and_cannot_overlap(db):
    enable(db)
    left = ask(db)
    checkpoint = db.one("SELECT checkpoint FROM trees WHERE id=?", (left.tree_id,))["checkpoint"]
    with pytest.raises(ForestError, match="pending"):
        Search(db).ask(left.tree_id, ["C"], 1, "base", 2, "unused", "not-used")
    assert db.one("SELECT checkpoint FROM trees WHERE id=?", (left.tree_id,))["checkpoint"] == checkpoint
    outcome = finish(db, left, 1.0)
    assert not Search(db).finish(left, outcome)
    assert len(state(db).tree.root.children) == 1
    assert ask(db, 2).parent_id is None


def test_interrupted_child_keeps_absent_score_and_is_not_replayed(db):
    enable(db)
    left = ask(db)
    assert Search(db).recover_pending() == 1
    assert Search(db).recover_pending() == 0
    assert state(db).tree.root.children[0].score is None
    right = ask(db, 2)
    finish(db, right, 1.0)
    assert ask(db, 3).parent_id == right.id
    assert db.one("SELECT state FROM trials WHERE id=?", (left.id,))["state"] == "cancelled_interrupted"


def test_policy_switch_requires_a_fresh_campaign(db):
    Search(db).initialize(1, "C", 23)
    enable(db)
    with pytest.raises(InfrastructureError, match="new campaign"):
        ask(db)


def test_siblings_and_pruned_branches_are_absent_from_binary_observations(db, tmp_path):
    enable(db)
    left = ask(db)
    finish(db, left, 3.0)
    right = ask(db, 2)
    context = measured_observations(db, tmp_path, right)
    assert context["recent_own_role"] == context["own_role_history"] == []
    finish(db, right, 1.0)
    child = ask(db, 3)
    context = measured_observations(db, tmp_path, child)
    assert context["selected_parent"]["experiment_id"] == right.id
    assert [r["experiment_id"] for r in context["recent_own_role"]] == [right.id]
    assert [r["experiment_id"] for r in context["own_role_history"]] == [right.id]


@pytest.mark.parametrize("value", [True, "true", 1, None, {"enabled": 1}, {"enabled": "true"}])
def test_invalid_binary_switch_is_rejected(config, value):
    config["binary_tree"] = value
    with pytest.raises(ForestError, match="binary_tree.enabled"):
        validate(config)


@pytest.mark.parametrize("method", ["U", "H-enumeration"])
def test_binary_policy_rejects_shared_or_enumerated_trees(config, method):
    config.update(method=method, binary_tree={"enabled": True})
    with pytest.raises(ForestError, match="separate H trees"):
        validate(config)


def test_cli_switch_is_explicit_and_reversible():
    assert parser().parse_args(["init", "fresh"]).binary_tree is None
    assert parser().parse_args(["init", "fresh", "--binary-tree"]).binary_tree is True
    assert parser().parse_args(["init", "fresh", "--no-binary-tree"]).binary_tree is False


def controller_fixture(db, tmp_path, monkeypatch, *, depth=6):
    config = enable(db, max_depth=depth)
    config["roles"] = ["C"]
    config["schedule"].update(cycles=1, trials_per_role_per_cycle=6, integrations_per_cycle=2)
    db.set("config", config)
    db.set("current_epoch", 1)
    controller = object.__new__(Controller)
    controller.root, controller.db, controller.config = tmp_path, db, config
    controller.search = Search(db)
    controller.backend = SimpleNamespace(generate=lambda *args: Generated())
    monkeypatch.setattr(controller, "_start", lambda: None)
    monkeypatch.setattr(controller, "_baseline", lambda epoch: {"mean_seconds": 10.0})
    monkeypatch.setattr(controller, "_sources", lambda mission: [])
    monkeypatch.setattr("hpc_forest.controller.make_worktree", lambda *args: None)
    controller.evaluator = SimpleNamespace(deadline=db.get("deadline"))
    return controller


def test_controller_honors_depth_limit_and_keeps_other_tree_running(db, tmp_path, monkeypatch):
    controller = controller_fixture(db, tmp_path, monkeypatch, depth=1)
    monkeypatch.setattr(controller, "_evaluate_mission", lambda m, b: Outcome(
        "valid", commit=m.id, correct=True, mean_seconds=float(m.ordinal), score=0.5))
    result = controller.run()
    assert result["status"] == "search_complete"
    assert db.costs()["slots"] == 4  # C pair and independent G pair; no baseline fixture slot.
    assert [r["role"] for r in db.rows("SELECT role FROM trials ORDER BY created")] == ["C", "C", "G", "G"]
    assert len(db.rows("SELECT * FROM events WHERE kind='tree_exhausted'")) == 4


@pytest.mark.parametrize("depth", [0, 6])
def test_controller_budget_stop_preserves_best_candidate_and_partial_pair(
        db, tmp_path, monkeypatch, depth):
    controller = controller_fixture(db, tmp_path, monkeypatch, depth=depth)
    controller.config["budget"]["search_slots"] = 3
    db.set("config", controller.config)
    monkeypatch.setattr(controller, "_evaluate_mission", lambda m, b: Outcome(
        "valid", commit=m.id, tree_hash=m.id, correct=True,
        mean_seconds=1.0 / m.ordinal, score=0.5))
    result = controller.run()
    assert result["status"] == "budget_exhausted"
    assert len(db.archive(1, "C")) == 3
    assert Search(db).snapshot()["max_children"] == 2
    with pytest.raises(BudgetExhausted):
        db.reserve("search", "after-stop")


def test_binary_specialists_do_not_receive_integration_feedback(db, tmp_path, monkeypatch):
    controller = controller_fixture(db, tmp_path, monkeypatch)
    with db.connection:
        db.connection.execute("INSERT INTO interactions VALUES('g','[\"another-branch\"]','{}')")
    mission = ask(db)
    assert controller._context(mission, [])["interactions"] == []


def test_final_confirmation_can_retain_an_ancestor_better_than_last_pair(db, tmp_path, monkeypatch):
    controller = controller_fixture(db, tmp_path, monkeypatch)
    controller.config["schedule"]["trials_per_role_per_cycle"] = 4
    db.set("config", controller.config)
    times = [0.5, 1.0, 3.0, 2.0]
    monkeypatch.setattr(controller, "_evaluate_mission", lambda m, b: Outcome(
        "valid", commit=m.id, tree_hash=m.id, correct=True,
        mean_seconds=times[m.ordinal-1] if m.role == "C" else 4.0, score=0.5))
    controller.run()
    archived = db.archive(1, "C")
    assert archived[0]["mean_seconds"] == 0.5
    with db.connection:
        db.connection.execute("UPDATE epochs SET baseline_id='baseline-e1' WHERE id=1")
    monkeypatch.setattr("hpc_forest.controller.make_worktree", lambda *args: None)
    monkeypatch.setattr("hpc_forest.controller.git", lambda *args: None)
    def confirm(candidates, epoch):
        return {c["id"]: Outcome("valid", commit=c["commit"], correct=True,
                mean_seconds=10.0 if c.get("baseline") else next(
                    a["mean_seconds"] for a in db.archive(epoch) if a["id"] == c["id"]))
                for c in candidates}
    controller.evaluator.confirm = confirm
    # Protocol 2 promotes after a fresh interleaved series of winner and reference.
    controller.evaluator.remeasure = lambda reference, winner, epoch: {
        "reference_times": [10.0] * 3, "winner_times": [0.5] * 3, "winner_status": "valid",
        "winner_reason": "", "output_verification": "verified"}
    best = controller.confirm()
    assert best["experiment_id"] == archived[0]["id"]
    assert best["mean_seconds"] == 0.5 and not best["is_baseline"]


@pytest.mark.parametrize("depth", [0, 6])
def test_wall_deadline_stops_binary_search_before_generation(db, tmp_path, monkeypatch, depth):
    import time
    controller = controller_fixture(db, tmp_path, monkeypatch, depth=depth)
    db.set("deadline", time.time() - 1)
    calls = []
    controller.backend.generate = lambda *args: calls.append(args) or Generated()
    assert controller.run()["status"] == "budget_exhausted"
    assert calls == [] and db.costs()["slots"] == 0


@pytest.mark.parametrize("depth", [0, 6])
def test_token_limit_stops_binary_search_without_extra_generation(db, tmp_path, monkeypatch, depth):
    controller = controller_fixture(db, tmp_path, monkeypatch, depth=depth)
    controller.config["backend"] = "codex"
    controller.config["budget"].update(tokens=20, mission_tokens=10)
    db.set("config", controller.config)
    controller.backend.generate = lambda *args: Generated(tokens=7)
    monkeypatch.setattr(controller, "_evaluate_mission", lambda m, b: Outcome(
        "valid", commit=m.id, correct=True, mean_seconds=1.0, score=0.5))
    assert controller.run()["status"] == "budget_exhausted"
    assert db.costs()["tokens_used"] == 14 and db.costs()["slots"] == 2


def test_policy_objects_do_not_modify_previous_checkpoints():
    policy = BinaryGreedy()
    original = policy.init_tree()
    after_ask, trial = policy.ask(original, ["C"])
    assert original.pending is None
    after_tell = policy.tell(after_ask, trial.trial_id, ({
        "experiment_id": "left", "commit": "left", "depth": 1,
        "status": "valid", "correct": True, "mean_seconds": 1.0}, 0.5))
    assert after_ask.pending == trial and not after_ask.tree.root.children
    assert len(after_tell.tree.root.children) == 1
    assert copy.deepcopy(after_tell).pending is None


def test_binary_report_preserves_pruning_and_absent_scores(db, tmp_path):
    enable(db)
    finish(db, ask(db), None, status="infrastructure_error", correct=None, score=None)
    finish(db, ask(db, 2), 1.0)
    with sqlite3.connect(tmp_path / "registry.sqlite3") as copied:
        db.connection.backup(copied)
    assert report(tmp_path).is_file()
    payload = json.loads((tmp_path / "report/experiments.json").read_text(encoding="utf8"))
    topology = payload["search_topology"]
    assert topology["policy"] == "binary-greedy" and topology["scored_nodes"] == 1
    left = next(n for n in topology["trees"][0]["nodes"] if n.get("side") == "left")
    assert left["score"] is None and left["pruned"]



# Frozen measurements and decisions from official-depth-5af73c16/romeo-results.json.
# SHA256: c5b7408af4b5f739ab0090ad593d36dbff483402219fb38d9531200ee4889949.
# These are a recorded decision oracle, not timings to reproduce or a policy implementation.
# The corresponding archived binary_search.py SHA256 is
# 38e204860f8ec21c84bc2aeea12c3f285857b4f59ad713a315f2fb817b42a2f5.
HISTORICAL_CAMPAIGN = [('A',
  [('0571c7afb2414b21', None, 1, 0.05987244533995787, 'valid', True, 0.568420057229678),
   ('522022823068479e', None, 1, 0.04877548043926557, 'valid', True, 0.6178415155618683),
   ('bc34bbdfb30f437d',
    '522022823068479e',
    2,
    0.049008108054598175,
    'valid',
    True,
    0.6167174556494884),
   ('b892c1d2826f413e',
    '522022823068479e',
    2,
    0.04892297803113858,
    'valid',
    True,
    0.617128330293474)],
  [{'parent_id': None,
    'left_id': '0571c7afb2414b21',
    'right_id': '522022823068479e',
    'winner_id': '522022823068479e',
    'pruned_ids': ['0571c7afb2414b21'],
    'reason': 'fastest_correct_child'},
   {'parent_id': '522022823068479e',
    'left_id': 'bc34bbdfb30f437d',
    'right_id': 'b892c1d2826f413e',
    'winner_id': 'b892c1d2826f413e',
    'pruned_ids': ['bc34bbdfb30f437d'],
    'reason': 'fastest_correct_child'}]),
 ('B',
  [('437718d0bb74491c', None, 1, 0.008870001882314682, 'valid', True, 0.8988897878971567),
   ('738c84cbd9794911', None, 1, 0.025127456833918888, 'valid', True, 0.7583515654176081),
   ('14f7b27562b34e39',
    '437718d0bb74491c',
    2,
    0.008036130107939243,
    'valid',
    True,
    0.9075160950789267),
   ('6ad31031c0354a1d',
    '437718d0bb74491c',
    2,
    0.009006607656677565,
    'valid',
    True,
    0.8974922259655048)],
  [{'parent_id': None,
    'left_id': '437718d0bb74491c',
    'right_id': '738c84cbd9794911',
    'winner_id': '437718d0bb74491c',
    'pruned_ids': ['738c84cbd9794911'],
    'reason': 'fastest_correct_child'},
   {'parent_id': '437718d0bb74491c',
    'left_id': '14f7b27562b34e39',
    'right_id': '6ad31031c0354a1d',
    'winner_id': '14f7b27562b34e39',
    'pruned_ids': ['6ad31031c0354a1d'],
    'reason': 'fastest_correct_child'}]),
 ('C',
  [('217cc8d4931d4180', None, 1, 0.015504783329864344, 'valid', True, 0.8356862772720572),
   ('b5c2ba05f3c145c0', None, 1, 0.014104238090415796, 'valid', True, 0.8482767736139988),
   ('0bd29fb072a04059',
    'b5c2ba05f3c145c0',
    2,
    0.01384212945898374,
    'valid',
    True,
    0.850675317080969),
   ('a10cebf0e74d4479', 'b5c2ba05f3c145c0', 2, None, 'duplicate', None, None)],
  [{'parent_id': None,
    'left_id': '217cc8d4931d4180',
    'right_id': 'b5c2ba05f3c145c0',
    'winner_id': 'b5c2ba05f3c145c0',
    'pruned_ids': ['217cc8d4931d4180'],
    'reason': 'fastest_correct_child'},
   {'parent_id': 'b5c2ba05f3c145c0',
    'left_id': '0bd29fb072a04059',
    'right_id': 'a10cebf0e74d4479',
    'winner_id': '0bd29fb072a04059',
    'pruned_ids': ['a10cebf0e74d4479'],
    'reason': 'fastest_correct_child'}]),
 ('G',
  [('3560ac342ccd4dc4', None, 1, 0.008875148991743723, 'valid', True, 0.8988370508660373),
   ('71c26eaa16464dfd', None, 1, 0.008917057265837988, 'valid', True, 0.8984078909392833),
   ('582ee27a76ef45d5', '3560ac342ccd4dc4', 2, None, 'infrastructure_error', None, None)],
  [{'parent_id': None,
    'left_id': '3560ac342ccd4dc4',
    'right_id': '71c26eaa16464dfd',
    'winner_id': '3560ac342ccd4dc4',
    'pruned_ids': ['71c26eaa16464dfd'],
    'reason': 'fastest_correct_child'}])]


@pytest.mark.parametrize("role,trials,decisions", HISTORICAL_CAMPAIGN, ids=["A", "B", "C", "G"])
def test_restored_policy_replays_first_campaign_decisions(role, trials, decisions):
    policy = BinaryGreedy()
    tree = policy.init_tree()
    for experiment, expected_parent, depth, seconds, status, correct, score in trials:
        policy.check_admission(tree, 0)
        tree, trial = policy.ask(tree, [role])
        parent = trial.parent_state
        assert (parent["experiment_id"] if parent else None) == expected_parent
        assert (parent["depth"] + 1 if parent else 1) == depth
        tree = policy.tell(tree, trial.trial_id, ({
            "experiment_id": experiment, "commit": experiment, "depth": depth,
            "mean_seconds": seconds, "status": status, "correct": correct,
        }, score))
    assert tree.decisions == decisions
    assert not tree.stopped


@pytest.mark.parametrize("role", ["A", "B", "C", "G"])
@pytest.mark.parametrize("left_seconds,right_seconds,keep_left", [
    (1.0, 1.01, True),
    (1.01, 1.0, False),
    (1.0, 1.0, True),
    (1.0, math.nextafter(1.0, math.inf), True),
])
def test_measured_time_and_stable_ties_override_favorable_secondary_metrics(
    db, tmp_path, role, left_seconds, right_seconds, keep_left,
):
    enable(db)
    left = ask(db, role=role)
    left_log = tmp_path / "left.log"
    left_log.write_text(json.dumps({
        "vectorization": ["loop missed: a", "loop missed: b"],
        "rusage": {"max_rss_kb": 32768, "minor_page_faults": 500,
                   "cpu_utilization_ratio": 1.0, "sys_seconds": 0.25},
    }), encoding="utf8")
    assert Search(db).finish(left, Outcome(
        "valid", commit="code-" + left.id, correct=True,
        mean_seconds=left_seconds, score=0.1, logs=[str(left_log)],
    ))
    right = ask(db, 2, role=role)
    right_log = tmp_path / "right.log"
    right_log.write_text(json.dumps({
        "vectorization": ["loop optimized: a", "loop optimized: b"],
        "rusage": {"max_rss_kb": 8192, "minor_page_faults": 100,
                   "cpu_utilization_ratio": 4.0, "sys_seconds": 0.0},
    }), encoding="utf8")
    assert Search(db).finish(right, Outcome(
        "valid", commit="code-" + right.id, correct=True,
        mean_seconds=right_seconds, score=0.9, logs=[str(right_log)],
    ))
    expected = left if keep_left else right
    decision = state(db, f"e1:{role}").decisions[-1]
    assert decision["winner_id"] == expected.id
    assert decision["reason"] == "fastest_correct_child"
    assert ask(db, 3, role=role).parent_id == expected.id


@pytest.mark.parametrize("old_version", ["binary-greedy-v1", "binary-role-aware-v2"])
def test_restored_policy_requires_fresh_checkpoints(db, old_version):
    enable(db)
    search = Search(db)
    tree = search.initialize(1, "A", 23)
    assert VERSION == "binary-greedy-v3"
    assert db.one("SELECT version FROM trees WHERE id=?", (tree,))["version"] == VERSION
    with db.connection:
        db.connection.execute("UPDATE trees SET version=? WHERE id=?", (old_version, tree))
    with pytest.raises(InfrastructureError, match="new campaign"):
        Search(db).initialize(1, "A", 23)
    with pytest.raises(InfrastructureError, match="new campaign"):
        Search(db).check_admission(tree, 0)


def test_zero_depth_cap_descends_beyond_the_former_default_without_extra_budget(db):
    config = enable(db, max_depth=0)
    for pair in range(8):
        left = ask(db, pair * 2 + 1)
        finish(db, left, 1.0 / (pair + 1))
        right = ask(db, pair * 2 + 2)
        finish(db, right, 0.9 / (pair + 1))
    snapshot = Search(db).snapshot()
    assert snapshot["max_depth"] == 8 and snapshot["scored_nodes"] == 16
    assert snapshot["max_children"] == 2
    assert db.get("config")["budget"] == config["budget"]
    assert db.costs()["slots"] == 16



def test_dead_end_stops_without_reopening_a_pruned_branch(db):
    enable(db)
    left = ask(db, 1, role="A")
    finish(db, left, 1.2)
    right = ask(db, 2, role="A")
    finish(db, right, 1.0)
    first_failure = ask(db, 3, role="A")
    assert first_failure.parent_id == right.id
    finish(db, first_failure, None, correct=False, status="build_failed", score=0.0)
    second_failure = ask(db, 4, role="A")
    finish(db, second_failure, None, correct=False, status="incorrect", score=0.0)
    tree = state(db, "e1:A")
    assert tree.stopped
    assert tree.tree.root.children[0].state["pruned"]
    assert tree.decisions[-1] == {
        "parent_id": right.id, "left_id": first_failure.id, "right_id": second_failure.id,
        "winner_id": None, "pruned_ids": [first_failure.id, second_failure.id],
        "reason": "no_eligible_child",
    }
    before = db.costs()
    with pytest.raises(SearchExhausted, match="Neither sibling"):
        ask(db, 5, role="A")
    assert db.costs() == before


def test_regressed_pair_still_descends_locally_without_reopening_a_pruned_branch(db):
    enable(db)
    left = ask(db, 1, role="B")
    finish(db, left, 0.9)
    right = ask(db, 2, role="B")
    finish(db, right, 0.5)
    slower_left = ask(db, 3, role="B")
    assert slower_left.parent_id == right.id
    finish(db, slower_left, 2.0)
    slower_right = ask(db, 4, role="B")
    finish(db, slower_right, 1.8)
    tree = state(db, "e1:B")
    assert tree.tree.root.children[0].state["pruned"]
    assert tree.decisions[-1] == {
        "parent_id": right.id, "left_id": slower_left.id, "right_id": slower_right.id,
        "winner_id": slower_right.id, "pruned_ids": [slower_left.id],
        "reason": "fastest_correct_child",
    }
    assert ask(db, 5, role="B").parent_id == slower_right.id
