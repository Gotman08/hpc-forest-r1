"""Time-driven lifecycle, including final G independently of its search rank."""

import copy
import json
import time
from types import SimpleNamespace

import pytest

from hpc_forest.adaptive_budget import admit, forecast, parse_duration, record_timing
from hpc_forest.backends import Generated
from hpc_forest.config import load_config, validate
from hpc_forest.controller import Controller
from hpc_forest.core import BudgetExhausted, Outcome
from hpc_forest.search import Search


@pytest.fixture
def adaptive_config(finish_started_config):
    finish_started_config["completion"].update(reserve_policy="adaptive", confirm_final_g=True)
    finish_started_config["budget"].update(search_slots=None, max_depth=0, wall_seconds=1800)
    finish_started_config["schedule"]["cycles"] = None
    return finish_started_config


@pytest.mark.parametrize("duration,seconds", [("30m", 1800), ("2h", 7200), ("5h", 18000),
                                               ("24h", 86400), ("1h30m", 5400), ("2d", 172800)])
def test_configurable_duration_without_cycle_or_token_ceiling(duration, seconds):
    config = load_config()
    config["budget"]["wall_seconds"] = parse_duration(duration)
    validate(config)
    assert config["budget"]["wall_seconds"] == seconds
    assert config["budget"]["tokens"] is config["budget"]["mission_tokens"] is None
    assert config["budget"]["search_slots"] is config["schedule"]["cycles"] is None


@pytest.mark.parametrize("duration", ["0", "-1h", "nan", "inf", "2 hours", "1h30", "", "30x"])
def test_duration_rejects_ambiguous_or_nonfinite_values(duration):
    with pytest.raises(ValueError):
        parse_duration(duration)


@pytest.mark.parametrize("value", [None, True, float("nan"), float("inf"), 10**400, -1, 0])
def test_invalid_reserve_settings_fail_before_execution(adaptive_config, value):
    from hpc_forest.core import ForestError

    adaptive_config["completion"]["initial_model_seconds"] = value
    with pytest.raises(ForestError):
        validate(adaptive_config)


def test_cli_duration_initializes_an_unlimited_adaptive_campaign(tmp_path, monkeypatch):
    from hpc_forest import cli

    captured = {}
    def create(path, config, source, validation):
        captured.update(config)
        return path
    monkeypatch.setattr(cli, "create_workspace", create)
    assert cli.main(["init", str(tmp_path / "new"), "--duration", "24h", "--binary-tree"]) == 0
    validate(captured)
    assert captured["budget"]["wall_seconds"] == 86400
    assert captured["binary_tree"]["enabled"]
    assert captured["completion"]["confirm_final_g"]


def test_all_exhausted_trees_stop_without_spinning(db, tmp_path, adaptive_config, monkeypatch):
    from hpc_forest.search.binary import SearchExhausted

    db.set("config", adaptive_config)
    db.set("current_epoch", 1)
    db.set("deadline", time.time() + 1800)
    controller = Controller.__new__(Controller)
    controller.root, controller.db, controller.config = tmp_path, db, adaptive_config
    controller.search = Search(db)
    controller._start = lambda: setattr(controller, "evaluator", SimpleNamespace(deadline=None))
    controller._baseline = lambda epoch: {"mean_seconds": 2}
    def exhausted(*args):
        raise SearchExhausted("All finite trees exhausted")
    controller._new_mission = exhausted
    finalized = []
    monkeypatch.setattr("hpc_forest.controller.finalize", lambda *args: finalized.append(True))
    state = controller.run()
    assert state["status"] == "search_complete" and len(finalized) == 1
    assert state["completed_batches"] == len(controller.plan())


def test_reserve_learns_wall_times_and_persists_across_restarts(db, adaptive_config):
    db.set("config", adaptive_config)
    db.set("mother_enabled", True)
    now = time.time()
    db.set("deadline", now + 1800)
    initial = forecast(db, ["A"], now=now)
    record_timing(db, "baseline", 2)
    record_timing(db, "mother", 30)
    record_timing(db, "mission:A", 75)
    record_timing(db, "mission:G", 90)
    learned = forecast(db, ["A"], now=now)
    assert learned["reserve_seconds"] != initial["reserve_seconds"]
    assert learned["mother_seconds"] == 30 and learned["final_g_seconds"] == 90
    for duration in [7200, 18000, 86400]:
        db.set("deadline", now + duration)
        assert forecast(db, now=now)["reserve_seconds"] == learned["reserve_seconds"]
    from hpc_forest.registry import Registry

    reopened = Registry(db.path)
    try:
        assert forecast(reopened, ["A"], now=now)["next_work_seconds"] == learned["next_work_seconds"]
    finally:
        reopened.close()
    for sample in range(30):
        record_timing(db, "mother", sample)
    assert len(db.get("timing_samples")["mother"]) == 12


