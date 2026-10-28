from __future__ import annotations

import copy
import json
import math
import re
import sys
import tomllib
from pathlib import Path

from hpc_forest.memory.contract import validate_settings as validate_memory

from .adaptive_budget import validate_adaptive
from .compatibility import require_current
from .core import ForestError
from .forest import persistent_mother, validate_forest
from .model_policy import EFFORT, MODEL, require_identity
from .model_skills import validate_settings as validate_skills
from .submission import validate_submission
from .support.budgets import (
    FINISH_STARTED,
    NATIVE_TOKEN_CEILING,
    adaptive,
    finish_started,
    unlimited_tokens,
)
from .support.validation import require_finite_number, require_integer

DEFAULT = {
    "problem": "matmul",
    "method": "H",
    "backend": "recipe",
    "seed": 23,
    "binary_tree": {"enabled": False},
    "forest": {"policy": "fixed"},
    "completion": {"policy": FINISH_STARTED, "postprocess_tokens": None,
                   "reserve_policy": "adaptive", "confirm_final_g": True},
    "roles": ["A", "B", "C"],
    "budget": {
        "search_slots": None,
        "confirmation_slots": 3,
        "wall_seconds": 3600,
        "tokens": None,
        "mission_tokens": None,
        "max_workers": 3,
        "max_depth": 0,  # Zero disables only the depth cap.
        "generation_seconds": 180,
        "infrastructure_retries": 1,
        "confirmation_seconds": 180,
    },
    "schedule": {"cycles": None, "trials_per_role_per_cycle": 2, "integrations_per_cycle": 2},
    "protocol": {
        "build": ["{python}", "{trusted}/build.py", "{worktree}", "{build}"],
        "check": ["{python}", "{trusted}/check.py", "{binary}", "{phase}"],
        "benchmark": ["{binary}", "256", "17", "4"],
        "repetitions": 3,
        "confirmation_repetitions": 5,
        "warmups": 1,
        "timeout_seconds": 30,
        "build_timeout_seconds": 120,
        "environment": {"OMP_NUM_THREADS": "2", "OMP_DYNAMIC": "FALSE", "OMP_PROC_BIND": "TRUE"},
    },
    "codex": {"executable": "codex", "model": MODEL, "reasoning_effort": EFFORT},
    "ollama": {
        "base_url": "http://127.0.0.1:11434",
        "model": "qwen2.5-coder:7b",
        "temperature": 0.0,
        "context_tokens": 8192,
        "max_output_tokens": 4096,
        "num_threads": 4,
    },
    "minimum_gain": 0.03,
    "harness": {"enabled": False, "max_attempts": 2, "call_token_ceiling": None,
                "research": {"enabled": False, "corpus": None, "corpus_sha256": None,
                             "allowed_hosts": []}},
}


def _merge(base, changes):
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value


def load_config(path: Path | None = None) -> dict:
    if path:
        with path.open("rb") as stream:
            changes = json.load(stream) if path.suffix == ".json" else tomllib.load(stream)
        return config_from_data(changes)
    return config_from_data({})


def config_from_data(changes: dict) -> dict:
    """Apply explicit legacy defaults identically for file reads and migration."""
    config = copy.deepcopy(DEFAULT)
    if changes:
        # A supplied finite legacy profile keeps its original lifecycle. Only
        # new duration profiles inherit adaptive completion from DEFAULT.
        if (changes.get("completion", {}).get("reserve_policy") != "adaptive"
                and (changes.get("budget", {}).get("search_slots") is not None
                     or changes.get("schedule", {}).get("cycles") is not None
                     or changes.get("completion", {}).get("policy") == "hard"
                     or changes.get("budget", {}).get("tokens") is not None)):
            config["completion"] = {"policy": FINISH_STARTED, "postprocess_tokens": None}
            config["budget"].update(search_slots=39, max_depth=6)
            config["schedule"].update(cycles=2)
        _merge(config, changes)
    validate(config)
    return config


