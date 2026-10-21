"""Measured feedback only; no proposed algorithm, repair, or synthetic reward."""

from __future__ import annotations

import json
from pathlib import Path

from .binary_search import enabled
from .core import Mission, digest
from .registry import Registry


def _clip(value, limit=4000):
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "\n[diagnostic truncated]"
    if isinstance(value, dict):
        return {k: _clip(v, limit) for k, v in list(value.items())[:32]}
    if isinstance(value, list):
        return [_clip(v, limit) for v in value[:32]]
    return value


def _logs(root: Path, outcome: dict) -> list[dict]:
    result = []
    for name in outcome.get("logs", [])[:2]:
        path = Path(name)
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            continue
        with path.open("rb") as stream:
            raw = stream.read(65537)
        if not raw:
            continue
        text = raw[:65536].decode("utf-8", errors="replace")
        item = {"path": path.relative_to(root).as_posix(), "truncated": len(raw) > 65536}
        try:
            item["runner_output"] = _clip(json.loads(text))
        except ValueError:
            item["text"] = _clip(text)
        result.append(item)
    return result


def measured_observations(db: Registry, root: Path, mission: Mission) -> dict:
    allowed = None
    if enabled(db.get("config", {})):
        allowed = set()
        parent_id = mission.parent_id
        while parent_id and parent_id not in allowed:
            allowed.add(parent_id)
            row = db.one("SELECT mission FROM trials WHERE id=?", (parent_id,))
            parent_id = json.loads(row["mission"])["parent_id"] if row else None

    def observation(experiment_id):
        row = db.one("SELECT id,epoch,role,mission,result FROM trials WHERE id=?", (experiment_id,))
        if row is None:
            baseline = db.one(
                "SELECT payload FROM evaluations WHERE experiment_id=? AND phase='search'",
                (experiment_id,),
            )
            if baseline is None:
                return None
            outcome = json.loads(baseline["payload"])
            return {
                "experiment_id": experiment_id,
                "outcome": _clip(outcome),
                "raw_logs": _logs(root, outcome),
            }
        if row["result"] is None:
            return None
        outcome = json.loads(row["result"])
        selected = json.loads(row["mission"])
        item = {
            "experiment_id": experiment_id,
            "role": row["role"],
            "hypothesis": selected["hypothesis"][:1000],
            "outcome": _clip(outcome),
            "raw_logs": _logs(root, outcome),
        }
        if outcome["status"] == "duplicate" and outcome.get("tree_hash"):
            key = digest(
                {
                    "tree": outcome["tree_hash"],
                    "protocol": db.get("protocol_id"),
                    "epoch": row["epoch"],
                }
            )
            cached = db.cached(key)
            if cached is not None:
                item["duplicate_of"] = {
                    "experiment_id": cached["experiment_id"],
                    "measured_outcome": _clip(cached),
                    "raw_logs": _logs(root, cached),
                }
        return item

    recent = [
        observation(row["id"])
        for row in db.rows(
            "SELECT id FROM trials WHERE epoch=? AND role=? AND result IS NOT NULL ORDER BY created DESC,rowid DESC LIMIT 3",
            (mission.epoch, mission.role),
        ) if allowed is None or row["id"] in allowed
    ]
    history = []
    for row in db.rows(
        "SELECT id,result FROM trials WHERE epoch=? AND role=? AND result IS NOT NULL ORDER BY created DESC,rowid DESC LIMIT 32",
        (mission.epoch, mission.role),
    ):
        if allowed is not None and row["id"] not in allowed:
            continue
        outcome = json.loads(row["result"])
        history.append(
            {
                "experiment_id": row["id"],
                **{k: _clip(outcome.get(k), 300) for k in ["status", "score", "mean_seconds", "reason"]},
            }
        )
    return {
        "baseline": observation(f"baseline-e{mission.epoch}"),
        "selected_parent": observation(mission.parent_id) if mission.parent_id else None,
        "selected_base_commit": mission.base_commit,
        "recent_own_role": recent,
        "own_role_history": history,
    }
