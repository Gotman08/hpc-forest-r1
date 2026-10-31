"""Regression cases for late results, source-grounded analysis and bounded closure."""
import copy
import csv
import json
import time

import pytest
from test_active_architecture import action, campaign, decision, reply, report_data, trial  # noqa: F401

from hpc_forest import active_control as controls
from hpc_forest import active_lifecycle as life
from hpc_forest.active_analysis import source_page, validate
from hpc_forest.active_contract import validate_decision
from hpc_forest.active_scheduler import due
from hpc_forest.active_snapshot import freeze
from hpc_forest.active_state import apply, children, key, state
from hpc_forest.controller import Controller
from hpc_forest.core import BudgetExhausted, InfrastructureError


@pytest.fixture
def corrected(campaign):  # noqa: F811 - imported pytest fixture
    campaign.config["forest"]["active"].update(code_analysis=True, closure_guards=True, analysis_every=3, surprise_gain=0.25)
    campaign.db.set("config", campaign.config)
    life.initialize(campaign.db, 1)
    return campaign


def descendant(c, source, index):
    """Use a real independently seeded TreeQuest tree, not a fabricated admission."""
    role = "T9"
    c.search.initialize(1, role, 23, root_source_id=source.id)
    child = trial(c, role, 8.1)
    life.admitted(c.db, 1, role, child.id)
    return child


def grounded(snapshot, identity):
    value = report_data(identity)
    page = snapshot["code_packet"]["sources"][0]
    value["code_findings"] = [{"mechanism": "The declaration identifies this exact source variant",
        "citations": [{k: page[k] for k in ("evidence_id", "path", "sha256", "start_line", "end_line")}]}]
    return value


def analyze(c, role):
    job = controls.create(c, 1, "analyst", role)
    dossier = controls.snapshot(c, job)
    reply(c, job, grounded(dossier, dossier["trees"][role]["completed_ids"][-1]))
    assert job["status"] == "complete"
    return job


def close(c, identity):
    snapshot = freeze(c, 1)
    value = action("close")
    reviews = []
    for h in snapshot["closure_hypotheses"]:
        finding = snapshot["reports_as_interpretations"][h["tree"]]["report"]["code_findings"][0]
        ref = finding["citations"][0]
        reviews.append({"report_id": h["report_id"], "index": h["index"],
            "disposition": "rejected", "evidence_ids": [ref["evidence_id"]],
            "reason": "The cited immutable fixture source defines this constrained experiment",
            "basis": "source_or_contract", "source_citations": [ref]})
    value["hypothesis_review"] = reviews
    return apply(c.db, 1, identity, snapshot, decision(snapshot, value))


def test_sources_are_provided_before_first_call_and_citations_are_verified(corrected):
    one = trial(corrected, "T1")
    two = trial(corrected, "T2")
    job = analyze(corrected, "T1")
    dossier = controls.snapshot(corrected, job)
    assert two.id not in dossier["code_packet"]["selected_ids"]
    assert one.id in dossier["code_packet"]["selected_ids"]
    assert job["coverage"]["provided_sources"] and job["coverage"]["cited_sources"]
    assert job["coverage"]["reads"] == []  # Preloaded exposure is not a source-page read.
    assert life.analysis_current(corrected.db, 1, "T1")
    for mutation in ("sha256", "start_line", "evidence_id"):
        invalid = grounded(dossier, one.id)
        ref = invalid["code_findings"][0]["citations"][0]
        ref[mutation] = 99999 if mutation == "start_line" else "fabricated"
        with pytest.raises(InfrastructureError, match="citation"):
            validate(invalid, dossier, job)
    with pytest.raises(InfrastructureError, match="analyze at least one"):
        validate({**grounded(dossier, one.id), "code_findings": []}, dossier, job)


def test_source_pages_never_allow_citing_partial_or_missing_lines():
    record = {"id": "test", "outcome": {"commit": "a"}, "source_files": {"main.c": "abcdef\nxyz\nlast"}}
    page = source_page(record, "main.c", 3, 8)
    assert page["start_line"] == page["end_line"] == 2 and page["text"] == "2: xyz"
    assert source_page(record, "main.c", 1, 2) is None
    assert source_page(record, "main.c", 12, 20) is None


