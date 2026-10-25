"""Deadline regressions with offline fixtures: no hosted model or HPC calls."""

import copy
import json
import sys
import threading
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from hpc_forest import codex_mailbox as mailbox
from hpc_forest import codex_process
from hpc_forest.backends import Generated, RecipeBackend
from hpc_forest.config import load_config, validate
from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import BudgetExhausted, ForestError, InfrastructureError, digest, run_process
from hpc_forest.gitops import git
from hpc_forest.mother import MotherContext, plan_for
from hpc_forest.registry import Registry
from hpc_forest.reporting import package, report
from hpc_forest.search import Search
from hpc_forest.support.budgets import (
    FINISH_STARTED,
    generation_deadline,
    postprocess_token_limit,
    unlimited_tokens,
)


def test_new_default_is_soft_but_frozen_missing_policy_keeps_hard_contract():
    current = load_config()
    assert current["completion"]["policy"] == FINISH_STARTED
    assert current["budget"]["tokens"] is None and current["budget"]["mission_tokens"] is None
    assert unlimited_tokens(current)
    assert not unlimited_tokens({}) and not unlimited_tokens({"budget": {}})
    assert postprocess_token_limit(current) is None
    assert generation_deadline({"deadline": 50, "generation_deadline": 40}, 10, now=10) == 20
    assert generation_deadline({"deadline": -1, "deadline_policy": FINISH_STARTED}, 1) is None


@pytest.mark.parametrize("policy", [None, True, "unlimited-search"])
def test_invalid_completion_policy_is_rejected(config, policy):
    config["completion"] = {"policy": policy}
    with pytest.raises(ForestError, match="completion.policy"):
        validate(config)


def test_final_phase_is_persisted_before_generation_and_recovery_keeps_absent_score(db):
    config = db.get("config")
    config["backend"] = "codex"  # An interrupted model call has uncertain usage; a recipe uses exactly zero.
    config["completion"] = {"policy": FINISH_STARTED}
    db.set("config", config)
    search = Search(db)
    tree = search.initialize(1, "G-final", 23)
    slot = db.reserve("postprocess", "postprocess:e1:role:G", 16)
    mission = search.ask(tree, ["G"], 1, "base", 1, "", slot, budget_phase="postprocess")
    stored = db.one("SELECT mission FROM trials WHERE id=?", (mission.id,))
    assert json.loads(stored["mission"])["budget_phase"] == "postprocess"
    assert search.recover_pending() == 1
    assert not db.evaluations("search")
    assert db.evaluations("postprocess")[0]["outcome"]["score"] is None
    assert db.costs("postprocess")["unknown_usage_calls"] == 1


@pytest.mark.parametrize("authorized", [True, False])
@pytest.mark.parametrize("token_policy", ["limited", "observe-only"])
def test_native_model_has_no_subprocess_timer_only_with_completion_authorization(
    tmp_path, monkeypatch, authorized, token_policy,
):
    gate = {"completion": {"policy": FINISH_STARTED, "token_policy": token_policy}} if authorized else {}
    monkeypatch.setattr(codex_process, "check_dependencies", lambda *args: gate)
    def command(request, output, *args, **kwargs):
        (output / "instructions.txt").write_text(request["messages"][0]["content"])
        return ["offline-command-fixture"]
    monkeypatch.setattr(codex_process, "command_for", command)
    observed = []
    def process(argv, output, log, timeout, **kwargs):
        observed.append(timeout)
        log.write_text(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 2, "output_tokens": 1}}))
        (output / "agent-result.json").write_text('{"fixture":true}')
        return SimpleNamespace(returncode=0, timed_out=False, log=str(log))
    monkeypatch.setattr(codex_process, "run_process", process)
    request = {"nonce": "b" * 32, "session_id": "a" * 32, "expires_at": None,
               "model": mailbox.MODEL, "reasoning_effort": mailbox.EFFORT,
               "deadline_policy": FINISH_STARTED, "budget_phase": "postprocess",
               "token_policy": token_policy,
               "messages": [{"role": "system", "content": "fixture"}, {"role": "user", "content": "fixture"}]}
    if authorized:
        result = codex_process.run_codex(request, digest(request), tmp_path, tmp_path / "receipt", set())
        assert result["error"] is None and result["usage"]["tokens"] == 3
        assert observed == [None]
    else:
        with pytest.raises(InfrastructureError, match="authorization"):
            codex_process.run_codex(request, digest(request), tmp_path, tmp_path / "receipt", set())
        assert not observed


