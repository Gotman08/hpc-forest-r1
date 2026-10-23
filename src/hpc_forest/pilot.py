"""Matched budget plans. Running the experiment is explicit; no claims from fake timings."""

from __future__ import annotations

import copy
import json
import re
import uuid
from pathlib import Path

from .controller import Controller, create_workspace
from .core import ForestError, atomic_json, digest, file_digest, protected_manifest
from .reporting import report
from .support.sources import source_snapshot


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
        if entry.get("config_sha256") and file_digest(parent / entry["config"]) != entry["config_sha256"]:
            raise ForestError("Prepared reliability configuration changed")
        config = json.loads((parent / entry["config"]).read_text(encoding="utf-8"))
        root = parent / entry["workspace"]
        try:
            if not root.exists():
                if entry.get("input_digest") and entry["input_digest"] != _input_digest(
                    Path(entry["source"]), Path(entry["validation"])
                ):
                    raise ForestError("Prepared reliability source or validation changed; prepare a new study")
                create_workspace(root, config,
                    Path(entry["source"]) if "source" in entry else None,
                    Path(entry["validation"]) if "validation" in entry else None)
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


def _input_digest(source, validation):
    return digest({"source": source_snapshot(source), "validation": protected_manifest(validation)})


def prepare_suite(specification: Path, output: Path) -> Path:
    """Write plans only; each supplied program keeps its own protected protocol."""
    from .config import load_config, validate

    specification, output = specification.resolve(strict=True), output.resolve()
    value = json.loads(specification.read_text(encoding="utf8"))
    if not isinstance(value, dict):
        raise ForestError("Reliability specification must be an object")
    seeds, cases = value.get("seeds"), value.get("cases")
    if (not isinstance(seeds, list) or len(seeds) < 2 or any(type(v) is not int or v < 0 for v in seeds)
            or len(set(seeds)) != len(seeds) or not isinstance(cases, list) or not cases):
        raise ForestError("A reliability plan needs cases and at least two distinct nonnegative seeds")
    if output.exists():
        raise ForestError("Reliability plan destination already exists")
    prepared, names = [], set()
    for case in cases:
        if (not isinstance(case, dict) or set(case) != {"name", "config", "source", "validation"}
                or not isinstance(case["name"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", case["name"])
                or case["name"] in names or any(not isinstance(case.get(key), str) or not case[key]
                    for key in ("config", "source", "validation"))):
            raise ForestError("Each reliability case needs a unique safe name, config, source and validation")
        names.add(case["name"])
        paths = {key: (specification.parent / case[key]).resolve(strict=True) for key in ("config", "source", "validation")}
        if not (paths["source"] / "src").is_dir() or not paths["validation"].is_dir():
            raise ForestError("Reliability source must contain src/ and validation must be a directory")
        config = load_config(paths["config"])
        validate(config)
        prepared.append((case["name"], paths, config, _input_digest(paths["source"], paths["validation"])))
    order = []
    for index, seed in enumerate(seeds):
        # Alternate case order to reduce confounding by machine load or service changes.
        for name, paths, base, inputs in prepared if index % 2 == 0 else prepared[::-1]:
            config = copy.deepcopy(base)
            config["seed"] = seed
            entry = f"{name}-seed-{seed}"
            if config["backend"] == "codex" and config["codex"].get("transport") == "codex-mailbox":
                config["codex"].update(session_id=uuid.uuid4().hex, mailbox_dir=str(output / "channels" / entry))
            atomic_json(output / (entry + ".json"), config)
            order.append({"case": name, "seed": seed, "method": config["method"], "config": entry + ".json",
                          "workspace": entry, "source": str(paths["source"]), "validation": str(paths["validation"]),
                          "input_digest": inputs, "config_sha256": file_digest(output / (entry + ".json"))})
    atomic_json(output / "plan.json", {"schema": "hpc-forest-reliability-plan-v1", "order": order,
        "interpretation": "Prepared only. Use the original program for every case, keep validation fixed, and compare all runs. "
                          "Seeds control the search, not necessarily native model randomness. No allocation or model call was made."})
    return output / "plan.json"
