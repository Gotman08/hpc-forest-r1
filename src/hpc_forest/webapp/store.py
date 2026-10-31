"""Durable application records, separate from preserved Forest registries."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .paths import NotFound


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "application.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL,
                    created REAL NOT NULL, updated REAL NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS record_kind ON records(kind, updated);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, kind: str, payload: dict, identifier: str | None = None) -> dict:
        now = time.time()
        identifier = identifier or uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO records VALUES(?,?,?,?,?)",
                       (identifier, kind, now, now, json.dumps(payload, ensure_ascii=False)))
        return self.get(identifier, kind)

    def get(self, identifier: str, kind: str | None = None) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM records WHERE id=?", (identifier,)).fetchone()
        if row is None or (kind is not None and row["kind"] != kind):
            raise NotFound("Projet ou mission introuvable.")
        return {**json.loads(row["payload"]), "id": row["id"], "kind": row["kind"],
                "created": row["created"], "updated": row["updated"]}

    def list(self, kind: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM records WHERE kind=? ORDER BY updated DESC",
                (kind,)).fetchall()
        return [{**json.loads(r["payload"]), "id": r["id"], "kind": r["kind"],
                 "created": r["created"], "updated": r["updated"]} for r in rows]

    def update(self, identifier: str, payload: dict, *, kind: str) -> dict:
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE records SET payload=?,updated=? WHERE id=? AND kind=?",
                (json.dumps(payload, ensure_ascii=False), time.time(), identifier, kind))
            if cursor.rowcount != 1:
                raise NotFound("Projet ou mission introuvable.")
        return self.get(identifier, kind)

    def mutate(self, identifier: str, change, *, kind: str) -> dict:
        """Serialize a read-modify-write, preserving concurrent fields/attachments."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM records WHERE id=? AND kind=?",
                             (identifier, kind)).fetchone()
            if row is None:
                raise NotFound("Projet ou mission introuvable.")
            payload = change(json.loads(row["payload"]))
            db.execute("UPDATE records SET payload=?,updated=? WHERE id=? AND kind=?",
                       (json.dumps(payload, ensure_ascii=False, allow_nan=False), time.time(), identifier, kind))
        return self.get(identifier, kind)

    def find(self, kind: str, field: str, value: str) -> dict | None:
        if field not in {"prepared_id", "root"}:
            raise ValueError("Unsupported record lookup")
        with self.connect() as db:
            row = db.execute("SELECT id FROM records WHERE kind=? AND json_extract(payload,?)=?",
                             (kind, "$." + field, value)).fetchone()
        return self.get(row["id"], kind) if row else None

    def transition(self, identifier: str, expected: str, changes: dict, *, kind: str) -> bool:
        """Claim a lifecycle transition before any irreversible external action."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM records WHERE id=? AND kind=?",
                             (identifier, kind)).fetchone()
            if row is None:
                raise NotFound("Projet ou mission introuvable.")
            payload = json.loads(row["payload"])
            if payload.get("state") != expected:
                return False
            payload.update(changes)
            db.execute("UPDATE records SET payload=?,updated=? WHERE id=?",
                       (json.dumps(payload, ensure_ascii=False), time.time(), identifier))
            return True

    @staticmethod
    def payload(record: dict) -> dict:
        return {key: value for key, value in record.items()
                if key not in {"id", "kind", "created", "updated"}}
