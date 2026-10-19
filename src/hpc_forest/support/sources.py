"""Bounded source snapshots shared by mother, proposals and development checks."""

from __future__ import annotations

from pathlib import Path

from ..core import InfrastructureError
from .validation import require_integer


class SourceLimitExceeded(InfrastructureError):
    """The complete source does not fit; callers must never silently truncate it."""


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
