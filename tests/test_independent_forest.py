"""Offline scheduling regressions: real AB-MCTS-A, no hosted model or GPU job."""
import copy
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_mother_conversation import native_campaign

from hpc_forest.backends import Generated
from hpc_forest.core import BudgetExhausted, ForestError, InfrastructureError


class UnevenModels:
    def __init__(self, *, fail_fast=False):
        self.initial = threading.Barrier(2, timeout=10)
        self.fast_settled = threading.Event()
        self.slow_finished = threading.Event()
        self.calls = []
        self.fail_fast = fail_fast

    def generate(self, mission, context, config, root):
        self.calls.append((copy.deepcopy(mission), copy.deepcopy(context)))
        if mission.ordinal == 1:
            self.initial.wait()
        if mission.role == "T2":
            assert self.fast_settled.wait(10), "Slow tree was awaited before the fast tree could advance"
            self.slow_finished.set()
        elif self.fail_fast:
            raise InfrastructureError("Offline generation failure")
        elif mission.ordinal == 2:
            assert not self.slow_finished.is_set()
            history = context["automatic_observations"]["own_role_history"]
            assert history and history[0]["status"] == "valid" and history[0]["score"] > 0
        path = root / "worktrees" / mission.id / "src/params.h"
        tile = (8 if mission.role == "T1" else 32) + mission.ordinal
        path.write_text(re.sub(r"#define TILE \d+", f"#define TILE {tile}", path.read_text()))
        return Generated(7, {"llm_calls": 1, "backend": "offline-fixture"})


@pytest.mark.parametrize("failure", [None, "generation", "setup"])
def test_fast_tree_continues_after_its_score_and_all_admitted_work_drains(
    tmp_path, monkeypatch, need_compiler, failure,
):
    _, controller, native = native_campaign(tmp_path, monkeypatch, 2)
    native.expire_in_planning = False
    models = UnevenModels(fail_fast=failure == "generation")
    controller.backend = models
    controller.config["harness"]["enabled"] = False
    original = controller._complete_generation
    settled, finalized, progress = [], [], []
    if failure == "setup":
        new_mission = controller._new_mission
        def unavailable(*args, **kwargs):
            result = new_mission(*args, **kwargs)
            if result[0].role == "T1" and result[0].ordinal == 2:
                raise InfrastructureError("Offline context setup failed before generation")
            return result
        controller._new_mission = unavailable

    def complete(mission, slot, generated, baseline):
        fatal = original(mission, slot, generated, baseline)
        settled.append((mission.role, mission.ordinal))
        if mission.role == "T1" and (failure == "generation" or mission.ordinal == 2):
            controller.db.set("deadline", time.time() - 1)
            models.fast_settled.set()
        return fatal

    def finalize(controller, epoch, baseline):
        assert models.slow_finished.is_set()
        assert not controller.db.rows("SELECT id FROM trials WHERE state='pending'")
        assert not controller.db.get("research_pending:1")
        finalized.append(True)

    controller._complete_generation = complete
    monkeypatch.setattr("hpc_forest.controller.finalize", finalize)
    with controller:
        result = controller.run(on_progress=lambda state: progress.append(copy.deepcopy(state)))
        assert finalized == [True]
        assert len(native.calls) == 1  # Only offline Mother planning, never another decomposition.
        assert result["research_scheduler"]["parallelism"] == 2
        assert result["research_scheduler"]["policy"] == "independent-v1"
        assert controller.db.costs()["tokens_reserved"] == 0
        assert controller.db.one("SELECT count(*) AS n FROM trials WHERE role='T2'")["n"] == 1
        assert progress and all(state["research_scheduler"]["policy"] == "independent-v1" for state in progress)
        if failure:
            assert result["status"] == "infrastructure_error"
            assert len(models.calls) == 2
        else:
            assert result["status"] == "budget_exhausted"
            assert settled.index(("T1", 2)) < settled.index(("T2", 1))
            assert len(models.calls) == 3
            assert len(controller.db.get("timing_samples")["generation:T1"]) == 2


def test_initial_setup_failure_never_dispatches_a_partial_forest_or_replays_it(
    tmp_path, monkeypatch, need_compiler,
):
    _, controller, native = native_campaign(tmp_path, monkeypatch, 2)
    original = controller._new_mission
    def unavailable(*args, **kwargs):
        result = original(*args, **kwargs)
        if result[0].role == "T2":
            raise InfrastructureError("Offline initial context failure")
        return result
    controller._new_mission = unavailable
    with controller:
        with pytest.raises(InfrastructureError, match="initial context"):
            controller.run()
        assert len(native.calls) == 1  # Mother only; no model from a partial cohort.
        slots = controller.db.rows("SELECT * FROM slots WHERE purpose LIKE 'role:%'")
        assert len(slots) == 2 and all(s["tokens_settled"] == 1 and s["tokens_used"] == 0 for s in slots)
        with pytest.raises(ForestError, match="interrupted initial research wave"):
            controller.run()
        assert len(native.calls) == 1


def test_evaluation_queues_for_busy_target_without_infrastructure_failure(tmp_path):
    from hpc_forest.core import FileLock
    from hpc_forest.evaluator import Evaluator

    evaluator = Evaluator.__new__(Evaluator)
    evaluator.lock_path, evaluator.deadline = tmp_path / "target.lock", None
    entered = threading.Event()
    def use_target():
        with evaluator._target():
            entered.set()
    with ThreadPoolExecutor(1) as pool:
        with FileLock(evaluator.lock_path):
            future = pool.submit(use_target)
            assert not entered.wait(0.1)
        future.result(timeout=2)
    assert entered.is_set() and evaluator.last_wall_times["lock_wait_seconds"] >= 0
    assert evaluator.last_wall_times["work_seconds"] >= 0
    with FileLock(evaluator.lock_path):
        evaluator.deadline = time.time() - 1
        with pytest.raises(BudgetExhausted, match="expired waiting for target"), evaluator._target():
            pytest.fail("An expired hard-deadline evaluation must not acquire the target")
