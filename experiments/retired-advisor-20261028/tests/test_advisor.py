"""Offline adviser contracts; fake predictions never count as a TabPFN benchmark."""
import copy
import json
import math
import sys
import time
from concurrent.futures import Future
from pathlib import Path
from queue import SimpleQueue
from types import SimpleNamespace

import numpy as np
import pytest

from hpc_forest import advisor
from hpc_forest.advisor_worker import predict, ranking_accuracy
from hpc_forest.backends import Generated
from hpc_forest.core import (
    FileLock,
    ForestError,
    InfrastructureError,
    Mission,
    Outcome,
    atomic_json,
    digest,
)


def mission(name, root, **changes):
    path = root / name
    (path / "src").mkdir(parents=True)
    (path / "src/main.cpp").write_text("int main() { return 0; }\n", newline="\n")
    return Mission(name, "e1:T1", "trial-" + name, 1, "T1", "base", None, "R/T1", 1, 1,
                   str(path), **changes)


@pytest.fixture
def controller(db, tmp_path, monkeypatch):
    config = db.get("config")
    # Preserve historical-policy regression coverage explicitly; v3 has its own
    # measured-time/parent-disjoint fixtures in test_advisor_runtime.py.
    config["advisor"] = {"enabled": True, "validation_policy": "gain_rank_v2"}
    config["advisor_runtime"] = {"python": sys.executable, "model_path": str(tmp_path / "weights.safetensors"),
                                 "model_sha256": "0" * 64}
    db.set("config", config)
    db.set("protocol_id", "p")
    db.set("current_epoch", 1)
    monkeypatch.setattr(advisor, "committed_source_snapshot",
                        lambda *_: {"src/main.cpp": "int main() { return 0; }\n"})
    return SimpleNamespace(db=db, root=tmp_path, config=config,
                           evaluator=SimpleNamespace(lock_path=tmp_path / "measurement.lock"))


def seed_context(controller, count=8):
    for i in range(count):
        controller.db.set("advisor_sample:old-" + str(i), {
            "id": "old-" + str(i), "epoch": 1, "protocol_id": "p", "schema": advisor.VERSION,
            "source_sha256": str(i), "commit": str(i), "captured_at": i - 0.5, "observed_at": i,
            "target_kind": "child_minus_parent_measured_score",
            "features": [float(i)] * len(advisor.FEATURES), "target": float(i)})


def mock_response(monkeypatch, predictions, *, status="validated", corrupt=False, timeout=False):
    calls = []
    def run(argv, **kwargs):
        request = json.loads(Path(argv[-2]).read_text())
        calls.append((copy.deepcopy(request), kwargs))
        response = {"request_sha256": "wrong" if corrupt else digest(request),
                    "model_version": advisor.MODEL_VERSION, "status": status,
                    "validation": {"pairwise_accuracy": 1.0}, "predictions": predictions}
        atomic_json(Path(argv[-1]), response)
        return SimpleNamespace(returncode=0, timed_out=timeout)
    monkeypatch.setattr(advisor, "run_process", run)
    monkeypatch.setattr(advisor, "admission_deadline", lambda db: time.time() + 60)
    return calls


@pytest.mark.parametrize("value", [None, [], {"enabled": 1}, {"unknown": 3},
    {"min_samples": True}, {"min_samples": 7}, {"max_samples": 3}, {"exploration_every": 1},
    {"max_call_seconds": 0}, {"max_budget_fraction": float("nan")}, {"max_budget_fraction": 0.5}])
def test_invalid_settings_rejected(value):
    with pytest.raises(ForestError):
        advisor.settings({"advisor": value})


@pytest.mark.parametrize("changes", [{"python": "python"}, {"model_path": "/weights/../model"},
                                     {"python": "/runtime/python\n"}, {"model_sha256": "unpinned"}])
def test_runtime_is_controller_owned_and_pinned(controller, changes):
    with pytest.raises(ForestError):
        advisor.runtime({"advisor_runtime": {**controller.config["advisor_runtime"], **changes}})


