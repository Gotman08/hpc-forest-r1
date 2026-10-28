"""Controlled adviser ablations preserve the default and reject weak evidence."""
import pytest

from hpc_forest import advisor
from hpc_forest.advisor_validation import (
    POLICY,
    calibrated_choice,
    decision_validation,
    validation_split,
)
from hpc_forest.advisor_value import POLICY as RUNTIME_POLICY
from hpc_forest.core import ForestError


def rows(count=18):
    return [{"id": str(i), "role": "T1", "source_sha256": str(i),
             "captured_at": i * 2, "observed_at": i * 2 + 1,
             "parent_score": .5, "measured_score": .6 + i * .01} for i in range(count)]


def test_corrected_default_and_explicit_historical_factors():
    cfg = advisor.settings({})
    assert cfg["context_scope"] == "campaign" and cfg["validation_policy"] == RUNTIME_POLICY
    for scope in ("campaign", "tree"):
        for policy in ("gain_rank_v2", POLICY, RUNTIME_POLICY):
            assert advisor.settings({"advisor": {"context_scope": scope, "validation_policy": policy}})
    for bad in ({"context_scope": "unknown"}, {"validation_policy": "unknown"}):
        with pytest.raises(ForestError):
            advisor.settings({"advisor": bad})


def test_tree_filter_precedes_context_limit_and_commit_deduplication(db):
    db.set("protocol_id", "p")
    for i in range(20):
        db.set(f"advisor_sample:{i}", {**rows(20)[i], "epoch": 1, "protocol_id": "p",
            "schema": advisor.VERSION, "commit": str(i % 10), "role": "T1" if i < 10 else "T2"})
    selected = advisor.samples(db, 1, 8, role="T1")
    assert [e["id"] for e in selected] == [str(i) for i in range(2, 10)]
    assert all(e["role"] == "T2" for e in advisor.samples(db, 1, 8))


def test_validation_excludes_future_and_same_parent_even_across_roles():
    data = rows()
    data[0]["source_sha256"] = data[-1]["source_sha256"]
    data[1]["observed_at"] = data[-6]["captured_at"] + 1
    data[0]["role"] = "T2"
    fit, held, info = validation_split(data, "T1")
    assert len(held) == 6 and 0 not in fit and 1 not in fit
    assert not info.get("reason")
    assert {data[i]["source_sha256"] for i in fit}.isdisjoint(data[i]["source_sha256"] for i in held)


def test_other_tree_pairs_cannot_validate_current_tree():
    data = rows()
    for e in data[4:]:
        e["role"] = "T2"
    _, _, info = validation_split(data, "T1")
    assert info["reason"] == "insufficient_same_tree_validation"


def test_multiple_children_do_not_create_independent_parent_evidence():
    data = rows()
    for e in data[-6:]:
        e["source_sha256"] = "one-parent"
    _, _, info = validation_split(data, "T1")
    assert info["reason"] == "insufficient_independent_parent_context"


def test_decision_validation_checks_child_values_not_gain_ranks():
    held = rows(6)
    for i, e in enumerate(held):
        e["parent_score"] = .9 - i * .04
        e["measured_score"] = .88 - i * .02
    gains = [e["measured_score"] - e["parent_score"] for e in held]
    result = decision_validation(held, gains, {"policy": POLICY})
    assert result["pair_count"] == 15 and result["pairwise_accuracy"] == 1
    assert result["mae_child_score"] == 0 and not result.get("reason")
    assert not result["margin_is_confidence_bound"]


def test_good_rank_but_poor_calibration_is_rejected():
    held = rows(6)
    result = decision_validation(held, [.4 + i * .01 for i in range(6)], {"policy": POLICY})
    assert result["pairwise_accuracy"] == 1
    assert result["reason"] == "calibration_not_better_than_parent_baseline"


def test_clipped_tie_and_small_margin_cannot_change_parent():
    evidence = {"policy": POLICY, "decision_margin": .04}
    candidates = [{"parent_score": .813156}, {"parent_score": .925595}]
    chosen, values, reason = calibrated_choice(candidates, [.203749, .159566], evidence)
    assert chosen == 0 and values[0] > 1 and values[1] > values[0]
    assert reason == "out_of_range_child_value"
    assert calibrated_choice(candidates, [.12, .02], evidence)[0] == 0
    assert calibrated_choice(candidates, [0, .02], evidence)[0] == 1
    with pytest.raises(ValueError):
        calibrated_choice(candidates, [0, .02], {"policy": POLICY})
