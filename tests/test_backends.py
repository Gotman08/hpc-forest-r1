import json
from pathlib import Path

import pytest

import hpc_forest.backends as backends
from hpc_forest.core import Mission, ProcessResult
from hpc_forest.model_policy import DSH_MODEL


@pytest.mark.parametrize("with_usage", [True, False])
@pytest.mark.parametrize("model", ["gpt-6-luna", DSH_MODEL])
def test_codex_contract_preserves_model_and_records_available_usage(
    tmp_path, monkeypatch, config, with_usage, model
):
    captured = {}
    config["codex"]["model"] = model
    if model == DSH_MODEL:
        from hpc_forest.controller import RESULT_SCHEMA

        monkeypatch.setenv("ROMEO_LLM_KEY", "fixture-private-key")
        (tmp_path / "trusted").mkdir()
        (tmp_path / "trusted/result-schema.json").write_text(json.dumps(RESULT_SCHEMA))
    monkeypatch.setattr(backends.shutil, "which", lambda _: "fake-codex-for-contract-test")

    def fake_process(argv, cwd, log, timeout, **kwargs):
        captured.update(argv=argv, stdin=kwargs["stdin"])
        log.parent.mkdir(parents=True, exist_ok=True)
        events = (
            [
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 120, "output_tokens": 30, "cached_input_tokens": 40},
                }
            ]
            if with_usage
            else []
        )
        log.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
        response = Path(argv[argv.index("--output-last-message") + 1])
        response.write_text(
            json.dumps(
                {
                    "hypothesis": "test contract",
                    "transformations": ["tiling"],
                    "sources_kept": ["A1"],
                    "notes": "not a measured result",
                }
            ),
            encoding="utf-8",
        )
        return ProcessResult(argv, 0, 0.01, False, str(log))

    monkeypatch.setattr(backends, "run_process", fake_process)
    mission = Mission(
        "test",
        "e1:G",
        "trial",
        1,
        "G",
        "base",
        None,
        "R/G",
        1,
        1,
        str(tmp_path),
        sources=["A1", "B1"],
        source_commits=["a", "b"],
    )
    result = backends.CodexBackend().generate(mission, {"deadline": 9999999999}, config, tmp_path)
    assert result.error is None
    assert result.tokens == (150 if with_usage else None)
    assert captured["argv"][captured["argv"].index("--model") + 1] == model
    assert ("--output-schema" in captured["argv"]) is (model != DSH_MODEL)
    if model == DSH_MODEL:
        assert json.loads(captured["stdin"].splitlines()[-1]) == RESULT_SCHEMA
    assert 'model_reasoning_effort="max"' in captured["argv"]
    assert "workspace-write" in captured["argv"]
    assert not any("bypass" in arg for arg in captured["argv"])
    assert "DATA_CONTEXT_BEGIN" in captured["stdin"]
    assert mission.sources == ["A1"] and mission.source_commits == ["a"]


def test_c_compile_failure_gets_zero_reward_and_no_fake_timing(
    tmp_path, config, monkeypatch, need_compiler
):
    from hpc_forest.controller import Controller, create_workspace

    original = backends.RecipeBackend.generate

    def wrong_code(self, mission, *args):
        result = original(self, mission, *args)
        (Path(mission.worktree) / "src" / "main.c").write_text(
            "#error deliberately broken candidate\n"
        )
        return result

    monkeypatch.setattr(backends.RecipeBackend, "generate", wrong_code)
    config["roles"] = ["A"]
    config["budget"]["search_slots"] = 2
    root = create_workspace(tmp_path / "build-failure", config)
    with Controller(root) as controller:
        controller.run()
        result = controller.db.archive(1)
        assert result == []
        evaluation = [
            r for r in controller.db.evaluations() if not r["experiment_id"].startswith("baseline")
        ][0]
        outcome = evaluation["outcome"]
        assert outcome["status"] == "build_failed"
        assert outcome["score"] == 0
        assert outcome["mean_seconds"] is None


def test_missing_infrastructure_does_not_become_an_incorrect_solution(
    tmp_path, config, monkeypatch, need_compiler
):
    from hpc_forest.controller import Controller, create_workspace
    from hpc_forest.core import InfrastructureError
    from hpc_forest.evaluator import Evaluator

    real = Evaluator.evaluate

    def unavailable(self, experiment, *args, **kwargs):
        if experiment.startswith("baseline"):
            return real(self, experiment, *args, **kwargs)
        raise InfrastructureError("simulated unavailable measurement target")

    monkeypatch.setattr(Evaluator, "evaluate", unavailable)
    config["roles"] = ["A"]
    config["budget"]["infrastructure_breaker"] = 1  # Protocol 2 stops at its breaker: here the first failure.
    root = create_workspace(tmp_path / "infrastructure", config)
    with Controller(root) as controller:
        state = controller.run()
        assert state["status"] == "infrastructure_error"
        row = controller.db.rows("SELECT result FROM trials")[0]
        outcome = json.loads(row["result"])
        assert outcome["correct"] is None and outcome["score"] is None
