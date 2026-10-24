from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

from .adaptive_budget import admission_deadline, forecast
from .core import BudgetExhausted, ForestError, canonical
from .forest import forest_plan, model_selected, pairwise_mother, research_roles
from .memory_contract import guided
from .support.budgets import (
    adaptive,
    expired,
    finish_started,
    mandatory_final_g,
    postprocess_token_limit,
    unlimited_tokens,
)
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
 usage_known INTEGER NOT NULL DEFAULT 1, created REAL NOT NULL,
 tokens_settled INTEGER NOT NULL DEFAULT 0 CHECK(tokens_settled IN (0,1)));
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
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(slots)")}
            if "tokens_settled" not in columns:
                self.connection.execute(
                    "ALTER TABLE slots ADD COLUMN tokens_settled INTEGER NOT NULL DEFAULT 0"
                )
                # Old model reservations are positive until settled. Preserve their existing
                # exact/unknown charges, including exact zero, without rewriting historical use.
                self.connection.execute(
                    "UPDATE slots SET tokens_settled=1 WHERE tokens_reserved=0"
                )

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

    def reserve(self, phase: str, purpose: str, tokens: int = 0, *, continuation_of: str | None = None) -> str:
        if phase not in {"search", "confirmation", "postprocess"}:
            raise ForestError("Unknown budget phase")
        require_integer(tokens, "reserved tokens")
        c = self.get("config")
        if unlimited_tokens(c):
            tokens = 0  # Usage is recorded after execution; no token admission reservation.
        deadline = self.get("deadline")
        soft = finish_started(c)
        scope = ""
        if phase == "postprocess":
            if not soft:
                raise ForestError("Postprocessing requires an explicit finish-started policy")
            scope = f"postprocess:e{self.get('current_epoch', 1)}:"
            if not purpose.startswith(scope):
                raise ForestError("Postprocessing reservations must identify their epoch")
            deadline = None
        elif phase == "confirmation" and soft:
            if mandatory_final_g(c):
                scope = f"confirmation:e{self.get('current_epoch', 1)}:"
                if not purpose.startswith(scope):
                    raise ForestError("Confirmation reservations must identify their epoch")
            deadline = self.get(f"confirmation_deadline:{self.get('current_epoch', 1)}")
            if deadline is None and not (mandatory_final_g(c) and self.get(
                    f"confirmation_started:{self.get('current_epoch', 1)}") is not None):
                raise ForestError("Start the independent confirmation window before reserving it")
        if phase == "search":
            continuation = None
            if continuation_of is not None:
                continuation = self.one(
                    "SELECT id FROM trials WHERE id=? AND epoch=? AND state='pending'",
                    (continuation_of, self.get("current_epoch")),
                )
                if not (soft and adaptive(c) and purpose.startswith("mother:") and continuation):
                    raise ForestError("Only an admitted pending node can continue its Mother call")
            if soft and not continuation and self.get(f"search_closed:{self.get('current_epoch', 1)}") is not None:
                raise BudgetExhausted("Search admission is permanently closed for this epoch")
            if continuation:
                deadline = None
            elif (purpose == "mother:preparation" and model_selected(c) and not forest_plan(self)):
                pass  # Initial Mother commits its first complete N-tree pass within the target window.
            elif purpose != "baseline" or not adaptive(c):
                deadline = admission_deadline(self)
        if expired(deadline):
            raise BudgetExhausted("Campaign wall-clock limit reached (includes restarts)")
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            count = self.connection.execute(
                "SELECT count(*) FROM slots WHERE phase=? AND purpose LIKE ?", (phase, scope + "%")
            ).fetchone()[0]
            limit = 2 if phase == "postprocess" else c["budget"][
                "search_slots" if phase == "search" else "confirmation_slots"]
            if phase == "postprocess" and pairwise_mother(c):
                limit = max(1, len(research_roles(self)) - 1)
                expected = f"{scope}merge:{count + 1}"
                if purpose != expected:
                    raise ForestError("Pairwise integration reservations must follow their recorded sequence")
            if phase == "postprocess" and guided(c):
                from .integration_policy import limits

                bounds = limits(c, len(research_roles(self)))
                limit = bounds["postprocess_slots"]
                allowed = {f"{scope}memory:code:{number}" for number in range(1, bounds["rounds"] + 1)}
                allowed.update(f"{scope}memory:select:{number}:{turn}"
                    for number in range(1, bounds["rounds"] + 1)
                    for turn in range(1, bounds["selection_calls_per_round"] + 1))
                if purpose not in allowed or self.connection.execute(
                        "SELECT 1 FROM slots WHERE purpose=?", (purpose,)).fetchone():
                    raise ForestError("Memory integration reservation is outside its frozen bounds or already claimed")
            if phase == "confirmation" and mandatory_final_g(c):
                limit += int(self.get(f"confirmation_extra_slot:{self.get('current_epoch', 1)}", False))
            if limit is not None and count >= limit:
                raise BudgetExhausted(f"{phase} slot limit reached: {count}/{limit}")
            condition = "phase='postprocess' AND purpose LIKE ?" if phase == "postprocess" else "phase<>'postprocess'"
            args = (scope + "%",) if phase == "postprocess" else ()
            used = self.connection.execute(
                "SELECT coalesce(sum(tokens_reserved+tokens_used),0) FROM slots WHERE " + condition,
                args,
            ).fetchone()[0]
            token_limit = postprocess_token_limit(c) if phase == "postprocess" else c["budget"]["tokens"]
            if (not unlimited_tokens(c) and token_limit is not None and used + tokens > token_limit
                    and not (soft and phase == "confirmation" and tokens == 0)):
                raise BudgetExhausted("Token admission budget exhausted")
            if not unlimited_tokens(c) and soft and phase == "search" and self.connection.execute(
                "SELECT count(*) FROM slots WHERE phase='search' AND usage_known=0"
            ).fetchone()[0]:
                raise BudgetExhausted("Unknown previous search usage; no new child can be admitted")
            slot_id = uuid.uuid4().hex
            admitted_at = time.time()
            if expired(deadline, now=admitted_at):
                raise BudgetExhausted("Admission window closed while waiting for the registry")
            self.connection.execute(
                "INSERT INTO slots(id,phase,purpose,tokens_reserved,created) VALUES(?,?,?,?,?)",
                (slot_id, phase, purpose, tokens, admitted_at),
            )
        return slot_id

    def reserve_research_wave(self, roles: list[str], cursor: int) -> dict[str, str]:
        """Admit all N trees together. The first pass continues admitted Mother planning."""
        config, epoch = self.get("config"), self.get("current_epoch")
        plan = forest_plan(self)
        if (not model_selected(config) or not adaptive(config) or not unlimited_tokens(config)
                or config["budget"]["search_slots"] is not None or not plan
                or roles != research_roles(self)):
            raise ForestError("A research wave must contain exactly Mother's N recorded trees")
        key = f"forest_wave:{epoch}:{cursor}"
        previous = self.get(key)
        if previous is not None:
            for slot in previous["slots"].values():
                if not self.one("SELECT id FROM trials WHERE slot_id=?", (slot,)):
                    self.settle_tokens(slot, 0)  # No trial was created, so no generation was invoked.
            raise ForestError("An interrupted research wave cannot replay its model invocations")
        if self.get(f"search_closed:{epoch}") is not None:
            raise BudgetExhausted("Search admission is permanently closed")
        first = cursor == 0
        if first:
            parent = self.one("SELECT * FROM slots WHERE id=?", (plan["mother_slot_id"],))
            if not parent or parent["phase"] != "search" or parent["purpose"] != "mother:preparation":
                raise ForestError("The first research pass needs its admitted Mother planning receipt")
        decision = forecast(self, roles)
        decision["first_wave_continues_mother"] = first
        if first:
            decision["can_admit"] = True
        self.set(f"adaptive_budget:{epoch}", decision)
        self.event("adaptive_admission", decision)
        if not decision["can_admit"]:
            raise BudgetExhausted("Remaining time reserved for final Mother, G and confirmation")
        created = time.time()
        slots = {role: uuid.uuid4().hex for role in roles}
        record = {"roles": roles, "slots": slots, "admitted_at": created,
                  "parent_mother_slot": plan["mother_slot_id"] if first else None}
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            self.connection.executemany(
                "INSERT INTO slots(id,phase,purpose,tokens_reserved,created) VALUES(?,'search',?,0,?)",
                [(slot, "role:" + role, created) for role, slot in slots.items()])
            self.connection.execute("INSERT INTO metadata VALUES(?,?)", (key, canonical(record)))
        return slots

    def settle_tokens(self, slot_id: str, used: int | None, *, upper_bound: bool = False,
                      observed_tokens: int = 0) -> None:
        if upper_bound and (type(used) is not int or used < 0):
            raise ForestError("A bounded token charge requires a nonnegative integer ceiling")
        if used is not None:
            require_integer(used, "consumed tokens")
        require_integer(observed_tokens, "observed tokens")
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE slots SET "
                "tokens_used=CASE WHEN ? IS NOT NULL THEN ? "
                "WHEN tokens_settled=1 THEN tokens_used ELSE max(tokens_reserved,?) END,"
                "usage_known=CASE WHEN ? IS NOT NULL THEN ? "
                "WHEN tokens_settled=1 THEN usage_known ELSE 0 END,"
                "tokens_reserved=0,tokens_settled=1 WHERE id=?",
                (
                    used,
                    used,
                    observed_tokens,
                    used,
                    2 if upper_bound else 1,
                    slot_id,
                ),
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

    def costs(self, phase: str | None = None, *, purpose_prefix: str | None = None) -> dict:
        filters, args = [], []
        if phase is not None:
            filters.append("phase=?")
            args.append(phase)
        if purpose_prefix is not None:
            filters.append("purpose LIKE ?")
            args.append(purpose_prefix + "%")
        return self.one(
            "SELECT count(*) AS slots,coalesce(sum(tokens_used),0) AS tokens_used,"
            "coalesce(sum(tokens_reserved),0) AS tokens_reserved,"
            "coalesce(sum(CASE WHEN usage_known=0 THEN 1 ELSE 0 END),0) AS unknown_usage_calls,"
            "coalesce(sum(CASE WHEN usage_known=2 THEN 1 ELSE 0 END),0) AS bounded_usage_calls,"
            "coalesce(sum(CASE WHEN usage_known=1 THEN tokens_used ELSE 0 END),0) AS exact_tokens_used FROM slots"
            + (" WHERE " + " AND ".join(filters) if filters else ""),
            args,
        )
