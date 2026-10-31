"""Evaluation protocol 2: candidate faults, breaker, verified timed outputs.

Protocol 1 stays the behaviour of campaigns created before it; each test pins
the version it exercises.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from hpc_forest.config import load_config
from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import InfrastructureError, Outcome, protected_manifest
from hpc_forest.evaluator import Evaluator, _probe_loaded
from hpc_forest.gitops import git, initialize_source, worktree_changed
from hpc_forest.registry import Registry


def evaluator_for(tmp_path, program, *, version=2, **protocol):
    """A minimal protected campaign whose 'program' is the timed Python workload."""
    root = tmp_path / "campaign"
    source = tmp_path / "input"
    (source / "src").mkdir(parents=True)
    (source / "src/program.py").write_text(program, encoding="utf-8")
    commit = initialize_source(source, root / "repo")
    trusted = root / "trusted"
    trusted.mkdir()
    (trusted / "build.py").write_text("import pathlib,sys\npathlib.Path(sys.argv[1]).write_bytes(b'fixture')\n")
    (trusted / "check.py").write_text("print('{\"correct\": true, \"cases\": 1}')\n")
    config = load_config()
    config["target_id"] = "protocol-test-" + tmp_path.name
    config["protocol"].update({"version": version, "warmups": 0, "repetitions": 3, "confirmation_repetitions": 3,
                               "build": ["{python}", "{trusted}/build.py", "{binary}"],
                               "check": ["{python}", "{trusted}/check.py"],
                               "benchmark": ["{python}", "{worktree}/src/program.py"], **protocol})
    return root, commit, Evaluator(root, config, protected_manifest(trusted), "protocol-test", None)


def commit_program(root, program):
    (root / "repo/src/program.py").write_text(program, encoding="utf-8")
    git(root / "repo", "commit", "-qam", "candidate")
    return git(root / "repo", "rev-parse", "HEAD")


def test_relative_writes_of_a_candidate_never_dirty_its_commit(tmp_path):
    program = "from pathlib import Path\nPath('scratch.tmp').write_text('x')\nprint('result 42')\n"
    root, commit, evaluator = evaluator_for(tmp_path, program)
    outcome = evaluator.evaluate("e1-T1-1", 1, root / "repo", commit, None)
    assert outcome.correct is True and not worktree_changed(root / "repo", commit)
    legacy_root, legacy_commit, legacy = evaluator_for(tmp_path / "legacy", program, version=1)
    with pytest.raises(InfrastructureError, match="unchanged exact commit"):
        legacy.evaluate("e1-T1-1", 1, legacy_root / "repo", legacy_commit, None)


def test_a_candidate_writing_into_its_source_tree_scores_zero(tmp_path):
    # The run uses an export of the commit, so only an absolute path reaches the worktree.
    target = tmp_path / "campaign" / "repo" / "src" / "dirt.txt"
    program = f"from pathlib import Path\nPath({str(target)!r}).write_text('x')\nprint('42')\n"
    root, commit, evaluator = evaluator_for(tmp_path, program)
    outcome = evaluator.evaluate("e1-T1-1", 1, root / "repo", commit, None)
    assert outcome.status == "contract_violation" and outcome.score == 0.0 and outcome.correct is False


def test_every_timed_output_must_match_the_reference(tmp_path):
    root, base, evaluator = evaluator_for(tmp_path, "print('value 1.0')\n")
    reference = evaluator.evaluate("baseline-e1", 1, root / "repo", base, None)
    assert reference.output_verification == "reference" and reference.output_sha256
    rounding = commit_program(root, "print('value 1.0000000000001')\n")
    close = evaluator.evaluate("e1-T1-1", 1, root / "repo", rounding, reference.median_seconds,
                               reference_output=reference.output_sha256)
    assert close.correct is True and close.output_verification == "verified"
    wrong = commit_program(root, "print('value 2.0')\n")
    outcome = evaluator.evaluate("e1-T1-2", 1, root / "repo", wrong, reference.median_seconds,
                                 reference_output=reference.output_sha256)
    assert outcome.status == "incorrect" and outcome.score == 0.0 and outcome.output_verification == "mismatch"


def test_an_unstable_reference_output_is_recorded_not_enforced(tmp_path):
    root, base, evaluator = evaluator_for(tmp_path, "import time\nprint(time.perf_counter_ns())\n")
    reference = evaluator.evaluate("baseline-e1", 1, root / "repo", base, None)
    assert reference.correct is True and reference.output_verification == "reference_unstable"
    candidate = commit_program(root, "print('anything')\n")
    outcome = evaluator.evaluate("e1-T1-1", 1, root / "repo", candidate, reference.median_seconds,
                                 reference_output=reference.output_sha256)
    assert outcome.correct is True and outcome.output_verification == "reference_unstable"


def test_a_changed_reference_output_is_an_infrastructure_failure(tmp_path):
    root, base, evaluator = evaluator_for(tmp_path, "print('value 1')\n")
    reference = evaluator.evaluate("baseline-e1", 1, root / "repo", base, None)
    (root / "builds/e1/benchmark-reference.out").write_text("value 2\n")
    candidate = commit_program(root, "print('value 2')\n")
    with pytest.raises(InfrastructureError, match="reference output changed"):
        evaluator.evaluate("e1-T1-1", 1, root / "repo", candidate, reference.median_seconds,
                           reference_output=reference.output_sha256)


def test_medians_decide_and_one_disturbed_sample_cannot_move_them(tmp_path):
    root, commit, evaluator = evaluator_for(tmp_path, "print(1)\n")
    outcome = evaluator._finalize(Outcome("pending", correct=True, times=[1.0, 1.1, 9.0]), 1.0)
    assert outcome.median_seconds == 1.1 and outcome.mean_seconds > 3
    assert outcome.score == pytest.approx(1 / (1 + 1.1))


def test_confirmation_isolates_one_finalist_infrastructure_failure(tmp_path, monkeypatch):
    root, base, evaluator = evaluator_for(tmp_path, "print('value 1')\n")
    first = commit_program(root, "print('value 1')  # variant a\n")
    second = commit_program(root, "print('value 1')  # variant b\n")
    candidates = [{"id": "baseline-e1", "commit": base, "baseline": True},
                  {"id": "a", "commit": first, "baseline": False},
                  {"id": "b", "commit": second, "baseline": False}]
    for candidate in candidates:
        path = root / "worktrees" / candidate["id"]
        git(root / "repo", "worktree", "add", "--detach", str(path), candidate["commit"])
        candidate["worktree"] = str(path)
    prepare = evaluator._prepare

    def node_failure(experiment, *args, **kwargs):
        if experiment == "b":
            raise InfrastructureError("Synthetic node failure")
        return prepare(experiment, *args, **kwargs)

    monkeypatch.setattr(evaluator, "_prepare", node_failure)
    outcomes = evaluator.confirm(candidates, 1)
    assert outcomes["b"].status == "infrastructure_error" and outcomes["b"].score is None
    assert outcomes["a"].correct is True and outcomes["a"].output_verification == "verified"
    evaluator.config["protocol"]["version"] = 1
    with pytest.raises(InfrastructureError, match="Synthetic node failure"):
        evaluator.confirm(candidates, 1)


def test_breaker_trips_only_after_consecutive_infrastructure_failures(tmp_path):
    config = load_config()
    db = Registry(tmp_path / "registry.sqlite3")
    try:
        controller = SimpleNamespace(config=config, db=db)
        assert [Controller.infrastructure_failure(controller) for _ in range(2)] == [None, None]
        Controller.infrastructure_recovered(controller)
        assert [Controller.infrastructure_failure(controller) for _ in range(3)] == [None, None, "infrastructure_error"]
        config["protocol"]["version"] = 1
        Controller.infrastructure_recovered(controller)
        assert Controller.infrastructure_failure(controller) == "infrastructure_error"
    finally:
        db.close()


@pytest.mark.parametrize("version,stops", [(1, True), (2, False)])
def test_one_infrastructure_failure_stops_only_a_protocol_1_search(tmp_path, config, need_compiler,
                                                                     monkeypatch, version, stops):
    config["protocol"]["version"] = version
    root = create_workspace(tmp_path / "campaign", config)
    evaluate, calls = Controller._evaluate_mission, []

    def first_node_fails(self, mission, baseline):
        calls.append(mission.id)
        if len(calls) == 1:
            return Outcome("infrastructure_error", reason="Synthetic node failure")
        return evaluate(self, mission, baseline)

    monkeypatch.setattr(Controller, "_evaluate_mission", first_node_fails)
    with Controller(root) as controller:
        state = controller.run()
        trials = len(controller.db.rows("SELECT id FROM trials"))
    # Protocol 1 settles the admitted batch (A, B, C) and stops; protocol 2 keeps searching.
    assert (state["status"] == "infrastructure_error") is stops
    assert (trials > 3) is not stops


def test_probe_receipt_tells_an_observer_failure_from_a_candidate_exit(tmp_path):
    trace = tmp_path / "trace.jsonl"
    assert not _probe_loaded(trace)
    trace.write_text(json.dumps({"schema": "forest-gomp-probe-v1", "loaded": True}) + "\n")
    assert _probe_loaded(trace)


def test_project_runner_reports_storage_failures_as_infrastructure(tmp_path):
    runner = Path(__file__).parents[1] / "src/hpc_forest/webapp/project_protocol.py"
    result = subprocess.run([sys.executable, str(runner), "check", str(tmp_path / "missing-trusted"),
                             str(tmp_path), str(tmp_path), "search"], capture_output=True, text=True)
    assert result.returncode == 70


def test_gain_bound_separates_a_real_gain_from_noise():
    from hpc_forest.support.gains import gain, gain_lower_bound

    reference = [1.00, 1.01, 0.99, 1.00, 1.02]
    faster = [0.80, 0.81, 0.79, 0.80, 0.82]
    assert gain(reference, faster) == pytest.approx(0.2)
    assert gain_lower_bound(reference, faster, seed=7) > 0.15
    noisy = [0.97, 1.15, 0.88, 1.05, 0.99]
    assert gain_lower_bound([1.0, 1.2, 0.9, 1.1, 1.0], noisy, seed=7) < 0.03


@pytest.mark.parametrize("winner_times,promoted", [
    ([0.80, 0.81, 0.79, 0.80, 0.82], True),
    ([0.97, 1.15, 0.88, 1.05, 0.99], False),
    ([], False),
])
def test_promotion_needs_a_fresh_series_whose_gain_bound_clears_the_threshold(tmp_path, winner_times, promoted):
    calls = []

    def remeasure(reference, winner, epoch):
        calls.append(winner["id"])
        return {"reference_times": [1.00, 1.01, 0.99, 1.00, 1.02] if winner_times[:1] == [0.80]
                else [1.0, 1.2, 0.9, 1.1, 1.0], "winner_times": winner_times,
                "winner_status": "valid" if winner_times else "incorrect", "winner_reason": "",
                "output_verification": "verified"}

    db = Registry(tmp_path / "registry.sqlite3")
    try:
        controller = SimpleNamespace(db=db, config=load_config(), evaluator=SimpleNamespace(remeasure=remeasure))
        reference, winner = {"experiment_id": "baseline-e1"}, {"experiment_id": "w"}
        candidates = [{"id": "baseline-e1"}, {"id": "w"}]
        for _ in range(2):  # The durable series is reused, never measured twice.
            chosen, improvement, record = Controller._remeasured(controller, {"id": 1}, candidates, reference, winner)
        assert calls == ["w"]
        assert (chosen is winner) is promoted
        assert (improvement > 0.15) is promoted and (improvement == 0.0) is not promoted
    finally:
        db.close()


@pytest.mark.parametrize("version,built_before_lock", [(1, True), (2, False)])
def test_development_builds_wait_for_calm_in_protocol_2(tmp_path, version, built_before_lock):
    import time

    from hpc_forest.core import BudgetExhausted, FileLock

    root, commit, evaluator = evaluator_for(tmp_path, "print(1)\n", version=version)
    evaluator.deadline = time.time() + 0.5
    with FileLock(evaluator.lock_path), pytest.raises(BudgetExhausted):
        evaluator.precheck("e1-T1-1", 1, root / "repo", commit)
    assert (root / "logs/e1/e1-T1-1/search").is_dir() is built_before_lock


@pytest.mark.parametrize("version,uses_ignored_file", [(1, True), (2, False)])
def test_protocol_2_evaluates_only_the_files_of_the_commit(tmp_path, version, uses_ignored_file):
    program = "from pathlib import Path\nprint((Path(__file__).parent / 'helper.txt').read_text())\n"
    root, commit, evaluator = evaluator_for(tmp_path, program, version=version)
    (root / "repo/src/.gitignore").write_text("helper.txt\n")
    git(root / "repo", "add", "src/.gitignore")
    git(root / "repo", "commit", "-qm", "ignore helper")
    commit = git(root / "repo", "rev-parse", "HEAD")
    (root / "repo/src/helper.txt").write_text("present only in the worktree\n")
    outcome = evaluator.evaluate("e1-T1-1", 1, root / "repo", commit, None)
    assert (outcome.correct is True) is uses_ignored_file


def test_confirmation_inputs_are_drawn_at_confirmation_and_shared_by_finalists(tmp_path):
    root, base, evaluator = evaluator_for(
        tmp_path, "print('value 1')\n",
        check=["{python}", "-c", "import json,os; print(json.dumps({'correct': True, 'cases': 1, "
               "'seeds': os.environ.get('FOREST_CONFIRMATION_SEEDS')}))"])
    other = commit_program(root, "print('value 1')  # variant\n")
    candidates = [{"id": "baseline-e1", "commit": base, "baseline": True},
                  {"id": "a", "commit": other, "baseline": False}]
    for candidate in candidates:
        path = root / "worktrees" / candidate["id"]
        git(root / "repo", "worktree", "add", "--detach", str(path), candidate["commit"])
        candidate["worktree"] = str(path)
    searched = evaluator.evaluate("e1-T1-1", 1, root / "repo", other, None)
    assert json.loads(Path(searched.logs[1]).read_text())["seeds"] is None
    evaluator.confirm(candidates, 1)
    seeds = {json.loads(next((root / "logs/e1" / key / "confirmation").rglob("correctness.log")).read_text())["seeds"]
             for key in ("baseline-e1", "a")}
    assert len(seeds) == 1 and None not in seeds and len(seeds.pop().split(",")) == 4
    assert evaluator.confirmation_environment is None


def test_default_checker_uses_drawn_confirmation_seeds(tmp_path, need_compiler):
    from importlib.resources import files

    from hpc_forest.toolchain import build

    assets = Path(str(files("hpc_forest") / "assets"))
    source = tmp_path / "matmul"
    source.mkdir()
    (source / "src").mkdir()
    for name in ("main.c", "params.h"):
        (source / "src" / name).write_bytes((assets / "matmul/src" / name).read_bytes())
    assert build(source, tmp_path / "build") == 0
    binary = next(p for p in (tmp_path / "build").iterdir() if p.name.startswith("solution"))
    checker = [sys.executable, str(assets / "validation/check.py"), str(binary), "confirmation"]
    drawn = subprocess.run(checker, capture_output=True, text=True,
                           env={**os.environ, "FOREST_CONFIRMATION_SEEDS": "11,22,33,44"})
    assert json.loads(drawn.stdout) == {"correct": True, "cases": 8, "phase": "confirmation", "seeds": [11, 22, 33, 44]}
    fixed = subprocess.run(checker, capture_output=True, text=True)
    assert json.loads(fixed.stdout)["seeds"] == [99, 103, 107, 109]
