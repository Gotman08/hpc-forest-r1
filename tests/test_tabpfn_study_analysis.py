"""Verify study accounting; these fixtures are not ROMEO benchmark results."""
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

STUDY = Path(__file__).resolve().parents[1] / "experiments/tabpfn-advisor-20261025"
SPEC = importlib.util.spec_from_file_location("tabpfn_study_analysis", STUDY / "reproduction/analyze.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf8")


@pytest.fixture
def experiment(tmp_path):
    pair = tmp_path / "pair"
    arm = {"id": "a", "condition": "advisor_on", "enabled": True}
    root = pair / "forest-app-a"
    write(pair / "pair.json", {"case": "utf8", "repeat": 1, "seed": 23, "pair_id": "fixture",
                              "target_seconds": 1800, "cap_seconds": 3600})
    write(pair / "allocation.json", {"job_id": "synthetic", "host": "fixture", "pc_relay": False})
    write(root / "fresh-memory.json", {"trials": 0, "documents": 0, "advisor_samples": 0,
                                      "imported_candidates": False})
    write(root / "arm-result.json", {"pipeline_complete": True, "finished_within_cap": True,
                                    "elapsed_seconds": 1900})
    metadata = {"config": {"advisor": {"enabled": True}, "codex": {"model": "gpt-6-luna",
        "reasoning_effort": "max", "generator_pool": []}}, "current_epoch": 1, "started": 100, "deadline": 1900,
        "advisor_totals": {"calls": 1, "reorders": 0, "seconds": 6},
        "active_control:bad": {"kind": "analyst", "status": "unavailable",
                               "coverage": {"code_analysis_complete": True}},
        "research_scheduler:1": {"stop_reason": "final_reserve_or_deadline", "status": "budget_exhausted"}}
    campaign = root / "campaign"
    campaign.mkdir()
    connection = sqlite3.connect(campaign / "registry.sqlite3")
    connection.executescript("""
        CREATE TABLE metadata(key TEXT,value TEXT);
        CREATE TABLE trials(id TEXT,tree_id TEXT,role TEXT,mission TEXT,result TEXT,state TEXT);
        CREATE TABLE evaluations(experiment_id TEXT,phase TEXT,payload TEXT,created REAL);
        CREATE TABLE events(kind TEXT,payload TEXT);
        CREATE TABLE slots(tokens_used INTEGER,usage_known INTEGER);
    """)
    connection.executemany("INSERT INTO metadata VALUES (?,?)",
                          [(key, json.dumps(value)) for key, value in metadata.items()])
    def outcome(seconds):
        return {"status": "valid", "correct": True, "mean_seconds": seconds, "score": 0.5}
    for identity, seconds, timestamp in (("baseline-e1", 4, 105), ("early", 2, 1800),
                                         ("late", 1, 1901), ("development-h01", 0.1, 1700)):
        connection.execute("INSERT INTO evaluations VALUES (?,?,?,?)",
                           (identity, "search", json.dumps(outcome(seconds)), timestamp))
    connection.execute("INSERT INTO trials VALUES (?,?,?,?,?,?)", ("early", "t1", "T1",
        json.dumps({"kind": "research", "budget_phase": "search", "depth": 2, "parent_id": "parent"}),
        json.dumps(outcome(2)), "completed"))
    connection.execute("INSERT INTO trials VALUES (?,?,?,?,?,?)", ("late", "t1", "T1",
        json.dumps({"kind": "research", "budget_phase": "search", "depth": 3, "parent_id": "early"}),
        json.dumps(outcome(1)), "completed"))
    connection.commit()
    connection.close()
    measured = {"naive": outcome(4), "advisor_on": {**outcome(1), "speedup": 4}}
    return pair, arm, measured


def test_target_deadline_uses_observed_time_not_later_best(experiment):
    pair, arm, measured = experiment
    row, details, trajectory = analysis.arm_summary(pair, arm, measured)
    assert row["best_measured_before_target_speedup"] == 2
    assert row["speedup_common"] == 4
    assert row["elapsed_seconds"] == 1900
    assert row["advisor_calls"] == 1 and row["advisor_reorders"] == 0
    assert row["analyst_jobs_unavailable"] == 1 and row["code_analyses_complete"] == 0
    assert row["control_jobs_code_coverage_complete"] == 1
    assert details["best_before_target_id"] == "early"
    assert len(trajectory) == 4


@pytest.mark.parametrize("field", ["pipeline_complete", "finished_within_cap"])
def test_incomplete_or_late_delivery_never_claims_speedup(experiment, field):
    pair, arm, measured = experiment
    path = pair / "forest-app-a/arm-result.json"
    value = json.loads(path.read_text())
    value[field] = False
    write(path, value)
    row, _, _ = analysis.arm_summary(pair, arm, measured)
    assert not row["delivery_valid"]
    assert row["speedup_common"] is None


def test_incorrect_common_measurement_never_claims_speedup(experiment):
    pair, arm, measured = experiment
    measured["advisor_on"]["correct"] = False
    row, _, _ = analysis.arm_summary(pair, arm, measured)
    assert not row["delivery_valid"] and row["speedup_common"] is None


def test_preloaded_memory_is_detected(experiment):
    pair, arm, measured = experiment
    path = pair / "forest-app-a/fresh-memory.json"
    data = json.loads(path.read_text())
    data["advisor_samples"] = 8
    write(path, data)
    with pytest.raises(ValueError, match="Fresh-memory"):
        analysis.arm_summary(pair, arm, measured)
