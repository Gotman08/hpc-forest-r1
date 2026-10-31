"""Capability failures must not occupy the GPU again; assembly grants stay bounded."""
import copy
import time
import uuid

from test_diagnostics import diagnostic_campaign, request_for  # noqa: F401

from hpc_forest.core import atomic_json, protected_manifest
from hpc_forest.diagnostics import DiagnosticFailure, Diagnostics
from hpc_forest.diagnostics_contract import authorize, load_grant
from hpc_forest.registry import Registry


def test_missing_tool_never_waits_for_official_target_lock(diagnostic_campaign, monkeypatch):  # noqa: F811
    root, _ = diagnostic_campaign
    request = request_for(root)
    service = Diagnostics(root, request["diagnostics"], request)
    monkeypatch.setattr(service, "capabilities", lambda: {"collectors": {
        "perf-stat": {"availability": "missing", "missing_executables": ["perf"]}}})
    def locked(_):
        raise AssertionError("An absent tool must not acquire the target lock")
    monkeypatch.setattr(service, "_locked", locked)
    value = service.collect("baseline-e1", "perf-stat", "Missing counters", request_key="missing")
    assert value["status"] == "unavailable" and value["score"] is None


def test_ncu_denial_reused_across_grants_only_on_same_allocation_and_tool(diagnostic_campaign, monkeypatch, tmp_path):  # noqa: F811
    root, _ = diagnostic_campaign
    executable = tmp_path / "ncu"
    executable.write_bytes(b"same native profiler")
    monkeypatch.setattr("hpc_forest.diagnostics.shutil.which", lambda tool: str(executable) if tool == "ncu" else None)
    calls = []
    def service():
        request = request_for(root)
        obj = Diagnostics(root, request["diagnostics"], request)
        obj.grant["allocation_id"] = "123"
        monkeypatch.setattr(obj, "capabilities", lambda: {"collectors": {
            "ncu": {"availability": "probe_required", "missing_executables": []}}})
        def denied(_):
            calls.append(obj.grant["nonce"])
            path = next((root / "diagnostics/collections").glob(obj.grant["nonce"] + "-*/summary.json"))
            (path.parent / "ncu-profile.log").write_text("==ERROR== ERR_NVGPUCTRPERM: counters denied")
            raise DiagnosticFailure("permission_denied", "ncu-profile: inspect preserved ncu-profile.log")
        monkeypatch.setattr(obj, "_locked", denied)
        return obj
    first = service().collect("baseline-e1", "ncu", "Counters", request_key="one")
    second = service().collect("baseline-e1", "ncu", "Counters", request_key="two")
    assert len(calls) == 1 and first["target_permission_denied"]["code"] == "ERR_NVGPUCTRPERM"
    assert second["reused_target_capability_from"] == first["id"] and second["score"] is None
    other = service()
    other.grant["allocation_id"] = "456"
    assert "reused_target_capability_from" not in other.collect("baseline-e1", "ncu", "Counters", request_key="three")
    executable.write_bytes(b"different profiler installation")
    assert "reused_target_capability_from" not in service().collect("baseline-e1", "ncu", "Counters", request_key="four")
    assert len(calls) == 3


def test_reserved_refinement_can_profile_measured_g_with_code_and_confirmation_preserved(diagnostic_campaign):  # noqa: F811
    root, config = diagnostic_campaign
    config = copy.deepcopy(config)
    config["forest"].update(conversation="persistent", integration="memory-guided-v1",
                           active={"mode": "full", "closure_guards": True})
    config["memory"] = {"mode": "active"}
    atomic_json(root / "trusted/config.json", config)
    db = Registry(root / "registry.sqlite3")
    db.set("config", config)
    db.set("manifest", protected_manifest(root / "trusted"))
    db.set("search_closed:1", time.time())
    db.set("postprocess:1", {"steps": [{"mission_id": "g-measured", "outcome": {"correct": True}}]})
    commit = db.one("SELECT base_commit FROM epochs")["base_commit"]
    db.record_evaluation("g-measured", 1, "postprocess", {
        "commit": commit, "correct": True, "score": .7, "mean_seconds": .5})
    db.close()
    def request():
        return {"nonce": uuid.uuid4().hex, "session_id": "a" * 32, "mission_id": "g-refinement",
                "meta_role": "generator", "budget_phase": "postprocess", "expires_at": time.time() + 300}
    ordinary = request()
    authorize(root, ordinary, source_ids=["g-measured"])
    assert not load_grant(root, ordinary["diagnostics"])["can_collect"]
    reserved = request()
    authorize(root, reserved, source_ids=["g-measured"], refinement=True)
    grant = load_grant(root, reserved["diagnostics"])
    assert grant["can_collect"] and set(grant["sources"]) == {"g-measured"}
    assert 0 < grant["reserved_refinement_seconds"] <= 45
    assert grant["policy"]["request_seconds"] <= 45
    db = Registry(root / "registry.sqlite3")
    db.set("deadline", time.time() + 1)
    db.close()
    late = request()
    authorize(root, late, source_ids=["g-measured"], refinement=True)
    assert not load_grant(root, late["diagnostics"])["can_collect"]
