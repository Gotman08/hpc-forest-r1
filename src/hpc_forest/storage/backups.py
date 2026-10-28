"""Offline application backups and verified restoration into a new directory.

External campaign directories are references, not owned data; the manifest lists
them explicitly. A restored snapshot never resubmits unfinished remote work.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import time
from pathlib import Path

from ..core import FileLock, ForestError, file_digest
from .files import atomic_json
from .sqlite import backup_database


def _new_directory(source: Path, destination: Path) -> tuple[Path, Path]:
    source, destination = source.resolve(strict=True), destination.resolve()
    if destination.exists() or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ForestError("Backup/restore requires a new directory outside the source")
    destination.mkdir(parents=True)
    return source, destination


def _files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ForestError("Backup refuses links: " + str(path))
        sidecar = path.name.endswith(("-wal", "-shm")) and path.with_name(path.name[:-4]).is_file()
        if path.is_file() and path != root / "application.lock" and not sidecar:
            yield path


def backup_application(source: Path, destination: Path) -> dict:
    if not (source / "application.sqlite3").is_file():
        raise ForestError("Application database not found")
    with FileLock(source / "application.lock"):
        source, destination = _new_directory(source, destination)
        inventory = {}
        for path in _files(source):
            relative = path.relative_to(source).as_posix()
            target = destination / "data" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".sqlite3":
                backup_database(path, target)
            else:
                shutil.copy2(path, target)
                if file_digest(path) != file_digest(target):
                    raise ForestError("Source changed during backup: " + relative)
            inventory[relative] = {"sha256": file_digest(target), "bytes": target.stat().st_size}
        database = sqlite3.connect(destination / "data/application.sqlite3")
        try:
            external = [json.loads(row[0])["source_root"] for row in database.execute(
                "SELECT payload FROM records WHERE kind='campaign'")
                if not Path(json.loads(row[0])["source_root"]).resolve().is_relative_to(source)]
        finally:
            database.close()
        receipt = {"schema": "forest-application-backup-v1", "source": str(source),
                   "created": time.time(), "files": inventory, "external_campaigns": external}
        atomic_json(destination / "manifest.json", receipt)
        verify_backup(destination)
        return receipt


def verify_backup(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "forest-application-backup-v1":
        raise ForestError("Unknown backup format")
    actual = {p.relative_to(root / "data").as_posix(): p for p in _files(root / "data")}
    if set(actual) != set(manifest["files"]):
        raise ForestError("Backup file inventory differs from its manifest")
    for name, entry in manifest["files"].items():
        path = actual[name]
        if file_digest(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]:
            raise ForestError("Backup integrity mismatch: " + name)
        if path.suffix == ".sqlite3":
            db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise ForestError("Corrupt backup database: " + name)
            finally:
                db.close()
    return manifest


def restore_application(backup: Path, destination: Path) -> dict:
    manifest = verify_backup(backup)
    backup, destination = _new_directory(backup, destination)
    for name in manifest["files"]:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup / "data" / name, target)
        if file_digest(target) != manifest["files"][name]["sha256"]:
            raise ForestError("Restored file differs: " + name)
    quarantined = []
    original_root = Path(manifest["source"])
    with sqlite3.connect(destination / "application.sqlite3") as db:
        for identifier, kind, serialized in db.execute("SELECT id,kind,payload FROM records").fetchall():
            payload = json.loads(serialized)
            if kind == "campaign" and Path(payload["source_root"]).is_relative_to(original_root):
                payload["source_root"] = str(destination / Path(payload["source_root"]).relative_to(original_root))
            if kind == "mission" and payload.get("state") not in {"completed", "failed", "cancelled"}:
                payload.update(state="recovery_required", previous_state=payload.get("state"),
                               recovery_pending=False, last_error="Sauvegarde restaurée : réconciliez le job existant avant toute reprise.")
                quarantined.append(identifier)
            db.execute("UPDATE records SET payload=? WHERE id=?", (json.dumps(payload, ensure_ascii=False), identifier))
    receipt = {"schema": "forest-application-restore-v1", "source": str(backup),
               "destination": str(destination), "verified_files": len(manifest["files"]),
               "quarantined_missions": quarantined, "external_campaigns": manifest["external_campaigns"]}
    atomic_json(destination / "restore-receipt.json", receipt)
    return receipt
