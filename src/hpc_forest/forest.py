"""Model-selected research trees, kept separate from the frozen execution config."""
from __future__ import annotations

import re

from .core import ForestError
from .support.validation import require_integer


def model_selected(config: dict) -> bool:
    return config.get("forest", {}).get("policy", "fixed") == "mother"


def persistent_mother(config: dict) -> bool:
    return model_selected(config) and config["forest"].get("conversation") == "persistent"


def pairwise_mother(config: dict) -> bool:
    return persistent_mother(config) and config["forest"].get("integration") == "pairwise"


def forest_plan(db, epoch: int | None = None) -> dict | None:
    return db.get(f"forest_plan:{epoch if epoch is not None else db.get('current_epoch')}")


def research_roles(db, epoch: int | None = None) -> list[str]:
    if not model_selected(db.get("config")):
        return db.get("config")["roles"][:]
    from .active_contract import enabled

    if enabled(db.get("config")):
        from .active_state import children

        return [c["role"] for c in children(db, epoch if epoch is not None else db.get("current_epoch"))
                if c.get("kind") != "intermediate_integration"]
    plan = forest_plan(db, epoch)
    return [child["role"] for child in plan["children"]] if plan else []


def assignment(db, role: str, epoch: int) -> dict | None:
    from .active_contract import enabled

    if enabled(db.get("config")):
        from .active_state import children

        return next((child for child in children(db, epoch) if child["role"] == role), None)
    plan = forest_plan(db, epoch)
    return next((child for child in plan["children"] if child["role"] == role), None) if plan else None


def role_goal(role: str, context: dict) -> str:
    child = context.get("research_tree")
    if child is not None:
        if child.get("role") != role or not child.get("objective"):
            raise ForestError("Research objective does not belong to this tree")
        return child["objective"]
    from .backends import ROLE_PURPOSE

    if role not in ROLE_PURPOSE:
        raise ForestError("Research tree has no model-authored objective: " + role)
    return ROLE_PURPOSE[role]


def forest_width(record: dict, session_id: str) -> int:
    children = record.get("children")
    if (record.get("protocol") != "hpc-forest-mother-forest-v1"
            or record.get("session_id") != session_id or record.get("status") != "complete"
            or not isinstance(children, list) or not children
            or type(record.get("parallelism")) is not int or record["parallelism"] != len(children)
            or any(not isinstance(child, dict) or child.get("role") != f"T{index}"
                   for index, child in enumerate(children, 1))):
        raise ForestError("Invalid or unrelated controller research forest")
    extra = record.get("active_control")
    if extra is not None:
        from .active_contract import VERSION

        if (not isinstance(extra, dict) or set(extra) != {"version", "control_workers"}
                or extra["version"] != VERSION or type(extra["control_workers"]) is not int
                or not 1 <= extra["control_workers"] <= 4):
            raise ForestError("Invalid declared active control capacity")
    return len(children) + (extra["control_workers"] if extra else 0)


def validate_forest(config: dict) -> None:
    settings = config.get("forest", {})
    if not isinstance(settings, dict) or settings.get("policy", "fixed") not in {"fixed", "mother"}:
        raise ForestError("forest.policy must be fixed or mother")
    if "statement" in settings and not isinstance(settings["statement"], str):
        raise ForestError("forest.statement must be problem text")
    if "conversation" in settings and (settings["conversation"] != "persistent" or not model_selected(config)):
        raise ForestError("A persistent Mother conversation requires Mother-selected trees")
    if "integration" in settings and (settings["integration"] not in {"pairwise", "memory-guided-v1"}
                                      or not persistent_mother(config)):
        raise ForestError("Pairwise or memory-guided integration requires the persistent Mother conversation")
    require_integer(settings.get("plan_review_calls", 0), "forest.plan_review_calls", minimum=0, maximum=32)
    if settings.get("plan_review_calls", 0) and not persistent_mother(config):
        raise ForestError("Plan review requires persistent Mother")
    if model_selected(config):
        if persistent_mother(config) and config["schedule"]["integrations_per_cycle"] != 0:
            raise ForestError("Persistent Mother assembles once after research; no G-to-research cycles")
        if (config["method"] not in {"H", "H-no-feedback"}
                or config.get("binary_tree", {}).get("enabled")):
            raise ForestError("Mother-selected trees require separate AB-MCTS research trees")
        if config["backend"] != "codex" or config["codex"].get("transport") != "codex-mailbox":
            raise ForestError("Mother-selected trees require the structured Codex mailbox transport")
        identity = config["codex"]
        if (any(not isinstance(identity.get(key), str) or not identity[key].strip()
                for key in ("model", "reasoning_effort", "mailbox_dir"))
                or not isinstance(identity.get("session_id"), str)
                or not re.fullmatch(r"[a-f0-9]{32}", identity["session_id"])):
            raise ForestError("Mother-selected trees need an explicit model identity, session and mailbox")
        if (config.get("completion", {}).get("reserve_policy") != "adaptive"
                or config.get("completion", {}).get("policy") != "finish-started"
                or config.get("completion", {}).get("confirm_final_g") is not True
                or config["budget"]["tokens"] is not None
                or config["budget"]["search_slots"] is not None
                or config["schedule"]["cycles"] is not None or config["budget"]["max_depth"] != 0):
            raise ForestError("Mother-selected trees require adaptive duration and unlimited tokens, slots and cycles")
