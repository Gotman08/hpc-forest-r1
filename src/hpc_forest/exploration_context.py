"""Bounded, scoped source evidence for varied proposals; no parent selection."""
from __future__ import annotations

import json

from .active_analysis import source_excerpts
from .core import ForestError, digest
from .support.sources import committed_source_snapshot

VERSION = "forest-exploration-context-v1"
SOURCE_CHARACTERS = 6000


def source_context(controller, mission, archive):
    """Expose archived mechanisms and recent attempts without changing the base."""
    rows = controller.db.rows(
        "SELECT id,mission,result FROM trials WHERE epoch=? AND role=? AND state<>'pending' "
        "ORDER BY created DESC,id DESC LIMIT 6", (mission.epoch, mission.role))
    recent = []
    for row in rows:
        previous, outcome = json.loads(row["mission"]), json.loads(row["result"] or "{}")
        recent.append({"id": row["id"], "parent_id": previous.get("parent_id"),
                       "hypothesis_as_interpretation": previous.get("hypothesis", "")[:400],
                       "status": outcome.get("status"), "correct": outcome.get("correct"),
                       "mean_seconds": outcome.get("mean_seconds"), "score": outcome.get("score")})
    base = getattr(mission, "base_commit", None)
    eligible = [e for e in archive["entries"] if e["commit"] != base]
    pages, missing = [], []
    allowance = SOURCE_CHARACTERS // max(1, len(eligible))
    for entry in eligible:
        root = getattr(controller, "root", None)
        try:
            if root is None:
                raise ForestError("Campaign source repository unavailable")
            files = committed_source_snapshot(root / "repo", entry["commit"])
            if digest(files) != entry["source_sha256"]:
                raise ForestError("Archived source fingerprint does not match committed files")
            record = {"id": entry["id"], "outcome": {"commit": entry["commit"]}, "source_files": files}
            paths = sorted(files)[:2]
            for path in paths:
                pages.extend(source_excerpts(record, path, allowance // len(paths)))
        except (ForestError, OSError, ValueError) as exc:
            missing.append({"id": entry["id"], "reason": str(exc)[:240]})
    parent = getattr(mission, "parent_id", None)
    return {"schema": VERSION, "selected_parent_id": parent, "base_commit": base,
            "intent": "refine_selected_parent" if parent else "explore_from_assigned_base",
            "recent_attempts": recent, "source_excerpts": pages, "unavailable_sources": missing,
            "rule": "TreeQuest selected the unchanged base and parent. These scoped sources are "
                    "inspiration, not extra parents or evaluations. Lexical difference does not prove "
                    "algorithmic novelty. Missing lines remain accessible through authorized memory reads."}


def summarize(records):
    """Program identity is exact source text, not a renamed hypothesis or commit."""
    settled = [r for r in records if r["kind"] == "trial"]
    correct = [r for r in settled if r["outcome"].get("correct") is True and r.get("source_files")]
    return {"settled_trials": len(settled),
            "correct_source_variants": len({digest(r["source_files"]) for r in correct}),
            "parent_sources": len({(r.get("mission") or {}).get("parent_id")
                                   or (r.get("mission") or {}).get("base_commit") for r in settled}),
            "root_expansions": sum(not (r.get("mission") or {}).get("parent_id") for r in settled),
            "interpretation": "Exact source variants and parent identities; not semantic strategy counts."}