def test_postprocessing_has_two_separately_accounted_reservations_after_cutoff(db):
    config = db.get("config")
    config["completion"] = {"policy": FINISH_STARTED}
    db.set("config", config)
    db.set("deadline", time.time() - 1)
    with pytest.raises(BudgetExhausted):
        db.reserve("search", "late-child")
    child = db.reserve("postprocess", "postprocess:e1:role:G", config["budget"]["mission_tokens"])
    mother = db.reserve("postprocess", "postprocess:e1:mother:synthesis", mailbox.TOKEN_CEILING)
    assert db.costs("postprocess")["tokens_reserved"] == config["budget"]["mission_tokens"] + mailbox.TOKEN_CEILING
    assert db.costs("search")["slots"] == 0
    db.settle_tokens(child, 23)
    db.settle_tokens(mother, 11)
    assert db.costs("postprocess")["exact_tokens_used"] == 34
    with pytest.raises(BudgetExhausted, match="slot limit"):
        db.reserve("postprocess", "postprocess:e1:extra")
    db.set(f"confirmation_deadline:{1}", time.time() + 20)
    assert db.reserve("confirmation", "baseline")
    db.set("deadline", time.time() + 600)
    db.set("search_closed:1", time.time())
    with pytest.raises(BudgetExhausted, match="permanently closed"):
        db.reserve("search", "no-reopen")


def test_no_quota_records_usage_but_never_blocks_admission_on_tokens(db, finish_started_config):
    db.set("config", finish_started_config)
    first = db.reserve("search", "large", 999999999)
    assert db.costs()["tokens_reserved"] == 0
    db.settle_tokens(first, 999999999)
    second = db.reserve("search", "missing-final-usage")
    db.settle_tokens(second, None, observed_tokens=123)
    assert db.reserve("search", "allowed-after-unknown")
    assert db.costs()["tokens_used"] == 1000000122
    assert db.costs()["exact_tokens_used"] == 999999999
    assert db.costs()["unknown_usage_calls"] == 1


@pytest.mark.parametrize("tokens", [mailbox.TOKEN_CEILING + 1000000, None])
def test_uncapped_mother_uses_valid_plan_with_large_or_missing_final_usage(
    db, tmp_path, finish_started_config, monkeypatch, tokens,
):
    config = finish_started_config
    config["backend"] = "codex"
    config["codex"].update(model=mailbox.MODEL, reasoning_effort=mailbox.EFFORT,
                           session_id="a" * 32, mailbox_dir=str(tmp_path / "mailbox"))
    db.set("config", config)
    worktree = tmp_path / "program"
    (worktree / "src").mkdir(parents=True)
    (worktree / "src/main.c").write_text("int main(void) { return 0; }\n")
    controller = SimpleNamespace(db=db, config=config, statement="offline fixture", root=tmp_path)
    mission = SimpleNamespace(epoch=1, worktree=str(worktree))
    monkeypatch.setattr(mailbox, "publish_request", lambda channel, request: digest(request))
    def receive(channel, request, sha):
        assert request["token_ceiling"] is None and request["expires_at"] is None
        return mailbox.response_envelope(request, sha,
            data={key: "fixture" for key in ("analysis", "A", "B", "C", "G")},
            usage={"tokens": tokens, "token_accounting": "unknown" if tokens is None else "exact"})
    monkeypatch.setattr(mailbox, "wait_response", receive)
    result = plan_for(controller, mission, {"deadline_policy": FINISH_STARTED,
                                           "budget_phase": "postprocess"}, "synthesis")
    assert result["status"] == "complete"
    assert db.costs()["exact_tokens_used"] == (tokens or 0)
    assert db.costs()["unknown_usage_calls"] == (tokens is None)
    assert db.reserve("postprocess", "postprocess:e1:role:G")


def test_process_without_deadline_has_no_watchdog(tmp_path, monkeypatch):
    def forbidden_timer(*args, **kwargs):
        raise AssertionError("An unlimited model call must not install a cancellation timer")
    monkeypatch.setattr(threading, "Timer", forbidden_timer)
    result = run_process([sys.executable, "-c", "import time; time.sleep(0.02); print('done')"],
                         tmp_path, tmp_path / "process.log", None)
    assert result.returncode == 0 and not result.timed_out
    assert "done" in Path(result.log).read_text()


def test_unlimited_mailbox_still_verifies_identity_and_receives_completed_response(tmp_path):
    channel = tmp_path / "mailbox"
    mailbox.initialize_channel(channel, "a" * 32, "offline-test")
    request = {"nonce": "b" * 32, "session_id": "a" * 32,
               "model": mailbox.MODEL, "reasoning_effort": mailbox.EFFORT,
               "expires_at": None, "deadline_policy": FINISH_STARTED}
    request_sha = digest(request)
    response = mailbox.response_envelope(request, request_sha, data={"finished": True})
    def complete():
        time.sleep(0.02)
        mailbox.publish_response(channel, response)
    thread = threading.Thread(target=complete)
    thread.start()
    try:
        assert mailbox.wait_response(channel, request, request_sha, poll_seconds=0.005)["data"]["finished"]
    finally:
        thread.join(timeout=2)
    assert not thread.is_alive()


