"""A same-tree runtime or an unsupported rejection is not a tested mechanism."""
import copy
import hashlib
import time

import pytest
from test_active_architecture import action, campaign, decision, trial  # noqa: F401
from test_active_corrections import analyze
from test_active_corrections import corrected as corrected_fixture

from hpc_forest.active_closure_evidence import validate_review
from hpc_forest.active_contract import validate_decision
from hpc_forest.active_snapshot import freeze
from hpc_forest.active_state import apply, state
from hpc_forest.core import InfrastructureError
from hpc_forest.independent_budget import forecast_independent

corrected = corrected_fixture


def record(identity, parent=None, role="T1", score=.7, correct=True):
    text = "void run() { " + identity + "(); }\n"
    return {"id": identity, "kind": "trial", "mission": {"role": role, "parent_id": parent},
            "outcome": {"commit": identity, "score": score, "correct": correct},
            "source_files": {"src/x.cpp": text}}


def cite(r):
    return {"evidence_id": r["id"], "path": "src/x.cpp", "start_line": 1, "end_line": 1,
            "sha256": hashlib.sha256(r["source_files"]["src/x.cpp"].encode()).hexdigest()}


def test_tested_requires_a_changed_measured_child_of_the_hypothesis_source():
    before, after, unrelated = record("a"), record("b", "a"), record("c", "other")
    hypothesis = {"tree": "T1", "evidence_ids": ["a"]}
    snap = {"epoch": 1, "records": [before, after, unrelated]}
    valid = {"disposition": "tested", "basis": "measured_comparison", "evidence_ids": ["a", "b"],
             "source_citations": [cite(before), cite(after)]}
    validate_review(hypothesis, valid, snap)
    for bad in ({**valid, "evidence_ids": ["b"]},
                {**valid, "evidence_ids": ["a", "c"], "source_citations": [cite(before), cite(unrelated)]},
                {**valid, "source_citations": []}):
        with pytest.raises(InfrastructureError):
            validate_review(hypothesis, bad, snap)
    broken = copy.deepcopy(snap)
    broken["records"][1]["outcome"]["score"] = None
    with pytest.raises(InfrastructureError):
        validate_review(hypothesis, valid, broken)


def test_an_incorrect_child_cannot_test_a_hypothesis():
    before, after = record("a"), record("b", "a", score=0.0, correct=False)
    hypothesis = {"tree": "T1", "evidence_ids": ["a"]}
    review = {"disposition": "tested", "basis": "measured_comparison", "evidence_ids": ["a", "b"],
              "source_citations": [cite(before), cite(after)]}
    with pytest.raises(InfrastructureError, match="measured parent-child comparison"):
        validate_review(hypothesis, review, {"epoch": 1, "records": [before, after]})


def test_rejection_needs_bounded_code_evidence_and_cannot_relabel_an_opinion_as_test():
    source = record("a")
    hypothesis, snapshot = {"tree": "T1", "evidence_ids": ["a"]}, {"epoch": 1, "records": [source]}
    review = {"disposition": "rejected", "basis": "source_or_contract", "evidence_ids": ["a"],
              "source_citations": [cite(source)]}
    validate_review(hypothesis, review, snapshot)
    with pytest.raises(InfrastructureError):
        validate_review(hypothesis, {**review, "source_citations": []}, snapshot)
    with pytest.raises(InfrastructureError):
        validate_review(hypothesis, {**review, "disposition": "tested"}, snapshot)
    bad = copy.deepcopy(review)
    bad["source_citations"][0]["sha256"] = "invented"
    with pytest.raises(InfrastructureError):
        validate_review(hypothesis, bad, snapshot)


def test_empty_rejection_cannot_permanently_close_live_forest(corrected):
    trial(corrected, "T1")
    analyze(corrected, "T1")
    snapshot = freeze(corrected, 1)
    initial = action("close")
    apply(corrected.db, 1, "request", snapshot, decision(snapshot, initial))
    snapshot = freeze(corrected, 1)
    h = snapshot["closure_hypotheses"][0]
    closing = action("close")
    closing["hypothesis_review"] = [{"report_id": h["report_id"], "index": h["index"],
        "disposition": "rejected", "basis": "source_or_contract", "evidence_ids": [],
        "source_citations": [], "reason": "I think it will be slower"}]
    result = apply(corrected.db, 1, "unsupported", snapshot, decision(snapshot, closing))
    assert result["actions"][0]["status"] == "rejected"
    assert not state(corrected.db, 1)["closed"]


