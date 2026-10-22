"""Scoped, read-only retrieval with exact source versions and explicit pagination."""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from pathlib import Path

from .core import CandidateRejected, InfrastructureError, canonical, digest
from .memory_contract import VERSION, settings, validate_read
from .memory_overview import tree_overview
from .memory_store import terms
from .support.sources import committed_source_snapshot, source_snapshot


def text_digest(content):
    return hashlib.sha256(content.encode("utf8")).hexdigest()


def card(record):
    """Small evidence card; never rank an idea solely by its standalone runtime."""
    facts = record.get("facts", {})
    outcome = facts.get("outcome", {})
    interpretation = record.get("model_interpretation", {})
    return {key: record[key] for key in ("id", "kind", "role", "tree_id", "mission_id")} | {
        "facts": {key: facts.get(key) for key in ("commit", "base_commit", "parent_id")} | {
            "source_ids": (facts.get("source_ids") or [])[:6],
            "source_count": len(facts.get("source_ids") or [])},
        "measured_outcome": {key: outcome.get(key) for key in ("status", "correct", "mean_seconds", "score")},
        "diagnostic": str(outcome.get("reason") or "")[:500],
        "model_interpretation": {
            "claim": str(interpretation.get("claim") or interpretation.get("hypothesis") or "")[:1200],
            "transformations": canonical(interpretation.get("transformations", {}))[:1000],
            "applicability": str(interpretation.get("applicability", ""))[:600],
            "next_experiment": str(interpretation.get("next_experiment", ""))[:600],
            "evidence_ids": interpretation.get("evidence_ids", []),
        },
        "source_available": bool(facts.get("commit") or facts.get("source_snapshot")),
        "details_are_bounded": True,
    }


