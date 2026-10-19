import json
import zipfile

import pytest

from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import ForestError, InfrastructureError
from hpc_forest.gitops import git
from hpc_forest.reporting import package, report
from hpc_forest.toolchain import compiler_identity


@pytest.fixture(scope="module", autouse=True)
def need_compiler():
    try:
        compiler_identity()
    except InfrastructureError as exc:
        pytest.skip(str(exc))


def test_real_build_search_resume_integration_confirmation_and_archive(tmp_path, config):
    root = create_workspace(tmp_path / "campaign", config)
    with Controller(root) as controller:
        with pytest.raises(ForestError, match="confirmed"):
            package(root, tmp_path / "too-early.zip")
        state = controller.run(max_batches=1)
        assert state["status"] == "checkpointed"
        assert state["costs"]["slots"] == 4  # baseline + A/B/C
        a = controller.db.one("SELECT checkpoint FROM trees WHERE role='A'")["checkpoint"]
    with Controller(root) as controller:
        state = controller.run()
        assert state["status"] == "search_complete"
        assert state["costs"]["slots"] == 6
        assert controller.db.one("SELECT checkpoint FROM trees WHERE role='A'")["checkpoint"] == a
        integrations = controller.db.archive(1, "G")
        assert integrations
        assert len(integrations[0]["sources"]) == 3
        # The second identical integration is not a second independent observation.
        assert (
            controller.db.one("SELECT count(*) AS n FROM trials WHERE state='duplicate'")["n"] >= 1
        )
        best = controller.confirm()
        assert controller.status()["costs"]["slots"] <= 9
        slots = controller.status()["costs"]["slots"]
        assert controller.confirm() == best
        assert controller.status()["costs"]["slots"] == slots
        assert git(root / "repo", "rev-parse", "submit/matmul") == best["commit"]
    archive = package(root, tmp_path / "submission.zip")
    with zipfile.ZipFile(archive) as zipped:
        manifest = json.loads(zipped.read("HPC_FOREST_MANIFEST.json"))
        assert manifest["commit"] == best["commit"]
        assert manifest["confirmation"]["correct"] is True
        assert {"src/main.c", "src/params.h", "Makefile", "run.sh"}.issubset(zipped.namelist())
        assert all("trusted" not in name for name in zipped.namelist())
    assert archive.with_suffix(".zip.sha256").is_file()
    assert report(root).is_file()
    payload = json.loads((root / "report" / "experiments.json").read_text(encoding="utf-8"))
    assert len(payload["experiments"]) == 5
    assert payload["costs"]["tokens_used"] == 0
    # Protect final delivery even after a successful confirmation.
    (root / "trusted" / "check.py").write_text("tampered", encoding="utf-8")
    with pytest.raises(InfrastructureError, match="changed"):
        package(root, tmp_path / "tampered.zip")


def test_u_uses_one_real_tree_with_all_specialists(tmp_path, config):
    config["method"] = "U"
    config["budget"]["search_slots"] = 4
    root = create_workspace(tmp_path / "single-tree", config)
    with Controller(root) as controller:
        controller.run()
        trees = controller.db.rows("SELECT role FROM trees")
        assert trees == [{"role": "U"}]
        trials = controller.db.rows("SELECT role,tree_id FROM trials")
        assert len(trials) == 3
        assert all(t["role"] in "ABCG" and t["tree_id"] == "e1:U" for t in trials)


def test_existing_destination_is_preserved(tmp_path, config):
    root = tmp_path / "existing"
    root.mkdir()
    (root / "precious").write_text("keep")
    with pytest.raises(ForestError, match="overwrite"):
        create_workspace(root, config)
    assert (root / "precious").read_text() == "keep"
