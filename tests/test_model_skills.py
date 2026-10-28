"""Exercise skill delivery, audit declarations and the complete N-tree lifecycle."""
import copy
import hashlib
import json
from importlib.resources import files

import pytest
from test_depth_campaign import load_tool
from test_mother_conversation import native_campaign

from hpc_forest import codex_process
from hpc_forest.core import CandidateRejected, InfrastructureError, Mission
from hpc_forest.model_skills import (
    FIELD,
    NAMES,
    PHASE_SKILLS,
    SHARED,
    campaign_traces,
    consume_report,
    policy,
    validate_settings,
    verify_binding,
)
from hpc_forest.mother import render_plan
from hpc_forest.reporting import report
from hpc_forest.source_request import proposal_messages


def proposal(tmp_path, role="T1", *, attempt=1):
    source = tmp_path / "src"
    source.mkdir(exist_ok=True)
    (source / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf8")
    context = {"mother_assembly": role == "G",
               "automatic_observations": {"node_development": {"attempt": attempt}}}
    if role != "G":
        context["research_tree"] = {"role": role, "objective": "Investigate this arbitrary program."}
    mission = Mission("fixture", "e1:" + role, "local", 1, role, "base", None,
                      "root", 1, 1, str(tmp_path))
    rendered = proposal_messages(tmp_path, mission, context, skills=policy())
    if role == "G":
        rendered["meta_role"] = "mother-final-assembly"
    return {"nonce": "a" * 32, "session_id": "b" * 32, "mission_id": mission.id,
            "model": codex_process.MODEL, "reasoning_effort": codex_process.EFFORT,
            "token_policy": "observe-only", **rendered}


@pytest.mark.parametrize("role", ["T1", "T5", "T137", "G"])
@pytest.mark.parametrize("attempt", [1, 2])
def test_each_child_and_assembly_repair_get_their_full_versioned_instructions(tmp_path, role, attempt):
    request = proposal(tmp_path, role, attempt=attempt)
    manifest = verify_binding(request)
    phase = "assembly" if role == "G" else "research"
    assert manifest["role"] == ("Mother" if role == "G" else role)
    assert {entry["name"] for entry in manifest["loaded"]} == {PHASE_SKILLS[phase], *SHARED}
    for entry in manifest["loaded"]:
        raw = files("hpc_forest").joinpath(entry["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
        assert raw.decode("utf8") in request["messages"][0]["content"]
    assert FIELD in request["schema"]["required"]


@pytest.mark.parametrize("phase", ["preparation", "investigation"])
def test_planning_uses_its_own_skills_and_preserves_base_schema(phase):
    rendered = render_plan(phase, {}, "An arbitrary optimization problem.", {},
                           choose_trees=True, skills=policy())
    verify_binding(rendered)
    assert {entry["name"] for entry in rendered["model_skills"]["loaded"]} == {
        "planifier-optimisation", *SHARED}
    assert ("children" in rendered["schema"]["properties"]) is (phase == "preparation")
    legacy = render_plan(phase, {}, "The same problem.", {}, choose_trees=True)
    assert "model_skills" not in legacy and FIELD not in legacy["schema"]["properties"]


@pytest.mark.parametrize("fault", ["instructions", "hash", "role", "phase", "schema"])
def test_changed_skills_or_missing_instructions_are_rejected_before_a_native_call(tmp_path, monkeypatch, fault):
    request = proposal(tmp_path)
    if fault == "instructions":
        request["messages"][0]["content"] = "No project skill contents."
    elif fault in {"hash", "role", "phase"}:
        key = "bundle_sha256" if fault == "hash" else fault
        request["model_skills"][key] = "changed"
    else:
        request["schema"]["required"].remove(FIELD)
    monkeypatch.setattr(codex_process.shutil, "which", lambda _: "codex.exe")
    with pytest.raises(InfrastructureError, match="skills"):
        codex_process.command_for(request, tmp_path / "rejected")
    assert not (tmp_path / "rejected/instructions.txt").exists()


def declarations(request):
    return [{"name": entry["name"], "status": "not_needed",
             "summary": "This fixture has no unresolved technical property.", "references": []}
            for entry in request["model_skills"]["loaded"]]


@pytest.mark.parametrize("fault", ["missing", "duplicate", "unknown", "empty_reason", "bad_reference"])
def test_model_declarations_must_cover_loaded_skills_with_specific_explanations(tmp_path, fault):
    request = proposal(tmp_path)
    entries = declarations(request)
    if fault == "missing":
        entries.pop()
    elif fault == "duplicate":
        entries[0] = entries[1]
    elif fault == "unknown":
        entries[0]["name"] = "unloaded-skill"
    elif fault == "empty_reason":
        entries[0]["summary"] = " "
    else:
        entries[0]["references"] = [None]
    with pytest.raises(CandidateRejected):
        consume_report({FIELD: entries}, request["model_skills"])


@pytest.mark.parametrize("omit_report", [False, True])
def test_native_trace_distinguishes_injected_skills_declarations_and_observed_tools(tmp_path, monkeypatch, omit_report):
    request = proposal(tmp_path)
    entries = declarations(request)
    def process(argv, output, log, timeout, **kwargs):
        data = {"fixture": True}
        if not omit_report:
            data[FIELD] = entries
        (output / "agent-result.json").write_text(json.dumps(data), encoding="utf8")
        log.write_text(json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 20, "output_tokens": 5}}), encoding="utf8")
        from types import SimpleNamespace

        return SimpleNamespace(returncode=0, timed_out=False, log=str(log))
    monkeypatch.setattr(codex_process.shutil, "which", lambda _: "codex.exe")
    monkeypatch.setattr(codex_process, "run_process", process)
    response = codex_process._invoke(request, "c" * 64, tmp_path / "native", "codex", None, True)
    audit = response["usage"]["model_skills"]
    assert audit["manifest"] == request["model_skills"]
    assert audit["observed_mcp_calls"] == []
    assert audit["native_turn_completed"]
    assert audit["model_declarations_are_execution_proof"] is False
    assert audit["report_status"] == ("invalid" if omit_report else "reported")
    assert bool(response["error"]) is omit_report
    if not omit_report:
        assert audit["model_reported"] == entries and response["data"] == {"fixture": True}
    assert json.loads((tmp_path / "native/skills-usage.json").read_text()) == audit
    invocation = json.loads((tmp_path / "native/invocation.json").read_text())
    assert invocation["model_skills"] == audit["manifest"]
    assert invocation["effective_instructions_sha256"] == audit["effective_instructions_sha256"]


