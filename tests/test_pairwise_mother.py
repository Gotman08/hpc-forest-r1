"""Offline generation, real parallel AB-MCTS and compilation, sequential native Mother turns."""
import copy
import json
import time
import uuid
import zipfile
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_mother_conversation import native_campaign, persistent_settings

from hpc_forest.adaptive_budget import forecast, record_timing
from hpc_forest.completion import finalize
from hpc_forest.config import validate
from hpc_forest.core import BudgetExhausted, ForestError, InfrastructureError
from hpc_forest.gitops import git, initialize_source
from hpc_forest.reporting import package, report
from hpc_forest.support.sources import committed_source_snapshot


@pytest.mark.parametrize("count", [1, 2, 5, 8])
def test_parallel_forest_then_measured_pairs_in_original_mother_and_final_confirmation(
    tmp_path, monkeypatch, need_compiler, count,
):
    root, controller, fixture = native_campaign(tmp_path, monkeypatch, count, pairwise=True, skills=True)
    with controller:
        state = controller.run()
        post = state["postprocess"]
        assert post["status"] == "complete" and post["integration_policy"] == "pairwise"
        assert post["context_compaction"] == "codex-cli-automatic"
        assert not post["missing_valid_roles"]
        expected = max(1, count - 1)
        assert len(post["steps"]) == expected and len(post["leaf_program_ids"]) == count
        assert controller.db.costs("postprocess")["slots"] == expected
        assert len(fixture.calls) == 1 + count + expected
        original = state["forest_plan"]["conversation"]
        first = fixture.calls[0]
        observed = json.loads(first["messages"][1]["content"])["automatic_observations_as_data"]
        assert set(observed["automatic_observations"]) == {"baseline"}
        assert "Consider the available duration" not in first["messages"][0]["content"]
        assert "maxItems" not in first["schema"]["properties"]["children"]
        assemblies = [call for call in fixture.calls if call.get("meta_role") == "mother-final-assembly"]
        assert [call["conversation"]["turn"] for call in assemblies] == list(range(1, expected + 1))
        assert fixture.calls[-expected:] == assemblies  # No research invocation after assembly starts.
        previous = original
        for call in assemblies:
            assert call["conversation"]["id"] == original["id"]
            assert call["conversation"]["thread_id"] == original["thread_id"]
            assert call["conversation"]["previous_request_sha256"] == previous["request_sha256"]
            payload = json.loads(call["messages"][1]["content"].split("\n\nCURRENT SOURCE AS DATA:")[0])
            context = payload["context_as_data"]
            assert 1 <= len(context["sources"]) <= 2
            assert len(context["sources"]) == len(payload["integration_source_ids"])
            assert call["expires_at"] is call["token_ceiling"] is None
            assert len(call["model_skills"]["loaded"]) == 4
            assert call["model_skills"]["phase"] == "assembly"
            for source in context["sources"]:
                assert "diff" not in source
                assert source["files"] == committed_source_snapshot(root / "repo", source["commit"])
                assert source["mean_seconds"] > 0
            request_log = root / "logs" / call["mission_id"] / "codex-response.json"
            previous = json.loads(request_log.read_text())["conversation"]
        assert state["mother_conversation"] == previous
        assert post["steps"][-1]["final"] is True
        assert post["steps"][-1]["mission_id"] == post["mission_id"]
        assert all(step["status"] == "complete" for step in post["steps"])
        assert controller.db.one("SELECT count(*) AS n FROM trials WHERE role <> 'G'")["n"] == count
        assert controller.db.one("SELECT count(*) AS n FROM trials WHERE tree_id='e1:G-final'")["n"] == 1
        controller.confirm()
        final = controller.status()["final_g_confirmation"]
        assert final["status"] == "confirmed" and final["experiment_id"] == post["mission_id"]
        assert final["outcome"]["commit"] == post["outcome"]["commit"]
        assert len(final["outcome"]["times"]) == controller.config["protocol"]["confirmation_repetitions"]
        before = len(fixture.calls)
        controller.run()
        controller.confirm()
        assert len(fixture.calls) == before
        with pytest.raises(BudgetExhausted, match="closed"):
            controller.db.reserve_research_wave(state["research_roles"], 999)
    report(root)
    package(root, root / "submission.zip")
    payload = json.loads((root / "report/experiments.json").read_text())
    assert payload["postprocess"]["steps"] == post["steps"]
    with zipfile.ZipFile(root / "submission.zip") as archive:
        manifest = json.loads(archive.read("HPC_FOREST_MANIFEST.json"))
        assert manifest["final_g_confirmation"]["experiment_id"] == post["mission_id"]


