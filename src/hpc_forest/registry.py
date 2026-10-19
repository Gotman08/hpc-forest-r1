from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

from .core import BudgetExhausted, ForestError, canonical
from .support.budgets import search_deadline
from .support.validation import require_integer

SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS epochs(
 id INTEGER PRIMARY KEY, base_commit TEXT NOT NULL, protocol_id TEXT NOT NULL,
 baseline_id TEXT, created REAL NOT NULL, closed REAL);
CREATE TABLE IF NOT EXISTS trees(
 id TEXT PRIMARY KEY, epoch INTEGER NOT NULL REFERENCES epochs(id), role TEXT NOT NULL,
 checkpoint BLOB NOT NULL, sha256 TEXT NOT NULL, version TEXT NOT NULL,
 stopped INTEGER NOT NULL DEFAULT 0, UNIQUE(epoch,role));
CREATE TABLE IF NOT EXISTS slots(
 id TEXT PRIMARY KEY, phase TEXT NOT NULL, purpose TEXT NOT NULL,
 tokens_reserved INTEGER NOT NULL, tokens_used INTEGER NOT NULL DEFAULT 0,
 usage_known INTEGER NOT NULL DEFAULT 1, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS trials(
 id TEXT PRIMARY KEY, tree_id TEXT NOT NULL REFERENCES trees(id), trial_id TEXT NOT NULL,
 epoch INTEGER NOT NULL, role TEXT NOT NULL, slot_id TEXT NOT NULL REFERENCES slots(id),
 mission TEXT NOT NULL, before_state BLOB NOT NULL, state TEXT NOT NULL,
 result TEXT, created REAL NOT NULL, UNIQUE(tree_id,trial_id));
CREATE TABLE IF NOT EXISTS evaluations(
 id INTEGER PRIMARY KEY, experiment_id TEXT NOT NULL, epoch INTEGER NOT NULL,
 phase TEXT NOT NULL, cache_key TEXT, payload TEXT NOT NULL, created REAL NOT NULL,
 UNIQUE(experiment_id,phase));
CREATE INDEX IF NOT EXISTS evaluations_cache ON evaluations(cache_key,phase);
CREATE TABLE IF NOT EXISTS interactions(
 experiment_id TEXT PRIMARY KEY, sources TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(
 id INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS documents(
 id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL, version TEXT NOT NULL,
 preconditions TEXT NOT NULL, text TEXT NOT NULL, sha256 TEXT NOT NULL, created REAL NOT NULL);
"""


class Registry:
    def __init__(self, path: Path):
        self.path = path
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript(SCHEMA)

    def close(self):
        self.connection.close()

    def rows(self, sql: str, args=()) -> list[dict]:
        return [dict(r) for r in self.connection.execute(sql, args)]

    def one(self, sql: str, args=()) -> dict | None:
        row = self.connection.execute(sql, args).fetchone()
        return dict(row) if row is not None else None

    def set(self, key: str, value) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO metadata VALUES(?,?)", (key, canonical(value))
            )

    def get(self, key: str, default=None):
        row = self.one("SELECT value FROM metadata WHERE key=?", (key,))
        return json.loads(row["value"]) if row else default

    def event(self, kind: str, payload: dict) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO events(kind,payload,created) VALUES(?,?,?)",
                (kind, canonical(payload), time.time()),
            )

    def reserve(self, phase: str, purpose: str, tokens: int = 0) -> str:
        if phase not in {"search", "confirmation"}:
            raise ForestError("Unknown budget phase")
        require_integer(tokens, "reserved tokens")
        c = self.get("config")
        deadline = self.get("deadline")
        if phase == "search":
            deadline = search_deadline(deadline, c["budget"]["confirmation_seconds"])
        if time.time() >= deadline:
            raise BudgetExhausted("Campaign wall-clock limit reached (includes restarts)")
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            count = self.connection.execute(
                "SELECT count(*) FROM slots WHERE phase=?", (phase,)
            ).fetchone()[0]
            limit = c["budget"]["search_slots" if phase == "search" else "confirmation_slots"]
            if count >= limit:
                raise BudgetExhausted(f"{phase} slot limit reached: {count}/{limit}")
            used = self.connection.execute(
                "SELECT coalesce(sum(tokens_reserved+tokens_used),0) FROM slots"
            ).fetchone()[0]
            if used + tokens > c["budget"]["tokens"]:
                raise BudgetExhausted("Token admission budget exhausted")
            slot_id = uuid.uuid4().hex
            self.connection.execute(
                "INSERT INTO slots VALUES(?,?,?,?,?,?,?)",
                (slot_id, phase, purpose, tokens, 0, 1, time.time()),
            )
        return slot_id

    def settle_tokens(self, slot_id: str, used: int | None, *, upper_bound: bool = False) -> None:
        if upper_bound and (type(used) is not int or used < 0):
            raise ForestError("A bounded token charge requires a nonnegative integer ceiling")
        if used is not None:
            require_integer(used, "consumed tokens")
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE slots SET tokens_used=coalesce(?,tokens_reserved),tokens_reserved=0,"
                "usage_known=? WHERE id=?",
                (used, 2 if upper_bound else int(used is not None), slot_id),
            )
            if cursor.rowcount != 1:
                raise ForestError("Cannot settle an unknown budget slot")

    def evaluations(self, phase: str = "search", epoch: int | None = None) -> list[dict]:
        sql = "SELECT * FROM evaluations WHERE phase=?"
        args: list = [phase]
        if epoch is not None:
            sql += " AND epoch=?"
            args.append(epoch)
        return [{**r, "outcome": json.loads(r["payload"])} for r in self.rows(sql, args)]

    def record_evaluation(self, experiment: str, epoch: int, phase: str, outcome: dict) -> bool:
        with self.connection:
            cursor = self.connection.execute(
                "INSERT OR IGNORE INTO evaluations(experiment_id,epoch,phase,cache_key,payload,created)"
                " VALUES(?,?,?,?,?,?)",
                (
                    experiment,
                    epoch,
                    phase,
                    outcome.get("cache_key"),
                    canonical(outcome),
                    time.time(),
                ),
            )
            return cursor.rowcount == 1

    def cached(self, cache_key: str) -> dict | None:
        row = self.one(
            "SELECT experiment_id,payload FROM evaluations WHERE cache_key=? AND phase='search'",
            (cache_key,),
        )
        return (
            {"experiment_id": row["experiment_id"], **json.loads(row["payload"])} if row else None
        )

    def archive(self, epoch: int, role: str | None = None) -> list[dict]:
        results = []
        for row in self.rows("SELECT * FROM trials WHERE epoch=? AND state='completed'", (epoch,)):
            outcome = json.loads(row["result"])
            mission = json.loads(row["mission"])
            if outcome["correct"] is True and outcome["mean_seconds"] is not None:
                if role is None or mission["role"] == role:
                    results.append({**mission, **outcome})
        # Keep all distinct valid alternatives, not only the winner of each role.
        return sorted(results, key=lambda r: r["mean_seconds"])

    def costs(self) -> dict:
        return self.one(
            "SELECT count(*) AS slots,coalesce(sum(tokens_used),0) AS tokens_used,"
            "coalesce(sum(tokens_reserved),0) AS tokens_reserved,"
            "coalesce(sum(CASE WHEN usage_known=0 THEN 1 ELSE 0 END),0) AS unknown_usage_calls,"
            "coalesce(sum(CASE WHEN usage_known=2 THEN 1 ELSE 0 END),0) AS bounded_usage_calls,"
            "coalesce(sum(CASE WHEN usage_known=1 THEN tokens_used ELSE 0 END),0) AS exact_tokens_used FROM slots"
        )
