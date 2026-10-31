from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .core import CandidateRejected, ForestError, InfrastructureError


def git(repo: Path, *args: str, binary: bool = False):
    command = ["git"]
    if os.name == "nt":
        # Scope long-path support to this command; never change the user's Git config.
        command += ["-c", "core.longpaths=true"]
    command += ["-C", str(repo), *args]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=True,
            text=not binary,
            encoding=None if binary else "utf-8",
            # Imported sources may be Latin-1; file contents are read with binary=True.
            errors=None if binary else "replace",
            timeout=120,
        )
        return result.stdout if binary else result.stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        detail = getattr(exc, "stderr", "")
        raise InfrastructureError(f"Git command failed ({args[0]}): {detail or exc}") from exc


def initialize_source(source: Path, destination: Path) -> str:
    if destination.exists():
        raise ForestError(f"Destination exists: {destination}")
    # Import a snapshot, never modify the caller's original checkout or copy its .git.
    shutil.copytree(
        source, destination, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.exe", "*.obj")
    )
    git(destination, "init", "-b", "main")
    git(destination, "config", "user.name", "HPC Forest local controller")
    git(destination, "config", "user.email", "controller@hpc-forest.invalid")
    git(destination, "config", "core.autocrlf", "false")
    git(destination, "add", ".")
    git(destination, "commit", "-m", "chore: preserve imported baseline")
    return git(destination, "rev-parse", "HEAD")


def make_worktree(repo: Path, destination: Path, branch: str, commit: str) -> None:
    git(repo, "worktree", "add", "-b", branch, str(destination), commit)


def assert_allowed_changes(worktree: Path, allowed: tuple[str, ...] = ("src/",)) -> None:
    changed = git(worktree, "diff", "--name-only", "HEAD", "--").splitlines()
    changed += git(worktree, "ls-files", "--others", "--exclude-standard").splitlines()
    for path in changed:
        if not any(path.startswith(prefix) for prefix in allowed):
            raise CandidateRejected(f"Candidate changed a protected path: {path}")
    for path in (worktree / "src").rglob("*"):
        if path.is_symlink():
            raise CandidateRejected("Candidate symlinks are not allowed")


def commit_candidate(
    worktree: Path, mission_id: str, expected_parent: str | None = None
) -> tuple[str, str]:
    if expected_parent and git(worktree, "rev-parse", "HEAD") != expected_parent:
        raise CandidateRejected("Worker changed Git HEAD; candidate provenance is invalid")
    assert_allowed_changes(worktree)
    git(worktree, "add", "--", "src")
    git(worktree, "commit", "--allow-empty", "-m", f"experiment: {mission_id}")
    return git(worktree, "rev-parse", "HEAD"), git(worktree, "rev-parse", "HEAD^{tree}")


def worktree_tree_hash(worktree: Path) -> str:
    git(worktree, "add", "--", "src")
    try:
        return git(worktree, "write-tree")
    finally:
        git(worktree, "reset", "--quiet", "HEAD", "--", "src")


def ensure_clean(worktree: Path, commit: str) -> None:
    if git(worktree, "rev-parse", "HEAD") != commit or git(worktree, "status", "--porcelain"):
        raise InfrastructureError("Evaluation requires an unchanged exact commit")

