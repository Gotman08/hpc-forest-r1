"""Atomic publication on the destination filesystem, with durable file contents."""
from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


def extended_path(path: Path) -> Path:
    """Address files beyond Windows' legacy MAX_PATH; other platforms are unchanged."""
    if os.name != "nt":
        return Path(path)
    absolute = str(Path(path).absolute())
    if absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def plain_path(path) -> Path:
    """The drive or UNC form of a path, without the Win32 extended-length prefix."""
    value = str(path)
    if value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value[8:])
    if value.startswith("\\\\?\\"):
        return Path(value[4:])
    return Path(value)


def sync_directory(directory: Path) -> None:
    """Persist a rename on POSIX; Windows provides atomic replace but no dir fsync."""
    if os.name != "nt":
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


@contextmanager
def atomic_path(path: Path):
    """Publish a complete file or preserve the previous file on write failure.

    Each writer owns a unique temporary file. Concurrent complete replacements
    use last-writer-wins semantics; use a transaction/lock for read-modify-write.
    A directory-sync error after replacement reports uncertain durability.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        yield temporary
        with temporary.open("r+b") as stream:
            os.fsync(stream.fileno())
        for attempt in range(8):
            try:
                os.replace(temporary, path)
                break
            except PermissionError as exc:
                # Windows readers and antivirus can briefly deny replacement.
                # Never delete the destination as a fallback or retry forever.
                if os.name != "nt" or exc.winerror not in {5, 32, 33} or attempt == 7:
                    raise
                time.sleep(0.01 * (attempt + 1))
        sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_bytes(path: Path, value: bytes) -> None:
    with atomic_path(path) as temporary:
        temporary.write_bytes(value)


def atomic_json(path: Path, value) -> None:
    encoded = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    atomic_bytes(path, encoded)
