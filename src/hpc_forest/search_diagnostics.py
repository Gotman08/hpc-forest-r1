"""Read-only measurements of search shape and generator outcomes, not model opinions."""
from __future__ import annotations

import json
import math
from collections import Counter

from .search_policy import label, settings


def diagnostics(config: dict, trials: list[dict]) -> dict:
    models, trees = {}, {}
    for row in trials:
        mission = row.get("mission") or {}
        outcome = row.get("result") or {}
        if isinstance(mission, str):
            mission = json.loads(mission)
        if isinstance(outcome, str):
            outcome = json.loads(outcome)
        if (mission.get("budget_phase", "search") != "search"
                or mission.get("kind", "research") != "research" or row["role"] == "G"):
            continue
        selected = (mission.get("generator") or config.get("codex", {})) if config.get("backend") == "codex" else {}
        key = (selected.get("model", config.get("backend", "unknown")), selected.get("reasoning_effort"))
        group = models.setdefault(key, {"model": key[0], "effort": key[1], "admitted": 0,
            "scored": 0, "correct": 0, "incorrect": 0, "unscored": 0, "pending": 0,
            "best_seconds": None, "selection_seconds": 0.0})
        group["admitted"] += 1
        scored = outcome.get("score") is not None
        group["scored"] += int(scored)
        group["correct"] += int(outcome.get("correct") is True)
        group["incorrect"] += int(outcome.get("correct") is False)
        group["pending"] += int(row.get("state") == "pending")
        group["unscored"] += int(not scored and row.get("state") != "pending")
        seconds = outcome.get("mean_seconds")
        if outcome.get("correct") is True and type(seconds) in (float, int) and math.isfinite(seconds) and seconds > 0:
            group["best_seconds"] = min(group["best_seconds"] or seconds, seconds)
        selection_seconds = mission.get("selection", {}).get("seconds", 0)
        if type(selection_seconds) in (float, int) and math.isfinite(selection_seconds):
            group["selection_seconds"] += selection_seconds
        tree = trees.setdefault(row["tree_id"], {"tree_id": row["tree_id"], "role": row["role"],
            "admitted": 0, "root_trials": 0, "refinements": 0, "max_depth": 0, "parents": Counter()})
        tree["admitted"] += 1
        tree["root_trials"] += int(mission.get("parent_id") is None)
        tree["refinements"] += int(mission.get("parent_id") is not None)
        tree["max_depth"] = max(tree["max_depth"], mission.get("depth", 0))
        tree["parents"][mission.get("parent_id")] += 1
    for tree in trees.values():
        counts = tree.pop("parents")
        tree["max_children"] = max(counts.values(), default=0)
        tree["sibling_trials"] = sum(max(0, n - 1) for n in counts.values())
    return {"policy": label(config), "settings": settings(config),
            "generator_pool": config.get("codex", {}).get("generator_pool", []),
            "model_selection": "thompson" if not config.get("binary_tree", {}).get("enabled")
                and settings(config)["algorithm"].startswith("ab-mcts-") else "baseline",
            "models": list(models.values()), "trees": list(trees.values()),
            "interpretation": "Admitted trials include failures and duplicates; best trial time is not final confirmation. "
                "Adaptive model allocation is confounded by different code and parents, not a controlled model ranking."}
