"""Runtime-aware advice: no future labels, no clipped scores, no futile workers."""
import json
import math

import pytest
from test_advisor import controller as controller_fixture
from test_advisor import mission

from hpc_forest import advisor
from hpc_forest.advisor_validation import calibrated_choice, decision_validation
from hpc_forest.advisor_value import MIN_MARGIN, POLICY, TARGET, from_log_ratio, measured
from hpc_forest.core import Outcome, atomic_json, digest

controller = controller_fixture


def runtime_context(c, count=18, *, single_parent=False):
    c.config["advisor"].update(validation_policy=POLICY)
    c.db.set("config", c.config)
    for i in range(count):
        c.db.set(f"advisor_sample:old-{i}", {"id": f"old-{i}", "epoch": 1,
            "protocol_id": "p", "schema": advisor.VERSION, "target_kind": TARGET, "role": "T1",
            "source_sha256": "same" if single_parent else str(i), "commit": str(i),
            "captured_at": 2 * i, "observed_at": 2 * i + 1,
            "features": [0.] * len(advisor.FEATURES), "parent_score": .5,
            "parent_value": math.log(2), "measured_value": math.log(2) + (i + 1) / 10,
            "target": (i + 1) / 10})


def test_new_value_distinguishes_large_speedups_without_changing_treequest_score():
    a, b = measured(1, 1 / 80, True), measured(1, 1 / 100, True)
    assert b - a > 20 * MIN_MARGIN
    assert measured(1, None, False) == 0
    assert from_log_ratio(-1000) == 1000
    assert math.isfinite(from_log_ratio(1000))
    for bad in (0, float("nan"), float("inf"), True):
        with pytest.raises(ValueError):
            measured(1, bad, True)
    with pytest.raises(ValueError):
        measured(1, 1, None)


def test_runtime_target_is_immutable_parent_then_measured_child(controller):
    runtime_context(controller, 0)
    controller.db.record_evaluation("baseline-e1", 1, "search", {"mean_seconds": 10})
    m = mission("new", controller.root)
    entry = advisor.capture(controller, m)
    assert entry["parent_value"] == pytest.approx(math.log(2))
    assert entry["target_kind"] == TARGET and "measured_value" not in entry
    result = Outcome("valid", correct=True, commit="child", mean_seconds=.1, score=100 / 101)
    before = dict(result.__dict__)
    advisor.observe(controller, m, result)
    row = advisor.samples(controller.db, 1, 128, target=TARGET)[0]
    assert row["measured_value"] == pytest.approx(math.log(101))
    assert row["target"] == pytest.approx(math.log(101) - math.log(2))
    assert result.__dict__ == before  # No change to the measured evaluator reward.
    assert controller.db.get("advisor_features:" + m.id) == entry
    assert advisor.samples(controller.db, 1, 128, target="child_minus_parent_measured_score") == []


def test_invalid_measured_time_does_not_create_a_runtime_label(controller):
    runtime_context(controller, 0)
    m = mission("new", controller.root)
    advisor.capture(controller, m)
    advisor.observe(controller, m, Outcome("valid", correct=True, commit="child", mean_seconds=1, score=.5))
    assert advisor.samples(controller.db, 1, 128) == []  # Baseline is missing.
    advisor.observe(controller, m, Outcome("incorrect", correct=False, commit="bad", score=0))
    assert advisor.samples(controller.db, 1, 128)[0]["target"] == pytest.approx(-math.log(2))


@pytest.mark.parametrize("policy", [POLICY, "decision_calibrated_v1"])
def test_insufficient_independent_context_never_starts_worker(controller, monkeypatch, policy):
    runtime_context(controller, single_parent=True)
    controller.config["advisor"]["validation_policy"] = policy
    if policy != POLICY:
        for i in range(18):
            row = controller.db.get(f"advisor_sample:old-{i}")
            row["target_kind"] = "child_minus_parent_measured_score"
            controller.db.set(f"advisor_sample:old-{i}", row)
    monkeypatch.setattr(advisor, "run_process", lambda *a, **kw: pytest.fail("Unnecessary inference"))
    choices = [mission(n, controller.root) for n in ("a", "b")]
    assert advisor.choose(controller, choices) == "a"
    event = json.loads(controller.db.rows("SELECT payload FROM events WHERE kind='advisor_decision'")[-1]["payload"])
    assert event["status"] == "validation_preflight_rejected" and not event["called"]
    assert event["validation"]["reason"] == "insufficient_independent_parent_context"
    assert not (controller.root / "advisor").exists()


def test_chronology_and_parent_baseline_gate_runtime_predictions():
    held = [{"source_sha256": str(i), "parent_value": math.log(81) + i * .05,
             "measured_value": math.log(81) + i * .05 + .03} for i in range(6)]
    good = decision_validation(held, [.03] * 6, {"policy": POLICY})
    assert not good.get("reason") and good["mae_child_value"] == 0
    assert good["value_scale"] == "log1p_speedup" and not good["margin_is_confidence_bound"]
    bad = decision_validation(held, [.4] * 6, {"policy": POLICY})
    assert bad["pairwise_accuracy"] == 1
    assert bad["reason"] == "calibration_not_better_than_parent_baseline"