def test_bad_intermediate_preserves_better_input_and_remaining_pairs_continue(tmp_path, monkeypatch, need_compiler):
    _, controller, fixture = native_campaign(tmp_path, monkeypatch, 5, pairwise=True)
    evaluate = controller._evaluate_mission
    def slow_intermediate(mission, baseline):
        outcome = evaluate(mission, baseline)  # Real compiler and protected correctness checks.
        if mission.role == "G" and mission.ordinal == 1:
            assert outcome.correct is True
            seconds = baseline["mean_seconds"] * 100
            # Deterministic performance fixture; correctness remains the real result.
            return replace(outcome, mean_seconds=seconds, times=[seconds], score=0.001)
        return outcome
    monkeypatch.setattr(controller, "_evaluate_mission", slow_intermediate)
    with controller:
        post = controller.run()["postprocess"]
        first = post["steps"][0]
        assert post["status"] == "complete"
        assert first["selected_id"] in first["input_ids"]
        assert first["selected_id"] != first["mission_id"]
        later = [step for step in post["steps"][1:] if first["selected_id"] in step["input_ids"]]
        assert later
        assert all(first["mission_id"] not in step["input_ids"] for step in post["steps"][1:])
        assert len(fixture.calls) == 10  # Plan + five concurrent children + four sequential assemblies.
        controller.confirm()
        assert controller.status()["final_g_confirmation"]["status"] == "confirmed"


def test_pair_repair_continues_same_thread_without_extra_fusion_slot(tmp_path, monkeypatch, need_compiler):
    _, controller, fixture = native_campaign(tmp_path, monkeypatch, 3, pairwise=True, harness=True, skills=True)
    fixture.repair_assembly = True
    with controller:
        post = controller.run()["postprocess"]
        assert post["status"] == "complete" and len(post["steps"]) == 2
        turns = [call["conversation"] for call in fixture.calls if call.get("meta_role") == "mother-final-assembly"]
        assert [turn["turn"] for turn in turns] == [1, 2, 3]
        assert len({turn["thread_id"] for turn in turns}) == 1
        assert controller.db.costs("postprocess")["slots"] == 2
        controller.confirm()
        assert controller.status()["final_g_confirmation"]["status"] == "confirmed"


def test_mcp_docs_and_project_skills_remain_loaded_for_every_pair(tmp_path, monkeypatch, need_compiler):
    pytest.importorskip("mcp")
    pytest.importorskip("pypdf")
    from hpc_forest.documentation_mcp import DocumentationMCP
    from hpc_forest.model_mcp import RomeoMCP

    _, controller, fixture = native_campaign(tmp_path, monkeypatch, 3, pairwise=True, skills=True)
    config = tmp_path / "codex.toml"
    config.write_text('[mcp_servers.romeo]\ncommand="offline-fixture"')
    fixture.romeo_mcp = RomeoMCP.bind(config)
    fixture.documentation_mcp = DocumentationMCP.bind(tmp_path / "references", "a" * 32)
    with controller:
        post = controller.run()["postprocess"]
        assert post["status"] == "complete" and len(post["steps"]) == 2
        assemblies = [call for call in fixture.calls if call.get("conversation", {}).get("phase") == "assembly"]
        assert len(assemblies) == 2 and all(len(call["model_skills"]["loaded"]) == 4 for call in assemblies)
        controller.confirm()
        assert controller.status()["final_g_confirmation"]["status"] == "confirmed"


def test_no_valid_child_still_resumes_mother_on_the_baseline_then_confirms_final_g(
    tmp_path, monkeypatch, need_compiler,
):
    _, controller, fixture = native_campaign(tmp_path, monkeypatch, 1, pairwise=True)
    process = fixture.process
    def incorrect_research(argv, output, log, timeout, **kwargs):
        result = process(argv, output, log, timeout, **kwargs)
        request = json.loads((output / "request.json").read_text())
        if not request.get("conversation"):
            path = output / "agent-result.json"
            value = json.loads(path.read_text())
            value["files"][0]["content"] += "\nint offline_invalid_child = ;\n"
            path.write_text(json.dumps(value))
        return result
    monkeypatch.setattr("hpc_forest.codex_process.run_process", incorrect_research)
    with controller:
        post = controller.run()["postprocess"]
        assert post["status"] == "complete" and post["missing_valid_roles"] == ["T1"]
        assert post["leaf_program_ids"] == []
        assert len(post["steps"]) == 1 and post["steps"][0]["input_ids"] == ["baseline-e1"]
        controller.confirm()
        assert controller.status()["final_g_confirmation"]["status"] == "confirmed"


def test_failed_intermediate_never_replans_or_claims_a_final_program(tmp_path, monkeypatch, need_compiler):
    _, controller, fixture = native_campaign(tmp_path, monkeypatch, 5, pairwise=True)
    fixture.invalid_assembly = True
    with controller:
        post = controller.run()["postprocess"]
        assert post["status"] == "failed" and "mission_id" not in post
        assert len(post["steps"]) == 1 and post["steps"][0]["status"] == "failed"
        assert len(fixture.calls) == 7
        controller.run()
        assert len(fixture.calls) == 7


