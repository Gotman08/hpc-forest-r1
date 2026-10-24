"""Rebuildable memory projection. Only the controller writes measured evidence."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .core import canonical, digest
from .memory_contract import VERSION, enabled
from .source_diversity import source_evidence

SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_facts(
 id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, epoch INTEGER NOT NULL,
 protocol_id TEXT NOT NULL, tree_id TEXT NOT NULL, role TEXT NOT NULL,
 kind TEXT NOT NULL, created REAL NOT NULL, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS memory_scope ON memory_facts(epoch,protocol_id,tree_id,created);
CREATE INDEX IF NOT EXISTS memory_role ON memory_facts(epoch,protocol_id,role,kind,created);
CREATE TABLE IF NOT EXISTS memory_terms(
 term TEXT NOT NULL, fact_id TEXT NOT NULL REFERENCES memory_facts(id),
 PRIMARY KEY(term,fact_id));
CREATE TABLE IF NOT EXISTS memory_ingested(mission_id TEXT PRIMARY KEY, version TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS memory_generation_events ON events(json_extract(payload,'$.experiment_id'))
 WHERE kind='generation_usage';
"""


def terms(text):
    return sorted({v for v in re.findall(r"[\w-]+", text.casefold()) if len(v) > 2})[:400]


class MemoryStore:
    def __init__(self, db, root):
        self.db, self.root = db, Path(root)
        db.connection.executescript(SCHEMA)

    def _put(self, mission, protocol, created, key, kind, payload):
        payload = {"id": key, "schema": VERSION, "kind": kind, "epoch": mission["epoch"],
                   "protocol_id": protocol, "tree_id": mission["tree_id"], "role": mission["role"],
                   "mission_id": mission["id"], **payload}
        raw = canonical(payload)
        cursor = self.db.connection.execute("INSERT OR IGNORE INTO memory_facts VALUES(?,?,?,?,?,?,?,?,?)",
            (key, mission["id"], mission["epoch"], protocol, mission["tree_id"], mission["role"],
             kind, created, raw))
        if cursor.rowcount:
            self.db.connection.executemany("INSERT INTO memory_terms VALUES(?,?)",
                                          ((term, key) for term in terms(raw)))

    def ingest(self, row):
        if not row.get("result") or self.db.one(
                "SELECT 1 FROM memory_ingested WHERE mission_id=?", (row["id"],)):
            return
        mission, outcome = json.loads(row["mission"]), json.loads(row["result"])
        epoch = self.db.one("SELECT protocol_id FROM epochs WHERE id=?", (row["epoch"],))
        protocol = epoch["protocol_id"]
        journal = self.root / "logs" / row["id"] / "node-harness.json"
        attempts = json.loads(journal.read_text(encoding="utf8")).get("attempts", []) if journal.is_file() else []
        events = self.db.rows("SELECT payload FROM events WHERE kind='generation_usage' "
                             "AND json_extract(payload,'$.experiment_id')=? ORDER BY id", (row["id"],))
        usages = [json.loads(item["payload"]) for item in events]
        source_change = source_evidence(self.root, mission, outcome)
        with self.db.connection:
            self._put(mission, protocol, row["created"], row["id"], "experiment", {
                "facts": {"outcome": outcome, "commit": outcome.get("commit"),
                          "base_commit": mission["base_commit"], "parent_id": mission["parent_id"],
                          "delegation_parent": mission["delegation_parent"],
                          "source_ids": mission["sources"], "source_commits": mission["source_commits"],
                          "kind": mission.get("kind", "research"),
                          "base_source_id": mission.get("base_source_id"),
                          "control_decision_id": mission.get("control_decision_id"),
                          "advice_ids": mission.get("advice_ids", []),
                          "authorized_import_ids": mission.get("import_ids", []),
                          "source_change": source_change},
                "model_interpretation": {"hypothesis": mission["hypothesis"],
                                         "transformations": mission["transformations"]}})
            for attempt in attempts:
                if "development_outcome" not in attempt:
                    continue
                snapshot = journal.parent / f"harness-source-{attempt['attempt']:02d}.json"
                if not snapshot.is_file():
                    continue
                files = json.loads(snapshot.read_text(encoding="utf8"))
                self._put(mission, protocol, row["created"], attempt["generation_id"], "development", {
                    "facts": {"outcome": attempt["development_outcome"],
                              "source_snapshot": str(snapshot.relative_to(self.root)),
                              "source_digest": digest(files), "source_paths": list(files),
                              "parent_id": mission["parent_id"], "base_commit": mission["base_commit"]},
                    "model_interpretation": attempt.get("proposal", {})})
            for usage in usages:
                for call, item in enumerate(usage.get("attempt_usage") or [usage]):
                    for index, lesson in enumerate(item.get("memory_lessons", [])):
                        refs = lesson.get("evidence_ids", [])
                        # Defense in depth: no cross-protocol or cross-tree lesson laundering.
                        if not refs or any(ref not in mission.get("import_ids", []) and not self.db.one(
                            "SELECT 1 FROM memory_facts WHERE id=? AND epoch=? AND protocol_id=? "
                            "AND (?='G' OR tree_id=? OR tree_id='baseline')",
                            (ref, row["epoch"], protocol, row["role"], row["tree_id"]))
                            for ref in refs):
                            self.db.connection.execute("INSERT INTO events(kind,payload,created) VALUES(?,?,?)",
                                ("memory_lesson_rejected", canonical({"mission_id": row["id"], "lesson": lesson}), row["created"]))
                            continue
                        self._put(mission, protocol, row["created"], f"lesson:{row['id']}:{call}:{index}",
                                  "lesson", {"model_interpretation": lesson,
                                             "facts": {"authored_in": row["id"], "evidence_ids": refs}})
            self.db.connection.execute("INSERT INTO memory_ingested VALUES(?,?)", (row["id"], VERSION))

    def sync(self):
        for row in self.db.rows("SELECT e.*,v.payload FROM epochs e JOIN evaluations v "
                               "ON v.experiment_id=e.baseline_id AND v.phase='search'"):
            mission = {"id": row["baseline_id"], "tree_id": "baseline", "epoch": row["id"], "role": "baseline"}
            with self.db.connection:
                self._put(mission, row["protocol_id"], row["created"], row["baseline_id"], "experiment", {
                    "facts": {"outcome": json.loads(row["payload"]), "commit": row["base_commit"],
                              "base_commit": row["base_commit"], "parent_id": None,
                              "source_ids": [], "source_commits": []}, "model_interpretation": {}})
        # Restart recovery replays derived records, never generation or evaluation.
        rows = self.db.rows("SELECT t.* FROM trials t LEFT JOIN memory_ingested m ON m.mission_id=t.id "
                            "WHERE t.result IS NOT NULL AND m.mission_id IS NULL ORDER BY t.created,t.id")
        for row in rows:
            self.ingest(row)