def bounded_page(items, *, offset, total, maximum):
    result = {"schema": VERSION, "items": [], "offset": offset, "total": total, "next_offset": None}
    for item in items:
        if "model_interpretation" in item:
            item = copy.deepcopy(item)
            while len(canonical({**result, "items": [item]})) > maximum - 120:
                before = canonical(item)
                fields = item["model_interpretation"]
                for key, value in fields.items():
                    if isinstance(value, str):
                        fields[key] = value[:len(value) // 2]
                item["diagnostic"] = item.get("diagnostic", "")[:len(item.get("diagnostic", "")) // 2]
                if canonical(item) == before:
                    raise InfrastructureError("Memory evidence identity exceeds the context allowance")
        proposed = {**result, "items": [*result["items"], item]}
        if len(canonical(proposed)) > maximum - 120:
            break
        result = proposed
    following = offset + len(result["items"])
    result["next_offset"] = following if following < total else None
    if items and not result["items"]:
        raise InfrastructureError("A memory card cannot fit the configured context allowance")
    return result


class MemoryReader:
    def __init__(self, root, mission, config, protocol_id):
        self.root, self.mission = Path(root), mission
        self.cfg, self.protocol = settings(config), protocol_id
        self.connection = sqlite3.connect((self.root / "registry.sqlite3").as_uri() + "?mode=ro", uri=True)
        self.connection.row_factory = sqlite3.Row
        self.scope = "epoch=? AND protocol_id=?"
        self.args = [mission.epoch, protocol_id]
        if mission.role != "G":
            self.scope += " AND (tree_id=? OR tree_id='baseline')"
            self.args.append(mission.tree_id)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.connection.close()

    def exact(self, identity):
        row = self.connection.execute("SELECT payload FROM memory_facts WHERE " + self.scope + " AND id=?",
                                      [*self.args, identity]).fetchone()
        if not row:
            raise CandidateRejected("Unknown, unrelated or unavailable memory evidence: " + identity)
        return json.loads(row["payload"])

    def search(self, query="", offset=0):
        words = terms(query)[:16]
        rank = "0 AS relevance"
        rank_args = []
        if words:
            rank = ("(SELECT count(*) FROM memory_terms t WHERE t.fact_id=f.id AND t.term IN ("
                    + ",".join("?" for _ in words) + ")) AS relevance")
            rank_args = words
        # Round-robin rows within roles provide diversity without loading N programs.
        sql = ("SELECT *,row_number() OVER(PARTITION BY role ORDER BY relevance DESC,created DESC,id) AS turn "
               "FROM (SELECT f.*," + rank + " FROM memory_facts f WHERE " + self.scope + ") "
               "ORDER BY relevance DESC,turn,role,id LIMIT ? OFFSET ?")
        rows = self.connection.execute(sql, [*rank_args, *self.args, self.cfg["page_size"], offset]).fetchall()
        total = self.connection.execute("SELECT count(*) FROM memory_facts WHERE " + self.scope, self.args).fetchone()[0]
        return bounded_page([card(json.loads(row["payload"])) for row in rows], offset=offset,
                            total=total, maximum=self.cfg["context_characters"])

    def catalog(self, offset=0):
        row = self.connection.execute("SELECT value FROM metadata WHERE key=?",
                                      (f"forest_plan:{self.mission.epoch}",)).fetchone()
        children = json.loads(row["value"])["children"] if row else []
        if self.mission.role != "G":
            children = [item for item in children if item["role"] == self.mission.role]
        items = [{"role": child["role"], "subject": child["subject"][:600],
                  "objective": child["objective"][:1200],
                  **tree_overview(self.connection, self.scope, self.args, child["role"]),
                  "text_truncated": len(child["subject"]) > 600 or len(child["objective"]) > 1200}
                 for child in children[offset:offset + self.cfg["page_size"]]]
        # Preserve numerical facts/IDs. Smaller pages beat truncating evidence identities.
        per_item = max(1600, (self.cfg["context_characters"] - 200) // self.cfg["page_size"])
        for item in items:
            while len(canonical(item)) > per_item:
                before = canonical(item)
                item["subject"] = item["subject"][:len(item["subject"]) // 2]
                item["objective"] = item["objective"][:len(item["objective"]) // 2]
                for key in ("best", "latest", "alternative"):
                    if item[key]:
                        text = item[key]["hypothesis_as_data"]
                        item[key]["hypothesis_as_data"] = text[:len(text) // 2]
                item["text_truncated"] = True
                if canonical(item) == before:
                    raise InfrastructureError("Memory topic identity exceeds the context allowance")
        return bounded_page(items, offset=offset, total=len(children), maximum=self.cfg["context_characters"])

    def source(self, identity, path, offset):
        if identity == "current":
            files = source_snapshot(Path(self.mission.worktree))
            provenance = {"base_commit": self.mission.base_commit, "snapshot_digest": digest(files)}
        else:
            record = self.exact(identity)
            facts = record.get("facts", {})
            if facts.get("commit"):
                files = committed_source_snapshot(self.root / "repo", facts["commit"])
                provenance = {"commit": facts["commit"], "snapshot_digest": digest(files)}
            elif facts.get("source_snapshot"):
                snapshot = (self.root / facts["source_snapshot"]).resolve()
                if not snapshot.is_relative_to(self.root.resolve()):
                    raise InfrastructureError("Invalid memory snapshot path")
                files = json.loads(snapshot.read_text(encoding="utf8"))
                if digest(files) != facts["source_digest"]:
                    raise InfrastructureError("Memory source snapshot changed")
                provenance = {"snapshot_digest": facts["source_digest"], "development_only": True}
            else:
                raise CandidateRejected("This evidence has no source artifact")
        result = {"schema": VERSION, "id": identity, **provenance, "offset_unit": "characters"}
        if not path:
            items = [{"path": name, "characters": len(content), "sha256": text_digest(content)}
                     for name, content in sorted(files.items())]
            return {**result, **bounded_page(items[offset:offset + self.cfg["page_size"]], offset=offset,
                                             total=len(items), maximum=self.cfg["context_characters"] - 600)}
        if path not in files:
            raise CandidateRejected("Unknown source path in this exact version")
        # JSON escaping can expand characters; size the serialized result, not just the text.
        content = files[path]
        length = min(len(content) - min(offset, len(content)), self.cfg["context_characters"] - 800)
        while True:
            following = offset + length
            page = {**result, "path": path, "file_sha256": text_digest(content), "total_characters": len(content),
                    "text": content[offset:following], "next_offset": following if following < len(content) else None}
            if len(canonical(page)) <= self.cfg["context_characters"]:
                return page
            length //= 2

    def read(self, request):
        validate_read(request)
        operation, offset = request["operation"], request["offset"]
        if operation == "search":
            return self.search(request["query"], offset)
        if operation == "catalog":
            return self.catalog(offset)
        if operation == "source":
            return self.source(request["ids"][0], request["path"], offset)
        if operation == "read":
            records = [card(self.exact(identity)) for identity in request["ids"]]
            return bounded_page(records[offset:], offset=offset, total=len(records),
                                maximum=self.cfg["context_characters"])
        raise CandidateRejected("No memory operation requested")


def evidence_ids(page):
    ids = [item["id"] for item in page.get("items", []) if "id" in item]
    for item in page.get("items", []):
        for key in ("best", "latest", "alternative"):
            if item.get(key):
                ids.append(item[key]["id"])
    if page.get("id") not in {None, "current"}:
        ids.append(page["id"])
    return list(dict.fromkeys(ids))
