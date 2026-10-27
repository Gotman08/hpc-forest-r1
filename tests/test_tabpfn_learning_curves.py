"""A long-run prefix must not count future or development-only measurements."""
import importlib.util
import sys
from pathlib import Path


def load_curves(monkeypatch):
    folder = Path(__file__).resolve().parents[1] / "experiments/tabpfn-admission-20261025/reproduction"
    monkeypatch.syspath_prepend(str(folder))
    monkeypatch.delitem(sys.modules, "analyze", raising=False)
    spec = importlib.util.spec_from_file_location("admission_learning_curves", folder / "learning_curves.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_curve_waits_for_settlement_and_excludes_development_harness(monkeypatch):
    module = load_curves(monkeypatch)

    def evaluation(identity, seconds, created):
        return {"experiment_id": identity, "phase": "search", "created": created,
                "payload": {"status": "valid", "correct": True, "mean_seconds": seconds}}

    db = {
        "metadata": {"started": 100, "deadline": 5500, "pipeline_finished:1": 1200},
        "trials": [{"id": "child", "mission": {"budget_phase": "search"}}],
        "evaluations": [evaluation("baseline-e1", 10, 101), evaluation("child", 5, 690),
                        evaluation("harness-draft", .001, 400)],
        "events": [{"kind": "research_node_settled", "created": 710,
                    "payload": {"experiment_id": "child", "settled_at": 710}}],
    }
    ten, thirty = module.checkpoints(db, (10, 30))
    assert ten["best_trial"] == "baseline-e1" and ten["settled_trials"] == 0
    assert thirty["best_trial"] == "child" and thirty["best_search_speedup"] == 2
    assert not ten["pipeline_already_finished"] and thirty["pipeline_already_finished"]
    assert thirty["is_confirmed_delivery"] is False
    failed = module.checkpoints(db, (10, 30), receipt={
        "started_at": 90, "elapsed_seconds": 700, "pipeline_complete": False,
    })
    assert failed[0]["campaign_outcome_at_checkpoint"] == "active"
    assert failed[1]["campaign_outcome_at_checkpoint"] == "failed"
    assert failed[1]["campaign_already_stopped"] is True


def test_curve_does_not_backdate_advice_or_observations(monkeypatch):
    module = load_curves(monkeypatch)
    db = {
        "metadata": {"started": 0, "deadline": 5400,
                     "advisor_sample:future": {"observed_at": 900}},
        "trials": [],
        "evaluations": [{"experiment_id": "baseline-e1", "phase": "search", "created": 1,
                         "payload": {"status": "valid", "correct": True, "mean_seconds": 10}}],
        "events": [{"kind": "advisor_decision", "created": 950,
                    "payload": {"called": True, "reordered": True, "status": "advised"}}],
    }
    ten, thirty = module.checkpoints(db, (10, 30))
    assert ten["advisor_samples"] == ten["advisor_calls"] == ten["advisor_changed_parents"] == 0
    assert thirty["advisor_samples"] == thirty["advisor_calls"] == thirty["advisor_changed_parents"] == 1
