"""ShinkaEvolve-inspired diversity archive with measured eligibility and scoped reuse.

Lexical sketches are hints, never semantic equivalence tests or performance rewards.
No extra model, embedding service, automatic rejection or synthetic observation.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import math
import re

from .core import ForestError, digest
from .support.sources import committed_source_snapshot


def settings(config):
    value = config.get("evolution", {})
    if not isinstance(value, dict) or set(value) - {"enabled", "archive_size", "inspirations"}:
        raise ForestError("Invalid evolution archive settings")
    result = {"enabled": False, "archive_size": 12, "inspirations": 3, **value}
    if type(result["enabled"]) is not bool:
        raise ForestError("evolution.enabled must be boolean")
    for name, low, high in (("archive_size", 2, 32), ("inspirations", 1, 5)):
        if type(result[name]) is not int or not low <= result[name] <= high:
            raise ForestError(f"evolution.{name} must be between {low} and {high}")
    if result["inspirations"] > result["archive_size"]:
        raise ForestError("Archive must contain at least as many entries as inspirations")
    return result


def fingerprint(files):
    tokens = re.findall(r"\w+|[^\w\s]", "\n".join(files[name] for name in sorted(files)))
    grams = ("\x1f".join(tokens[i:i + 5]).encode() for i in range(max(1, len(tokens) - 4)))
    hashes = {hashlib.blake2b(gram, digest_size=8).hexdigest() for gram in grams}
    return {"source_sha256": digest(files), "sketch": heapq.nsmallest(128, hashes),
            "source_paths": sorted(files), "tokens": len(tokens)}


def distance(left, right):
    a, b = set(left["sketch"]), set(right["sketch"])
    return 1 - len(a & b) / len(a | b) if a or b else 0.0


def select(entries, maximum):
    """Keep the measured champion, then distant correct code, with speed as a tie-break."""
    ordered = sorted(entries, key=lambda e: (e["mean_seconds"], e["id"]))
    unique = {}
    for entry in ordered:
        unique.setdefault(entry["source_sha256"], entry)
    remaining = list(unique.values())
    if not remaining:
        return []
    chosen = [remaining.pop(0)]
    while remaining and len(chosen) < maximum:
        best = max(remaining, key=lambda e: (
            min(distance(e, retained) for retained in chosen), -e["mean_seconds"]))
        chosen.append(best)
        remaining.remove(best)
    return chosen


def record(controller, mission, outcome):
    cfg = settings(controller.config)
    if (not cfg["enabled"] or outcome.status != "valid" or outcome.correct is not True
            or outcome.score is None or not outcome.commit or not outcome.mean_seconds
            or not math.isfinite(outcome.mean_seconds) or outcome.mean_seconds <= 0):
        return
    try:
        profile = fingerprint(committed_source_snapshot(controller.root / "repo", outcome.commit))
    except (ForestError, OSError, ValueError) as exc:
        controller.db.event("evolution_archive_unavailable", {"experiment_id": mission.id, "reason": str(exc)})
        return
    entry = {"id": mission.id, "epoch": mission.epoch, "role": mission.role,
             "commit": outcome.commit, "mean_seconds": outcome.mean_seconds,
             "protocol_id": controller.db.get("protocol_id"), **profile}
    # The entire ledger remains available, including correct slower variants evicted from a bounded view.
    controller.db.set("evolution_entry:" + mission.id, entry)


def view(db, epoch, *, role=None, authorized_ids=(), maximum=None):
    cfg = settings(db.get("config", {}))
    if not cfg["enabled"]:
        return None
    allowed = set(authorized_ids)
    entries = [json.loads(row["value"]) for row in db.rows(
        "SELECT value FROM metadata WHERE key LIKE 'evolution_entry:%' ORDER BY key")]
    eligible = [e for e in entries if e["epoch"] == epoch and e["protocol_id"] == db.get("protocol_id")
                and (role is None or e["role"] == role or e["id"] in allowed)]
    chosen = select(eligible, maximum or cfg["archive_size"])
    public = [{k: v for k, v in e.items() if k != "sketch"} for e in chosen]
    for index, item in enumerate(public):
        item["selection_reason"] = "fastest_measured" if index == 0 else "lexical_diversity"
        item["distance_from_champion"] = distance(chosen[index], chosen[0])
    return {"schema": "forest-diversity-archive-v1", "eligible_count": len(eligible), "entries": public,
            "scope": {"epoch": epoch, "role": role, "authorized_import_ids": sorted(allowed)},
            "rule": "Lexical diversity is a source-reading hint, not semantic novelty or speedup. "
                "Small edits may be valuable. Never reject or score code from similarity. "
                "Every combination needs its own tests and measurements. Older variants remain in the ledger."}


def attach(controller, mission, context):
    cfg = settings(controller.config)
    if not cfg["enabled"]:
        return context
    # Cross-tree knowledge follows the existing explicit Mother import decisions.
    archive = view(controller.db, mission.epoch, role=mission.role,
                   authorized_ids=mission.import_ids + mission.sources, maximum=cfg["inspirations"])
    if archive["entries"]:
        return {**context, "diverse_measured_sources": archive}
    return context
