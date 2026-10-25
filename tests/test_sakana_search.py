"""Real TreeQuest algorithms, bounded failures and explicit per-trial model routing."""
import copy
import importlib.util
import json

import numpy as np
import pytest
import treequest as tq

from hpc_forest.config import validate
from hpc_forest.core import ForestError, InfrastructureError, Outcome
from hpc_forest.model_policy import (
    EFFORT,
    MODEL,
    generator_pool,
    mission_identity,
    require_request_identity,
)
from hpc_forest.search import Search, unpack
from hpc_forest.search_diagnostics import diagnostics
from hpc_forest.search_policy import DEFAULT, make_algorithm, settings

POLICIES = [DEFAULT, {"algorithm": "ab-mcts-a", "distribution": "beta"},
            {"algorithm": "standard-mcts"}, {"algorithm": "repeated-sampling"},
            {"algorithm": "sequential-refinement"}]
POOL = [{"model": MODEL, "reasoning_effort": EFFORT},
        {"model": "gpt-6.1-sol", "reasoning_effort": "max"},
        {"model": "gpt-6-astra", "reasoning_effort": "high"}]


def setup_search(db, policy, pool=None):
    config = db.get("config")
    config["search"] = policy
    config["budget"]["search_slots"] = 100
    if pool:
        config["backend"] = "codex"
        config["codex"]["generator_pool"] = pool
    db.set("config", config)
    search = Search(db)
    search.initialize(1, "A", 23)
    return search


def ask(search, db, ordinal, role="A", **kwargs):
    return search.ask("e1:" + role, [role], 1, "base", ordinal, "unused", db.reserve("search", role), **kwargs)


@pytest.mark.parametrize("policy", POLICIES, ids=lambda p: p["algorithm"] + p.get("distribution", ""))
def test_policies_resume_rollback_and_distinguish_incorrect_from_infrastructure(db, policy):
    search = setup_search(db, policy)
    parents, ids = [], []
    for i in range(8):
        search = Search(db)  # New object and restored RNG/state each time.
        mission = ask(search, db, i + 1)
        parents.append(mission.parent_id)
        ids.append(mission.id)
        result = Outcome("valid", correct=True, commit="code" + str(i), score=0.1 + i / 10, mean_seconds=10 - i)
        assert search.finish(mission, result)
        assert not search.finish(mission, result)
    before = search.snapshot()
    mission = ask(search, db, 9)
    search.finish(mission, Outcome("infrastructure_error", reason="unavailable"))
    assert search.snapshot() == before
    invalid = ask(search, db, 10)
    search.finish(invalid, Outcome("incorrect", correct=False, score=0.0))
    assert search.snapshot()["scored_nodes"] == 9
    if policy["algorithm"] == "repeated-sampling":
        assert parents == [None] * 8
    if policy["algorithm"] == "sequential-refinement":
        assert parents == [None] + ids[:-1]
    assert diagnostics(db.get("config"), db.rows("SELECT * FROM trials"))["models"][0]["unscored"] == 1


def test_default_parent_choices_match_unmodified_treequest(db):
    search = setup_search(db, {})
    original, state = tq.ABMCTSA(), tq.ABMCTSA().init_tree()
    native_rng = np.random.RandomState(23).get_state()
    ids = {}
    for i in range(20):
        mission = ask(search, db, i + 1)
        saved = np.random.get_state()
        np.random.set_state(native_rng)
        state, trial = original.ask(state, ["A"])
        native_rng = np.random.get_state()
        np.random.set_state(saved)
        assert mission.parent_id == (ids[trial.parent_state["i"]] if trial.parent_state else None)
        score = (i * 7 % 19) / 20
        state = original.tell(state, trial.trial_id, ({"i": i}, score))
        ids[i] = mission.id
        search.finish(mission, Outcome("valid", commit=str(i), correct=True, score=score, mean_seconds=1))