def test_imported_recent_source_cannot_replace_own_latest_program(corrected):
    one, two = trial(corrected, "T1"), trial(corrected, "T2", 6)
    snap = freeze(corrected, 1)
    apply(corrected.db, 1, "share", snap, decision(snap, action("share", "T1", [two.id])))
    packet = freeze(corrected, 1, "T1")["code_packet"]
    assert packet["selected_ids"][0] == one.id
    assert two.id in packet["selected_ids"]


@pytest.mark.parametrize("kind", ["suspend", "close"])
def test_stop_decision_cannot_ignore_late_completed_evidence(corrected, kind):
    trial(corrected, "T1")
    snap = freeze(corrected, 1)
    late = trial(corrected, "T1", 6)
    value = action(kind, "T1" if kind == "suspend" else "")
    receipt = apply(corrected.db, 1, "stale", snap, decision(snap, value))
    assert receipt["actions"][0]["status"] == "rejected"
    assert receipt["newer_evidence_ids"] == [late.id]
    assert not state(corrected.db, 1)["closed"] and not state(corrected.db, 1)["suspended"]
    assert state(corrected.db, 1)["lifecycle"]["review_revision"] > 0


def test_late_progress_reopens_suspended_tree_and_requires_code_review(corrected):
    for _ in range(3):
        trial(corrected, "T1", 8)
    snapshot = freeze(corrected, 1)
    receipt = apply(corrected.db, 1, "suspend", snapshot, decision(snapshot, action("suspend", "T1")))
    assert receipt["actions"][0]["status"] == "applied"
    late = trial(corrected, "T1", 6)
    life.observe(corrected.db, 1, late.id)
    assert "T1" not in state(corrected.db, 1)["suspended"]
    assert life.waiting_for_analysis(corrected.db, 1, "T1")
    assert due(corrected.db, 1, "T1", corrected.config["forest"]["active"]) == "progress_or_closure_review"
    analyze(corrected, "T1")
    assert not life.waiting_for_analysis(corrected.db, 1, "T1")
    snap = freeze(corrected, 1)
    rejected = apply(corrected.db, 1, "premature-suspend", snap, decision(snap, action("suspend", "T1")))
    assert rejected["actions"][0]["status"] == "rejected"


def test_invalid_or_noisy_trials_do_not_manufacture_progress(corrected):
    bad = trial(corrected, "T1", None, correct=False, status="infrastructure_error")
    life.observe(corrected.db, 1, bad.id)
    assert not state(corrected.db, 1)["lifecycle"]["protections"]
    good = trial(corrected, "T1", 8)
    life.observe(corrected.db, 1, good.id)
    current = copy.deepcopy(state(corrected.db, 1))
    for seconds in (8.1, 7.99):
        later = trial(corrected, "T1", seconds)
        life.observe(corrected.db, 1, later.id)
    assert state(corrected.db, 1)["lifecycle"]["protections"] == current["lifecycle"]["protections"]
    life.observe(corrected.db, 1, good.id)
    assert state(corrected.db, 1)["lifecycle"]["review_revision"] == current["lifecycle"]["review_revision"]


def test_protected_trials_are_finite_and_cannot_consume_final_reserve(corrected):
    good = trial(corrected, "T1")
    life.observe(corrected.db, 1, good.id)
    assert life.protection_admissible(corrected.db, 1, "T1")
    for index in range(2):
        descendant(corrected, good, index)
    assert not life.protection_admissible(corrected.db, 1, "T1")
    current = state(corrected.db, 1)
    assert current["lifecycle"]["protections"]["T1"]["remaining"] == 0
    assert current["lifecycle"]["protected_seconds_reserved"] > 0
    later = trial(corrected, "T1", 5)
    life.observe(corrected.db, 1, later.id)
    corrected.db.set("deadline", time.time() + 1)
    assert not life.protection_admissible(corrected.db, 1, "T1")