def test_admission_includes_pending_siblings_and_reserves_the_entire_finish(db, adaptive_config):
    db.set("config", adaptive_config)
    db.set("current_epoch", 1)
    record_timing(db, "baseline", 1)
    record_timing(db, "mission:A", 100)
    reserve = forecast(db)["reserve_seconds"]
    db.set("deadline", time.time() + reserve + 130)
    admit(db, ["A"])
    with pytest.raises(BudgetExhausted, match="Mother, final G"):
        admit(db, ["A", "B"])
    decision = db.get("adaptive_budget:1")
    assert decision["pending_roles"] == ["A", "B"] and not decision["can_admit"]


def test_pending_node_can_finish_its_mother_after_admission_closes(db, adaptive_config):
    db.set("config", adaptive_config)
    db.set("current_epoch", 1)
    db.set("deadline", time.time() + 1800)
    search = Search(db)
    tree = search.initialize(1, "A", 23)
    slot = db.reserve("search", "role:A")
    mission = search.ask(tree, ["A"], 1, "base", 1, "unused", slot)
    db.set("deadline", time.time() - 1000)
    with pytest.raises(BudgetExhausted):
        db.reserve("search", "role:B")
    mother = db.reserve("search", "mother:preparation", continuation_of=mission.id)
    db.settle_tokens(mother, None)
    assert db.costs()["unknown_usage_calls"] == 1
    search.finish(mission, Outcome("valid", correct=True, commit="abc", mean_seconds=1, score=0.5))
    from hpc_forest.core import ForestError

    with pytest.raises(ForestError, match="pending"):
        db.reserve("search", "mother:synthesis", continuation_of=mission.id)


@pytest.mark.parametrize("binary", [False, True])
def test_real_trees_repeat_past_old_trial_limit_and_resume_with_same_deadline(
        db, tmp_path, adaptive_config, monkeypatch, binary):
    config = copy.deepcopy(adaptive_config)
    config["binary_tree"]["enabled"] = binary
    config["budget"]["max_workers"] = 1
    config["schedule"].update(trials_per_role_per_cycle=2, integrations_per_cycle=2)
    db.set("config", config)
    db.set("current_epoch", 1)
    deadline = time.time() + 86400
    db.set("deadline", deadline)
    controller = Controller.__new__(Controller)
    controller.root, controller.db, controller.config = tmp_path, db, config
    controller.search = Search(db)
    controller.backend = SimpleNamespace(generate=lambda *args: Generated(0))
    controller._start = lambda: setattr(controller, "evaluator", SimpleNamespace(deadline=None))
    controller._baseline = lambda epoch: {"mean_seconds": 2}
    controller._context = lambda *args: {"fixture": True}
    controller._evaluate_mission = lambda mission, baseline: Outcome(
        "valid", correct=True, commit=mission.id, tree_hash=mission.id,
        mean_seconds=1 / mission.ordinal, score=0.5)
    monkeypatch.setattr("hpc_forest.controller.make_worktree", lambda *args: None)
    with pytest.raises(BudgetExhausted):
        # No call is made: the reserve is a prerequisite, even with no slot cap.
        short = forecast(db)["reserve_seconds"]
        db.set("deadline", time.time() + short - 1)
        admit(db, ["A"])
    db.set("deadline", deadline)
    first = controller.run(max_batches=72)  # Nine cycles, 18 trials per role.
    assert first["status"] == "checkpointed" and first["completed_batches"] == 72
    assert len(db.rows("SELECT * FROM trials WHERE role='A'")) == 18
    next_state = controller.run(max_batches=8)
    assert next_state["completed_batches"] == 80 and db.get("deadline") == deadline
    assert all(row["state"] == "completed" for row in db.rows("SELECT state FROM trials"))