@pytest.mark.parametrize("policy", POLICIES)
def test_generator_actions_do_not_change_research_roles_or_parents(db, policy):
    search = setup_search(db, policy, POOL)
    observed = set()
    for i in range(20):
        mission = ask(search, db, i + 1)
        assert mission.role == "A" and mission.delegation_parent == "R/A"
        assert mission_identity(db.get("config"), mission) in POOL
        observed.add(mission.generator["model"])
        if mission.parent_id:
            parent = db.one("SELECT result FROM trials WHERE id=?", (mission.parent_id,))
            assert mission.base_commit == json.loads(parent["result"])["commit"]
        search.finish(mission, Outcome("valid", commit=str(i), correct=True, mean_seconds=i + 1, score=0.5))
    assert len(observed) > 1
    search.initialize(1, "G", 4)
    integration = ask(search, db, 1, "G")
    assert integration.generator == {}
    assert mission_identity(db.get("config"), integration) == POOL[0]
    search.initialize(1, "Gm1", 4)
    intermediate = ask(search, db, 1, "Gm1", route_generators=False)
    intermediate.kind = "intermediate_integration"
    assert mission_identity(db.get("config"), intermediate) == POOL[0]


def test_changed_policy_or_generator_pool_cannot_resume_checkpoint(db):
    setup_search(db, {}, POOL)
    config = db.get("config")
    config["codex"]["generator_pool"] = POOL[:2]
    db.set("config", config)
    with pytest.raises(InfrastructureError, match="policy/version changed"):
        Search(db).initialize(1, "A", 23)
    config["codex"]["generator_pool"] = POOL
    config["search"]["distribution"] = "beta"
    db.set("config", config)
    with pytest.raises(InfrastructureError, match="policy/version changed"):
        Search(db).initialize(1, "A", 23)


@pytest.mark.parametrize("bad", [None, [], {"algorithm": "fake"}, {"reward_prior": 0},
    {"reward_prior": float("nan")}, {"distribution": "bad"}, {"unused": True},
    {"algorithm": "standard-mcts", "samples_per_action": True},
    {"algorithm": "standard-mcts", "exploration_weight": float("inf")},
    {"algorithm": "ab-mcts-m", "distribution": "beta"}])
def test_invalid_policy_fails_before_search(bad):
    with pytest.raises(ForestError):
        settings({"search": bad})


def test_model_pool_is_opt_in_and_only_authorizes_research():
    primary = POOL[0]
    assert generator_pool(primary) == [primary]
    value = {**primary, "generator_pool": POOL}
    request = {**POOL[1], "kind": "source-proposal", "budget_phase": "search",
        "generator_selection": {"identity": POOL[1], "role": "T1", "action": "T1|gpt-6.1-sol|max"}}
    require_request_identity(request, value)
    for changed in [{"meta_role": "mother"}, {"conversation": {}}, {"active_control": {}},
                    {"budget_phase": "postprocess"}, {"generator_selection": None}]:
        with pytest.raises(InfrastructureError):
            require_request_identity({**request, **changed}, value)
    with pytest.raises(InfrastructureError):
        require_request_identity(request, primary)
    for pool in [[POOL[1]], [POOL[0], POOL[0]], [POOL[1], POOL[2]], None]:
        with pytest.raises(InfrastructureError):
            generator_pool({**primary, "generator_pool": pool})


def test_missing_optional_sampler_never_falls_back(monkeypatch):
    def missing(**_):
        raise ImportError("numpyro")
    monkeypatch.setattr(tq, "ABMCTSM", missing)
    with pytest.raises(InfrastructureError, match="sakana-m"):
        make_algorithm(settings({"search": {"algorithm": "ab-mcts-m"}}))


@pytest.mark.parametrize("value", [None, False, 0, ""])
def test_invalid_empty_model_pool_is_not_silently_disabled(config, value):
    config["codex"]["generator_pool"] = value
    with pytest.raises(ForestError, match="generator_pool"):
        validate(config)


@pytest.mark.parametrize("value", [None, [], "luna"])
def test_invalid_model_settings_are_rejected_before_pool_access(config, value):
    config["codex"] = value
    with pytest.raises(ForestError, match="codex must be an object"):
        validate(config)


@pytest.mark.skipif(importlib.util.find_spec("numpyro") is None, reason="Optional sakana-m environment required")
def test_optional_mixed_model_sampler_roundtrip(db):
    search = setup_search(db, {"algorithm": "ab-mcts-m"}, POOL[:2])
    for i in range(3):
        mission = ask(search, db, i + 1)
        search.finish(mission, Outcome("valid", commit=str(i), correct=True, score=0.3 + i * 0.2, mean_seconds=3 - i))
        search = Search(db)
    row = db.one("SELECT * FROM trees WHERE id='e1:A'")
    state, rng = unpack(row["checkpoint"], row["sha256"])
    assert len(state.tree.get_nodes()) == 4
    assert search.algo.max_process_workers == 1 and search.algo.enable_pruning is False
    assert len(copy.deepcopy(rng)) == 5