def test_closure_drains_work_requires_fresh_reports_then_reviews_hypotheses(corrected):
    trial(corrected, "T1")
    analyze(corrected, "T1")
    corrected.db.set("research_pending:1", [{"kind": "research", "role": "T1", "phase": "generation", "started_at": time.time()}])
    first = close(corrected, "first-close")
    assert first["actions"][0]["closure_pending"] and not state(corrected.db, 1)["closed"]
    with pytest.raises(BudgetExhausted):
        Controller._new_mission(corrected, "T1", {"id": 1})
    assert not life.ready_for_mother(corrected.db, 1)
    late = trial(corrected, "T1", 7)
    corrected.db.set("research_pending:1", [])
    assert not life.ready_for_mother(corrected.db, 1)
    analyze(corrected, "T1")
    assert life.ready_for_mother(corrected.db, 1)
    snap = freeze(corrected, 1)
    invalid = apply(corrected.db, 1, "missing-review", snap, decision(snap, action("close")))
    assert invalid["actions"][0]["status"] == "rejected"
    last = close(corrected, "confirmed-close")
    assert last["actions"][0]["closure_confirmed"] and state(corrected.db, 1)["closed"]
    assert late.id in state(corrected.db, 1)["analysts"]["T1"]["reviewed_ids"]


def test_close_defers_for_bounded_progress_and_all_suspended_triggers_one_review(corrected):
    good = trial(corrected, "T1")
    life.observe(corrected.db, 1, good.id)
    analyze(corrected, "T1")
    close(corrected, "first-close")
    result = close(corrected, "review-close")
    assert result["actions"][0]["closure_deferred"] == "protected_experiments"
    assert state(corrected.db, 1)["lifecycle"]["closing"] is None
    current = state(corrected.db, 1)
    current["suspended"] = ["T1", "T2"]
    corrected.db.set(key(1), current)
    assert life.idle_review(corrected.db, 1)
    assert not life.idle_review(corrected.db, 1)


def test_protection_envelope_and_noise_do_not_reset_on_restart(corrected):
    one = trial(corrected, "T1", 8)
    row = corrected.db.one("SELECT result FROM trials WHERE id=?", (one.id,))
    result = json.loads(row["result"])
    result["times"] = [7, 8, 9]
    with corrected.db.connection:
        corrected.db.connection.execute("UPDATE trials SET result=? WHERE id=?", (json.dumps(result), one.id))
    life.observe(corrected.db, 1, one.id)
    descendant(corrected, one, 0)
    previous = state(corrected.db, 1)["lifecycle"]
    new = trial(corrected, "T1", 7.5)
    life.observe(corrected.db, 1, new.id)
    life.initialize(corrected.db, 1)
    current = state(corrected.db, 1)["lifecycle"]
    assert current["protections"] == previous["protections"]
    assert current["protected_seconds_reserved"] == previous["protected_seconds_reserved"]
    assert current["protection_limit_seconds"] == previous["protection_limit_seconds"]


def test_exhausted_or_checkpointed_tree_cannot_block_closure_forever(corrected):
    one = trial(corrected, "T1")
    life.observe(corrected.db, 1, one.id)
    analyze(corrected, "T1")
    corrected.db.set("active_unavailable:1", {"T1": "checkpoint_limit"})
    assert not life.protection_admissible(corrected.db, 1, "T1")
    close(corrected, "request")
    assert close(corrected, "finish")["actions"][0]["closure_confirmed"]


def test_unavailable_analysis_is_explicit_and_not_replayed(corrected):
    one = trial(corrected, "T1")
    life.observe(corrected.db, 1, one.id)
    job = controls.create(corrected, 1, "analyst", "T1")
    job["maximum"] = 1
    reply(corrected, job, report_data(one.id))  # Missing source analysis fails the live contract.
    assert job["status"] == "unavailable"
    assert not life.analysis_current(corrected.db, 1, "T1")
    assert life.analysis_current(corrected.db, 1, "T1", attempted=True)
    assert not due(corrected.db, 1, "T1", corrected.config["forest"]["active"])
    corrected.db.set("active_unavailable:1", {"T1": "exhausted"})
    close(corrected, "request")
    result = close(corrected, "finish")["actions"][0]
    assert result["unavailable_analyses"] == ["T1"]