def test_code_features_have_no_comments_strings_or_outcome(controller):
    m = mission("candidate", controller.root)
    a = advisor.feature_vector({"x": 'int f(){ return 1; } // for for cudaMalloc\n'}, m)
    b = advisor.feature_vector({"x": 'int f(){ return 1; } "for cudaMalloc"'}, m)
    assert a[advisor.FEATURES.index("for")] == b[advisor.FEATURES.index("for")] == 0
    assert a[advisor.FEATURES.index("cuda")] == b[advisor.FEATURES.index("cuda")] == 0
    captured = advisor.capture(controller, m)
    assert "target" not in captured and "mean_seconds" not in captured
    assert len(captured["features"]) == len(advisor.FEATURES)


@pytest.mark.parametrize("outcome", [Outcome("infrastructure_error"), Outcome("duplicate"),
    Outcome("valid", correct=False, mean_seconds=1, commit="x"),
    Outcome("valid", correct=True, mean_seconds=float("nan"), commit="x")])
def test_invalid_or_unmeasured_result_cannot_train(controller, outcome):
    m = mission("candidate", controller.root)
    advisor.capture(controller, m)
    advisor.observe(controller, m, outcome)
    assert advisor.samples(controller.db, 1, 128) == []


def test_context_is_campaign_protocol_epoch_scoped_and_deduplicated(controller):
    seed_context(controller)
    example = controller.db.get("advisor_sample:old-0")
    for name, changes in [("epoch", {"epoch": 2}), ("protocol", {"protocol_id": "q"}),
                          ("schema", {"schema": "old"}), ("duplicate", {"observed_at": 9})]:
        controller.db.set("advisor_sample:" + name, {**example, "id": name, **changes})
    chosen = advisor.samples(controller.db, 1, 128)
    assert len(chosen) == 8
    assert [e["observed_at"] for e in chosen] == sorted(e["observed_at"] for e in chosen)
    assert {e["id"] for e in chosen} == {"duplicate", *("old-" + str(i) for i in range(1, 8))}


def test_validated_prediction_selects_parent_proposal_without_inventing_measurement(controller, monkeypatch):
    seed_context(controller)
    calls = mock_response(monkeypatch, [-0.2, 0.5])
    a, b = [mission(n, controller.root) for n in ("a", "b")]
    before = controller.db.rows("SELECT * FROM trees")
    assert advisor.choose(controller, [a, b]) == "b"
    assert controller.db.rows("SELECT * FROM trees") == before
    assert not controller.db.rows("SELECT * FROM evaluations")
    assert calls[0][0]["context"][-1]["id"] == "old-7"
    assert not {"a", "b"} & {e["id"] for e in calls[0][0]["context"]}
    assert calls[0][1]["timeout"] <= 20
    assert calls[0][1]["env"]["HF_HUB_OFFLINE"] == "1"
    assert advisor.summary(controller.db)["reorders"] == 1


@pytest.mark.parametrize("kwargs", [{"status": "validation_rejected"}, {"corrupt": True},
                                    {"timeout": True}, {"predictions": [float("nan"), 0]},
                                    {"predictions": [0]}])
def test_untrusted_unavailable_or_bad_predictions_fall_back(controller, monkeypatch, kwargs):
    seed_context(controller)
    mock_response(monkeypatch, **{"predictions": [2, 1], **kwargs})
    assert advisor.choose(controller, [mission("a", controller.root), mission("b", controller.root)]) == "a"
    assert advisor.summary(controller.db)["reorders"] == 0


def test_budget_and_exploration_prevent_calls(controller, monkeypatch):
    seed_context(controller)
    calls = mock_response(monkeypatch, [2, 1])
    candidates = [mission(n, controller.root) for n in ("a", "b")]
    controller.db.set("advisor_totals", {"opportunities": 3})
    assert advisor.choose(controller, candidates) == "a"
    assert advisor.summary(controller.db)["last_status"] == "exploration_treequest"
    controller.db.set("advisor_totals", {"seconds": 30})
    assert advisor.choose(controller, candidates) == "a"
    assert advisor.summary(controller.db)["last_status"] == "advisor_budget_exhausted"
    assert calls == []


