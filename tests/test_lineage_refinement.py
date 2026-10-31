"""Actual parentage, fresh dispatch and measured post-integration refinement."""
import copy
import time
from types import SimpleNamespace

import numpy as np
import pytest
from test_active_architecture import action, campaign, decision, trial  # noqa: F401
from test_active_corrections import corrected  # noqa: F401

from hpc_forest import active_control as controls
from hpc_forest import active_lifecycle as life
from hpc_forest.active_contract import decision_schema, validate_decision
from hpc_forest.active_snapshot import freeze
from hpc_forest.active_state import apply, state
from hpc_forest.core import InfrastructureError
from hpc_forest.independent_budget import assembly_admission, forecast_independent
from hpc_forest.integration_policy import _select, limits
from hpc_forest.memory.contract import empty_read
from hpc_forest.memory.store import sync_memory
from hpc_forest.search.policy import make_algorithm


def test_unrelated_ab_mcts_trial_does_not_spend_best_program_followup(corrected):  # noqa: F811
    good = trial(corrected, "T1", 6)
    life.observe(corrected.db, 1, good.id)
    # Seed 23 chooses a fresh root on its second real AB-MCTS ask.
    other = trial(corrected, "T1", 9)
    assert other.parent_id is None
    before = copy.deepcopy(state(corrected.db, 1)["lifecycle"]["protections"]["T1"])
    life.admitted(corrected.db, 1, "T1", other.id)
    life.admitted(corrected.db, 1, "T1", other.id)
    after = state(corrected.db, 1)["lifecycle"]["protections"]["T1"]
    assert after["remaining"] == before["remaining"] == 2
    assert after["admissions"] == [] and after["unrelated_admissions"] == [other.id]
    with pytest.raises(InfrastructureError, match="actual research mission"):
        life.admitted(corrected.db, 1, "T1", "invented")


def test_measured_continuation_has_real_parent_and_independent_ab_mcts_state(corrected):  # noqa: F811
    good = trial(corrected, "T1", 6)
    life.observe(corrected.db, 1, good.id)
    before = corrected.db.one("SELECT checkpoint FROM trees WHERE role='T1'")["checkpoint"]
    snap = freeze(corrected, 1)
    request = decision(snap, action("refine", "T1", sources=[good.id]))
    request = validate_decision(request, snap, {good.id})
    receipt = apply(corrected.db, 1, "refine-good", snap, request)["actions"][0]
    assert receipt["status"] == "applied" and receipt["search_root"] == good.id
    role = receipt["created_tree"]
    corrected.search.initialize(1, role, 124, root_source_id=good.id)
    child = trial(corrected, role, 5)
    assert child.parent_id == good.id and child.depth == good.depth + 1
    assert child.delegation_parent == "R/" + role
    assert child.selection["policy"] == "ab-mcts-a"
    life.admitted(corrected.db, 1, role, child.id)
    assert state(corrected.db, 1)["lifecycle"]["protections"]["T1"]["remaining"] == 1
    assert corrected.db.one("SELECT checkpoint FROM trees WHERE role='T1'")["checkpoint"] == before
    assert corrected.search.snapshot()["scored_nodes"] == 2  # Seed root supplies no extra reward.
    again = apply(corrected.db, 1, "refine-good-again", freeze(corrected, 1), request)["actions"][0]
    assert again["existing_tree"] == role


def test_refinement_schema_names_one_source_and_inherits_objective(corrected):  # noqa: F811
    good = trial(corrected, "T1", 6)
    snap = freeze(corrected, 1)
    payload = {**snap, "visible_evidence_ids": [good.id]}
    variant = next(v["properties"] for v in decision_schema(payload=payload)["properties"]["decisions"]["items"]["anyOf"]
                   if v["properties"]["kind"]["enum"] == ["refine"])
    assert "objective" not in variant and variant["source_ids"]["maxItems"] == 1
    assert variant["tree"]["enum"] == ["T1", "T2"]
    invalid = decision(snap, action("refine", "T1", sources=[]))
    with pytest.raises(InfrastructureError, match="one measured source"):
        validate_decision(invalid, snap, {good.id})


def test_seeded_search_matches_unmodified_treequest_ask_tell_sequence(corrected):  # noqa: F811
    good = trial(corrected, "T1", 6)
    corrected.search.initialize(1, "T9", 124, root_source_id=good.id)
    algorithm = make_algorithm(corrected.search.settings)
    tree = algorithm.init_tree()
    tree.tree.root.state = {"experiment_id": good.id, "commit": "T11",
                            "depth": good.depth, "seeded_root": True}
    rng = np.random.RandomState(124).get_state()
    for index in range(8):
        global_rng = np.random.get_state()
        try:
            np.random.set_state(rng)
            tree, expected = algorithm.ask(tree, ["T9"])
            rng = np.random.get_state()
        finally:
            np.random.set_state(global_rng)
        actual = trial(corrected, "T9", 5 + index)
        assert actual.parent_id == expected.parent_state["experiment_id"]
        assert actual.depth == expected.parent_state["depth"] + 1
        tree = algorithm.tell(tree, expected.trial_id, ({
            "experiment_id": actual.id, "commit": "T9" + str(index + 1), "depth": actual.depth,
            "generator": actual.generator, "search_action": actual.search_action}, .6))