def test_bundle_is_frozen_and_not_implicitly_added_to_old_plans(monkeypatch):
    settings = policy()
    validate_settings(settings)
    validate_settings(None)
    validate_settings({"enabled": False})
    with pytest.raises(InfrastructureError):
        validate_settings({**settings, "bundle_sha256": "0" * 64})
    smoke = load_tool("native_smoke", monkeypatch)
    assert not smoke.skills_enabled({"scope": smoke.FOREST_SCOPE})
    assert smoke.skills_enabled({"scope": smoke.FOREST_SCOPE, "skills": settings})
    with pytest.raises(InfrastructureError):
        smoke.skills_enabled({"scope": smoke.LEGACY_FOREST_SCOPE, "skills": settings})


@pytest.mark.parametrize("count", [2, 5])
@pytest.mark.parametrize("with_mcp", [False, True])
def test_parallel_n_trees_repairs_same_mother_and_final_confirmation_keep_skill_receipts(
    tmp_path, monkeypatch, need_compiler, count, with_mcp,
):
    root, controller, fixture = native_campaign(tmp_path, monkeypatch, count, harness=True, skills=True)
    if with_mcp:
        pytest.importorskip("mcp")
        pytest.importorskip("pypdf")
        from hpc_forest.documentation_mcp import DocumentationMCP
        from hpc_forest.model_mcp import RomeoMCP

        config_path = tmp_path / "codex.toml"
        config_path.write_text('[mcp_servers.romeo]\ncommand="offline-fixture"', encoding="utf8")
        fixture.romeo_mcp = RomeoMCP.bind(config_path)
        fixture.documentation_mcp = DocumentationMCP.bind(tmp_path / "references", "a" * 32)
    fixture.repair_research = fixture.repair_assembly = True
    with controller:
        state = controller.run()
        assert state["postprocess"]["status"] == "complete"
        assert len(fixture.calls) == count + 4  # Planning, N children, child repair, assembly + repair.
        controller.confirm()
        assert controller.status()["final_g_confirmation"]["status"] == "confirmed"
        traces = campaign_traces(controller.db)
        assert len(traces) == len(fixture.calls)
        assert {trace["manifest"]["role"] for trace in traces} == {
            "Mother", *(f"T{i}" for i in range(1, count + 1))}
        for request in fixture.calls:
            manifest = verify_binding(request)
            trace = next(trace for trace in traces if trace["nonce"] == request["nonce"])
            assert trace["manifest"] == manifest
            assert trace["report_status"] == "reported"
            assert len(trace["model_reported"]) == 4
            assert len(trace["observed_mcp_calls"]) == (2 if with_mcp else 0)
        mother = [trace for trace in traces if trace["manifest"]["role"] == "Mother"]
        assert len({trace["conversation"]["id"] for trace in mother}) == 1
        assert [trace["manifest"]["phase"] for trace in mother] == ["planning", "assembly", "assembly"]
        assert {name for trace in traces for name in (
            entry["name"] for entry in trace["manifest"]["loaded"])} == set(NAMES)
        before = copy.deepcopy(fixture.calls)
        controller.run()
        assert fixture.calls == before
    report(root)
    exported = json.loads((root / "report/experiments.json").read_text())
    assert exported["model_skills"] == traces
