"""Statistical bookkeeping with synthetic fixtures, never performance claims."""
import copy
import json
import shutil

import pytest
from test_mother_conversation import persistent_settings

from hpc_forest.cli import main
from hpc_forest.core import ForestError, atomic_json, digest, file_digest
from hpc_forest.pilot import execute, prepare_suite
from hpc_forest.registry import Registry
from hpc_forest.reliability import compare, measured


def campaign(tmp_path, config, index, *, speedup=2, program="program-a", engine="engine-a", epoch=1, corrupt=False):
    root = tmp_path / str(index)
    root.mkdir()
    db = Registry(root / "registry.sqlite3")
    try:
        config = copy.deepcopy(config)
        config["seed"] = index
        for key, value in {"config": config, "identity": {"controller_implementation": engine, "target": "test"},
            "manifest": {"oracle.py": "oracle-hash", "config.json": "per-run-config"}, "current_epoch": epoch,
            "started": 10 + index, "confirmation_finished:1": 110 + index}.items():
            db.set(key, value)
        with db.connection:
            for number in range(1, epoch + 1):
                db.connection.execute("INSERT INTO epochs(id,base_commit,protocol_id,baseline_id,created) VALUES(?,?,?,?,?)",
                    (number, "base-commit", "p", f"baseline-e{number}", index + number / 10))
        baseline = {"correct": True, "mean_seconds": 1., "times": [1., 1.], "commit": "base-commit", "tree_hash": program}
        db.record_evaluation(f"baseline-e{epoch}", epoch, "search", baseline)
        db.record_evaluation(f"baseline-e{epoch}", epoch, "confirmation", baseline)
        if speedup is not None:
            winner = {"correct": True, "mean_seconds": 1 / speedup, "times": [1 / speedup] * 2,
                      "commit": "candidate-commit", "tree_hash": "candidate"}
            db.record_evaluation("winner", epoch, "confirmation", winner)
            db.set("best_confirmed", {"experiment_id": "winner", "epoch": epoch, "protocol_id": "p",
                "commit": "candidate-commit", "mean_seconds": 1 / speedup, "reference_seconds": 1.,
                "evaluation_digest": "wrong" if corrupt else digest(winner)})
    finally:
        db.close()
    return root


def test_median_worst_and_frequency_count_missing_confirmations_without_invented_timings(tmp_path, config):
    roots = [campaign(tmp_path, config, i, speedup=gain) for i, gain in enumerate([4, 1, None])]
    before = [file_digest(root / "registry.sqlite3") for root in roots]
    report = compare(roots)
    assert len(report["groups"]) == 1
    group = report["groups"][0]
    assert group["median_speedup"] == 2.5 and group["worst_speedup"] == 1
    assert group["improvement_frequency"] == pytest.approx(1 / 3)
    assert group["confirmed_campaigns"] == 2 and group["unconfirmed_campaigns"] == 1
    assert [file_digest(root / "registry.sqlite3") for root in roots] == before


def test_copies_and_later_epochs_are_not_independent_repetitions(tmp_path, config):
    original = campaign(tmp_path, config, 1)
    copied = tmp_path / "copied"
    shutil.copytree(original, copied)
    continued = campaign(tmp_path, config, 2, epoch=2)
    result = compare([original, copied, continued])
    assert result["groups"][0]["independent_campaigns"] == 1
    assert {row["reason"] for row in result["excluded"]} == {
        "duplicate_campaign", "continued_epoch_not_an_independent_restart"}


def test_different_programs_engines_and_protocols_do_not_get_pooled(tmp_path, config):
    other = copy.deepcopy(config)
    other["protocol"]["repetitions"] += 1
    roots = [campaign(tmp_path, config, 1), campaign(tmp_path, config, 2, program="program-b"),
             campaign(tmp_path, config, 3, engine="engine-b"), campaign(tmp_path, other, 4)]
    result = compare(roots)
    assert len(result["groups"]) == 4 and result["distinct_programs"] == 2
    assert not any(group["repeated_campaigns_observed"] for group in result["groups"])


def test_inconsistent_confirmation_is_not_a_success_and_output_cannot_overwrite_inputs(tmp_path, config, capsys):
    root = campaign(tmp_path, config, 1, corrupt=True)
    result = compare([root])
    assert result["groups"][0]["median_speedup"] is None
    assert result["groups"][0]["improvement_frequency"] == 0
    before = file_digest(root / "registry.sqlite3")
    assert main(["reliability", str(root), "--output", str(root / "registry.sqlite3")]) == 2
    assert file_digest(root / "registry.sqlite3") == before
    assert "outside" in capsys.readouterr().err
    destination = tmp_path / "comparison.json"
    assert main(["reliability", str(root), "--output", str(destination)]) == 0
    assert json.loads(destination.read_text())["schema"] == "hpc-forest-reliability-v1"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0, -1, True])
def test_nonphysical_or_boolean_measurements_are_not_accepted(value):
    assert not measured({"correct": True, "mean_seconds": value, "times": [value]})


def suite_specification(tmp_path, config):
    cases = []
    for name in ("first", "second"):
        source, validation = tmp_path / name / "input", tmp_path / name / "validation"
        (source / "src").mkdir(parents=True)
        validation.mkdir(parents=True)
        (source / "src/main.c").write_text("/* " + name + " */\nint main(void) { return 0; }")
        (validation / "check.py").write_text("# independent fixture oracle")
        atomic_json(tmp_path / name / "config.json", config)
        cases.append({"name": name, "config": f"{name}/config.json", "source": f"{name}/input",
                      "validation": f"{name}/validation"})
    spec = tmp_path / "suite.json"
    atomic_json(spec, {"seeds": [23, 29, 31], "cases": cases})
    return spec


def test_suite_prepares_independent_sessions_and_alternating_order_without_execution(tmp_path, monkeypatch):
    config = persistent_settings(tmp_path)
    spec = suite_specification(tmp_path, config)
    monkeypatch.setattr("hpc_forest.pilot.create_workspace", lambda *args: pytest.fail("Preparation must not run"))
    output = tmp_path / "prepared"
    plan = prepare_suite(spec, output)
    entries = json.loads(plan.read_text())["order"]
    assert [e["case"] for e in entries] == ["first", "second", "second", "first", "first", "second"]
    configs = [json.loads((output / entry["config"]).read_text()) for entry in entries]
    assert len({c["codex"]["session_id"] for c in configs}) == 6
    assert len({c["codex"]["mailbox_dir"] for c in configs}) == 6
    assert all(c["budget"]["wall_seconds"] == config["budget"]["wall_seconds"] for c in configs)
    assert not any((output / entry["workspace"]).exists() for entry in entries)
    with pytest.raises(ForestError, match="exists"):
        prepare_suite(spec, output)


def test_suite_detects_changed_source_before_creating_any_campaign(tmp_path, config, monkeypatch):
    spec = suite_specification(tmp_path, config)
    plan = prepare_suite(spec, tmp_path / "prepared")
    for name in ("first", "second"):
        (tmp_path / name / "input/src/main.c").write_text("changed after registration")
    monkeypatch.setattr("hpc_forest.pilot.create_workspace", lambda *args: pytest.fail("Changed source must not run"))
    results = json.loads(execute(plan).read_text())
    assert len(results) == 6 and all("source or validation changed" in row["error"] for row in results)
