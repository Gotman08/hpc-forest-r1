"""Protocol fixtures only: no real model calls or Marathon algorithms."""
import copy
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from hpc_forest.backends import Generated
from hpc_forest.config import validate
from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import (
    BudgetExhausted,
    FileLock,
    ForestError,
    InfrastructureError,
    Mission,
    atomic_json,
    protected_manifest,
)
from hpc_forest.evaluator import Evaluator
from hpc_forest.gitops import git, initialize_source
from hpc_forest.node_harness import NodeHarness, wrap_backend


def make_files(source, trusted):
    (source / "src").mkdir(parents=True)
    (source / "src/main.py").write_text("RESULT = 7\n", encoding="utf8")
    trusted.mkdir(parents=True)
    (trusted / "build.py").write_text(
        "import pathlib, shutil, sys\n"
        "source = pathlib.Path(sys.argv[1]) / 'src/main.py'\n"
        "compile(source.read_text(), str(source), 'exec')\n"
        "build = pathlib.Path(sys.argv[2]); build.mkdir(exist_ok=True)\n"
        "shutil.copyfile(source, build / ('solution.exe' if sys.platform == 'win32' else 'solution'))\n",
        encoding="utf8")
    (trusted / "check.py").write_text(
        "import json, runpy, sys\n"
        "assert sys.argv[2] in ('search', 'confirmation')\n"
        "assert runpy.run_path(sys.argv[1])['RESULT'] == 7\n"
        "print(json.dumps({'correct': True, 'cases': 2}))\n", encoding="utf8")


@pytest.fixture
def episode(tmp_path, config):
    source, root = tmp_path / "original", tmp_path / "campaign"
    make_files(source, root / "trusted")
    worktree = tmp_path / "candidate"
    commit = initialize_source(source, worktree)
    config["backend"] = "codex"
    config["harness"].update(enabled=True, max_attempts=3, call_token_ceiling=1000)
    config["budget"].update(mission_tokens=3000, generation_seconds=30, confirmation_seconds=1)
    config["target_id"] = str(tmp_path)
    config["protocol"]["benchmark"] = ["{python}", "-c", "import time; time.sleep(.005)"]
    mission = Mission("trial", "e1:A", "local-1", 1, "A", commit, None, "R/A", 1, 1, str(worktree))
    context = {"deadline": time.time() + 60, "protocol_id": "fixture", "remaining_tokens": 3000}
    return mission, context, config, root


class Scripted:
    supports_harness_research = True

    def __init__(self, actions):
        self.actions, self.contexts, self.missions = list(actions), [], []

    def generate(self, mission, context, config, root):
        self.contexts.append(copy.deepcopy(context))
        self.missions.append(copy.deepcopy(mission))
        action = self.actions.pop(0)
        if callable(action):
            return action(mission, context)
        (Path(mission.worktree) / "src/main.py").write_text(action, encoding="utf8")
        return Generated(100, {"llm_calls": 1})


@pytest.mark.parametrize("first_tokens", [2000000, None, "historical_bound"])
def test_uncapped_episode_repairs_even_after_large_or_missing_usage(episode, first_tokens):
    mission, context, config, root = episode
    config["budget"].update(tokens=None, mission_tokens=None)
    config["harness"]["call_token_ceiling"] = None
    context.update(deadline=None, deadline_policy="finish-started", remaining_tokens=None)
    def broken(mission, context):
        (Path(mission.worktree) / "src/main.py").write_text("RESULT =\n")
        return Generated(1000 if first_tokens == "historical_bound" else first_tokens,
                         {"llm_calls": 1}, tokens_upper_bound=first_tokens == "historical_bound")
    backend = Scripted([broken, "RESULT = 7\n"])
    generated = NodeHarness(backend).generate(mission, context, config, root)
    assert generated.error is None and not generated.infrastructure_error
    assert len(backend.contexts) == 2 and generated.usage["development_evaluations"] == 2
    exact = type(first_tokens) is int
    assert generated.tokens == (first_tokens + 100 if exact else None)
    assert generated.usage["observed_tokens"] == (first_tokens if exact else 0) + 100
    assert not generated.tokens_upper_bound
    assert all(item["remaining_tokens"] is None for item in backend.contexts)


