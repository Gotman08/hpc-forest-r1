"""Search stop guards and real grant limits; no reward or TreeQuest substitution."""
import time

import pytest
from test_active_architecture import action, campaign, decision, trial  # noqa: F401
from test_diagnostics import diagnostic_campaign, request_for  # noqa: F401

from hpc_forest.active_lifecycle import observe
from hpc_forest.active_snapshot import freeze
from hpc_forest.active_state import apply, state
from hpc_forest.diagnostics import DiagnosticFailure, Diagnostics


def suspend(controller, name):
    controller.config["forest"]["active"]["closure_guards"] = True
    controller.db.set("config", controller.config)
    snap = freeze(controller, 1)
    return apply(controller.db, 1, name, snap, decision(snap, action("suspend", "T1")))["actions"][0]


def test_one_numeric_failure_keeps_a_bounded_repair_window(campaign):  # noqa: F811
    trial(campaign, "T1", None, correct=False, status="incorrect")
    assert suspend(campaign, "first")["status"] == "rejected"
    trial(campaign, "T1", None, correct=False, status="incorrect")
    assert suspend(campaign, "second")["status"] == "rejected"
    trial(campaign, "T1", None, correct=False, status="incorrect")
    assert suspend(campaign, "third")["status"] == "applied"
    assert state(campaign.db, 1)["suspended"] == ["T1"]


def test_suspension_preserves_admitted_work_and_late_progress_reopens(campaign):  # noqa: F811
    for _ in range(3):
        trial(campaign, "T1")
    pending = [{"role": "T1", "kind": "research", "phase": "generation", "started_at": time.time()}]
    campaign.db.set("research_pending:1", pending)
    result = suspend(campaign, "inflight")
    assert result["status"] == "applied" and state(campaign.db, 1)["suspended"] == ["T1"]
    assert campaign.db.get("research_pending:1") == pending
    late = trial(campaign, "T1", seconds=4)
    campaign.db.set("research_pending:1", [])
    observe(campaign.db, 1, late.id)
    assert state(campaign.db, 1)["suspended"] == []
    assert state(campaign.db, 1)["lifecycle"]["protections"]["T1"]["source_id"] == late.id


def test_pending_work_does_not_replace_a_measured_repair(campaign):  # noqa: F811
    for _ in range(2):
        trial(campaign, "T1", None, correct=False, status="incorrect")
    campaign.db.set("research_pending:1", [{"role": "T1", "kind": "research", "phase": "generation",
                                          "started_at": time.time()}])
    assert suspend(campaign, "third-pending")["status"] == "rejected"


def test_repair_floor_does_not_bypass_confirmation_budget(campaign):  # noqa: F811
    trial(campaign, "T1", None, correct=False, status="incorrect")
    campaign.db.set("deadline", time.time() + 1)
    assert suspend(campaign, "budget")["status"] == "applied"


def test_survey_accounts_for_every_tool_and_reuses_exact_source(diagnostic_campaign, monkeypatch):  # noqa: F811
    root, _ = diagnostic_campaign
    request = request_for(root, "generator")
    service = Diagnostics(root, request["diagnostics"], request)
    runtime = service.collect("baseline-e1", "runtime", "Control", request_key="runtime")
    calls = []

    def unavailable(source, collector, question, **kwargs):
        calls.append(collector)
        raise DiagnosticFailure("permission_denied", "Synthetic denied collector")

    monkeypatch.setattr(service, "collect", unavailable)
    survey = service.survey("baseline-e1", "Compare the optimized mechanism", "suite")
    assert len(survey["collectors"]) == 10 and len(calls) == 9
    reused = next(r for r in survey["collectors"] if r["collector"] == "runtime")
    assert reused["reused"] and reused["id"] == runtime["id"]
    assert all(r["score"] is None for r in survey["collectors"])
    assert survey["status"] == "partial"
    service.grant["can_collect"] = False
    with pytest.raises(DiagnosticFailure, match="read-only"):
        service.survey("baseline-e1", "Denied", "denied")
