"""Durable consultation receipts without growing the model's list of identifiers."""
from __future__ import annotations

from hpc_forest.core import InfrastructureError
from hpc_forest.memory.retrieval import evidence_ids

SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_consultations(
 epoch INTEGER NOT NULL, protocol_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
 evidence_id TEXT NOT NULL, PRIMARY KEY(epoch,protocol_id,conversation_id,evidence_id));
CREATE TABLE IF NOT EXISTS memory_topic_views(
 epoch INTEGER NOT NULL, protocol_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
 role TEXT NOT NULL, PRIMARY KEY(epoch,protocol_id,conversation_id,role));
"""


class Consultations:
    def __init__(self, db, epoch, protocol, conversation):
        if not conversation:
            raise InfrastructureError("Memory selection needs an identified Mother conversation")
        self.db = db
        self.scope = (epoch, protocol, conversation)
        db.connection.executescript(SCHEMA)

    def remember(self, page):
        ids = evidence_ids(page)
        # Validate before writing: a receipt never grants access to another campaign.
        for identity in ids:
            if not self.db.one("SELECT 1 FROM memory_facts WHERE epoch=? AND protocol_id=? AND id=?",
                               (*self.scope[:2], identity)):
                raise InfrastructureError("Cannot register unrelated memory evidence: " + identity)
        with self.db.connection:
            self.db.connection.executemany("INSERT OR IGNORE INTO memory_consultations VALUES(?,?,?,?)",
                                           ((*self.scope, identity) for identity in ids))
            self.db.connection.executemany("INSERT OR IGNORE INTO memory_topic_views VALUES(?,?,?,?)",
                ((*self.scope, item["role"]) for item in page.get("items", []) if "results" in item and "role" in item))

    def known(self):
        return {row["evidence_id"] for row in self.db.rows(
            "SELECT evidence_id FROM memory_consultations WHERE epoch=? AND protocol_id=? AND conversation_id=?",
            self.scope)}

    def coverage(self, total):
        viewed = self.db.one("SELECT count(*) AS n FROM memory_topic_views "
                            "WHERE epoch=? AND protocol_id=? AND conversation_id=?", self.scope)["n"]
        return {"total_topics": total, "summaries_seen": viewed, "summaries_unseen": max(0, total - viewed),
                "all_summaries_seen": viewed >= total, "all_variants_read": False}
