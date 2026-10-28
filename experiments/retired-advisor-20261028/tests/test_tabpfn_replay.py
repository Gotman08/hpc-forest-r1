"""The offline diagnosis must not learn labels recorded after a candidate capture."""
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("tabpfn_replay", Path(__file__).resolve().parents[1]
    / "experiments/tabpfn-advisor-20261025/reproduction/replay_advisor.py")
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)


def examples(count):
    return [{"id": str(i), "source_sha256": str(i), "captured_at": i + 0.5,
             "observed_at": i + 1, "features": [i], "target": i} for i in range(count)]


def test_context_precedes_both_concurrent_candidates():
    values = examples(12)
    values[-2]["captured_at"] = 9
    context, held = replay.select_examples(values)
    assert [row["id"] for row in held] == ["10", "11"]
    assert [row["id"] for row in context] == [str(i) for i in range(8)]
    assert max(row["observed_at"] for row in context) < min(row["captured_at"] for row in held)


def test_duplicate_codes_cannot_manufacture_sufficient_context():
    values = examples(12)
    for row in values[8:]:
        row["source_sha256"] = "0"
    assert replay.select_examples(values) == ([], [])


def test_latest_candidates_are_chosen_without_consulting_targets():
    values = examples(12)
    expected = replay.select_examples(values)[1]
    for row in values:
        row["target"] = -row["target"]
    assert [r["id"] for r in replay.select_examples(values)[1]] == [r["id"] for r in expected]