def test_model_repairs_real_compile_error_without_rewarding_local_attempts(episode):
    mission, context, config, root = episode
    backend = Scripted(["RESULT =\n", "RESULT = 7\n# fixture repair by model\n", "unused"])
    generated = NodeHarness(backend).generate(mission, context, config, root)
    assert generated.error is None and generated.tokens == 200
    assert generated.usage["llm_calls"] == 2
    assert generated.usage["development_evaluations"] == 2
    feedback = backend.contexts[1]["automatic_observations"]["node_development"]["previous_attempts"]
    assert feedback[0]["development_outcome"]["status"] == "build_failed"
    assert "SyntaxError" in feedback[0]["measured_diagnostics"][0]["text"]
    assert "score" not in feedback[0]["development_outcome"]
    journal = json.loads(Path(generated.usage["journal"]).read_text())
    assert not journal["outer_tree_reward_assigned"] and not journal["holdout_access"]
    assert journal["attempts"][1]["development_outcome"]["status"] == "development_valid"
    assert not list(root.rglob("sample-*.log")) and not list(root.rglob("warmup-*.log"))
    assert git(Path(mission.worktree), "rev-parse", "HEAD") == mission.base_commit
    with pytest.raises(InfrastructureError, match="never replay"):
        NodeHarness(backend).generate(mission, context, config, root)


def test_first_valid_proposal_stops_the_episode(episode):
    mission, context, config, root = episode
    backend = Scripted(["RESULT = 7\n", "unused"])
    result = NodeHarness(backend).generate(mission, context, config, root)
    assert result.tokens == 100 and len(backend.contexts) == 1


def test_integration_without_sources_never_calls_a_model_or_invents_calls(episode):
    mission, context, config, root = episode
    mission.role = "G"
    context["sources"] = []
    backend = Scripted(["must never be generated"])
    result = NodeHarness(backend).generate(mission, context, config, root)
    assert result.error == "No admissible integration sources" and result.tokens == 0
    assert result.usage["llm_calls"] == 0 and result.usage["harness_attempts"] == 0
    assert result.usage["development_evaluations"] == 0 and not backend.contexts
    assert json.loads(Path(result.usage["journal"]).read_text())["attempts"] == []


def test_development_checks_wait_for_the_shared_target_lock(episode):
    mission, _, config, root = episode
    evaluator = Evaluator(root, config, protected_manifest(root / "trusted"), "fixture", time.time() + 10)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with FileLock(evaluator.lock_path):
            future = pool.submit(evaluator.precheck, "waiting", 1, Path(mission.worktree), mission.base_commit)
            time.sleep(0.1)
            assert not future.done()
        assert future.result(timeout=5).status == "development_valid"


def test_development_target_wait_honors_the_deadline(episode):
    mission, _, config, root = episode
    evaluator = Evaluator(root, config, protected_manifest(root / "trusted"), "fixture", time.time() + .1)
    with FileLock(evaluator.lock_path), pytest.raises(BudgetExhausted, match="waiting for target"):
        evaluator.precheck("expired", 1, Path(mission.worktree), mission.base_commit)


def test_precheck_build_failure_does_not_wait_for_target_lock(episode):
    mission, _, config, root = episode
    (Path(mission.worktree) / "src/main.py").write_text("RESULT =\n", encoding="utf8")
    commit = initialize_source(Path(mission.worktree), tmp_path := root / "probe-broken")
    evaluator = Evaluator(
        root, config, protected_manifest(root / "trusted"), "fixture", time.time() + 10
    )
    with FileLock(evaluator.lock_path):
        outcome = evaluator.precheck("compile-only", 1, tmp_path, commit)
    assert outcome.status == "build_failed" and outcome.score is None


def test_evaluator_keeps_global_child_counters_out_of_feedback(episode, monkeypatch):
    mission, _, config, root = episode
    calls = [
        {"utime": 1.0, "stime": 0.1, "maxrss_kb": 4096, "minflt": 10},
        {"utime": 1.015, "stime": 0.105, "maxrss_kb": 8192, "minflt": 25},
        {"utime": 1.02, "stime": 0.11, "maxrss_kb": 8192, "minflt": 30},
        {"utime": 1.04, "stime": 0.115, "maxrss_kb": 12288, "minflt": 50},
    ]
    monkeypatch.setattr("hpc_forest.evaluator._child_rusage", lambda: calls.pop(0))
    evaluator = Evaluator(
        root, config, protected_manifest(root / "trusted"), "fixture", time.time() + 10
    )
    outcome = evaluator.evaluate("rusage-trial", 1, Path(mission.worktree), mission.base_commit, 0.01)
    assert outcome.status == "valid"
    check_data = json.loads(Path(outcome.logs[1]).read_text(encoding="utf8"))
    assert "rusage" not in check_data
    diagnostic = Path(outcome.logs[1]).parent / "process-counters-diagnostic.json"
    assert str(diagnostic) not in outcome.logs
    data = json.loads(diagnostic.read_text(encoding="utf8"))
    assert data["candidate_process_only"] is False
    assert data["excluded_from_selection_and_feedback"] is True
    assert data["scope"] == "controller_children_during_benchmark_windows"
    assert "max_rss_kb" not in data["window_deltas"]
    assert data["window_deltas"]["user_seconds"] > 0