@pytest.mark.parametrize("alive", [True, False])
def test_unlimited_wait_distinguishes_long_running_model_from_dead_worker(tmp_path, monkeypatch, alive):
    channel = tmp_path / "mailbox"
    mailbox.initialize_channel(channel, "a" * 32, "offline-test")
    request = {"nonce": "b" * 32, "session_id": "a" * 32, "expires_at": None,
               "model": mailbox.MODEL, "reasoning_effort": mailbox.EFFORT}
    sha = digest(request)
    clock = [0]
    def tick(_):
        clock[0] += 60
        if alive:
            (channel / "worker-heartbeat.json").write_text(json.dumps({
                "session_id": "a" * 32, "model": mailbox.MODEL,
                "reasoning_effort": mailbox.EFFORT, "alive_at": clock[0]}))
            if clock[0] >= 3600:
                mailbox.publish_response(channel, mailbox.response_envelope(request, sha, data={"done": True}))
    monkeypatch.setattr(mailbox, "time", SimpleNamespace(monotonic=lambda: clock[0], sleep=tick))
    if alive:
        assert mailbox.wait_response(channel, request, sha)["data"]["done"]
        assert clock[0] == 3600  # A full hour, without a model timeout.
    else:
        with pytest.raises(InfrastructureError, match="heartbeats"):
            mailbox.wait_response(channel, request, sha)
        assert clock[0] == mailbox.HEARTBEAT_GRACE_SECONDS


class OfflineModel:
    """Real recipe edits and compilation, with fixture model responses only."""

    def __init__(self, *, repair=False, invalid_final=False, tokens=7):
        self.calls = []
        self.repair, self.invalid_final = repair, invalid_final
        self.tokens = tokens

    def generate(self, mission, context, config, root):
        self.calls.append((mission.role, mission.budget_phase, copy.deepcopy(context)))
        assert context["deadline"] is None and generation_deadline(context, 1) is None
        worktree = Path(mission.worktree)
        if self.repair and mission.role == "A" and len(self.calls) > 1:
            original = git(worktree, "show", mission.base_commit + ":src/main.c")
            (worktree / "src/main.c").write_text(original + "\n")
        RecipeBackend().generate(mission, context, config, root)
        if mission.role == "A":
            registry = Registry(root / "registry.sqlite3")
            try:
                registry.set("deadline", time.time() - 1)
            finally:
                registry.close()
            if self.repair and len(self.calls) == 1:
                (worktree / "src/main.c").write_text("int main( { broken source\n")
        else:
            params = worktree / "src/params.h"
            params.write_text(params.read_text().replace("#define SIMD 0", "#define SIMD 1"))
            mission.transformations["SIMD"] = 1
            if self.invalid_final:
                (worktree / "src/main.c").write_text("int main( { broken final source\n")
        return Generated(self.tokens, {"llm_calls": 1, "backend": "offline-model-fixture"})


def mother_controller(tmp_path, config, monkeypatch, *, repair=False, invalid_final=False, tokens=7):
    config.update(backend="codex")
    config["budget"].update(tokens=None, mission_tokens=None, max_workers=1)
    config["codex"] = {"model": mailbox.MODEL, "reasoning_effort": mailbox.EFFORT,
                       "session_id": "a" * 32, "mailbox_dir": str(tmp_path / "mailbox")}
    if repair:
        config["harness"].update(enabled=True, max_attempts=2, call_token_ceiling=None)
    calls = []
    def publish(channel, request):
        calls.append(copy.deepcopy(request))
        return digest(request)
    def receive(channel, request, sha):
        plan = {key: "offline fixture guidance" for key in ("analysis", "A", "B", "C", "G")}
        return mailbox.response_envelope(request, sha, data=plan, error=None,
            usage={"tokens": 11, "llm_calls": 1, "token_accounting": "exact"})
    monkeypatch.setattr(mailbox, "publish_request", publish)
    monkeypatch.setattr(mailbox, "wait_response", receive)
    root = create_workspace(tmp_path / "campaign", config)
    model = OfflineModel(repair=repair, invalid_final=invalid_final, tokens=tokens)
    class OfflineController(MotherContext, Controller):
        def __init__(self, root):
            super().__init__(root)
            self.statement = "Offline integer matrix correctness fixture."
            self.backend = model
    return root, OfflineController, model, calls


