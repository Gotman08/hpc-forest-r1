"""Persisted timing and accounting reports, without model calls or benchmarks."""

import json

from hpc_forest.registry import Registry
from hpc_forest.reporting import report


def test_report_distinguishes_admission_deadline_drain_and_postprocessing(tmp_path, finish_started_config):
    finish_started_config["budget"]["wall_seconds"] = 1800
    root = tmp_path / "campaign"
    root.mkdir()
    registry = Registry(root / "registry.sqlite3")
    try:
        registry.set("config", finish_started_config)
        registry.set("current_epoch", 1)
        registry.set("started", 100)
        registry.set("deadline", 1900)
        registry.set("search_closed:1", 1800)
        registry.set("postprocess:1", {"status": "complete", "elapsed_seconds": 50})
        registry.set("confirmation_deadline:1", 2030)
    finally:
        registry.close()
    report(root)
    data = json.loads((root / "report/experiments.json").read_text())
    assert data["timing"]["search_admission_deadline"] == 1720
    assert data["timing"]["search_elapsed_seconds"] == 1700
    assert data["timing"]["drain_seconds"] == 80
    assert data["timing"]["postprocess_elapsed_seconds"] == 50
    assert data["timing"]["confirmation_deadline"] == 2030
    assert set(data["phase_costs"]) == {"search", "postprocess", "confirmation"}