def test_hypothesis_budget_excuse_and_missing_typed_review_are_rejected(corrected):
    trial(corrected, "T1")
    analyze(corrected, "T1")
    close(corrected, "request")
    snap = freeze(corrected, 1)
    with pytest.raises(InfrastructureError, match="hypothesis_review"):
        validate_decision(decision(snap, action("close")), snap, set())
    hypothesis = snap["closure_hypotheses"][0]
    value = action("close")
    value["hypothesis_review"] = [{"report_id": hypothesis["report_id"], "index": hypothesis["index"],
        "disposition": "budget", "evidence_ids": [], "reason": "No budget",
        "basis": "budget", "source_citations": []}]
    receipt = apply(corrected.db, 1, "false-budget", snap, decision(snap, value))
    assert receipt["actions"][0]["status"] == "rejected"
    assert "admission budget" in receipt["actions"][0]["reason"]


def test_ordinary_followups_end_progress_window_when_protection_envelope_is_spent(corrected):
    one = trial(corrected, "T1")
    life.observe(corrected.db, 1, one.id)
    analyze(corrected, "T1")
    current = state(corrected.db, 1)
    current["lifecycle"]["protection_limit_seconds"] = 1  # No protected generation fits.
    corrected.db.set(key(1), current)
    for n in range(2):
        child = descendant(corrected, one, n)
        life.admitted(corrected.db, 1, "T9", child.id)  # Durable admission is idempotent.
        later = trial(corrected, "T1", 8.1)
        life.observe(corrected.db, 1, later.id)
    item = state(corrected.db, 1)["lifecycle"]
    assert item["protections"]["T1"]["remaining"] == 0
    assert item["protected_seconds_reserved"] == 0
    assert not life.analysis_needed(corrected.db, 1, "T1")
    assert not due(corrected.db, 1, "T1", corrected.config["forest"]["active"])
    assert len(corrected.db.rows("SELECT * FROM events WHERE kind='active_unprotected_followup'")) == 2


def test_trees_created_by_one_decision_receive_distinct_roles(corrected):
    one, two = trial(corrected, "T1", 6), trial(corrected, "T2", 7)
    snapshot = freeze(corrected, 1)
    request = validate_decision(decision(snapshot, action("refine", "T1", sources=[one.id]),
                                         action("refine", "T2", sources=[two.id])),
                                snapshot, {one.id, two.id})
    receipt = apply(corrected.db, 1, "two-refinements", snapshot, request)
    assert [a["status"] for a in receipt["actions"]] == ["applied", "applied"]
    created = [a["created_tree"] for a in receipt["actions"]]
    roles = [c["role"] for c in children(corrected.db, 1)]
    assert len(set(created)) == 2 and len(roles) == len(set(roles))
    # Each continuation imports only its own measured source, never the other tree's program.
    imports = state(corrected.db, 1)["imports"]
    assert imports[created[0]] == [one.id] and imports[created[1]] == [two.id]


def test_exported_decision_rationales_never_become_spreadsheet_formulas(corrected, tmp_path):
    from hpc_forest.active_reporting import export

    trial(corrected, "T1")
    snapshot = freeze(corrected, 1)
    value = action("suspend", "T1")
    value["rationale"] = '=HYPERLINK("https://example.invalid","open")'
    apply(corrected.db, 1, "formula", snapshot, validate_decision(decision(snapshot, value), snapshot, set()))
    export(corrected.db, tmp_path)
    with (tmp_path / "active-decisions.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [row["rationale"] for row in rows] == ["'" + value["rationale"]]


def test_protection_envelope_is_shared_by_every_progress(corrected):
    from hpc_forest.independent_budget import forecast_independent

    one = trial(corrected, "T1", 6)
    life.observe(corrected.db, 1, one.id)
    current = state(corrected.db, 1)
    # Room for one protected follow-up in the whole campaign.
    current["lifecycle"]["protection_limit_seconds"] = 1.5 * forecast_independent(
        corrected.db, ["T9"])["candidate_work_seconds"]
    corrected.db.set(key(1), current)
    descendant(corrected, one, 0)
    assert state(corrected.db, 1)["lifecycle"]["protected_seconds_reserved"] > 0
    assert not life.protection_admissible(corrected.db, 1, "T1")
    two = trial(corrected, "T2", 6)
    life.observe(corrected.db, 1, two.id)
    assert state(corrected.db, 1)["lifecycle"]["protections"]["T2"]["remaining"]
    assert not life.protection_admissible(corrected.db, 1, "T2")