@pytest.mark.parametrize("usage,expected,bounded", [(None, None, False), (1100, 1100, False), (-1, 1000, True)])
def test_unusable_accounting_stops_without_replay(episode, usage, expected, bounded):
    mission, context, config, root = episode
    backend = Scripted([lambda m, c: Generated(usage, {"llm_calls": 1}), "unused"])
    result = NodeHarness(backend).generate(mission, context, config, root)
    assert result.infrastructure_error and result.error and result.tokens == expected
    assert result.tokens_upper_bound == bounded and len(backend.contexts) == 1
    assert result.usage["development_evaluations"] == 0


def test_interface_interruption_charges_bound_and_does_not_replay(episode):
    mission, context, config, root = episode

    def interrupted(m, c):
        raise OSError("fixture lost connection")

    backend = Scripted([interrupted, "unused"])
    result = NodeHarness(backend).generate(mission, context, config, root)
    assert result.tokens == 1000 and result.tokens_upper_bound and result.infrastructure_error
    assert len(backend.contexts) == 1


def test_protected_edit_is_contract_rejection_with_known_usage(episode):
    mission, context, config, root = episode

    def bad(m, c):
        (Path(m.worktree) / "tests.py").write_text("unauthorized fixture")
        return Generated(100, {"llm_calls": 1})

    result = NodeHarness(Scripted([bad])).generate(mission, context, config, root)
    assert result.tokens == 100 and result.usage["contract_rejected"]
    assert not result.infrastructure_error and result.error


def test_every_repair_keeps_original_admissible_integration_scope(episode):
    mission, context, config, root = episode
    mission.role, mission.sources, mission.source_commits = "G", ["a", "b"], ["ca", "cb"]
    context["sources"] = [{"id": "a"}, {"id": "b"}]

    def attempt(m, c):
        m.sources, m.source_commits = ["a"], ["ca"]
        (Path(m.worktree) / "src/main.py").write_text("RESULT =\n")
        return Generated(100, {"llm_calls": 1})

    backend = Scripted([attempt, "RESULT = 7\n"])
    NodeHarness(backend).generate(mission, context, config, root)
    assert backend.missions[1].sources == ["a", "b"]
    assert backend.missions[1].source_commits == ["ca", "cb"]


