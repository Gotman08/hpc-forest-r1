"""Storage failures must not destroy evidence or masquerade as completed searches."""
import importlib.util
import json
import os
import subprocess
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

STUDY = Path(__file__).resolve().parents[1] / "experiments/controlled-advisor-20261026"

def load(name):
    spec = importlib.util.spec_from_file_location(name, STUDY / "reproduction" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def quota(used=1450000, grace="5 days"):
    return ("mmlsquota:user:HEADER:version:reserved:reserved:filesystemName:quotaType:id:name:"
            "blockUsage:blockQuota:blockLimit:blockInDoubt:blockGrace:filesUsage:filesQuota:"
            "filesLimit:filesInDoubt:filesGrace:remarks:fid:filesetname:\n"
            f"mmlsquota:user:0:1:::gpfs:USR:123:u:100:200:300:0:none:{used}:1000000:1500000:100:{grace}:host:2:scratch:\n")

def test_quota_inodes_and_grace_are_independent_of_free_filesystem():
    storage = load("study_storage")
    row = storage.quota_rows(quota())["scratch"]
    assert storage.available(row)["files"] == 49900
    assert storage.available(row)["bytes"] == 200 * 1024
    assert storage.available(storage.quota_rows(quota(grace="expired"))["scratch"])["files"] == 0

def test_guard_rejects_quota_even_with_ample_physical_free_space(tmp_path, monkeypatch):
    storage = load("study_storage")
    monkeypatch.setattr(storage.os, "statvfs", lambda p: SimpleNamespace(
        f_bavail=10**9, f_frsize=4096, f_favail=10**9), raising=False)
    monkeypatch.setattr(storage.os, "getuid", lambda: 123, raising=False)
    monkeypatch.setattr(storage.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=quota()))
    with pytest.raises(RuntimeError, match="Insufficient storage"):
        storage.storage_check(tmp_path, min_bytes=0, min_files=60000)

@pytest.mark.skipif(os.name == "nt", reason="ROMEO relocation uses POSIX directory symlinks")
def test_preservation_keeps_old_paths_and_verifies_full_archive(tmp_path):
    storage = load("study_storage")
    source, target = tmp_path / "work/source", tmp_path / "preserved/source"
    source.mkdir(parents=True)
    (source / "code.cpp").write_text("int main() { return 0; }")
    (source / "link").symlink_to("code.cpp")
    expected = storage.inventory(source)
    archive = tmp_path / "evidence.tar.gz"
    result = storage.preserve(source, target, archive, allowed_root=source.parent)
    assert result["verified"] and result["relocated"] and source.is_symlink()
    assert (source / "code.cpp").read_text() == "int main() { return 0; }"
    assert storage.inventory(target) == expected
    storage.verify_archive(archive, expected)

def test_copy_failure_leaves_original_and_verified_archive(tmp_path, monkeypatch):
    storage = load("study_storage")
    source = tmp_path / "source"
    source.mkdir()
    (source / "result.json").write_text('{"value":7}')
    expected = storage.inventory(source)
    def fail(*args, **kwargs):
        raise OSError("injected destination full")
    monkeypatch.setattr(storage.shutil, "copytree", fail)
    with pytest.raises(OSError, match="destination full"):
        storage.preserve(source, tmp_path / "saved", tmp_path / "evidence.tar.gz", allowed_root=tmp_path)
    assert source.is_dir() and not source.is_symlink()
    assert storage.inventory(source) == expected
    storage.verify_archive(tmp_path / "evidence.tar.gz", expected)


@pytest.mark.skipif(os.name == "nt", reason="ROMEO preservation uses POSIX directory symlinks")
def test_preserved_git_history_and_linked_worktrees_remain_usable(tmp_path):
    storage = load("study_storage")
    source = tmp_path / 'source'
    repository = source / 'campaign/repo'
    repository.mkdir(parents=True)
    def git(*args):
        return subprocess.run(['git', '-C', str(repository), *args],
                              check=True, capture_output=True, text=True).stdout.strip()
    git('init')
    git('config', 'user.name', 'Test')
    git('config', 'user.email', 'test@example.invalid')
    (repository / 'code.cpp').write_text('original')
    git('add', '.')
    git('commit', '-m', 'initial')
    commit = git('rev-parse', 'HEAD')
    linked = source / 'campaign/worktrees/one'
    git('worktree', 'add', '--detach', str(linked), commit)
    storage.preserve(source, tmp_path / 'preserved', tmp_path / 'source.tar.gz', allowed_root=tmp_path)
    assert git('rev-parse', 'HEAD') == commit
    assert subprocess.run(['git', '-C', str(linked), 'rev-parse', 'HEAD'],
                          check=True, capture_output=True, text=True).stdout.strip() == commit
    delivered = tmp_path / 'delivered'
    git('worktree', 'add', '--detach', str(delivered), commit)
    assert (delivered / 'code.cpp').read_text() == 'original'