def test_final_g_below_top_two_is_confirmed_in_an_extra_slot_once(
        tmp_path, adaptive_config, monkeypatch, need_compiler):
    from test_finish_started import mother_controller

    root, controller_type, model, mothers = mother_controller(tmp_path, adaptive_config, monkeypatch)
    with controller_type(root) as controller:
        state = controller.run()  # Fixture A expires the target while running.
        assert state["status"] == "budget_exhausted"
        final_id = state["postprocess"]["mission_id"]
        final_commit = state["postprocess"]["outcome"]["commit"]
        actual = controller.db.archive(1)
        # Simulate two search finalists ahead of G using real valid source commits.
        search = next(item for item in actual if item["id"] != final_id)
        finalists = [{**search, "id": "faster-one", "mean_seconds": 0.001},
                     {**search, "id": "faster-two", "commit": controller.epoch()["base_commit"],
                      "mean_seconds": 0.002}]
        # A second unique commit with the same valid source is sufficient for
        # this rank/admission regression; the independent evaluator still runs.
        from hpc_forest.gitops import git

        git(root / "repo", "commit", "--allow-empty", "-m", "fixture independent finalist")
        finalists[1]["commit"] = git(root / "repo", "rev-parse", "HEAD")
        monkeypatch.setattr(controller.db, "archive", lambda *args: [*finalists,
                             {**actual[0], "id": final_id, "commit": final_commit, "mean_seconds": 1}])
        calls_before = len(model.calls), len(mothers)
        controller.confirm()
        plan = controller.db.get("confirmation_plan:1")
        assert [item["id"] for item in plan] == ["baseline-e1", "faster-one", "faster-two", final_id]
        assert controller.db.costs("confirmation")["slots"] == 4
        final = controller.status()["final_g_confirmation"]
        assert final["status"] == "confirmed" and final["experiment_id"] == final_id
        assert final["outcome"]["commit"] == final_commit and len(final["outcome"]["times"]) == 2
        assert controller.evaluator.deadline is None and controller.db.get("deadline") < time.time()
        controller.confirm()
        assert controller.db.costs("confirmation")["slots"] == 4
        assert (len(model.calls), len(mothers)) == calls_before


def test_invalid_final_g_is_independently_rejected_and_cannot_win(
        tmp_path, adaptive_config, monkeypatch, need_compiler):
    from test_finish_started import mother_controller

    root, controller_type, _, _ = mother_controller(tmp_path, adaptive_config, monkeypatch, invalid_final=True)
    with controller_type(root) as controller:
        controller.run()
        best = controller.confirm()
        final = controller.status()["final_g_confirmation"]
        assert final["status"] == "rejected" and final["outcome"]["correct"] is False
        assert best["experiment_id"] != final["experiment_id"]
    from hpc_forest.reporting import package

    package(root, root / "submission.zip")


def test_confirmation_resumes_after_worktree_failure_without_new_model_calls_or_slots(
        tmp_path, adaptive_config, monkeypatch, need_compiler):
    from test_finish_started import mother_controller

    import hpc_forest.controller as module

    root, controller_type, model, mothers = mother_controller(tmp_path, adaptive_config, monkeypatch)
    with controller_type(root) as controller:
        state = controller.run()
        final_id = state["postprocess"]["mission_id"]
        before = len(model.calls), len(mothers)
        original = module.make_worktree
        def fail_final(repo, path, branch, commit):
            if branch.startswith("confirm/") and str(path).endswith(final_id):
                raise OSError("fixture interrupted worktree creation")
            return original(repo, path, branch, commit)
        monkeypatch.setattr(module, "make_worktree", fail_final)
        with pytest.raises(OSError, match="interrupted"):
            controller.confirm()
        reserved = controller.db.rows("SELECT id,purpose FROM slots WHERE phase='confirmation'")
        monkeypatch.setattr(module, "make_worktree", original)
        best = controller.confirm()
        assert best["commit"] and controller.status()["final_g_confirmation"]["status"] == "confirmed"
        after = controller.db.rows("SELECT id,purpose FROM slots WHERE phase='confirmation'")
        assert all(slot in after for slot in reserved)
        assert len(after) == len(controller.db.get("confirmation_plan:1"))
        assert len({slot["purpose"] for slot in after}) == len(after)
        assert (len(model.calls), len(mothers)) == before


