"""Shared per-campaign reference snapshots, passage retrieval and access receipts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .core import FileLock, InfrastructureError
from .documentation_fetch import (
    CATALOGUE,
    CATALOGUE_SHA256,
    SOURCES,
    fetch_document,
    official_url,
    source_version,
)


class DocumentationStore:
    def __init__(self, root: Path, session_id: str):
        self.root, self.session_id = root.resolve(), session_id
        (self.root / "objects").mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS binding(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documents(
                    url TEXT PRIMARY KEY, source_id TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS document_source ON documents(source_id);
                CREATE TABLE IF NOT EXISTS accesses(
                    id TEXT PRIMARY KEY, request_id TEXT, time REAL, action TEXT, payload TEXT);
            """)
            for key, value in {"session_id": session_id, "catalogue_sha256": CATALOGUE_SHA256}.items():
                db.execute("INSERT OR IGNORE INTO binding VALUES(?,?)", (key, value))
                if db.execute("SELECT value FROM binding WHERE key=?", (key,)).fetchone()[0] != value:
                    raise ValueError("The documentation campaign or official catalogue changed")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.root / "index.sqlite3", timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def audit(self, request_id: str, action: str, payload: dict):
        with self.connection() as db:
            db.execute("INSERT INTO accesses VALUES(?,?,?,?,?)", (
                uuid.uuid4().hex, request_id, time.time(), action, json.dumps(payload, ensure_ascii=False)))

    @staticmethod
    def metadata(document: dict) -> dict:
        return {key: document[key] for key in (
            "url", "resolved_url", "source_id", "title", "version", "media_type", "raw_sha256",
            "text_sha256", "retrieved_at", "pdf_pages",
        )} | {"evidence_type": "untrusted_official_documentation"}

    def catalogue(self) -> dict:
        with self.connection() as db:
            cached = db.execute("SELECT count(*) FROM documents").fetchone()[0]
        return {**CATALOGUE, "catalogue_sha256": CATALOGUE_SHA256, "cached_documents": cached,
                "romeo_documentation": "Use the existing romeo MCP search_docs/read_doc",
                "version_policy": "Choose the release matching the frozen target, compiler and libraries; "
                    "current publisher pages may describe a development release. "
                    "A URL's first successful snapshot is shared unchanged for this campaign.",
                "formats": ["HTML", "PDF", "XML", "plain text"], "read_only": True,
                "queries_leave_client": False}

    def _cached(self, url: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT payload FROM documents WHERE url=?", (url,)).fetchone()
        if row is None:
            return None
        document = json.loads(row[0])
        if hashlib.sha256(document["text"].encode()).hexdigest() != document["text_sha256"]:
            raise ValueError("Cached documentation text changed")
        return document

    def document(self, url: str) -> dict:
        url, source_id = official_url(url)
        if (cached := self._cached(url)) is not None:
            return cached
        # A model pool may request the same large PDF together. Share its first
        # download and extraction, while unrelated URLs remain concurrent.
        lock = FileLock(self.root / "fetch-locks" / (hashlib.sha256(url.encode()).hexdigest() + ".lock"))
        deadline = time.monotonic() + 150
        while True:
            try:
                lock.__enter__()
                break
            except InfrastructureError as exc:
                if not str(exc).startswith("Resource already locked:"):
                    raise
                if (cached := self._cached(url)) is not None:
                    return cached
                if time.monotonic() >= deadline:
                    raise TimeoutError("Waiting for the shared documentation fetch timed out") from exc
                time.sleep(0.05)
        try:
            if (cached := self._cached(url)) is not None:
                return cached
            return self._fetch(url, source_id)
        finally:
            lock.__exit__(None, None, None)

    def _fetch(self, url: str, source_id: str) -> dict:
        document = fetch_document(url)
        raw = document.pop("raw")
        if (document["url"] != url or document["source_id"] != source_id
                or hashlib.sha256(raw).hexdigest() != document["raw_sha256"]):
            raise ValueError("Invalid documentation fetch receipt")
        document["title"] = document["title"] or SOURCES[source_id]["title"]
        document["version"] = source_version(document["resolved_url"], document["title"] + "\n" + document["text"])
        target = self.root / "objects" / (document["raw_sha256"] + ".bin")
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
        try:
            os.replace(temporary, target)
            with self.connection() as db:
                # Concurrent fetches always return the first committed snapshot,
                # so Mother and the children cannot use different URL revisions.
                db.execute("INSERT OR IGNORE INTO documents VALUES(?,?,?)", (
                    url, source_id, json.dumps(document, ensure_ascii=False)))
        finally:
            temporary.unlink(missing_ok=True)
        return self._cached(url)

    def read(self, url: str, start_line: int = 1, line_count: int = 80) -> dict:
        if type(start_line) is not int or start_line < 1 or type(line_count) is not int or not 1 <= line_count <= 200:
            raise ValueError("Use a positive start_line and 1..200 lines per read")
        document = self.document(url)
        lines = document["text"].splitlines()
        selected, characters = [], 0
        for line in lines[start_line - 1:start_line - 1 + line_count]:
            # Split exceptionally long publisher lines into readable units during
            # extraction, so pagination can always advance without losing text.
            if selected and characters + len(line) > 16000:
                break
            selected.append(line)
            characters += len(line)
        next_line = start_line + len(selected)
        return {**self.metadata(document), "start_line": start_line, "total_lines": len(lines),
                "text": "\n".join(selected), "next_line": next_line if next_line <= len(lines) else None,
                "links": document["links"][:40]}

    @staticmethod
    def _terms(query: str) -> set[str]:
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            raise ValueError("Expected a documentation query of 1..1000 characters")
        return {term for term in re.findall(r"[\w]+", query.casefold()) if len(term) >= 2}

    def search(self, query: str, source_id: str, max_results: int = 5) -> dict:
        terms = self._terms(query)
        if source_id not in SOURCES or type(max_results) is not int or not 1 <= max_results <= 8:
            raise ValueError("Choose a source_id from documentation_catalog and 1..8 results")
        errors, links, seen = [], {}, set()
        for url in SOURCES[source_id]["roots"]:
            try:
                document = self.document(url)
                for link in document["links"]:
                    label = (link["title"] + " " + link["url"]).casefold()
                    relevance = sum(term in label for term in terms)
                    if relevance:
                        links[link["url"]] = max(links.get(link["url"], 0), relevance)
            except (OSError, ValueError, LookupError, ImportError) as exc:
                errors.append({"url": url, "error": str(exc)[:300]})
            seen.add(url)
        for url, _ in sorted(links.items(), key=lambda pair: (-pair[1], pair[0]))[:3]:
            if url in seen:
                continue
            try:
                self.document(url)
            except (OSError, ValueError, LookupError, ImportError) as exc:
                errors.append({"url": url, "error": str(exc)[:300]})
        with self.connection() as db:
            rows = db.execute("SELECT payload FROM documents WHERE source_id=? ORDER BY url", (source_id,)).fetchall()
        hits = []
        for row in rows:
            document = json.loads(row[0])
            if hashlib.sha256(document["text"].encode()).hexdigest() != document["text_sha256"]:
                raise ValueError("Cached documentation text changed")
            lines = document["text"].splitlines()
            positions = []
            for number, line in enumerate(lines):
                relevance = sum(term in line.casefold() for term in terms)
                if relevance:
                    positions.append((relevance, number))
            selected = []
            for relevance, number in sorted(positions, key=lambda pair: (-pair[0], pair[1])):
                if any(abs(number - old) < 16 for old in selected):
                    continue
                start = max(0, number - 3)
                hits.append({**self.metadata(document), "start_line": start + 1,
                             "excerpt": "\n".join(lines[start:start + 16])[:3500], "relevance": relevance})
                selected.append(number)
                if len(selected) == max_results:
                    break
        return {"query": query, "source_id": source_id, "catalogue_sha256": CATALOGUE_SHA256,
                "results": sorted(hits, key=lambda hit: (-hit["relevance"], hit["url"], hit["start_line"]))[:max_results],
                "errors": errors, "scope": "cached references plus up to three matching official links",
                "complete_web_search": False}
