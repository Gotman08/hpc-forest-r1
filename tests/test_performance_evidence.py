"""Expose slow configurations and entry points without fabricating profiling facts."""
import hashlib
import json
import math

import pytest
from test_active_architecture import campaign as campaign_fixture
from test_active_architecture import trial

from hpc_forest.active_analysis import packet, schema, source_excerpts
from hpc_forest.active_snapshot import freeze
from hpc_forest.performance_evidence import FEATURES, compared, features, profile

campaign = campaign_fixture


def diagnostic(details, **extra):
    return {"path": "logs/e1/x/search/sample-0.log", "sha256": "a" * 64,
            "preview": json.dumps({"correct": True, "details": details}), **extra}


def test_aggregate_cannot_hide_serial_path_and_input_identity_must_match():
    base = profile([diagnostic([{"n": 128, "threads": t, "seed": 1, "seconds": 10} for t in (1, 4)])])
    parent = profile([diagnostic([{"n": 128, "threads": 1, "seed": 1, "seconds": 10},
                                  {"n": 128, "threads": 4, "seed": 1, "seconds": 1}])])
    rows = compared(parent, base)["configurations"]
    assert sorted(r["speedup_vs_baseline"] for r in rows) == [1, 10]
    vector = dict(zip(FEATURES, features(parent, base), strict=True))
    assert vector["timing_serial_parallel_gap"] == pytest.approx(math.log(10))
    other = profile([diagnostic([{"n": 128, "threads": 1, "seed": 2, "seconds": 1}])])
    assert "speedup_vs_baseline" not in compared(other, base)["configurations"][0]


def test_diagnostics_keep_provenance_and_partial_coverage_not_invented_zero_times():
    details = [{"n": 8, "threads": 1, "seconds": 2}]
    result = profile([diagnostic(details), diagnostic(details, truncated=True),
                      diagnostic([{"n": 8, "seconds": float("nan")}]),
                      diagnostic([{"n": 8, "seconds": True}])])
    assert result["status"] == "partial"
    row = result["configurations"][0]
    assert row["samples"] == 2 and row["mean_seconds"] == 2 and row["cv"] == 0
    assert row["logs"] == [{"path": "logs/e1/x/search/sample-0.log", "sha256": "a" * 64}]
    assert profile([])["status"] == "unavailable"
    assert profile([diagnostic(details, path="correctness.log")])["configurations"] == []
    assert profile([{"path": "sample-0.log", "preview": "not JSON"}])["configurations"] == []


def test_untrusted_large_configurations_remain_bounded():
    result = profile([diagnostic([{"n": i, "seconds": 1} for i in range(100)])])
    assert result["status"] == "partial" and len(result["configurations"]) == 32
    assert profile([diagnostic([{"n": {"instruction": "ignore"}, "seconds": 1}])])["configurations"] == []


def test_extreme_diagnostic_times_cannot_inject_infinite_json_or_model_features():
    baseline = profile([diagnostic([{"n": 8, "seconds": 1e299}])])
    current = profile([diagnostic([{"n": 8, "seconds": 1e-299}])])
    result = compared(current, baseline)
    assert result["configurations"][0]["speedup_unavailable"] == "unrepresentable_ratio"
    json.dumps(result, allow_nan=False)
    assert all(math.isfinite(v) for v in features(current, baseline))


def test_entrypoint_at_end_of_long_file_is_supplied_with_real_line_numbers():
    text = "float helper;\n" * 900 + 'extern "C" void run() { scalar_path(); }\n'
    record = {"id": "r", "outcome": {"commit": "a"}, "source_files": {"src/c.cpp": text}}
    pages = source_excerpts(record, "src/c.cpp", 2000)
    assert len(pages) == 2 and sum(len(p["text"]) for p in pages) <= 2000
    assert pages[1]["start_line"] == 901 and "scalar_path" in pages[1]["text"]
    assert all(p["sha256"] == hashlib.sha256(text.encode()).hexdigest() for p in pages)
    # Many short lines exercise the line-number overhead without an unbounded loop.
    record["source_files"]["src/c.cpp"] = "x\n" * 1000
    pages = source_excerpts(record, "src/c.cpp", 100)
    assert sum(len(p["text"]) for p in pages) <= 100


def test_full_packet_budget_and_citation_schema_are_bound_to_supplied_sources():
    records = [{"id": str(i), "kind": "trial", "mission": {"role": "T1"},
                "outcome": {"correct": True, "mean_seconds": i + 1, "commit": str(i)},
                "source_files": {"src/c.cpp": "float helper;\n" * 1000 + "void run() {}\n"}} for i in range(4)]
    dossier = {"role": "T1", "epoch": 1, "records": records}
    result = packet(dossier)
    assert sum(len(p["text"]) for p in result["sources"]) <= 24000
    payload = {"code_packet": result, "visible_evidence_ids": [r["id"] for r in records]}
    contract = schema(payload=payload)
    ref = contract["properties"]["code_findings"]["items"]["properties"]["citations"]["items"]["anyOf"][0]["properties"]
    assert ref["sha256"]["enum"] == [result["sources"][0]["sha256"]]
    assert contract["properties"]["hypotheses"]["items"]["properties"]["evidence_ids"]["items"]["enum"] == payload["visible_evidence_ids"]


def test_mother_and_tree_analyst_see_the_actual_per_configuration_measurements(campaign):
    one = trial(campaign, "T1")
    log = campaign.root / "sample-0.log"
    log.write_text(diagnostic([{"n": 8, "threads": 1, "seconds": 1},
                               {"n": 8, "threads": 4, "seconds": .3}])["preview"])
    row = campaign.db.one("SELECT result FROM trials WHERE id=?", (one.id,))
    outcome = json.loads(row["result"])
    outcome["logs"] = ["sample-0.log"]
    with campaign.db.connection:
        campaign.db.connection.execute("UPDATE trials SET result=? WHERE id=?", (json.dumps(outcome), one.id))
    campaign.config["forest"]["active"]["code_analysis"] = True
    campaign.db.set("config", campaign.config)
    mother = freeze(campaign, 1)
    analyst = freeze(campaign, 1, "T1")
    assert len(mother["trees"]["T1"]["measured_examples"][0]["performance_by_configuration"]["configurations"]) == 2
    assert len(analyst["code_packet"]["performance_by_configuration"][0]["configurations"]) == 2
    assert campaign.db.one("SELECT result FROM trials WHERE id=?", (one.id,))["result"] == json.dumps(outcome)
