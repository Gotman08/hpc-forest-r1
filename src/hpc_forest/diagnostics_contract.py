"""Controller-issued diagnostic grants; no model-supplied commands or paths."""
from __future__ import annotations

import json
import os
import platform
import re
import time
from pathlib import Path

from .core import ForestError, InfrastructureError, atomic_json, digest, file_digest
from .registry import Registry

VERSION = "hpc-forest-diagnostics-v3-refinement-profiling"
DEFAULTS = {"enabled": False, "require_allocation": True, "max_collections": 12,
            "collection_seconds": 120, "request_seconds": 300, "max_bytes": 268435456}


def settings(config):
    return {**DEFAULTS, **config.get("investigation", {})}


def validate(config):
    supplied = config.get("investigation", {})
    if not isinstance(supplied, dict) or set(supplied) - set(DEFAULTS):
        raise ForestError("Unknown investigation settings")
    value = settings(config)
    for name in ("enabled", "require_allocation"):
        if type(value[name]) is not bool:
            raise ForestError("investigation." + name + " must be boolean")
    for name, upper in (("max_collections", 24), ("collection_seconds", 600),
                        ("request_seconds", 1800), ("max_bytes", 1073741824)):
        if type(value[name]) is not int or not 1 <= value[name] <= upper:
            raise ForestError("Invalid investigation." + name)
    if value["enabled"] and (config.get("backend") != "codex"
                             or config.get("forest", {}).get("policy") != "mother"):
        raise ForestError("Investigation requires a native Mother campaign")


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", value):
        raise ValueError("Invalid diagnostic identifier")
    return value


def owned(root: Path, name: str) -> Path:
    """Reject traversal and links, including links whose targets stay in the root."""
    if not isinstance(name, str) or "\\" in name or ":" in name:
        raise ValueError("Invalid diagnostic path")
    path = Path(name)
    if path.is_absolute() or not name or any(p in {"", ".", ".."} for p in name.split("/")):
        raise ValueError("Invalid diagnostic path")
    result = root / path
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError("Diagnostic path leaves its root")
    cursor = result
    while cursor != root:
        if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
            raise ValueError("Diagnostic links are forbidden")
        cursor = cursor.parent
    return result


def authorize(root: Path, request: dict, *, source_ids=None, collect=None, config=None,
              refinement=False) -> dict | None:
    """Freeze measured sources and permissions before publishing a native request.

    Research generators, Mother and analysts can collect on frozen measured
    sources. Assembly reads by default; an explicitly reserved refinement may
    collect on its measured inputs while preserving code and confirmation time.
    """
    if config is not None and not settings(config)["enabled"]:
        return None
    db = Registry(root / "registry.sqlite3", readonly=True)
    try:
        config = db.get("config")
        policy = settings(config)
        if not policy["enabled"]:
            return None
        epoch = db.get("current_epoch")
        sources = {}
        for row in db.rows("SELECT * FROM evaluations WHERE epoch=? AND phase IN ('search','postprocess')", (epoch,)):
            result = json.loads(row["payload"])
            if not result.get("commit") or (source_ids is not None and row["experiment_id"] not in source_ids):
                continue
            sources[row["experiment_id"]] = {"commit": result["commit"],
                "tree_hash": result.get("tree_hash"), "official_correct": result.get("correct"),
                "official_binary_sha256": result.get("binary_sha256"), "evaluation_id": row["id"]}
        role = request.get("meta_role", "generator")
        allowed = role.startswith("mother-") or role in {"active-analyst", "active-mother", "generator"}
        closed = (request.get("budget_phase") == "postprocess"
                  or db.get(f"search_closed:{epoch}") is not None)
        refinement_seconds = 0.0
        if refinement and request.get("budget_phase") == "postprocess":
            from .independent_budget import assembly_admission, required_assembly_rounds

            post = db.get(f"postprocess:{epoch}", {})
            steps = post.get("steps", [])
            budget = assembly_admission(db)
            if (required_assembly_rounds(config) > 1 and any(s.get("outcome", {}).get("correct") for s in steps)
                    and source_ids and budget["remaining_seconds"] is not None):
                refinement_seconds = min(45.0, max(0, budget["remaining_seconds"] - budget["finish_seconds"]))
        if refinement_seconds > 0:
            policy = {**policy, "request_seconds": min(policy["request_seconds"], refinement_seconds),
                      "collection_seconds": min(policy["collection_seconds"], refinement_seconds)}
            closed = False
        if collect is not None:
            allowed = allowed and collect
        grant = {"version": VERSION, "nonce": identifier(request["nonce"]),
                 "session_id": request["session_id"], "mission_id": request["mission_id"],
                 "role": role, "epoch": epoch, "protocol_id": db.get("protocol_id"),
                 "manifest": db.get("manifest"), "config_sha256": file_digest(root / "trusted/config.json"),
                 "sources": sources, "policy": policy, "can_collect": allowed and not closed,
                 "reserved_refinement_seconds": refinement_seconds,
                 "created_at": time.time(), "expires_at": min(
                     time.time() + policy["request_seconds"], request.get("expires_at") or float("inf"),
                     db.get("deadline") or float("inf")),
                 "allocation_id": os.environ.get("SLURM_JOB_ID"), "machine": platform.machine(),
                 "hostname": platform.node(),
                 "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None}
        path = root / "diagnostics/grants" / (request["nonce"] + ".json")
        if path.exists():
            raise InfrastructureError("A diagnostic grant cannot be replaced")
        atomic_json(path, grant)
        request["diagnostics"] = {"version": VERSION, "grant_id": request["nonce"],
                                  "sha256": file_digest(path)}
        return grant
    finally:
        db.close()


def load_grant(root, binding, request=None):
    if (not isinstance(binding, dict) or set(binding) != {"version", "grant_id", "sha256"}
            or binding["version"] != VERSION):
        raise InfrastructureError("Invalid diagnostic binding")
    path = owned(root, "diagnostics/grants/" + identifier(binding["grant_id"]) + ".json")
    if file_digest(path) != binding["sha256"]:
        raise InfrastructureError("Diagnostic grant changed")
    grant = json.loads(path.read_text(encoding="utf8"))
    if request is not None and any(grant[k] != request[k] for k in ("nonce", "session_id", "mission_id")):
        raise InfrastructureError("Diagnostic grant belongs to another request")
    if grant["config_sha256"] != file_digest(root / "trusted/config.json"):
        raise InfrastructureError("Diagnostic campaign configuration changed")
    return grant


def target_lock(config):
    import tempfile

    return Path(tempfile.gettempdir()) / "hpc-forest-locks" / (digest(config["target_id"]) + ".lock")
