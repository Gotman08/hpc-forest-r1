"""Bounded source snapshots shared by mother, proposals and development checks."""

from __future__ import annotations

from pathlib import Path

from ..core import InfrastructureError
from ..gitops import git
from .validation import require_integer


class SourceLimitExceeded(InfrastructureError):
    """The complete source does not fit; callers must never silently truncate it."""


def committed_source_snapshot(repo: Path, commit: str) -> dict[str, str]:
    """Read full, exact committed files for one integration input, never clipped diffs."""
    files = {}
    byte_count = 0
    entries = git(repo, "ls-tree", "-r", "-z", commit, "--", "src", binary=True)
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        header, path = entry.split(b"\t", 1)
        mode, kind, object_id = header.split()
        if mode not in {b"100644", b"100755"} or kind != b"blob":
            raise InfrastructureError("Integration source must contain regular files only")
        raw = git(repo, "cat-file", "blob", object_id.decode("ascii"), binary=True)
        byte_count += len(raw)
        if byte_count > 1024 * 1024:
            raise SourceLimitExceeded("Integration source exceeds its snapshot byte limit")
        files[path.decode("utf-8")] = raw.decode("utf-8")
    if not files:
        raise InfrastructureError("Integration source has no committed src/ files")
    return files


def _is_link(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def source_snapshot(
    worktree: Path,
    *,
    max_bytes: int = 1024 * 1024,
    max_characters: int | None = None,
    errors: str = "strict",
) -> dict[str, str]:
    """Read regular src/ files in stable order without traversing source links."""
    require_integer(max_bytes, "source byte limit", minimum=1)
    if max_characters is not None:
        require_integer(max_characters, "source character limit", minimum=1)
    worktree = Path(worktree)
    source = worktree / "src"
    if _is_link(source):
        raise InfrastructureError("Source links are not allowed")
    if not source.is_dir():
        raise InfrastructureError("The source directory does not exist")
    files: dict[str, str] = {}
    byte_count = character_count = 0
    for path in sorted(source.rglob("*")):
        if _is_link(path):
            raise InfrastructureError("Source links are not allowed")
        if not path.is_file():
            continue
        remaining = max_bytes - byte_count
        if max_characters is not None:
            remaining = min(remaining, 4 * (max_characters - character_count))
        with path.open("rb") as stream:
            raw = stream.read(remaining + 1)
        byte_count += len(raw)
        if len(raw) > remaining:
            raise SourceLimitExceeded("Source context exceeds its bounded snapshot limit")
        text = raw.decode("utf-8", errors=errors)
        character_count += len(text)
        if max_characters is not None and character_count > max_characters:
            raise SourceLimitExceeded("Source context exceeds its character limit")
        files[path.relative_to(worktree).as_posix()] = text
    return files