def validate(c: dict) -> None:
    from hpc_forest.search.policy import settings as search_settings

    from .model_policy import generator_pool

    search_settings(c)
    from .evolution_archive import settings as evolution_settings

    evolution_settings(c)
    require_current(c)
    codex = c.get("codex", {})
    if not isinstance(codex, dict):
        raise ForestError("codex must be an object")
    if "generator_pool" in codex:
        generator_pool(codex)
        if codex["generator_pool"] and (c["backend"] != "codex" or c.get("binary_tree", {}).get("enabled")):
            raise ForestError("Mixed generators require the Codex backend and a non-binary search policy")
    if c.get("backend") == "codex":
        require_identity(c.get("codex", {}))
    validate_memory(c)
    from .diagnostics_contract import validate as validate_investigation

    validate_investigation(c)
    validate_submission(c)
    validate_skills(c.get("skills"))
    if (c.get("skills") or {}).get("enabled") and (
        c["backend"] != "codex" or c["codex"].get("transport") != "codex-mailbox"
    ):
        raise ForestError("Project skills require the structured Codex mailbox backend")
    completion = c.get("completion", {})
    if (not isinstance(completion, dict)
            or completion.get("policy", "hard") not in {"hard", FINISH_STARTED}):
        raise ForestError("completion.policy must be hard or finish-started")
    validate_adaptive(c)
    if adaptive(c) and (not finish_started(c) or not unlimited_tokens(c)):
        raise ForestError("Adaptive completion requires finish-started and budget.tokens=null")
    if completion.get("confirm_final_g") and not finish_started(c):
        raise ForestError("Final G confirmation requires finish-started")
    post_tokens = completion.get("postprocess_tokens")
    if post_tokens is not None:
        require_integer(post_tokens, "completion.postprocess_tokens", minimum=1)
        if not unlimited_tokens(c) and post_tokens < (c["budget"]["mission_tokens"] or 0) + NATIVE_TOKEN_CEILING:
            raise ForestError("Reserve one Mother call and one complete G mission for postprocessing")
    binary = c.get("binary_tree", {})
    if not isinstance(binary, dict) or type(binary.get("enabled", False)) is not bool:
        raise ForestError("binary_tree.enabled must be a boolean")
    if binary.get("enabled") and c["method"] not in {"H", "H-no-feedback"}:
        raise ForestError("Binary search requires separate H trees, without enumeration")
    validate_forest(c)
    from .active_contract import validate_settings as validate_active

    validate_active(c)
    harness = c.get("harness", {})
    if type(harness.get("enabled", False)) is not bool:
        raise ForestError("harness.enabled must be a boolean")
    if harness.get("enabled"):
        if c["backend"] == "recipe":
            raise ForestError("The node harness expects a model backend, not the recipe demonstration")
        if type(harness.get("max_attempts")) is not int or not 1 <= harness["max_attempts"] <= 4:
            raise ForestError("harness.max_attempts must be an integer in [1,4]")
        if not unlimited_tokens(c):
            require_integer(harness.get("call_token_ceiling"), "harness.call_token_ceiling", minimum=1)
            require_integer(c["budget"]["mission_tokens"], "budget.mission_tokens", minimum=1)
            if c["budget"]["mission_tokens"] < harness["max_attempts"] * harness["call_token_ceiling"]:
                raise ForestError("Reserve all possible harness calls inside mission_tokens")
        research = harness.get("research", {})
        if type(research.get("enabled", False)) is not bool:
            raise ForestError("harness.research.enabled must be a boolean")
        if research.get("enabled"):
            hosts = research.get("allowed_hosts", [])
            if (not isinstance(hosts, list) or len(hosts) > 20
                    or any(not isinstance(h, str) or not re.fullmatch(
                        r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", h) for h in hosts)):
                raise ForestError("Research hosts must be explicit lowercase DNS names")
            corpus = research.get("corpus")
            if corpus and (not isinstance(corpus, str) or not isinstance(
                    research.get("corpus_sha256"), str) or not re.fullmatch(
                    r"[a-f0-9]{64}", research["corpus_sha256"])):
                raise ForestError("Pin the documentation corpus with a SHA-256")
            if not corpus and not hosts:
                raise ForestError("Mixed research needs a pinned corpus or public hosts")
            if c["backend"] not in {"ollama", "codex"}:
                raise ForestError("This research contract needs a structured model backend")
            if c["backend"] == "codex" and c["codex"].get("transport") != "codex-mailbox":
                raise ForestError("Mixed Codex research requires the structured mailbox transport")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", c["problem"]):
        raise ForestError("problem must be a short alphanumeric identifier")
    if c["method"] not in {"H", "U", "H-no-feedback", "H-enumeration"}:
        raise ForestError("Unknown search method")
    if c["backend"] not in {"recipe", "codex", "ollama"}:
        raise ForestError("Unknown generation backend")
    if c["backend"] == "ollama":
        from .ollama_backend import local_url

        local_url(c["ollama"]["base_url"])
        if not isinstance(c["ollama"]["model"], str) or not c["ollama"]["model"]:
            raise ForestError("An explicit installed local model is required")
        for key in ["context_tokens", "max_output_tokens", "num_threads"]:
            if type(c["ollama"][key]) is not int or c["ollama"][key] < 1:
                raise ForestError(f"ollama.{key} must be a positive integer")
        if not 0 <= c["ollama"]["temperature"] <= 2:
            raise ForestError("ollama.temperature must be in [0,2]")
        penalty = c["ollama"].get("repeat_penalty", 1.0)
        if type(penalty) not in {float, int} or not math.isfinite(penalty) or not 0 < penalty <= 2:
            raise ForestError("ollama.repeat_penalty must be finite in (0,2]")
        recent = c["ollama"].get("repeat_last_n", 64)
        if type(recent) is not int or not -1 <= recent <= c["ollama"]["context_tokens"]:
            raise ForestError("ollama.repeat_last_n must be an integer in [-1,context_tokens]")
    if (
        not isinstance(c["roles"], list)
        or not c["roles"]
        or any(not isinstance(r, str) or r not in {"A", "B", "C", "D", "E"} for r in c["roles"])
    ):
        raise ForestError("roles must be a nonempty subset of A..E")
    if len(set(c["roles"])) != len(c["roles"]):
        raise ForestError("Duplicate roles")
    if c["backend"] == "recipe" and any(r not in "ABC" for r in c["roles"]):
        raise ForestError("Recipe demonstration supports A/B/C only; use Codex for D/E")
    for name, value in c["budget"].items():
        if name in {"tokens", "mission_tokens", "search_slots"} and value is None:
            continue
        if name == "infrastructure_retries":
            require_integer(value, name, maximum=3)
            continue
        if name == "max_depth":
            continue
        if require_finite_number(value, f"budget.{name}") <= 0:
            raise ForestError(f"budget.{name} must be positive")
    require_integer(c["budget"]["max_depth"], "budget.max_depth", minimum=0)
    for name in [
        "search_slots",
        "confirmation_slots",
        "max_workers",
    ]:
        if name == "search_slots" and c["budget"][name] is None:
            continue
        require_integer(c["budget"][name], f"budget.{name}", minimum=1)
    for name in ["tokens", "mission_tokens"]:
        if c["budget"][name] is not None or not unlimited_tokens(c):
            require_integer(c["budget"][name], f"budget.{name}", minimum=1)
    if c["budget"]["max_workers"] > 4:
        raise ForestError("Initial controller supports at most four generation workers")
    if not adaptive(c) and c["budget"]["confirmation_seconds"] >= c["budget"]["wall_seconds"]:
        raise ForestError("Reserve less confirmation time than the full wall budget")
    for name in [
        "timeout_seconds",
        "build_timeout_seconds",
    ]:
        if require_finite_number(c["protocol"][name], f"protocol.{name}") <= 0:
            raise ForestError(f"protocol.{name} must be positive")
    for name in ["repetitions", "confirmation_repetitions", "warmups"]:
        require_integer(c["protocol"][name], f"protocol.{name}", minimum=0 if name == "warmups" else 1)
    for name in ["cycles", "trials_per_role_per_cycle", "integrations_per_cycle"]:
        if name == "cycles" and c["schedule"][name] is None:
            if c["method"] == "H-enumeration":
                raise ForestError("Enumeration needs a finite cycle count")
            continue
        minimum = 0 if name == "integrations_per_cycle" and persistent_mother(c) else 1
        require_integer(c["schedule"][name], f"schedule.{name}", minimum=minimum)
    for name in ["build", "check", "benchmark"]:
        command = c["protocol"][name]
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(a, str) for a in command)
        ):
            raise ForestError(f"protocol.{name} must be a nonempty argument array")
    if c["budget"]["confirmation_slots"] < 1:
        raise ForestError("Reserve at least one independent confirmation slot")
    if not 0 <= require_finite_number(c["minimum_gain"], "minimum_gain") < 1:
        raise ForestError("minimum_gain must be in [0, 1)")


def python_command() -> str:
    return sys.executable
