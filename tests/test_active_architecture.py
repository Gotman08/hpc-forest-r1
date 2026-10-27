"""Evidence scope, durable decisions and live control, without hosted inference."""
import copy
import json
import time
from types import SimpleNamespace

import pytest
from test_mother_conversation import complete_turn, persistent_settings, receipt_for, request_for
from test_mother_forest import decomposition

from hpc_forest import active_control as controls
from hpc_forest import codex_mailbox as mailbox
from hpc_forest.active_contract import (
    VERSION,
    decision_schema,
    enabled,
    validate_decision,
    validate_request,
    validate_settings,
)
from hpc_forest.active_scheduler import analyst_order, due
from hpc_forest.active_snapshot import freeze
from hpc_forest.active_state import apply, children, imports, key, state
from hpc_forest.codex_conversation import first_turn, next_turn
from hpc_forest.config import validate
from hpc_forest.core import ForestError, InfrastructureError, Outcome
from hpc_forest.forest import forest_width, research_roles
from hpc_forest.memory_retrieval import MemoryReader
from hpc_forest.memory_store import sync_memory
from hpc_forest.observer_contract import empty_read, schema_for
from hpc_forest.registry import Registry
from hpc_forest.search import Search


def action(kind, tree="", sources=(), evidence=()):
    return {"kind": kind, "tree": tree, "source_ids": list(sources), "evidence_ids": list(evidence),
            "subject": "New subject" if kind in {"branch", "integrate"} else "",
            "objective": "New measured experiment" if kind in {"branch", "integrate"} else "",
            "rationale": "Fixture interpretation", "stop_condition": "Stop after a measured regression"}


def decision(snapshot, *actions):
    return {"action": "decide", "snapshot_id": snapshot["snapshot_id"],
            "plan_revision": snapshot["plan_revision"], "read": empty_read(), "decisions": list(actions)}


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    cfg = persistent_settings(tmp_path)
    # Preserve the original active-loop contract as an explicit ablation. The
    # corrected defaults have separate source/closure tests and pipeline coverage.
    cfg["forest"]["active"] = {"mode": "full", "analysis_every": 1, "analysis_calls": 2, "steering_calls": 2,
                               "code_analysis": False, "closure_guards": False}
    cfg["memory"] = {"mode": "active"}
    cfg["harness"]["enabled"] = True
    validate(cfg)
    db = Registry(tmp_path / "registry.sqlite3")
    db.set("config", cfg)
    db.set("current_epoch", 1)
    db.set("protocol_id", "protocol")
    db.set("deadline", time.time() + 86400)
    db.set("research_scheduler:1", {"policy": "active-independent-v1"})
    db.connection.execute("INSERT INTO epochs VALUES(1,'base','protocol','baseline-e1',?,NULL)", (time.time(),))
    db.connection.commit()
    plan = {"protocol": "hpc-forest-mother-forest-v1", "status": "complete", "parallelism": 2,
            "children": [{"role": f"T{i}", **child} for i, child in enumerate(decomposition(2)["children"], 1)]}
    db.set("forest_plan:1", plan)
    db.record_evaluation("baseline-e1", 1, "search", {"status": "valid", "correct": True,
        "mean_seconds": 10, "score": 0.5, "commit": "base", "logs": []})
    search = Search(db)
    for role in ("T1", "T2"):
        search.initialize(1, role, 23)
    controller = SimpleNamespace(root=tmp_path, db=db, config=cfg, search=search)
    mailbox.initialize_channel(tmp_path / "mailbox", cfg["codex"]["session_id"], "offline test")
    initial = request_for(first_turn())
    db.set("mother_conversation:1", receipt_for(initial, "a" * 64))
    monkeypatch.setattr("hpc_forest.observer_snapshot.committed_source_snapshot",
                        lambda root, commit: {"src/main.c": "int " + commit + ";"})
    monkeypatch.setattr("hpc_forest.memory_store.source_evidence", lambda *args: {})
    yield controller
    db.close()


