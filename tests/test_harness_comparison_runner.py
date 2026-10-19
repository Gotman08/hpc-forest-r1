import importlib.util
from pathlib import Path

from hpc_forest.core import atomic_json


def test_comparison_keeps_fresh_arms_and_equal_outer_evaluation(monkeypatch, tmp_path):
    examples = Path(__file__).parents[1] / "examples/marathon22"
    monkeypatch.syspath_prepend(str(examples))
    spec = importlib.util.spec_from_file_location("comparison_test", examples / "romeo_harness_comparison.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.ORDER) == {(arm, slug) for arm in ("reference", "mixed-harness")
                                 for slug in ("knn", "sum", "nbody")}
    assert len(module.ORDER) == 6
    module.runner.CHANNEL, module.runner.SESSION_ID = tmp_path / "mailbox", "a" * 32
    for name, value in module.SCHEDULE.items():
        monkeypatch.setitem(module.runner.reference.SCHEDULE, name, value)
    for name, value in module.LIMITS.items():
        monkeypatch.setitem(module.runner.reference.LIMITS, name, value)
    monkeypatch.setattr(module.runner, "HARNESS", None)
    reference = module.runner.config_for("unused", "knn", "target", {"protocol_timeout_seconds": 40})
    monkeypatch.setattr(module.runner, "HARNESS", {"enabled": True, "max_attempts": 3,
        "call_token_ceiling": 196608, "research": {"enabled": True}})
    mixed = module.runner.config_for("unused", "knn", "target", {"protocol_timeout_seconds": 40})
    assert reference["protocol"] == mixed["protocol"]
    assert reference["seed"] == mixed["seed"] == 23
    for field in ("tokens", "wall_seconds", "generation_seconds", "max_workers"):
        assert reference["budget"][field] == mixed["budget"][field]
    assert reference["budget"]["mission_tokens"] == 196608
    assert mixed["budget"]["mission_tokens"] == 589824
    for config in (reference, mixed):
        controller = module.ObservedController.__new__(module.ObservedController)
        controller.config = config
        plan = controller.plan()
        assert all(len(batch) == 1 for batch in plan)
        roles = [role for batch in plan for role in batch]
        assert len(roles) == 24 and roles.count("G") == 6


def load_comparison(monkeypatch):
    examples = Path(__file__).parents[1] / "examples/marathon22"
    monkeypatch.syspath_prepend(str(examples))
    spec = importlib.util.spec_from_file_location("comparison_preparation_test", examples / "romeo_harness_comparison.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sequential_admission_preserves_all_roles_under_the_same_token_ceiling(monkeypatch, db, config):
    module = load_comparison(monkeypatch)
    config["budget"].update(tokens=1500000, search_slots=25, mission_tokens=589824)
    config["schedule"].update(module.SCHEDULE)
    db.set("config", config)
    controller = module.ObservedController.__new__(module.ObservedController)
    controller.config = config
    admitted = []
    for batch in controller.plan():
        assert len(batch) == 1
        slot = db.reserve("search", "role:" + batch[0], 589824)
        admitted.extend(batch)
        db.settle_tokens(slot, 30000)
    assert len(admitted) == 24 and set(admitted) == set("ABCG")
    assert db.costs()["tokens_used"] == 720000 and db.costs()["tokens_reserved"] == 0


def test_both_arms_use_identical_official_preparation_without_copying_a_candidate(monkeypatch, tmp_path):
    module = load_comparison(monkeypatch)
    calls = []

    def prepare(slug, official, output):
        calls.append(slug)
        root = output / "preparation" / slug
        source, validation = root / "frozen/source", root / "frozen/validation"
        source.mkdir(parents=True)
        validation.mkdir()
        (source / "official.c").write_text("/* official preparation fixture */\n")
        (validation / "input.data").write_bytes(b"same fixed input\n")
        receipt = {"source": str(source), "validation": str(validation), "fixtures": ["fixed hash"],
                   "benchmark_input_sha256": "fixed benchmark hash", "official_source_hashes": {}}
        atomic_json(root / "operator-preparation.json", receipt)
        return receipt

    matched = module.MatchedPreparation(prepare)
    first = matched("knn", tmp_path / "official", tmp_path / "reference")
    second = matched("knn", tmp_path / "official", tmp_path / "mixed-harness")
    assert calls == ["knn"]
    assert first["source"] != second["source"] and first["validation"] != second["validation"]
    for key in ("fixtures", "benchmark_input_sha256", "official_source_hashes"):
        assert first[key] == second[key]
    assert (Path(first["source"]) / "official.c").read_bytes() == (Path(second["source"]) / "official.c").read_bytes()
    assert (Path(first["validation"]) / "input.data").read_bytes() == (Path(second["validation"]) / "input.data").read_bytes()
