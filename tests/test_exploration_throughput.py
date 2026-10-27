"""Progress review and Mother cadence must leave room for measured experiments."""
import copy

from test_active_architecture import action, campaign, decision, trial  # noqa: F401
from test_active_corrections import analyze, corrected  # noqa: F401

from hpc_forest import active_control as controls
from hpc_forest import active_lifecycle as life
from hpc_forest.active_scheduler import due
from hpc_forest.active_snapshot import freeze
from hpc_forest.active_state import apply, key, state


def test_reviewed_progress_does_not_pause_each_nonprogressing_child(corrected):  # noqa: F811
    first = trial(corrected, "T1", 8)
    life.observe(corrected.db, 1, first.id)
    analyze(corrected, "T1")
    following = trial(corrected, "T1", 8.1)
    life.admitted(corrected.db, 1, "T1", following.id)
    life.observe(corrected.db, 1, following.id)
    assert not life.analysis_current(corrected.db, 1, "T1")
    assert not life.waiting_for_analysis(corrected.db, 1, "T1")
    assert due(corrected.db, 1, "T1", corrected.config["forest"]["active"]) is None
    # An asynchronous periodic report does not erase the existing source review.
    controls.create(corrected, 1, "analyst", "T1")
    assert not life.waiting_for_analysis(corrected.db, 1, "T1")
    # A genuine later improvement still requires a fresh source review.
    improved = trial(corrected, "T1", 6)
    life.observe(corrected.db, 1, improved.id)
    assert life.waiting_for_analysis(corrected.db, 1, "T1")


def test_closure_still_requires_unreviewed_descendants(corrected):  # noqa: F811
    first = trial(corrected, "T1", 8)
    life.observe(corrected.db, 1, first.id)
    analyze(corrected, "T1")
    late = trial(corrected, "T1", 8.1)
    life.admitted(corrected.db, 1, "T1", late.id)
    snap = freeze(corrected, 1)
    apply(corrected.db, 1, "close-request", snap, decision(snap, action("close")))
    assert life.analysis_needed(corrected.db, 1, "T1")
    assert not life.ready_for_mother(corrected.db, 1)


def test_mother_is_not_recalled_for_a_counter_without_a_new_report(corrected):  # noqa: F811
    one = trial(corrected, "T1")
    life.observe(corrected.db, 1, one.id)
    analyze(corrected, "T1")
    before = controls.report_watermark(state(corrected.db, 1))
    current = copy.deepcopy(state(corrected.db, 1))
    current["lifecycle"]["review_revision"] += 1
    assert controls.report_watermark(current) == before


def test_mother_batches_reports_but_idle_review_is_urgent(corrected):  # noqa: F811
    from hpc_forest.active_scheduler import mother_due

    cfg = {**corrected.config["forest"]["active"], "mother_every_reports": 2}
    trial(corrected, "T1")
    analyze(corrected, "T1")
    assert not mother_due(corrected.db, 1, cfg)
    trial(corrected, "T2")
    analyze(corrected, "T2")
    assert mother_due(corrected.db, 1, cfg)
    controls.create(corrected, 1, "mother")
    assert not mother_due(corrected.db, 1, cfg)
    current = state(corrected.db, 1)
    current["lifecycle"]["closing"] = {"id": "idle-review"}
    current["lifecycle"]["review_revision"] += 1
    corrected.db.set(key(1), current)
    assert mother_due(corrected.db, 1, cfg)


def test_single_report_is_not_starved_after_a_batch_of_new_trials(corrected):  # noqa: F811
    from hpc_forest.active_scheduler import mother_due

    cfg = {**corrected.config["forest"]["active"], "mother_every_reports": 2}
    for _ in range(3):
        trial(corrected, "T1")
    analyze(corrected, "T1")
    assert mother_due(corrected.db, 1, cfg)


def test_one_remaining_tree_does_not_wait_for_another_report(corrected):  # noqa: F811
    from hpc_forest.active_scheduler import mother_due

    cfg = {**corrected.config["forest"]["active"], "mother_every_reports": 2}
    trial(corrected, "T1")
    analyze(corrected, "T1")
    current = state(corrected.db, 1)
    current["suspended"] = ["T2"]
    corrected.db.set(key(1), current)
    assert mother_due(corrected.db, 1, cfg)
