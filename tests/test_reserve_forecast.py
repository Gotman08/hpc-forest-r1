"""Phase separation and admission regressions from ROMEO campaign 772311."""
import time

import pytest
from test_mother_conversation import native_campaign, persistent_settings

from hpc_forest.adaptive_budget import admit, forecast, record_timing
from hpc_forest.core import BudgetExhausted


@pytest.fixture
def pair_budget(db, tmp_path):
    config = persistent_settings(tmp_path)
    config["forest"]["integration"] = "pairwise"
    config["budget"]["wall_seconds"] = 1800
    db.set("config", config)
    db.set("current_epoch", 1)
    db.set("mother_enabled", True)
    db.set("forest_plan:1", {"children": [{"role": f"T{i}"} for i in range(1, 4)]})
    return db


def recorded_search(db):
    """Observed latencies only: no candidate, score or algorithm is imported."""
    record_timing(db, "baseline", 1.6364622116088867)
    record_timing(db, "mother", 158.95749306678772)
    values = {
        "T1": [138.00069785118103, 268.1382167339325, 204.161803483963],
        "T2": [139.65851354599, 269.7642593383789, 206.3708474636078],
        "T3": [141.11140179634094, 271.73189091682434, 207.7533984184265],
    }
    for role, samples in values.items():
        for sample in samples:
            record_timing(db, "mission:" + role, sample)
    for samples in zip(*values.values(), strict=True):
        record_timing(db, "research_wave:3", max(samples))


def test_recorded_early_stop_now_admits_another_parallel_wave(pair_budget):
    db = pair_budget
    recorded_search(db)
    db.set("deadline", time.time() + 1018.5708768367767)
    decision = forecast(db, ["T1", "T2", "T3"])
    assert decision["can_admit"]
    assert decision["integration_estimate_source"] == "initial_model_seconds"
    assert decision["integration_seconds"] == pytest.approx(2 * (120 + 1.6364622116088867))
    assert decision["reserve_seconds"] < 350  # Previously 709.2169 s from a research repair.
    assert decision["next_work_seconds"] == pytest.approx(1.25 * 207.7533984184265)
    admit(db, ["T1", "T2", "T3"])
    assert db.get("adaptive_budget:1")["can_admit"]


@pytest.mark.parametrize("duration", [1800, 7200, 18000, 86400])
def test_latency_replay_admits_more_cycles_and_still_finishes_g_within_target(pair_budget, duration):
    db = pair_budget
    recorded_search(db)
    origin = time.time()
    elapsed = 1800 - 1018.5708768367767
    db.set("deadline", origin + duration)
    count = 3
    wave = 207.7533984184265
    while forecast(db, ["T1", "T2", "T3"], now=origin + elapsed)["can_admit"]:
        elapsed += wave
        count += 1
        record_timing(db, "research_wave:3", wave)
    # Replay, not a new benchmark: future waves repeat the last observed cost.
    final_seconds = 97.34479570388794 + 156.18958735466003 + 6.768660545349121 + 0.018982887268066406
    assert count >= 6
    assert elapsed + final_seconds < duration
    assert duration - elapsed - final_seconds < wave
    if duration == 1800:
        assert count == 6
        assert 27 * 60 < elapsed + final_seconds < 28 * 60


def test_fusion_prior_does_not_reuse_research_or_planning_repairs(pair_budget):
    db = pair_budget
    config = db.get("config")
    config["harness"].update(enabled=True, max_attempts=4)
    db.set("config", config)
    record_timing(db, "baseline", 2)
    record_timing(db, "mother", 9000)
    record_timing(db, "mission:T1", 10000)
    decision = forecast(db)
    assert decision["final_g_seconds"] == 122
    assert decision["integration_seconds"] == 244
    assert decision["confirmation_seconds"] > 0


def test_measured_fusions_calibrate_remaining_pairs_and_n(pair_budget):
    db = pair_budget
    for sample in [90, 110, 500]:
        record_timing(db, "mission:G", sample)
    record_timing(db, "postprocess", 20000)  # An old total is not the cost of each new pair.
    record_timing(db, "confirmation", 17)
    for count in [1, 3, 8, 78]:
        db.set("forest_plan:1", {"children": [{"role": f"T{i}"} for i in range(1, count + 1)]})
        decision = forecast(db)
        assert decision["integration_seconds"] == max(1, count - 1) * 110
        assert decision["integration_estimate_source"] == "mission:G"
        assert decision["confirmation_seconds"] == 17
        assert decision["reserve_seconds"] > decision["integration_seconds"] + 17


def test_single_slow_wave_does_not_pin_reserve_but_sustained_slowdown_is_learned(pair_budget):
    db = pair_budget
    for sample in [100, 100, 100, 100, 100, 400]:
        record_timing(db, "research_wave:3", sample)
    assert forecast(db, ["T1", "T2", "T3"])["next_work_seconds"] == 125
    for _ in range(2):
        record_timing(db, "research_wave:3", 400)
    assert forecast(db, ["T1", "T2", "T3"])["next_work_seconds"] == 500


def test_wave_estimate_is_not_multiplied_by_n_or_shared_with_another_width(pair_budget):
    db = pair_budget
    record_timing(db, "research_wave:3", 200)
    record_timing(db, "research_wave:8", 500)
    assert forecast(db, ["T1", "T2", "T3"])["next_work_seconds"] == 250
    roles = [f"T{i}" for i in range(1, 9)]
    assert forecast(db, roles)["next_work_seconds"] == 625


def test_admission_still_requires_next_wave_plus_complete_finalization(pair_budget):
    db = pair_budget
    recorded_search(db)
    decision = forecast(db, ["T1", "T2", "T3"])
    needed = decision["reserve_seconds"] + decision["next_work_seconds"]
    db.set("deadline", time.time() + needed - 1)
    with pytest.raises(BudgetExhausted, match="independent confirmation"):
        admit(db, ["T1", "T2", "T3"])
    db.set("deadline", time.time() + needed + 1)
    admit(db, ["T1", "T2", "T3"])


def test_complete_wave_is_timed_once_before_same_mother_fusions_and_confirmation(
    tmp_path, monkeypatch, need_compiler,
):
    _, controller, fixture = native_campaign(tmp_path, monkeypatch, 3, pairwise=True)
    with controller:
        state = controller.run()
        timings = controller.db.get("timing_samples")
        assert len(timings["research_wave:3"]) == 1
        assert timings["research_wave:3"][0] > 0
        assert len(timings["mission:G"]) == 2
        assert state["postprocess"]["status"] == "complete"
        assert len(state["postprocess"]["steps"]) == 2
        assert all(c["expires_at"] is None and c["token_ceiling"] is None for c in fixture.calls)
        controller.confirm()
        assert controller.status()["final_g_confirmation"]["status"] == "confirmed"
        assert len({c["conversation"]["id"] for c in fixture.calls if c.get("conversation")}) == 1