def test_context_cost_is_included_even_when_example_collection_fails(controller, monkeypatch):
    ticks = iter((10.0, 12.0))
    monkeypatch.setattr(advisor.time, "perf_counter", lambda: next(ticks))
    with pytest.raises(ValueError), advisor.account_context(controller):
        raise ValueError("Bad source")
    totals = controller.db.get("advisor_totals")
    assert totals["seconds"] == totals["context_seconds"] == 2


def test_advice_never_competes_with_a_running_benchmark(controller, monkeypatch):
    seed_context(controller)
    calls = mock_response(monkeypatch, [0.1, 0.2])
    candidates = [mission(n, controller.root) for n in ("a", "b")]
    with FileLock(controller.evaluator.lock_path):
        assert advisor.choose(controller, candidates) == "a"
    assert not calls and advisor.summary(controller.db)["last_status"] == "target_busy"
    original = advisor.run_process
    def while_protected(*args, **kwargs):
        with pytest.raises(InfrastructureError), FileLock(controller.evaluator.lock_path):
            pytest.fail("Inference must hold the benchmark lock")
        return original(*args, **kwargs)
    monkeypatch.setattr(advisor, "run_process", while_protected)
    assert advisor.choose(controller, candidates) == "b"


def test_disabled_is_exact_fifo_and_does_not_read_source(controller, monkeypatch):
    controller.config["advisor"] = {"enabled": False}
    q = SimpleQueue()
    q.put("first")
    q.put("second")
    monkeypatch.setattr(advisor, "choose", lambda *args: pytest.fail("Disabled advisor called"))
    assert advisor.next_completed(controller, q, {}, []) == "first"
    assert q.get_nowait() == "second"


def test_queue_never_waits_for_sibling_and_drains_each_future_once(controller, monkeypatch):
    a, b = [mission(n, controller.root) for n in ("a", "b")]
    fa, fb, control = Future(), Future(), Future()
    fa.set_result((Generated(0, {}), 0, 1))
    q, ready = SimpleQueue(), []
    pending = {fa: {"kind": "research", "mission": a}, fb: {"kind": "research", "mission": b},
               control: {"kind": "control"}}
    q.put(fa)
    assert advisor.next_completed(controller, q, pending, ready) is fa
    assert not fb.done()
    # Identical FIFO order for on/off; the advisor no longer changes completion order.
    fb.set_result((Generated(0, {}), 0, 2))
    control.set_result(({}, 2))
    q.put(fb)
    q.put(control)
    assert advisor.next_completed(controller, q, pending, ready) is fb
    assert advisor.next_completed(controller, q, pending, ready) is control
    assert ready == [] and q.empty()