def sync_memory(db, root):
    if enabled(db.get("config")):
        MemoryStore(db, root).sync()


def rebuild_memory(root):
    """Recreate derived memory under the campaign lock; never replay an experiment."""
    from .core import FileLock, ForestError
    from .registry import Registry

    root = Path(root).resolve(strict=True)
    with FileLock(root / "campaign.lock"):
        db = Registry(root / "registry.sqlite3")
        try:
            if not enabled(db.get("config")):
                raise ForestError("The frozen campaign has no memory projection")
            store = MemoryStore(db, root)
            with db.connection:
                db.connection.execute("DELETE FROM memory_terms")
                db.connection.execute("DELETE FROM memory_facts")
                db.connection.execute("DELETE FROM memory_ingested")
            store.sync()
            return memory_summary(db)
        finally:
            db.close()


def memory_summary(db):
    if not enabled(db.get("config")):
        return {"mode": "off"}
    exists = db.one("SELECT 1 FROM sqlite_master WHERE name='memory_facts'")
    return {"schema": VERSION, "mode": db.get("config")["memory"]["mode"],
            "records": db.rows("SELECT kind,count(*) AS count FROM memory_facts GROUP BY kind") if exists else [],
            "measurements_owned_by": "controller", "lessons_are": "model_interpretations"}