def test_source_changed_during_copy_is_not_retired(tmp_path, monkeypatch):
    storage = load("study_storage")
    source = tmp_path / "source"
    source.mkdir()
    (source / "data").write_text("before")
    original_copy = storage.shutil.copytree
    def changed(*args, **kwargs):
        result = original_copy(*args, **kwargs)
        (source / "data").write_text("after")
        return result
    monkeypatch.setattr(storage.shutil, "copytree", changed)
    with pytest.raises(RuntimeError, match="source changed"):
        storage.preserve(source, tmp_path / "saved", tmp_path / "evidence.tar.gz", allowed_root=tmp_path)
    assert not source.is_symlink() and (source / "data").read_text() == "after"


def test_archive_verification_handles_hardlinks_and_detects_changed_bytes(tmp_path):
    storage = load('study_storage')
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'a').write_text('content')
    os.link(source / 'a', source / 'b')
    expected = storage.inventory(source)
    archive = tmp_path / 'archive.tar.gz'
    with tarfile.open(archive, 'w:gz', dereference=False) as stream:
        stream.add(source, arcname='.')
    storage.verify_archive(archive, expected)
    expected['b']['sha256'] = 'not the archived content'
    with pytest.raises(RuntimeError, match='differs'):
        storage.verify_archive(archive, expected)

def test_preservation_refuses_unbounded_or_reused_destinations(tmp_path):
    storage = load("study_storage")
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(RuntimeError, match="outside permitted"):
        storage.preserve(source, tmp_path / "saved", tmp_path / "a.tar.gz", allowed_root=source)
    saved = tmp_path / "saved"
    saved.mkdir()
    with pytest.raises(RuntimeError, match="already exists"):
        storage.preserve(source, saved, tmp_path / "a.tar.gz", allowed_root=tmp_path)

def test_independent_state_survives_unwritable_work_directory(tmp_path, monkeypatch):
    storage = load("study_storage")
    state, block = tmp_path / "independent", tmp_path / "work"
    block.mkdir()
    monkeypatch.setenv("FOREST_STUDY_STATE", str(state))
    storage.record_state(block, "result.json", {"pipeline_complete": False, "error": "ENOSPC"})
    assert json.loads((state / "result.json").read_text())["error"] == "ENOSPC"
    monkeypatch.setenv("FOREST_STUDY_STATE", str(block / "inside"))
    with pytest.raises(RuntimeError, match="outside"):
        storage.record_state(block, "result.json", {})

def test_unstarted_arms_are_not_report_errors_or_successes(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(STUDY / "reproduction"))
    from hpc_forest.core import digest
    module = load("analyze_controlled")
    block = tmp_path / "block"
    block.mkdir()
    common = {"analysis": "plan", "children": [{"subject": "a", "objective": "b"}], "G": "g"}
    (block / "frozen-plan.json").write_text(json.dumps({
        "plan": common, "plan_sha256": digest(common), "charged_planning_seconds": 120,
        "planning_receipt": {"thread_id": "common"}}))
    (block / "pair.json").write_text(json.dumps({"case": "gemm_cpu", "repeat": 1,
        "arms": [{"id": "one", "condition": "off", "advisor": {"enabled": False,
                  "context_scope": "campaign", "validation_policy": "gain_rank_v2"}}]}))
    report = module.analyze([block], tmp_path / "report")
    assert report["assigned_arms"] == 1 and report["delivered"] == 0
    assert not report["audit_errors"] and report["independent_mother_threads"] == 0
    assert all(c["complete_valid_pairs"] == 0 for c in report["contrasts"])

