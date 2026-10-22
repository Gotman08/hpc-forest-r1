"""Phase and in-flight accounting without running a model campaign."""
import pytest
from test_reserve_forecast import recorded_search

from hpc_forest.adaptive_budget import forecast, record_timing


def independent(db, *, count=4):
    config = db.get("config")
    config["backend"] = "codex"  # Match Mother/Luna's nominal call cost, not the recipe demo.
    config["forest"] = {"policy": "mother", "conversation": "persistent", "integration": "pairwise"}
    config["completion"].update(reserve_policy="adaptive", policy="finish-started", confirm_final_g=True)
    config["budget"]["tokens"] = None
    db.set("config", config)
    db.set("current_epoch", 1)
    db.set("forest_plan:1", {"children": [{"role": f"T{i}"} for i in range(1, count + 1)]})
    db.set("research_scheduler:1", {"policy": "independent-v1"})
    return db


def test_queued_siblings_and_elapsed_generation_are_not_recharged_as_a_wave(db):
    independent(db)
    now = 1000
    for role in ["T1", "T2", "T3", "T4"]:
        record_timing(db, "generation:" + role, 100)
        record_timing(db, "evaluation_work:" + role, 10)
        record_timing(db, "mission:" + role, 900)  # Old wave waits must not pollute the forecast.
    record_timing(db, "research_wave:4", 1200)
    db.set("research_pending:1", [
        {"role": "T2", "started_at": now - 90, "phase": "generation"},
        {"role": "T3", "started_at": now - 100, "phase": "evaluation"},
    ])
    decision = forecast(db, ["T1"], now=now)
    # T3 evaluates 0..10, T2 evaluates 10..20, new T1 generates 0..100 and evaluates 100..110.
    assert decision["predicted_drain_seconds"] == 110
    assert decision["next_work_seconds"] == 1.25 * 110
    assert decision["inflight_roles"] == ["T2", "T3"]
    assert decision["research_estimate_source"] == "generation_and_exclusive_evaluation"


def test_confirmation_repeats_only_timing_not_compilation_and_correctness(db):
    independent(db, count=1)
    config = db.get("config")
    config["protocol"].update(repetitions=3, confirmation_repetitions=5, warmups=0)
    db.set("config", config)
    record_timing(db, "evaluation_work:baseline", 15)
    record_timing(db, "evaluation_benchmark:baseline", 3)
    record_timing(db, "evaluation_work:G", 10)
    record_timing(db, "evaluation_benchmark:G", 3)
    assert forecast(db)["confirmation_seconds"] == pytest.approx(17 + 3 * 12)


def test_fusion_generation_and_exclusive_work_exclude_prior_queue_waits(db):
    independent(db)
    record_timing(db, "generation:G", 90)
    record_timing(db, "evaluation_work:G", 10)
    record_timing(db, "evaluation_lock_wait:G", 1000)
    record_timing(db, "mission:G", 1100)
    decision = forecast(db)
    assert decision["final_g_seconds"] == 100
    assert decision["integration_seconds"] == 300


@pytest.mark.parametrize("duration", [1800, 7200, 18000, 86400])
def test_reserve_does_not_scale_with_requested_campaign_duration(db, duration):
    independent(db)
    recorded_search(db)
    db.set("deadline", 1000 + duration)
    expected = forecast(db, ["T1"], now=1000)["reserve_seconds"]
    db.set("deadline", 1000 + duration * 2)
    assert forecast(db, ["T1"], now=1000)["reserve_seconds"] == expected


def test_cuda_772923_admission_replay_does_not_require_another_whole_wave(db):
    """Recorded wall times and the declared prior only, never a new model/GPU result."""
    independent(db)
    db.set("research_scheduler:1", {})  # Compare the retained historical estimator.
    config = db.get("config")
    config["protocol"].update(repetitions=3, confirmation_repetitions=5, warmups=0)
    db.set("config", config)
    record_timing(db, "baseline", 15.72364354133606)
    for value in [195.69392356462777, 231.30723954644054, 314.0925364494324]:
        record_timing(db, "research_wave:4", value)
    now = 1000
    db.set("deadline", now + 898.1559686660767)
    old = forecast(db, ["T1", "T2", "T3", "T4"], now=now)
    assert not old["can_admit"]
    db.set("research_scheduler:1", {"policy": "independent-v1"})
    new = forecast(db, ["T1", "T2", "T3", "T4"], now=now)
    assert new["can_admit"]
    assert new["reserve_seconds"] == pytest.approx(old["reserve_seconds"])
    assert new["next_work_seconds"] < old["next_work_seconds"]
    # With actual phase observations, the estimator uses those instead of the prior.
    for role in ["T1", "T2", "T3", "T4"]:
        record_timing(db, "generation:" + role, 240)
    assert not forecast(db, ["T1", "T2", "T3", "T4"], now=now)["can_admit"]