def test_legacy_finite_configuration_keeps_its_limits(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"budget": {"search_slots": 9, "tokens": 300000, "mission_tokens": 16000},
                                "schedule": {"cycles": 1}}))
    config = load_config(path)
    assert config["schedule"]["cycles"] == 1 and config["budget"]["search_slots"] == 9
    assert "reserve_policy" not in config["completion"]


def test_cli_finishes_report_archive_and_done_after_the_target(
        tmp_path, adaptive_config, monkeypatch, need_compiler):
    from test_finish_started import mother_controller

    from hpc_forest import cli

    root, controller_type, _, _ = mother_controller(tmp_path, adaptive_config, monkeypatch)
    monkeypatch.setattr(cli, "Controller", controller_type)
    assert cli.main(["run", str(root)]) == 0
    done = json.loads((root / "DONE.json").read_text())
    report = json.loads((root / "report/experiments.json").read_text())
    assert done["pipeline_complete"] and done["overrun_seconds"] > 0
    assert (root / "submission.zip").is_file()
    assert report["final_g_confirmation"]["status"] == "confirmed"
    assert report["timing"]["adaptive_reserve"]["reserve_seconds"] > 0


def test_archived_mailbox_keeps_more_than_500_completed_requests_without_filling_inbox(tmp_path):
    from hpc_forest import codex_mailbox as mailbox

    channel = tmp_path / "mailbox"
    mailbox.initialize_channel(channel, "a" * 32, "fixture")
    for index in range(501):
        request = {"nonce": f"{index:032x}", "session_id": "a" * 32, "expires_at": None,
                   "archive_request_after_response": True,
                   "model": mailbox.MODEL, "reasoning_effort": mailbox.EFFORT}
        sha = mailbox.publish_request(channel, request)
        mailbox.publish_response(channel, mailbox.response_envelope(request, sha, data={"ok": True}))
        assert mailbox.wait_response(channel, request, sha)["data"]["ok"]
    assert not list((channel / "requests").iterdir())
    archived = list((channel / "archive/requests").iterdir())
    assert len(archived) == 501
    assert json.loads(archived[-1].read_text())["archive_request_after_response"]


def test_cli_failure_receipt_does_not_claim_completion(tmp_path):
    from hpc_forest.cli import complete_local
    from hpc_forest.core import ForestError

    def fail():
        raise ForestError("Final confirmation unavailable")
    controller = SimpleNamespace(db=SimpleNamespace(get=lambda key: time.time() - 5), confirm=fail)
    with pytest.raises(ForestError, match="unavailable"):
        complete_local(controller, tmp_path)
    done = json.loads((tmp_path / "DONE.json").read_text())
    assert done["pipeline_complete"] is False and "unavailable" in done["error"]


def test_long_campaign_context_keeps_every_source_identity_without_unbounded_diffs(
        db, tmp_path, adaptive_config, monkeypatch):
    import hpc_forest.controller as module
    from hpc_forest.source_request import proposal_messages

    db.set("config", adaptive_config)
    controller = Controller.__new__(Controller)
    controller.root, controller.db, controller.config = tmp_path, db, adaptive_config
    controller.search = SimpleNamespace(binary=False)
    controller.epoch = lambda: {"base_commit": "base"}
    diffs = []
    monkeypatch.setattr(module, "git", lambda *args: diffs.append(args) or "x" * 6000)
    monkeypatch.setattr(module, "measured_observations", lambda *args: {})
    monkeypatch.setattr(module, "Knowledge", lambda db: SimpleNamespace(query=lambda text: []))
    sources = [{"id": str(index), "role": "ABCG"[index % 4], "commit": "commit" + str(index),
                "mean_seconds": 1 + index / 1000, "ordinal": index + 1,
                "transformations": {"retained": ["fixture transformation"]}} for index in range(1000)]
    mission = SimpleNamespace(id="final", ordinal=1, role="G", epoch=1, budget_phase="postprocess",
                              sources=[item["id"] for item in sources])
    context = controller._context(mission, sources)
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.c").write_text("int main(void) {return 0;}")
    request = proposal_messages(tmp_path, mission, context)
    assert len(context["sources"]) == 1000 and len(diffs) == 16
    assert request["schema"]["properties"]["sources_kept"]["items"]["enum"] == mission.sources
    assert len(json.dumps(request).encode()) < 2 * 1024 * 1024