def trial(controller, role, seconds=8, *, correct=True, status="valid"):
    db = controller.db
    n = db.one("SELECT count(*) AS n FROM trials WHERE role=?", (role,))["n"] + 1
    slot = db.reserve("search", "role:" + role)
    mission = controller.search.ask(f"e1:{role}", [role], 1, "base", n, "", slot)
    outcome = Outcome(status, commit=role + str(n), tree_hash=role + str(n),
                      correct=correct, mean_seconds=seconds, score=0.6 if correct else 0)
    controller.search.finish(mission, outcome)
    db.settle_tokens(slot, 3)
    db.record_evaluation(mission.id, 1, "search", outcome.__dict__)
    return mission


def test_off_is_default_and_active_requires_persistent_mother_and_scoped_memory(tmp_path):
    cfg = persistent_settings(tmp_path)
    assert not enabled(cfg)
    validate_settings(cfg)
    cfg["forest"]["active"] = {"mode": "full"}
    with pytest.raises(ForestError, match="active per-tree memory"):
        validate_settings(cfg)
    for changes in ({"mode": "unknown"}, {"control_workers": 0}, {"analysis_calls": True}, {"surprise_gain": float("nan")}):
        cfg["forest"]["active"] = {"mode": "full", **changes}
        with pytest.raises(ForestError):
            validate_settings(cfg)


def test_final_schemas_preserve_free_report_text_and_evidence_ids():
    analyst = schema_for(True)["properties"]
    mother = decision_schema(True)["properties"]
    for schema in (analyst, mother):
        for field, value in empty_read().items():
            assert schema["read"]["properties"][field]["enum"] == [value]
    for field in ("observations", "hypotheses"):
        fields = analyst[field]["items"]["properties"]
        assert fields["claim"] == {"type": "string"}
        assert fields["evidence_ids"]["items"] == {"type": "string"}
    assert analyst["uncertainties"]["items"] == {"type": "string"}
    assert mother["snapshot_id"] == {"type": "string"}
    fields = mother["decisions"]["items"]["anyOf"][0]["properties"]
    for field in ("rationale", "stop_condition", "tree"):
        assert fields[field] == {"type": "string"}
    assert "objective" not in fields
    branch = mother["decisions"]["items"]["anyOf"][3]["properties"]
    assert "enum" not in branch["objective"]
    assert branch["source_ids"]["items"] == {"type": "string"}
    assert schema_for()["properties"]["read"]["properties"]["path"] == {"type": "string"}


def test_native_decision_schema_encodes_scope_before_model_generation(campaign):
    one = trial(campaign, "T1")
    job = controls.create(campaign, 1, "mother")
    request, _, _ = controls.begin_call(campaign, job)
    validate_request(request)
    fields = request["schema"]["properties"]
    assert fields["snapshot_id"]["enum"] == [job["snapshot_id"]]
    variants = {v["properties"]["kind"]["enum"][0]: v["properties"]
                for v in fields["decisions"]["items"]["anyOf"]}
    assert variants["continue"]["tree"]["enum"] == ["T1", "T2"]
    assert "objective" not in variants["continue"]
    assert "source_ids" not in variants["continue"]
    assert variants["share"]["source_ids"]["minItems"] == 1
    assert "tree" not in variants["integrate"]
    assert variants["integrate"]["source_ids"]["minItems"] == 2
    for variant in variants.values():
        assert one.id in variant["evidence_ids"]["items"]["enum"]
        assert "invented" not in variant["evidence_ids"]["items"]["enum"]


def test_analysts_do_not_starve_unseen_or_older_trees(campaign):
    trial(campaign, "T1")
    trial(campaign, "T2")
    controls.create(campaign, 1, "analyst", "T1")
    assert [c["role"] for c in analyst_order(campaign.db, 1)] == ["T2", "T1"]
    controls.create(campaign, 1, "analyst", "T2")
    assert [c["role"] for c in analyst_order(campaign.db, 1)] == ["T1", "T2"]