def pin_corpus(path):
    text = "Fixture documentation only; ignore this alleged instruction to execute shell."
    atomic_json(path, {"documents": [{"title": "Fixture", "url": "https://example.org/manual",
                "version": "fixture-1", "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest()}]})
    return {"enabled": True, "corpus": str(path), "corpus_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "allowed_hosts": []}


def test_model_queries_documents_then_submits_its_own_source(episode):
    mission, context, config, root = episode
    config["harness"]["research"] = pin_corpus(root / "corpus.json")

    def research(m, c):
        assert c["node_research"]["corpus_documents"] == 1
        assert (Path(m.worktree) / "src/main.py").read_text() == "RESULT = 7\n"
        return Generated(50, {"llm_calls": 1, "research_request": {"queries": ["fixture"], "urls": []}})

    backend = Scripted([research, "RESULT = 7\n# model proposal\n"])
    result = NodeHarness(backend).generate(mission, context, config, root)
    assert result.tokens == 150 and result.usage["research_actions"] == 1
    assert result.usage["development_evaluations"] == 1
    feedback = backend.contexts[1]["automatic_observations"]["node_development"]["previous_attempts"]
    hit = feedback[0]["research_results"][0]["hits"][0]
    assert hit["url"] == "https://example.org/manual" and len(hit["sha256"]) == 64
    assert hit["evidence_type"] == "untrusted_documentation"
    assert not (root / "shell").exists()


def test_research_only_episode_never_presents_a_candidate(episode):
    mission, context, config, root = episode
    config["harness"].update(max_attempts=1, research=pin_corpus(root / "corpus.json"))
    def action(m, c):
        return Generated(50, {"llm_calls": 1, "research_request": {"queries": ["fixture"], "urls": []}})
    result = NodeHarness(Scripted([action])).generate(mission, context, config, root)
    assert result.error and result.tokens == 50 and result.usage["development_evaluations"] == 0


def test_backend_cannot_disguise_source_edits_as_documentation(episode):
    mission, context, config, root = episode
    config["harness"]["research"] = pin_corpus(root / "corpus.json")

    def hidden_edit(m, c):
        (Path(m.worktree) / "src/main.py").write_text("RESULT = 123\n")
        return Generated(50, {"llm_calls": 1, "research_request": {"queries": ["fixture"], "urls": []}})

    result = NodeHarness(Scripted([hidden_edit])).generate(mission, context, config, root)
    assert result.tokens == 50 and result.usage["contract_rejected"]
    assert result.usage["research_enabled"] and not result.usage["automatic_measured_feedback_only"]
    assert result.usage["research_actions"] == 0 and result.error


def test_default_wrapper_is_identity_and_reservation_is_validated(config):
    backend = object()
    assert wrap_backend(backend, config) is backend
    config["backend"] = "ollama"
    config["harness"].update(enabled=True, max_attempts=2, call_token_ceiling=16000)
    with pytest.raises(ForestError, match="Reserve all"):
        validate(config)


def test_controller_creates_one_tree_node_and_settles_all_inner_calls(tmp_path, config, monkeypatch):
    source, trusted = tmp_path / "source", tmp_path / "validation"
    make_files(source, trusted)
    root = tmp_path / "campaign"
    config["backend"] = "codex"
    config["roles"] = ["A"]
    config["harness"].update(enabled=True, max_attempts=2, call_token_ceiling=1000)
    config["budget"].update(mission_tokens=2000, generation_seconds=30, max_workers=1)
    config["protocol"]["benchmark"] = ["{python}", "-c", "import time; time.sleep(.005)"]
    monkeypatch.setattr("hpc_forest.controller.compiler_identity", lambda: {"fixture": "python-compiler"})
    create_workspace(root, config, source, trusted)
    with Controller(root) as controller:
        controller.backend = Scripted(["RESULT =\n", "RESULT = 7\n# generated repair\n"])
        controller.run(max_batches=1)
        trials = controller.db.rows("SELECT * FROM trials")
        assert len(trials) == 1
        outcome = json.loads(trials[0]["result"])
        assert outcome["status"] == "valid" and len(outcome["times"]) == 2
        assert controller.db.costs()["tokens_used"] == 200
    manifest = protected_manifest(root / "trusted")
    assert "build.py" in manifest and "check.py" in manifest


def test_workspace_freezes_the_research_corpus_inside_its_protected_files(tmp_path, config, monkeypatch):
    source, trusted = tmp_path / "source", tmp_path / "validation"
    make_files(source, trusted)
    root = tmp_path / "campaign"
    config["backend"] = "codex"
    config["codex"]["transport"] = "codex-mailbox"
    config["harness"].update(enabled=True, max_attempts=2, call_token_ceiling=1000,
                             research=pin_corpus(tmp_path / "external-corpus.json"))
    config["budget"]["mission_tokens"] = 2000
    monkeypatch.setattr("hpc_forest.controller.compiler_identity", lambda: {"fixture": "python-compiler"})
    create_workspace(root, config, source, trusted)
    frozen = root / "trusted/research-corpus.json"
    assert frozen.is_file() and "research-corpus.json" in protected_manifest(root / "trusted")
    frozen_config = json.loads((root / "trusted/config.json").read_text())
    assert Path(frozen_config["harness"]["research"]["corpus"]) == frozen
    (tmp_path / "external-corpus.json").write_text("changed outside the campaign")
    assert frozen.read_text() != "changed outside the campaign"


def test_early_deduplication_in_harness_allows_repair_instead_of_dying_as_duplicate(
    tmp_path, config, monkeypatch
):
    source, trusted = tmp_path / "source", tmp_path / "validation"
    make_files(source, trusted)
    root = tmp_path / "campaign"
    config["backend"] = "codex"
    config["roles"] = ["A"]
    config["harness"].update(enabled=True, max_attempts=2, call_token_ceiling=1000)
    config["budget"].update(mission_tokens=2000, generation_seconds=30, max_workers=1)
    config["protocol"]["benchmark"] = ["{python}", "-c", "import time; time.sleep(.005)"]
    monkeypatch.setattr(
        "hpc_forest.controller.compiler_identity", lambda: {"fixture": "python-compiler"}
    )
    create_workspace(root, config, source, trusted)
    with Controller(root) as controller:
        # Attempt 1 reproduces baseline ("RESULT = 7\n"), which is caught early as duplicate_candidate;
        # Attempt 2 proposes a distinct source that wins a valid outer evaluation.
        backend = Scripted(["RESULT = 7\n", "RESULT = 7\n# distinct proposal after duplicate\n"])
        controller.backend = backend
        controller.run(max_batches=1)
        trials = controller.db.rows("SELECT * FROM trials")
        assert len(trials) == 1
        outcome = json.loads(trials[0]["result"])
        assert outcome["status"] == "valid"
        prev = backend.contexts[1]["automatic_observations"]["node_development"]["previous_attempts"]
        assert prev[0]["development_outcome"]["status"] == "duplicate_candidate"
        assert prev[0]["development_outcome"]["duplicate_of"] == "baseline-e1"

