from __future__ import annotations

import copy
import json
import math
import re
import sys
import tomllib
from pathlib import Path

from .core import ForestError
from .support.validation import require_finite_number, require_integer

DEFAULT = {
    "problem": "matmul",
    "method": "H",
    "backend": "recipe",
    "seed": 23,
    "binary_tree": {"enabled": False},
    "roles": ["A", "B", "C"],
    "budget": {
        "search_slots": 39,
        "confirmation_slots": 3,
        "wall_seconds": 3600,
        "tokens": 300000,
        "mission_tokens": 16000,
        "max_workers": 3,
        "max_depth": 6,
        "generation_seconds": 180,
        "infrastructure_retries": 1,
        "confirmation_seconds": 180,
    },
    "schedule": {"cycles": 2, "trials_per_role_per_cycle": 5, "integrations_per_cycle": 4},
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
    "codex": {"executable": "codex", "model": None},
    "ollama": {
        "base_url": "http://127.0.0.1:11434",
        "model": "qwen2.5-coder:7b",
        "temperature": 0.0,
        "context_tokens": 8192,
        "max_output_tokens": 4096,
        "num_threads": 4,
    },
    "minimum_gain": 0.03,
    "harness": {"enabled": False, "max_attempts": 2, "call_token_ceiling": 16000,
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
    config = copy.deepcopy(DEFAULT)
    if path:
        with path.open("rb") as stream:
            changes = json.load(stream) if path.suffix == ".json" else tomllib.load(stream)
        _merge(config, changes)
    validate(config)
    return config


def validate(c: dict) -> None:
    binary = c.get("binary_tree", {})
    if not isinstance(binary, dict) or type(binary.get("enabled", False)) is not bool:
        raise ForestError("binary_tree.enabled must be a boolean")
    if binary.get("enabled") and c["method"] not in {"H", "H-no-feedback"}:
        raise ForestError("Binary search requires separate H trees, without enumeration")
    harness = c.get("harness", {})
    if type(harness.get("enabled", False)) is not bool:
        raise ForestError("harness.enabled must be a boolean")
    if harness.get("enabled"):
        if c["backend"] == "recipe":
            raise ForestError("The node harness expects a model backend, not the recipe demonstration")
        if type(harness.get("max_attempts")) is not int or not 1 <= harness["max_attempts"] <= 4:
            raise ForestError("harness.max_attempts must be an integer in [1,4]")
        if type(harness.get("call_token_ceiling")) is not int or harness["call_token_ceiling"] < 1:
            raise ForestError("harness.call_token_ceiling must be a positive integer")
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
        if name == "infrastructure_retries":
            require_integer(value, name, maximum=3)
            continue
        if require_finite_number(value, f"budget.{name}") <= 0:
            raise ForestError(f"budget.{name} must be positive")
    for name in [
        "search_slots",
        "confirmation_slots",
        "tokens",
        "mission_tokens",
        "max_workers",
        "max_depth",
    ]:
        require_integer(c["budget"][name], f"budget.{name}", minimum=1)
    if c["budget"]["max_workers"] > 4:
        raise ForestError("Initial controller supports at most four generation workers")
    if c["budget"]["confirmation_seconds"] >= c["budget"]["wall_seconds"]:
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
        require_integer(c["schedule"][name], f"schedule.{name}", minimum=1)
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
