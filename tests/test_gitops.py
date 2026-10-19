import os
import shutil
from importlib.resources import files
from pathlib import Path

import pytest

from hpc_forest.controller import create_workspace
from hpc_forest.gitops import ensure_clean, git, initialize_source


def test_imported_non_executable_runner_is_clean_and_executable(tmp_path, config, need_compiler):
    source = tmp_path / "import"
    shutil.copytree(Path(str(files("hpc_forest") / "assets" / "matmul")), source)
    (source / "run.sh").chmod(0o644)
    root = create_workspace(tmp_path / "campaign", config, source=source)
    ensure_clean(root / "repo", git(root / "repo", "rev-parse", "HEAD"))
    assert git(root / "repo", "ls-files", "--stage", "run.sh").startswith("100755 ")
    if os.name == "posix":
        assert (root / "repo" / "run.sh").stat().st_mode & 0o100


@pytest.mark.skipif(os.name != "nt", reason="Windows Git path-length regression")
def test_git_objects_survive_long_path_without_persisting_settings(tmp_path):
    source = tmp_path / "source"
    (source / "src").mkdir(parents=True)
    (source / "src" / "main.c").write_text("int main(void) { return 0; }\n")
    padding = max(1, 235 - len(str(tmp_path)) - len("/snapshot") - 1)
    destination = tmp_path / ("nested-" + "x" * padding) / "snapshot"
    assert len(str(destination)) < 260
    assert len(str(destination / ".git" / "objects" / "aa" / ("a" * 38))) > 260
    commit = initialize_source(source, destination)
    ensure_clean(destination, commit)
    assert (destination / "src" / "main.c").read_text() == "int main(void) { return 0; }\n"
    assert "core.longpaths" not in git(destination, "config", "--local", "--list")
