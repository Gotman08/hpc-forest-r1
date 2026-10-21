"""Matched budget plans. Running the experiment is explicit; no claims from fake timings."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from .controller import Controller, create_workspace
from .core import ForestError, atomic_json
from .reporting import report


def prepare(output: Path, config: dict, seeds: list[int], methods: list[str]) -> Path:
    if (
        not seeds
        or len(set(seeds)) != len(seeds)
        or not methods
        or len(set(methods)) != len(methods)
    ):
        raise ForestError("Pilot seeds and methods must be nonempty and unique")
    if output.exists():
        raise ForestError("Pilot destination already exists")
    output.mkdir(parents=True)
    order = []
    for index, seed in enumerate(seeds):
        for method in methods if index % 2 == 0 else methods[::-1]:
            c = copy.deepcopy(config)
            c["seed"], c["method"] = seed, method
            path = output / f"seed-{seed}-{method}.json"
            atomic_json(path, c)
            order.append(
                {
                    "seed": seed,
                    "method": method,
                    "config": path.name,
                    "workspace": f"seed-{seed}-{method}",
                }
            )
    atomic_json(
        output / "plan.json",
        {
            "order": order,
            "search_slots_per_campaign": config["budget"]["search_slots"],
            "confirmation_slots_per_campaign": config["budget"]["confirmation_slots"],
            "max_total_slots": len(order)
            * (config["budget"]["search_slots"] + config["budget"]["confirmation_slots"])
            if config["budget"]["search_slots"] is not None else None,
            "minimum_gain_preregistered": config["minimum_gain"],
            "interpretation": "No comparative result before all real campaigns and independent confirmations.",
        },
    )
    return output / "plan.json"


def execute(plan: Path) -> Path:
    parent = plan.parent
    schedule = json.loads(plan.read_text(encoding="utf-8"))
    summary = []
    for entry in schedule["order"]:
        config = json.loads((parent / entry["config"]).read_text(encoding="utf-8"))
        root = parent / entry["workspace"]
        try:
            if not root.exists():
                create_workspace(root, config)
            with Controller(root) as controller:
                controller.run()
                best = controller.confirm()
                status = controller.status()
            report(root)
            summary.append({**entry, "best": best, "status": status})
        except ForestError as exc:
            summary.append({**entry, "error": str(exc)})
        atomic_json(parent / "results.json", summary)
    return parent / "results.json"