def test_interrupted_reduction_is_not_replayed(tmp_path, monkeypatch, need_compiler):
    import hpc_forest.completion as completion

    _, controller, fixture = native_campaign(tmp_path, monkeypatch, 5, pairwise=True)
    integrate = completion._integrate
    def interrupt(controller, epoch, baseline, state, **kwargs):
        if len(state["steps"]) == 1:
            raise KeyboardInterrupt("offline interruption between two Mother turns")
        return integrate(controller, epoch, baseline, state, **kwargs)
    monkeypatch.setattr(completion, "_integrate", interrupt)
    with controller:
        with pytest.raises(KeyboardInterrupt):
            controller.run()
        before, costs = len(fixture.calls), controller.db.costs()
        post = finalize(controller, controller.epoch(), controller._baseline(controller.epoch()))
        assert post["status"] == "interrupted" and "mission_id" not in post
        assert len(fixture.calls) == before and controller.db.costs() == costs


def test_reserve_and_postprocess_slots_follow_n_without_exposing_duration(db, tmp_path):
    config = persistent_settings(tmp_path)
    config["forest"]["integration"] = "pairwise"
    db.set("config", config)
    db.set("current_epoch", 1)
    db.set("mother_enabled", True)
    db.set("forest_plan:1", {"children": [{"role": f"T{i}"} for i in range(1, 79)]})
    record_timing(db, "baseline", 1)
    record_timing(db, "mission:G", 8)
    for duration in [1800, 7200, 18000, 86400]:
        db.set("deadline", time.time() + duration)
        prediction = forecast(db)
        assert prediction["integration_steps"] == 77 and prediction["integration_seconds"] == 77 * 8
    with pytest.raises(ForestError, match="sequence"):
        db.reserve("postprocess", "postprocess:e1:merge:2")
    for step in range(1, 78):
        db.reserve("postprocess", f"postprocess:e1:merge:{step}")
    with pytest.raises(BudgetExhausted, match="slot limit"):
        db.reserve("postprocess", "postprocess:e1:merge:78")


def test_full_committed_pair_source_is_not_a_truncated_diff_or_mutable_worktree(tmp_path):
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    text = "\n// full input\n" + "// " + "a" * 12000 + "\nint main() { return 0; }\n\n"
    (source / "src/main.cpp").write_text(text, encoding="utf-8", newline="")
    repo = tmp_path / "repo"
    commit = initialize_source(source, repo)
    (repo / "src/main.cpp").write_text("uncommitted content", encoding="utf-8")
    assert committed_source_snapshot(repo, commit) == {"src/main.cpp": text}
    blob = git(repo, "rev-parse", commit + ":src/main.cpp")
    git(repo, "update-index", "--add", "--cacheinfo", f"120000,{blob},src/link")
    git(repo, "commit", "-m", "offline link fixture")
    with pytest.raises(InfrastructureError, match="regular files"):
        committed_source_snapshot(repo, "HEAD")


@pytest.mark.parametrize("forest", [{"policy": "fixed", "integration": "pairwise"},
                                  {"policy": "mother", "integration": "pairwise"},
                                  {"policy": "mother", "conversation": "persistent", "integration": "parallel"}])
def test_pairwise_requires_persistent_mother_and_known_policy(tmp_path, forest):
    config = persistent_settings(tmp_path)
    config["forest"] = copy.deepcopy(forest)
    with pytest.raises(ForestError, match="Pairwise"):
        validate(config)


def test_native_cli_keeps_automatic_compaction_defaults_and_original_workspace(tmp_path, monkeypatch):
    from test_mother_conversation import request_for

    from hpc_forest import codex_process
    from hpc_forest.codex_conversation import first_turn, next_turn
    from hpc_forest.support.budgets import OBSERVE_TOKENS

    monkeypatch.setattr(codex_process, "shutil", SimpleNamespace(which=lambda _: "codex.exe"))
    first = request_for(first_turn())
    first.update(token_policy=OBSERVE_TOKENS, schema={"type": "object"},
                 messages=[{"role": "system", "content": "Offline instructions"},
                           {"role": "user", "content": "Two input programs"}])
    receipt = {**first["conversation"], "thread_id": str(uuid.uuid4()), "request_sha256": "1" * 64}
    resumed = {**first, "conversation": next_turn(receipt)}
    start = codex_process.command_for(first, tmp_path / "first")
    resume = codex_process.command_for(resumed, tmp_path / "second")
    assert "--ephemeral" not in start + resume and "--last" not in resume
    assert resume[resume.index("resume") + 1] == receipt["thread_id"]
    assert start[start.index("-C") + 1] == resume[resume.index("-C") + 1]
    assert not any(arg.startswith(("model_context_window=", "model_auto_compact_token_limit=", "compact_prompt="))
                   for arg in start + resume)