def test_branch_needs_time_for_review_not_only_generation(corrected):
    source = trial(corrected, "T1")
    forecast = forecast_independent(corrected.db, ["T3"])
    corrected.db.set("deadline", time.time() + forecast["reserve_seconds"] + forecast["next_work_seconds"] + 5)
    assert forecast_independent(corrected.db, ["T3"])["can_admit"]
    snap = freeze(corrected, 1)
    result = apply(corrected.db, 1, "unreviewable", snap, decision(snap, action("branch", sources=[source.id])))
    assert result["actions"][0]["status"] == "rejected"
    assert "review" in result["actions"][0]["reason"]
    assert state(corrected.db, 1)["children"] == []


def test_mother_reexposes_an_old_analyst_citation_outside_the_catalog_page(corrected):
    from hpc_forest import active_control as controls

    first = trial(corrected, "T1", 9)
    analyze(corrected, "T1")
    for _ in range(28):
        trial(corrected, "T1", 7)
    job = controls.create(corrected, 1, "mother")
    snap = controls.snapshot(corrected, job)
    assert first.id not in {r["id"] for r in job["history"][0]["view"]["items"]}
    assert first.id in job["visible_ids"]
    page = snap["closure_code_packet"]["sources"][0]
    assert page["evidence_id"] == first.id and page["text"]
    measurement = snap["closure_code_packet"]["measurements"][0]
    assert measurement["measured_outcome"]["mean_seconds"] == 9
    h = snap["closure_hypotheses"][0]
    ref = {k: page[k] for k in ("evidence_id", "path", "sha256", "start_line", "end_line")}
    closing = action("close")
    closing["hypothesis_review"] = [{"report_id": h["report_id"], "index": h["index"],
        "disposition": "rejected", "basis": "source_or_contract", "evidence_ids": [first.id],
        "source_citations": [ref], "reason": "Inspect the immutable declaration before concluding"}]
    validate_decision(decision(snap, closing), snap, set(job["visible_ids"]))
    # Knowing an ID is insufficient: removing the actual supplied lines rejects
    # the citation. A real subsequent source read supplies those same lines.
    without = {**snap, "closure_code_packet": {"sources": []}}
    with pytest.raises(InfrastructureError, match="supplied"):
        validate_decision(decision(without, closing), without, set(job["visible_ids"]))
    validate_decision(decision(without, closing), without, set(job["visible_ids"]),
                      history=[{"view": {"citable_source": page}}])
    ref["sha256"] = "invented"
    with pytest.raises(InfrastructureError, match="supplied"):
        validate_decision(decision(snap, closing), snap, set(job["visible_ids"]))


def test_mother_source_packet_is_bounded_and_does_not_trust_report_hashes():
    from hpc_forest.active_analysis import SOURCE_LIMIT
    from hpc_forest.active_closure_evidence import packet

    records, reports = [], {}
    for i in range(18):
        item = record(str(i))
        item["source_files"]["src/x.cpp"] = ("// " + "x" * 90 + "\n") * 100
        ref = cite(item)
        ref["end_line"] = 100
        if i == 17:
            ref["sha256"] = "wrong-source"
        records.append(item)
        reports[str(i)] = {"report": {"code_findings": [{"citations": [ref]}]}}
    result = packet({"records": records, "reports_as_interpretations": reports})
    assert sum(len(p["text"]) for p in result["sources"]) <= SOURCE_LIMIT
    assert all(p["end_line"] - p["start_line"] < 40 for p in result["sources"])
    assert {o["reason"] for o in result["omitted"]} == {"excerpt_budget", "source_unavailable"}
    assert "17" not in result["selected_ids"]
