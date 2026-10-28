"""Verified online SQLite snapshots, including committed WAL transactions."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .files import atomic_path


def backup_database(source: Path, destination: Path) -> None:
    source, destination = source.resolve(strict=True), destination.resolve()
    if source == destination or destination.exists():
        raise FileExistsError("A database backup must use a new destination")
    with atomic_path(destination) as temporary:
        original = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=30)
        backup = sqlite3.connect(temporary)
        try:
            original.backup(backup)
            if backup.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise sqlite3.DatabaseError("Database backup failed integrity verification")
        finally:
            backup.close()
            original.close()