def test_chronological_holdout_precedes_candidate_prediction(tmp_path, monkeypatch):
    checkpoint = tmp_path / "weights.safetensors"
    checkpoint.write_bytes(b"test-only-weights")
    import hashlib

    fits, predictions = [], []
    class Model:
        @classmethod
        def create_default_for_version(cls, version, **kwargs):
            assert kwargs["device"] == "cpu" and kwargs["model_path"] == checkpoint
            return cls()
        def fit(self, x, y):
            fits.append(x.copy())
            return self
        def predict(self, x):
            predictions.append(x.copy())
            return x[:, 0]
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(set_num_threads=lambda x: None,
                                                              set_num_interop_threads=lambda x: None))
    monkeypatch.setitem(sys.modules, "tabpfn", SimpleNamespace(TabPFNRegressor=Model))
    monkeypatch.setitem(sys.modules, "tabpfn.constants", SimpleNamespace(ModelVersion=SimpleNamespace(V3_5="v3.5")))
    monkeypatch.setattr("hpc_forest.advisor_worker.importlib.metadata.version", lambda name: advisor.PACKAGE_VERSION)
    context = [{"id": str(i), "features": [float(i)] * len(advisor.FEATURES), "target": float(i),
                "captured_at": i * 2, "observed_at": i * 2 + 1} for i in range(8)]
    request = {"schema": advisor.VERSION, "feature_names": advisor.FEATURES,
               "model_version": advisor.MODEL_VERSION, "package_version": advisor.PACKAGE_VERSION,
               "runtime": {"model_path": str(checkpoint), "model_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest()},
               "context": context, "candidates": [{"features": [42.0] * len(advisor.FEATURES),
                                                    "captured_at": 100}], "seed": 23}
    response = predict(request)
    assert response["status"] == "validated" and response["predictions"] == [42.0]
    assert [len(x) for x in fits] == [5, 8]
    assert [len(x) for x in predictions] == [3, 1]
    assert response["validation"]["held_out_ids"] == ["5", "6", "7"]
    assert not np.isin(42, fits[-1]).any()
    # A sibling completed after the validation decision is not training data
    # that would have been available for that decision, even if it was admitted earlier.
    context[4]["observed_at"] = 11
    response = predict(request)
    assert response["status"] == "validation_rejected"
    assert response["validation"]["reason"] == "insufficient_strictly_earlier_context"
    context[-1]["observed_at"] = 101
    with pytest.raises(ValueError, match="Future outcomes"):
        predict(request)


def test_rank_validation_ignores_noise_ties():
    assert ranking_accuracy([0, math.log(1.001)], [1, 0]) is None
    assert ranking_accuracy([1, 2, 3], [3, 2, 1]) == 0
    assert ranking_accuracy([1, 2, 3], [1, 2, 3]) == 1


def test_advised_queue_preserves_all_admitted_work(controller, monkeypatch):
    seed_context(controller)
    mock_response(monkeypatch, [2, 1])
    pending, queue, ready = {}, SimpleQueue(), []
    futures = []
    for name in ("a", "b", "still_generating"):
        f = Future()
        futures.append(f)
        pending[f] = (mission(name, controller.root), "slot", time.time())
        if name != "still_generating":
            f.set_result((Generated(0, {}), 0, 1))
            queue.put(f)
    assert advisor.next_completed(controller, queue, pending, ready) is futures[0]
    assert advisor.next_completed(controller, queue, pending, ready) is futures[1]
    assert not futures[2].done() and not ready


def test_transition_uses_parent_before_generation_and_child_reward_after(controller, monkeypatch):
    m = mission("a", controller.root)
    frozen = advisor.capture(controller, m)
    monkeypatch.setattr(advisor, "_baseline", lambda *_: 2)
    monkeypatch.setattr(advisor, "committed_source_snapshot", lambda *_: pytest.fail("No child source in features"))
    advisor.observe(controller, m, Outcome("valid", correct=True, score=0.8, mean_seconds=1, commit="good"))
    record = advisor.samples(controller.db, 1, 128)[0]
    assert record["features"] == frozen["features"] and record["target"] == pytest.approx(0.3)
    assert record["captured_at"] <= record["observed_at"]
    n = mission("b", controller.root)
    monkeypatch.setattr(advisor, "committed_source_snapshot", lambda *_: {"src/main.cpp": "different parent"})
    advisor.capture(controller, n)
    n.base_commit = "unexpected-parent"
    advisor.observe(controller, n, Outcome("valid", correct=True, score=0.8, mean_seconds=0.5, commit="changed"))
    assert len(advisor.samples(controller.db, 1, 128)) == 1


def test_advisor_export_is_separate_from_measured_scores(controller, tmp_path):
    seed_context(controller)
    controller.db.event("advisor_decision", {"id": "d", "status": "warmup", "chosen_id": "a"})
    out = tmp_path / "export"
    out.mkdir()
    result = advisor.export(controller.db, out)
    assert result["weights_updated"] is False
    assert (out / "advisor-decisions.csv").is_file()
    assert "score" not in (out / "advisor-decisions.csv").read_text()