def test_snapshot_scope_imports_and_immutable_copy(campaign):
    one, two = trial(campaign, "T1"), trial(campaign, "T2")
    snap = freeze(campaign, 1, "T1")
    assert {r["id"] for r in snap["records"]} == {"baseline-e1", one.id}
    assert list(snap["trees"]) == ["T1"]
    global_snapshot = freeze(campaign, 1)
    value = decision(global_snapshot, action("share", "T1", [two.id]))
    apply(campaign.db, 1, "share-1", global_snapshot, value)
    shared = freeze(campaign, 1, "T1")
    assert two.id in {r["id"] for r in shared["records"]}
    assert two.id not in {r["id"] for r in snap["records"]}
    sync_memory(campaign.db, campaign.root)
    with MemoryReader(campaign.root, one, campaign.config, "protocol") as reader:
        with pytest.raises(ForestError, match="unavailable memory"):
            reader.exact(two.id)  # A decision never changes permissions of an admitted mission.
    one.import_ids = imports(campaign.db, 1, "T1")
    with MemoryReader(campaign.root, one, campaign.config, "protocol") as reader:
        assert reader.exact(two.id)["id"] == two.id


def test_new_branch_and_intermediate_integration_preserve_measured_source_provenance(campaign):
    one, two = trial(campaign, "T1", 8), trial(campaign, "T2", 7)
    snapshot = freeze(campaign, 1)
    data = decision(snapshot, action("branch", sources=[one.id]), action("integrate", sources=[one.id, two.id]))
    validate_decision(data, snapshot, {r["id"] for r in snapshot["records"]})
    before = campaign.search.snapshot()
    receipt = apply(campaign.db, 1, "new", snapshot, data)
    assert all(a["status"] == "applied" for a in receipt["actions"])
    assert apply(campaign.db, 1, "new", snapshot, data) == receipt
    added = state(campaign.db, 1)["children"]
    assert [c["role"] for c in added] == ["T3", "Gm1"]
    assert added[0]["base_source_id"] == one.id and added[1]["base_source_id"] == two.id
    assert research_roles(campaign.db) == ["T1", "T2", "T3"]
    assert campaign.search.snapshot() == before  # Decisions cannot write scores or select nodes.
    assert campaign.db.get("forest_plan:1")["parallelism"] == 2


def test_compact_wire_actions_preserve_internal_provenance_and_reject_nonempty_extras(campaign):
    one, two = trial(campaign, "T1"), trial(campaign, "T2", 7)
    snapshot = freeze(campaign, 1)
    keep = {"kind": "continue", "tree": "T1", "evidence_ids": [one.id],
            "rationale": "Retain measured control", "stop_condition": "One bounded test"}
    integrate = {"kind": "integrate", "source_ids": [one.id, two.id], "evidence_ids": [two.id],
                 "subject": "Combined experiment", "objective": "Measure a distinct combination",
                 "rationale": "Independent measured sources", "stop_condition": "One measured program"}
    raw = decision(snapshot, keep, integrate)
    normalized = validate_decision(raw, snapshot, {one.id, two.id})
    assert "source_ids" not in raw["decisions"][0] and "tree" not in raw["decisions"][1]
    receipt = apply(campaign.db, 1, "compact", snapshot, normalized)
    assert all(item["status"] == "applied" for item in receipt["actions"])
    assert receipt["actions"][1]["base_source_id"] == two.id
    with pytest.raises(InfrastructureError, match="does not accept source imports"):
        validate_decision(decision(snapshot, {**keep, "source_ids": [two.id]}), snapshot, {one.id, two.id})


@pytest.mark.parametrize("failure", ["incorrect", "unmeasured", "stale", "budget", "closed", "ablation"])
def test_invalid_mutations_cannot_spawn_experiments(campaign, failure):
    one = trial(campaign, "T1", correct=failure != "incorrect")
    two = trial(campaign, "T2", 7)
    snapshot = freeze(campaign, 1)
    data = decision(snapshot, action("integrate", sources=[one.id, two.id]))
    if failure == "unmeasured":
        with campaign.db.connection:
            campaign.db.connection.execute("UPDATE trials SET result=? WHERE id=?",
                (json.dumps({"correct": True, "commit": "missing"}), one.id))
    elif failure == "stale":
        current = state(campaign.db, 1)
        current["revision"] += 1
        campaign.db.set(key(1), current)
    elif failure == "budget":
        campaign.db.set("deadline", time.time() - 1)
    elif failure == "closed":
        campaign.db.set("search_closed:1", time.time())
    elif failure == "ablation":
        cfg = campaign.db.get("config")
        cfg["forest"]["active"]["mode"] = "steering"
        campaign.db.set("config", cfg)
    receipt = apply(campaign.db, 1, "invalid", snapshot, data)
    assert receipt["actions"][0]["status"] == "rejected"
    assert state(campaign.db, 1)["children"] == []