@pytest.mark.parametrize("repair", [False, True])
def test_started_child_and_repairs_finish_then_fresh_mother_g_and_confirmation(
    tmp_path, finish_started_config, monkeypatch, need_compiler, repair,
):
    root, controller_type, model, mothers = mother_controller(
        tmp_path, finish_started_config, monkeypatch, repair=repair)
    with controller_type(root) as controller:
        # A prior synthesis cannot replace the fresh final synthesis.
        controller.db.set("mother_plan:synthesis", {"status": "complete", "plan": {"G": "old guidance"}})
        result = controller.run(max_batches=1)
        assert result["status"] == "budget_exhausted"
        roles = [role for role, _, _ in model.calls]
        assert roles == (["A", "A", "G"] if repair else ["A", "G"])
        assert result["postprocess"]["status"] == "complete"
        rows = controller.db.rows("SELECT role,mission,result FROM trials ORDER BY created,id")
        assert [row["role"] for row in rows] == ["A", "G"]
        assert all(json.loads(row["result"])["correct"] is True for row in rows)
        assert json.loads(rows[1]["mission"])["budget_phase"] == "postprocess"
        assert len(controller.db.evaluations("postprocess")) == 1
        assert [request["meta_role"] for request in mothers] == ["mother-preparation", "mother-final-synthesis"]
        final = mothers[-1]
        assert final["expires_at"] is None and final["budget_phase"] == "postprocess"
        observations = json.loads(final["messages"][1]["content"])["automatic_observations_as_data"]
        assert len(observations["all_admissible_programs"]) == 1
        assert controller.db.costs("search")["tokens_used"] == (25 if repair else 18)
        assert controller.db.costs("postprocess")["tokens_used"] == 18
        best = controller.confirm()
        assert best["commit"] and controller.evaluator.deadline > time.time()
        assert controller.db.get("deadline") < time.time()
        before = len(model.calls), len(mothers)
        controller.run()
        controller.confirm()
        assert (len(model.calls), len(mothers)) == before
    report(root)
    package(root, root / "submission.zip")
    with zipfile.ZipFile(root / "submission.zip") as archive:
        assert "run.sh" in archive.namelist()
    payload = json.loads((root / "report/experiments.json").read_text())
    assert payload["phase_costs"]["postprocess"]["tokens_used"] == 18
    assert payload["postprocess"]["status"] == "complete"


@pytest.mark.parametrize("stop", ["time", "slots"])
def test_final_mother_and_g_still_run_when_no_search_child_can_be_admitted(
    tmp_path, finish_started_config, monkeypatch, need_compiler, stop,
):
    root, controller_type, model, mothers = mother_controller(tmp_path, finish_started_config, monkeypatch)
    with controller_type(root) as controller:
        controller.run(max_batches=0)
        if stop == "time":
            controller.db.set("deadline", time.time() - 1)
        else:
            while controller.db.costs("search")["slots"] < controller.config["budget"]["search_slots"]:
                slot = controller.db.reserve("search", "consumed")
                controller.db.settle_tokens(slot, 0)
        result = controller.run()
        assert result["status"] == "budget_exhausted"
        assert [role for role, _, _ in model.calls] == ["G"]
        assert [request["meta_role"] for request in mothers] == ["mother-final-synthesis"]
        assert result["postprocess"]["status"] == "complete"
        controller.confirm()
        assert controller.db.get("best_confirmed")
        assert not controller.db.rows("SELECT id FROM trials WHERE role IN ('A','B','C')")


def test_unknown_usage_does_not_interrupt_repair_or_final_integration(
    tmp_path, finish_started_config, monkeypatch, need_compiler,
):
    root, controller_type, model, mothers = mother_controller(
        tmp_path, finish_started_config, monkeypatch, repair=True, tokens=None)
    with controller_type(root) as controller:
        result = controller.run()
        assert [role for role, _, _ in model.calls] == ["A", "A", "G"]
        assert result["postprocess"]["status"] == "complete"
        assert all(context["remaining_tokens"] is None for _, _, context in model.calls)
        assert controller.db.costs()["unknown_usage_calls"] == 2
        assert controller.db.costs()["exact_tokens_used"] == 22  # The two Mother fixtures.
        assert all(request["token_ceiling"] is None for request in mothers)
        assert controller.confirm()["commit"]


def test_invalid_final_integration_keeps_previously_valid_programs(
    tmp_path, finish_started_config, monkeypatch, need_compiler,
):
    root, controller_type, model, mothers = mother_controller(
        tmp_path, finish_started_config, monkeypatch, invalid_final=True)
    with controller_type(root) as controller:
        result = controller.run()
        assert result["postprocess"]["status"] == "complete"
        assert result["postprocess"]["outcome"]["correct"] is False
        integration = result["postprocess"]["mission_id"]
        best = controller.confirm()
        assert best["experiment_id"] != integration
        assert controller.db.archive(1)