def test_protected_second_assembly_cannot_finish_or_abandon_its_measured_base(corrected):  # noqa: F811
    corrected.config["forest"]["integration"] = "memory-guided-v1"
    corrected.db.set("config", corrected.config)
    corrected.search.initialize(1, "G", 23)
    combined = trial(corrected, "G", 5)
    trial(corrected, "T1", 4)  # Even a faster standalone program cannot replace this controlled base.
    post = {"steps": [{"mission_id": combined.id, "input_ids": ["baseline-e1"],
                       "outcome": {"correct": True, "mean_seconds": 5}}], "selections": []}
    corrected.db.set("postprocess:1", post)
    corrected.db.set("search_closed:1", time.time())
    sync_memory(corrected.db, corrected.root)
    observed = []
    def finish_early(mission, context, config, root):
        observed.append(copy.deepcopy(context["assembly_selection"]))
        return SimpleNamespace(tokens=1, tokens_upper_bound=False, error=None, usage={
            "assembly_decision": {"action": "finish", "read": empty_read(), "base_id": "",
                                  "source_ids": [], "idea_ids": [], "rationale": "Stop early"}})
    corrected.backend = SimpleNamespace(generate=finish_early)
    decision = _select(corrected, {"id": 1, "base_commit": "base", "protocol_id": "protocol"},
                       {"mean_seconds": 10}, post, 2, limits(corrected.config, 2))
    assert all(not item["can_finish"] and item["refinement_base_id"] == combined.id for item in observed)
    assert decision["action"] == "integrate" and decision["base_id"] == combined.id
    assert decision["controller_fallback"]


def test_slow_first_correct_is_not_a_promising_protected_lineage(corrected):  # noqa: F811
    slow = trial(corrected, "T1", 16)
    life.observe(corrected.db, 1, slow.id)
    assert not state(corrected.db, 1)["lifecycle"]["protections"]


def test_queued_snapshot_refreshes_before_first_publish_and_retains_original(corrected):  # noqa: F811
    trial(corrected, "T1", 8)
    job = controls.create(corrected, 1, "mother")
    original = job["snapshot_id"]
    later = trial(corrected, "T1", 5)
    request, _, _ = controls.begin_call(corrected, job)
    current = controls.snapshot(corrected, job)
    assert job["snapshot_id"] != original and later.id in current["trees"]["T1"]["completed_ids"]
    assert request["active_control"]["snapshot_id"] == current["snapshot_id"]
    assert (corrected.root / "logs" / job["id"] / ("snapshot-queued-" + original + ".json")).is_file()
    trial(corrected, "T1", 4)
    controls.refresh_queued(corrected, job)
    assert controls.snapshot(corrected, job) == current  # A published request is immutable.


def test_late_progress_invalidates_stale_continuation_advice(corrected):  # noqa: F811
    first = trial(corrected, "T1", 8)
    life.observe(corrected.db, 1, first.id)
    snap = freeze(corrected, 1)
    latest = trial(corrected, "T1", 5)
    life.observe(corrected.db, 1, latest.id)
    receipt = apply(corrected.db, 1, "old-advice", snap, decision(snap, action("continue", "T1")))
    assert receipt["actions"][0]["status"] == "rejected"
    assert "fresh continuation" in receipt["actions"][0]["reason"]


def test_reserve_protects_one_combination_and_one_refinement_not_all_allowed_rounds(corrected):  # noqa: F811
    corrected.config["forest"]["integration"] = "memory-guided-v1"
    corrected.config["memory"]["assembly_rounds"] = 8
    corrected.db.set("config", corrected.config)
    early = forecast_independent(corrected.db)
    assert early["integration_steps"] == 2 and early["protected_refinement_rounds"] == 1
    before = assembly_admission(corrected.db)
    assert before["protected_future_refinement_seconds"] > 0
    corrected.db.set("postprocess:1", {"steps": [{"outcome": {"correct": True}}]})
    after = assembly_admission(corrected.db)
    assert after["protected_future_refinement_seconds"] == 0
    corrected.db.set("deadline", time.time() + after["round_required_seconds"] + 1)
    assert assembly_admission(corrected.db)["can_start_round"]
    corrected.db.set("deadline", time.time() + 1)
    assert not assembly_admission(corrected.db)["can_start_round"]