@pytest.mark.parametrize("mutation", ["made_up_id", "nonhashable_id", "changed_snapshot", "changed_objective", "unknown_tree"])
def test_typed_decisions_reject_fabricated_or_incompatible_actions(campaign, mutation):
    one = trial(campaign, "T1")
    snap = freeze(campaign, 1)
    data = decision(snap, action("continue", "T1", evidence=[one.id]))
    item = data["decisions"][0]
    if mutation == "made_up_id":
        item["evidence_ids"] = ["unseen"]
    elif mutation == "nonhashable_id":
        item["evidence_ids"] = [{}]
    elif mutation == "changed_snapshot":
        data["snapshot_id"] = "wrong"
    elif mutation == "changed_objective":
        item["objective"] = "Another task"
    else:
        item["tree"] = "T99"
    with pytest.raises(InfrastructureError):
        validate_decision(data, snap, {one.id})


def report_data(identity):
    return {"action": "report", "read": empty_read(),
            "observations": [{"claim": "Measured result", "evidence_ids": [identity]}],
            "hypotheses": [{"claim": "Unverified idea", "evidence_ids": [identity],
                            "proposed_test": "Measure the alternative", "stop_condition": "One failed test"}],
            "uncertainties": ["Offline fixture, not a performance claim"]}


def reply(controller, job, data, *, usage=True):
    request, sha, directory = controls.begin_call(controller, job)
    validate_request(request)
    response = mailbox.response_envelope(request, sha, data=data,
        usage={"tokens": 7, "token_accounting": "exact"} if usage else {})
    if job["kind"] == "mother":
        response["conversation"] = receipt_for(request, sha)
    controls.finish_call(controller, job, response, time.time())
    return request, response, directory


@pytest.mark.parametrize("kind", ["analyst", "mother"])
def test_known_malformed_reply_can_be_corrected_within_existing_call_budget(campaign, kind):
    one = trial(campaign, "T1")
    job = controls.create(campaign, 1, kind, "T1" if kind == "analyst" else None)
    snapshot = controls.snapshot(campaign, job)
    invalid = (report_data("fabricated") if kind == "analyst" else
               decision(snapshot, action("suspend", "T1", evidence=["fabricated"])))
    first, _, _ = reply(campaign, job, invalid)
    assert job["status"] == "ready" and job["calls"][0]["status"] == "failed"
    assert not state(campaign.db, 1)["suspended"]
    valid = report_data(one.id) if kind == "analyst" else decision(snapshot, action("suspend", "T1"))
    second, _, _ = reply(campaign, job, valid)
    assert job["status"] == "complete" and "error" not in job and len(job["calls"]) == 2
    assert first["nonce"] != second["nonce"]  # A new, billed turn, never a replay.
    payload = json.loads(second["messages"][1]["content"])
    assert "controller_rejection" in payload["history"][-1]
    assert second["schema"]["properties"]["action"]["enum"] == ["report" if kind == "analyst" else "decide"]
    assert sum(c["usage"]["tokens"] for c in job["calls"]) == 14
    if kind == "mother":
        assert state(campaign.db, 1)["suspended"] == ["T1"]
        assert second["conversation"]["turn"] == first["conversation"]["turn"] + 1


def test_last_malformed_decision_stops_and_reports_rejection_to_next_milestone(campaign):
    one = trial(campaign, "T1")
    job = controls.create(campaign, 1, "mother")
    job["maximum"] = 1
    snapshot = controls.snapshot(campaign, job)
    reply(campaign, job, decision(snapshot, action("continue", "T1", sources=[one.id])))
    assert job["status"] == "unavailable" and len(job["calls"]) == 1
    assert not controls.recover(campaign, 1)
    next_job = controls.create(campaign, 1, "mother")
    assert next_job["history"][-1]["controller_rejection"]["job_id"] == job["id"]
    assert not campaign.db.get("active_mother_broken:1")


