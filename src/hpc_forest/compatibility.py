"""Explicit retirement of old configuration, with read-only evidence helpers.

Historical data is never validated as a new execution contract or rewritten on
read. Retired settings require an explicit copy for a new campaign.
"""
from __future__ import annotations

import json

from .core import ForestError

RETIRED_SETTINGS = frozenset({"advisor", "advisor_runtime"})
RETIREMENT_MESSAGE = (
    "TabPFN a été retiré de Forest. Ce contrat historique reste consultable. "
    "Créez une nouvelle préparation sans advisor/advisor_runtime, ou utilisez "
    "migrate-config pour copier la configuration. Ne modifiez pas une campagne existante."
)


def require_current(config: dict) -> None:
    """Reject even disabled legacy settings: no silent contract reinterpretation."""
    if RETIRED_SETTINGS.intersection(config):
        raise ForestError(RETIREMENT_MESSAGE)


def without_retired(config: dict) -> dict:
    """Return an explicit migration copy; callers preserve the original."""
    return {key: value for key, value in config.items() if key not in RETIRED_SETTINGS}


def historical_advisor(config: dict, totals: dict) -> dict | None:
    """Expose recorded evidence only; no runtime, prediction or default version."""
    if "advisor" not in config and not totals:
        return None
    return {"enabled": (config.get("advisor") or {}).get("enabled", False),
            **totals, "retired": True, "read_only": True}


def recorded_topology(db) -> dict:
    """Render historical lineage without loading executable TreeQuest checkpoints."""
    trees, scored, depth, width = [], 0, 0, 0
    for tree in db.rows("SELECT id,role FROM trees ORDER BY role"):
        nodes = [{"id": tree["id"], "label": tree["role"], "parent": None, "depth": 0, "score": None}]
        for row in db.rows("SELECT mission,result FROM trials WHERE tree_id=? ORDER BY created,id", (tree["id"],)):
            mission, result = json.loads(row["mission"]), json.loads(row["result"] or "{}")
            if result.get("score") is None:
                continue
            nodes.append({"id": mission["id"], "label": mission["role"] + str(mission["ordinal"]),
                          "parent": mission.get("parent_id") or tree["id"], "depth": mission["depth"],
                          "score": result["score"]})
        for node in nodes:
            node["child_count"] = sum(n["parent"] == node["id"] for n in nodes)
            width = max(width, node["child_count"])
            depth = max(depth, node["depth"])
        scored += len(nodes) - 1
        trees.append({"role": tree["role"], "nodes": nodes})
    return {"source": "recorded_trials", "policy": "historical", "scored_nodes": scored,
            "max_depth": depth, "max_children": width, "trees": trees}
