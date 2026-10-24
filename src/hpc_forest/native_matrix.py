"""Compatibility adapter for native launchers, now restricted to GPT-6 Luna Max.

Historical matrix artifacts remain readable; they are not authorization to run
other models in the current experiment series.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .core import InfrastructureError, file_digest
from .model_policy import EFFORT, MODEL

MODELS = (MODEL,)
EFFORTS = (EFFORT,)
SCOPE = "hpc-forest-archives-2020-2024-mother-r1"


def validate_identity(model, effort):
    if model not in MODELS or effort not in EFFORTS:
        raise InfrastructureError("Model or effort is outside the human-authorized matrix")


def validate_receipt(path: Path, required_jobs: set[str]) -> dict:
    data = json.loads(path.read_text(encoding="utf8"))
    validate_identity(data.get("model"), data.get("effort"))
    if (data.get("schema") != "hpc-forest-native-matrix-authorization-v1"
            or data.get("scope_id") != SCOPE or required_jobs != {SCOPE}
            or data.get("expires_at", 0) <= time.time()
            or data.get("deepseek_completion_claimed") is not False
            or data.get("old_candidates_imported") is not False
            or data.get("operator_algorithm_advice") is not False
            or not data.get("user_messages") or len(data.get("session_id", "")) != 32):
        raise InfrastructureError("Invalid, expired or unrelated matrix authorization")
    for key in ("plan", "source_zip"):
        item = data[key]
        p = Path(item["path"])
        if p.is_symlink() or not p.is_file() or file_digest(p) != item["sha256"]:
            raise InfrastructureError("The frozen matrix artifact changed: " + key)
    plan = json.loads(Path(data["plan"]["path"]).read_text(encoding="utf8"))
    if (plan.get("scope_id") != SCOPE or plan.get("models") != list(MODELS)
            or plan.get("efforts") != list(EFFORTS)
            or plan.get("operator_algorithm_advice") is not False):
        raise InfrastructureError("Authorization does not name the frozen experiment")
    return data


def install_identity(model: str, effort: str, receipt: Path | None = None):
    """One model/effort per owned worker and per cluster process, never global config."""
    validate_identity(model, effort)
    from . import codex_mailbox, codex_process, codex_worker

    for module in (codex_mailbox, codex_process, codex_worker):
        module.MODEL, module.EFFORT = model, effort
    if receipt is not None:
        authorization = validate_receipt(receipt, {SCOPE})
        if (authorization["model"], authorization["effort"]) != (model, effort):
            raise InfrastructureError("Worker identity differs from its authorization")

        def gate(path, required_jobs):
            fresh = validate_receipt(path, required_jobs)
            if (fresh["model"], fresh["effort"]) != (model, effort):
                raise InfrastructureError("Generation identity changed inside the worker")
            return fresh

        codex_process.check_dependencies = gate
        codex_worker.check_dependencies = gate


def verified_catalog(path: Path) -> dict:
    """Read only model metadata; no authentication material is returned."""
    catalog = json.loads(path.read_text(encoding="utf8"))
    result = {}
    for model in catalog.get("models", []):
        slug = model.get("slug")
        if slug not in MODELS:
            continue
        supported = {level["effort"] for level in model.get("supported_reasoning_levels", [])}
        if not set(EFFORTS) <= supported:
            raise InfrastructureError("Missing requested reasoning effort for " + slug)
        result[slug] = {"supported_reasoning_efforts": sorted(supported),
                        "context_window_as_catalogued": model.get("context_window")}
    if set(result) != set(MODELS):
        raise InfrastructureError("At least one exact requested model is absent")
    return {"fetched_at": catalog.get("fetched_at"), "models": result,
            "scope": "catalogue capability; not proof of a completed generation"}