def test_live_analyst_paging_coverage_costs_and_deduplication(campaign):
    one = trial(campaign, "T1")
    assert due(campaign.db, 1, "T1", {"analysis_every": 1, "surprise_gain": 0.25})
    job = controls.create(campaign, 1, "analyst", "T1")
    assert not due(campaign.db, 1, "T1", {"analysis_every": 1, "surprise_gain": 0.25})
    data = {**report_data(one.id), "action": "read", "read": {
        "operation": "source", "evidence_id": one.id, "path": "src/main.c", "offset": 0},
        "observations": [], "hypotheses": [], "uncertainties": []}
    request, _, _ = reply(campaign, job, data)
    assert "conversation" not in request and job["status"] == "ready"
    reply(campaign, job, report_data(one.id), usage=False)
    assert job["status"] == "complete" and len(job["coverage"]["reads"]) == 1
    assert state(campaign.db, 1)["analysts"]["T1"]["report_id"] == job["id"]
    assert campaign.db.costs()["unknown_usage_calls"] == 1
    assert not controls.recover(campaign, 1)


@pytest.mark.parametrize("kind", ["analyst", "mother"])
def test_interrupted_calls_never_replay_or_manufacture_zero_usage(campaign, kind):
    trial(campaign, "T1")
    job = controls.create(campaign, 1, kind, "T1" if kind == "analyst" else None)
    controls.begin_call(campaign, job)
    assert controls.recover(campaign, 1) == []
    result = campaign.db.get(controls.job_key(job["id"]))
    assert result["status"] == "unavailable"
    assert "no automatic replay" in result["error"]
    assert campaign.db.costs()["unknown_usage_calls"] == 1
    assert bool(campaign.db.get("active_mother_broken:1")) == (kind == "mother")
    assert controls.recover(campaign, 1) == []


def test_durable_response_is_applied_once_after_controller_restart(campaign):
    trial(campaign, "T1")
    job = controls.create(campaign, 1, "mother")
    request, sha, directory = controls.begin_call(campaign, job)
    snap = controls.snapshot(campaign, job)
    data = decision(snap, action("suspend", "T1"))
    response = mailbox.response_envelope(request, sha, data=data, usage={"tokens": 4, "token_accounting": "exact"},
                                         conversation=receipt_for(request, sha))
    mailbox.publish_response(campaign.root / "mailbox", response)
    controls.recover(campaign, 1)
    assert state(campaign.db, 1)["suspended"] == ["T1"]
    assert (directory / "response.json").exists()
    before = campaign.db.costs()
    controls.recover(campaign, 1)
    assert campaign.db.costs() == before
    assert len(state(campaign.db, 1)["decisions"]) == 1


def test_steering_uses_same_native_mother_and_cannot_follow_assembly(tmp_path):
    start = request_for(first_turn())
    original = complete_turn(start, "1" * 64, tmp_path / "first")
    steer = {**start, "conversation": next_turn(original["conversation"], phase="steering")}
    middle = complete_turn(steer, "2" * 64, tmp_path / "steer")
    final = {**start, "conversation": next_turn(middle["conversation"])}
    result = complete_turn(final, "3" * 64, tmp_path / "last")
    assert original["conversation"]["thread_id"] == middle["conversation"]["thread_id"] == result["conversation"]["thread_id"]
    with pytest.raises(InfrastructureError):
        next_turn(result["conversation"], phase="steering")
    with pytest.raises(InfrastructureError):
        next_turn(middle["conversation"], phase="plan-review")


def test_worker_capacity_is_explicit_and_does_not_expand_with_dynamic_trees(campaign):
    plan = copy.deepcopy(campaign.db.get("forest_plan:1"))
    plan["session_id"] = "a" * 32
    assert forest_width(plan, "a" * 32) == 2
    plan["active_control"] = {"version": VERSION, "control_workers": 1}
    assert forest_width(plan, "a" * 32) == 3
    assert len(children(campaign.db, 1)) == 2
