"""Selected-child prediction errors never invent an unchosen outcome."""
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("admission_audit", Path(__file__).resolve().parents[1]
    / "experiments/tabpfn-admission-20261025/reproduction/audit_advice.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def fixture(tmp_path, future=False):
    root = tmp_path / "arm"
    directory = root / "campaign/advisor/d"
    directory.mkdir(parents=True)
    request = {"context": [{"observed_at": 15 if future else 5}],
               "candidates": [{"captured_at": 10}, {"captured_at": 10}]}
    (directory / "request.json").write_text(json.dumps(request))
    sample = {"id": "chosen", "feature_stage": "before_generation", "captured_at": 10,
              "observed_at": 30, "parent_score": .5, "measured_score": .75, "target": .25, "source_sha256": "p"}
    decision = {"id": "d", "chosen_id": "chosen", "candidate_ids": ["discarded", "chosen"],
                "parent_ids": [None, "p"], "status": "advised", "called": True, "reordered": True,
                "seconds": 1, "context_ids": ["old"], "expected_child_scores": [.6, .8]}
    with sqlite3.connect(root / "campaign/registry.sqlite3") as db:
        db.executescript("CREATE TABLE metadata(key TEXT,value TEXT);"
                        "CREATE TABLE events(id INTEGER,kind TEXT,payload TEXT,created REAL);"
                        "CREATE TABLE trials(id TEXT,mission TEXT,result TEXT);")
        db.execute("INSERT INTO metadata VALUES(?,?)", ("advisor_sample:chosen", json.dumps(sample)))
        db.execute("INSERT INTO events VALUES(1,?,?,11)", ("advisor_decision", json.dumps(decision)))
        db.execute("INSERT INTO events VALUES(2,?,?,20)", ("research_node_submitted", json.dumps({"experiment_id": "chosen"})))
        db.execute("INSERT INTO trials VALUES(?,?,?)", ("chosen", "{}", json.dumps({"status": "valid", "score": .75})))
    return root


def test_prequential_audit_has_only_the_selected_observed_child(tmp_path):
    rows, summary = audit.audit(fixture(tmp_path))
    assert len(rows) == 1 and rows[0]["chosen_trial"] == "chosen"
    assert rows[0]["counterfactual_outcome_available"] is False
    assert summary["selected_child_mae"] == pytest.approx(.05)
    assert summary["calls"] == summary["changed_parents"] == 1


def test_prequential_audit_rejects_future_training_label(tmp_path):
    with pytest.raises(ValueError, match="Future observation"):
        audit.audit(fixture(tmp_path, future=True))
