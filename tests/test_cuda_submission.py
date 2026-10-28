"""Archive/receipt fixtures only; these tests never run CUDA or a model."""
import copy
import hashlib
import io
import json
import zipfile
from dataclasses import asdict
from pathlib import Path

import pytest

from hpc_forest.controller import create_workspace
from hpc_forest.core import ForestError, Outcome, digest
from hpc_forest.gitops import git
from hpc_forest.registry import Registry
from hpc_forest.reporting import package
from hpc_forest.submission import delivery_manifest, validate_submission


def cuda_source(tmp_path):
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    original = Path(__file__).resolve().parent / "fixtures/cuda/reference.cu"
    (source / "src/nbody_kernel.cu").write_bytes(original.read_bytes())
    (source / "src/launch.json").write_text(json.dumps(
        {"block": 256, "items_per_block": 256, "shared_memory_bytes": 0}))
    return source


def confirmation_fixture(root):
    """Install an offline confirmation receipt to isolate the delivery contract."""
    db = Registry(root / "registry.sqlite3")
    try:
        commit = git(root / "repo", "rev-parse", "HEAD")
        outcome = asdict(Outcome("valid", correct=True, commit=commit, mean_seconds=0.1,
                                 times=[0.1, 0.1], score=0.5))
        db.record_evaluation("baseline-e1", 1, "confirmation", outcome)
        db.set("best_confirmed", {"experiment_id": "baseline-e1", "commit": commit, "epoch": 1,
               "mean_seconds": 0.1, "reference_seconds": 0.1, "improvement_fraction": 0,
               "protocol_id": db.get("protocol_id"), "evaluation_digest": digest(outcome),
               "is_baseline": True})
    finally:
        db.close()


def test_cuda_archive_exports_exact_confirmed_source_and_launch_without_c_runner(
    tmp_path, config, need_compiler,
):
    source = cuda_source(tmp_path)
    root = create_workspace(tmp_path / "campaign", config, source=source)
    with pytest.raises(ForestError, match="confirmed"):
        package(root, tmp_path / "early.zip")
    confirmation_fixture(root)
    output = package(root, tmp_path / "submission.zip")
    with zipfile.ZipFile(output) as archive:
        assert "Makefile" not in archive.namelist() and "run.sh" not in archive.namelist()
        manifest = json.loads(archive.read("HPC_FOREST_MANIFEST.json"))
        delivery = manifest["delivery"]
        assert delivery["kind"] == "cuda-kernel" and delivery["kernel"] == "nbody_step_naive"
        for key, name in [("source", "src/nbody_kernel.cu"), ("launch", "src/launch.json")]:
            assert archive.read(name) == (source / name).read_bytes()
            assert delivery["files"][key] == {"path": name, "sha256": hashlib.sha256(archive.read(name)).hexdigest()}
        assert manifest["commit"] == git(root / "repo", "rev-parse", "HEAD")
    assert output.with_suffix(".zip.sha256").is_file()


def test_cuda_export_still_requires_final_g_confirmation(tmp_path, config, need_compiler):
    config = copy.deepcopy(config)
    config["completion"] = {"policy": "finish-started", "confirm_final_g": True}
    root = create_workspace(tmp_path / "campaign", config, source=cuda_source(tmp_path))
    confirmation_fixture(root)
    with pytest.raises(ForestError, match="mandatory final G"):
        package(root, tmp_path / "unconfirmed-G.zip")


def test_cuda_export_accepts_verified_final_g_and_rejects_altered_receipt(tmp_path, config, need_compiler):
    config["completion"] = {"policy": "finish-started", "confirm_final_g": True}
    root = create_workspace(tmp_path / "campaign", config, source=cuda_source(tmp_path))
    confirmation_fixture(root)
    db = Registry(root / "registry.sqlite3")
    try:
        best = db.get("best_confirmed")
        outcome = asdict(Outcome("valid", correct=True, commit=best["commit"], mean_seconds=0.2,
                                 times=[0.2, 0.2], score=1 / 3))
        db.record_evaluation("fixture-G", 1, "confirmation", outcome)
        db.set("postprocess:1", {"mission_id": "fixture-G", "outcome": outcome})
        final = {"status": "confirmed", "experiment_id": "fixture-G", "outcome": outcome}
        db.set("final_g_confirmation:1", final)
    finally:
        db.close()
    output = package(root, tmp_path / "submission.zip")
    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read("HPC_FOREST_MANIFEST.json"))
        assert manifest["final_g_confirmation"]["status"] == "confirmed"
        assert manifest["experiment_id"] == "baseline-e1"  # G is required, never presumed faster.
    db = Registry(root / "registry.sqlite3")
    try:
        db.set("final_g_confirmation:1", {**final, "outcome": {**outcome, "mean_seconds": 0.1}})
    finally:
        db.close()
    with pytest.raises(ForestError, match="confirmation receipt"):
        package(root, tmp_path / "altered.zip")


@pytest.mark.parametrize("changes", [
    {"source": "../kernel.cu"}, {"source": "src/../kernel.cu"}, {"launch": "C:/launch.json"},
    {"kernel": "foo();"}, {"kind": "source-only"}, {"launch": "src\\launch.json"},
])
def test_cuda_delivery_rejects_unsafe_or_unsupported_contracts(changes):
    contract = {"kind": "cuda-kernel", "source": "src/kernel.cu", "launch": "src/launch.json", "kernel": "kernel"}
    with pytest.raises(ForestError):
        validate_submission({"submission": {**contract, **changes}})


@pytest.mark.parametrize("launch", [
    {"block": True, "items_per_block": 256, "shared_memory_bytes": 0},
    {"block": 1025, "items_per_block": 256, "shared_memory_bytes": 0},
    {"block": 256, "items_per_block": 0, "shared_memory_bytes": 0},
    {"block": 256, "items_per_block": 256, "shared_memory_bytes": 49153},
])
def test_invalid_imported_launch_fails_before_campaign_initialization(tmp_path, config, launch):
    from hpc_forest import controller

    source = cuda_source(tmp_path)
    (source / "src/launch.json").write_text(json.dumps(launch))
    # Toolchain discovery is unrelated to this validation and must not start a compiler.
    from unittest.mock import patch

    with patch.object(controller, "compiler_identity", return_value={}):
        with pytest.raises(ForestError, match="Invalid CUDA launch"):
            create_workspace(tmp_path / "campaign", config, source=source)
    assert not (tmp_path / "campaign").exists()


def test_executable_archive_contract_is_not_relaxed_for_other_imports():
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("src/main.c", "int main(void) { return 0; }")
    with zipfile.ZipFile(raw) as archive:
        with pytest.raises(ForestError, match="Makefile and run.sh"):
            delivery_manifest(archive, {})