def test_runtime_choice_has_no_artificial_tie_at_one():
    candidates = [{"parent_value": math.log(81)}, {"parent_value": math.log(101)}]
    evidence = {"policy": POLICY, "decision_margin": MIN_MARGIN}
    chosen, values, guard = calibrated_choice(candidates, [0, 0], evidence)
    assert chosen == 1 and values[1] > values[0] > 1 and guard == "margin_passed"
    assert calibrated_choice(candidates, [0, -10], evidence)[2] == "out_of_range_child_value"
    assert calibrated_choice(candidates, [.1, -.12], evidence)[0] == 0


def test_runtime_policy_reaches_worker_and_exports_separate_values(controller, monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace

    runtime_context(controller)
    def worker(argv, **kwargs):
        request = json.loads(Path(argv[-2]).read_text())
        assert request["validation_policy"] == POLICY
        atomic_json(Path(argv[-1]), {"request_sha256": digest(request), "model_version": advisor.MODEL_VERSION,
            "status": "validated", "predictions": [0, .3],
            "validation": {"policy": POLICY, "decision_margin": MIN_MARGIN}})
        return SimpleNamespace(returncode=0, timed_out=False)
    monkeypatch.setattr(advisor, "run_process", worker)
    assert advisor.choose(controller, [mission("a", controller.root), mission("b", controller.root)]) == "b"
    event = json.loads(controller.db.rows("SELECT payload FROM events WHERE kind='advisor_decision'")[-1]["payload"])
    assert event["expected_child_values"][1] > event["expected_child_values"][0]
    assert "expected_child_scores" not in event and event["prediction_target"] == TARGET


def test_old_samples_remain_reportable_but_cannot_feed_new_policy(controller):
    controller.config["advisor"] = {"enabled": True}
    controller.db.set("config", controller.config)
    controller.db.set("advisor_sample:old", {"id": "old", "epoch": 1, "protocol_id": "p",
        "schema": "forest-tabpfn-advisor-v2-parent-value", "features": [0.] * 80,
        "commit": "old", "observed_at": 1, "target_kind": "child_minus_parent_measured_score"})
    assert advisor.samples(controller.db, 1, 128) == []
    result = advisor.summary(controller.db)
    assert result["samples"] == 1 and result["feature_count"] == 80
    assert result["schema"] == "forest-tabpfn-advisor-v2-parent-value"
    assert result["settings"]["validation_policy"] == "gain_rank_v2"


def test_worker_preflight_rejects_before_reading_weights_or_importing_torch(controller, monkeypatch):
    from hpc_forest.advisor_worker import predict

    runtime_context(controller, single_parent=True)
    monkeypatch.setattr("hpc_forest.advisor_worker.importlib.metadata.version", lambda _: advisor.PACKAGE_VERSION)
    monkeypatch.setattr("hpc_forest.advisor_worker.file_digest", lambda _: pytest.fail("Weights must not be read"))
    request = {"schema": advisor.VERSION, "feature_names": advisor.FEATURES,
        "model_version": advisor.MODEL_VERSION, "package_version": advisor.PACKAGE_VERSION,
        "validation_policy": POLICY, "context": advisor.samples(controller.db, 1, 128),
        "candidates": [{"role": "T1", "captured_at": 100}], "runtime": {"model_path": "missing"}}
    response = predict(request)
    assert response["status"] == "validation_rejected"
    assert response["validation"]["reason"] == "insufficient_independent_parent_context"
    request["context"][-1]["observed_at"] = 101
    with pytest.raises(ValueError, match="Future outcomes"):
        predict(request)


def test_tied_validation_values_are_rejected_without_worker(controller, monkeypatch):
    runtime_context(controller)
    for i in range(18):
        item = controller.db.get(f"advisor_sample:old-{i}")
        item["measured_value"] = 1
        controller.db.set(f"advisor_sample:old-{i}", item)
    monkeypatch.setattr(advisor, "run_process", lambda *a, **kw: pytest.fail("No distinguishable validation pairs"))
    assert advisor.choose(controller, [mission("a", controller.root), mission("b", controller.root)]) == "a"
    assert advisor.summary(controller.db)["last_status"] == "validation_preflight_rejected"


def test_active_and_adviser_contract_changes_require_a_fresh_campaign(db):
    from hpc_forest.control_versions import contracts, verify
    from hpc_forest.core import InfrastructureError

    cfg = db.get("config")
    cfg["advisor"] = {"enabled": True}
    cfg["forest"]["active"] = {"mode": "full"}
    with pytest.raises(InfrastructureError, match="fresh memory"):
        verify(db, cfg)
    db.set("control_contracts", contracts(cfg))
    verify(db, cfg)
    db.set("control_contracts", {**contracts(cfg), "advisor": "old"})
    with pytest.raises(InfrastructureError, match="new campaign"):
        verify(db, cfg)
