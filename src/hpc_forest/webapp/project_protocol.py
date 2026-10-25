"""Protected project adapter, executed only inside an allocated compute job."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def run(phase: str, trusted: Path, worktree: Path, build: Path, evaluation_phase="search"):
    spec = json.loads((trusted / "project.json").read_text())
    project = build / "project"
    env = {**os.environ, "FOREST_PHASE": evaluation_phase, "FOREST_PROJECT": str(project),
           "FOREST_ATTACHMENTS": str(trusted / "attachments")}
    if phase == "build":
        project.mkdir(parents=True, exist_ok=False)
        shutil.copytree(trusted / "original", project, dirs_exist_ok=True)
        allowed = set(spec["editable_files"])
        for source in (worktree / "src").rglob("*"):
            if source.is_symlink():
                raise ValueError("Candidate symlink refused")
            if not source.is_file():
                continue
            name = source.relative_to(worktree / "src").as_posix()
            if name not in allowed:
                raise ValueError("Candidate changed an unapproved file: " + name)
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        command = spec["contract"]["build_command"]
    else:
        command = spec["contract"]["test_command" if phase == "check" else "benchmark_command"]
    started = time.perf_counter()
    with (build / (phase + "-output.log")).open("ab") as output:
        result = subprocess.run(["bash", "-euc", command], cwd=project, env=env,
                                stdout=output, stderr=subprocess.STDOUT, check=False)
    elapsed = time.perf_counter() - started
    if result.returncode:
        print((build / (phase + "-output.log")).read_text(errors="replace")[-12000:], file=sys.stderr)
        return 1
    if phase == "build":
        binary = project / spec["binary"]
        if not binary.is_file() or binary.is_symlink() or binary.read_bytes()[:4] != b"\x7fELF":
            raise ValueError("The benchmark command must name the ELF executable built by this project")
        print(json.dumps({"executable_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}))
    elif phase == "check":
        # One protected test-command suite. Individual assertions belong to the user's tests.
        print(json.dumps({"correct": True, "cases": 1, "scope": "provided_test_command"}))
    else:
        print(json.dumps({"seconds": elapsed, "metric": "benchmark_command_wall_seconds"}))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["build", "check", "benchmark"])
    parser.add_argument("trusted", type=Path)
    parser.add_argument("worktree", type=Path)
    parser.add_argument("build", type=Path)
    parser.add_argument("evaluation_phase")
    args = parser.parse_args()
    try:
        sys.exit(run(args.phase, args.trusted, args.worktree, args.build, args.evaluation_phase))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

