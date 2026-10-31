"""Authentication, provider routing and output contracts for the native harness."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from . import dsh_romeo
from .core import InfrastructureError
from .model_policy import DSH_MODEL, generator_pool


def structured_output_instructions(model: str, schema: dict) -> str:
    if model != DSH_MODEL:
        return ""
    # ROMEO's vLLM Responses grammar constrains tool calls as well as final
    # answers. Keep tools usable and enforce the original schema locally.
    return ("\n\nUse the authorized tools when needed before answering. Your FINAL response "
            "must be one JSON object matching the following schema, without Markdown or "
            "surrounding text. The controller validates every constraint; do not invent "
            "tool results. maxLength limits count characters, not words or tokens. Keep explanatory "
            "summaries well below these limits; do not shorten required source code.\n"
            + json.dumps(schema, ensure_ascii=False))


def structured_output_args(model: str, schema_path: Path, *, tools_enabled: bool = True) -> list[str]:
    # A tool-free turn can use the native grammar without constraining MCP calls.
    return [] if model == DSH_MODEL and tools_enabled else ["--output-schema", str(schema_path)]


def validate_structured_output(model: str, data, schema: dict) -> None:
    if model == DSH_MODEL:
        from jsonschema import Draft202012Validator, ValidationError

        try:
            Draft202012Validator(schema).validate(data)
        except ValidationError as exc:
            raise ValueError("Response violates the requested JSON schema at "
                             + exc.json_path[:200] + " (" + str(exc.validator) + ")") from None


def overrides(model: str, settings: dict | None = None) -> dict:
    if model == DSH_MODEL:
        return dsh_romeo.overrides(settings)
    return {"model_provider": "openai", "forced_login_method": "chatgpt"}


def environment(model: str, settings: dict | None = None) -> dict:
    if model == DSH_MODEL:
        return dsh_romeo.environment(settings)
    # dsh-romeo --env exports OpenAI-compatible aliases too. A mixed pool must
    # never inherit that endpoint when its next request selects an OpenAI model.
    return {"OPENAI_API_KEY": "", "CODEX_API_KEY": "", "ROMEO_LLM_KEY": "",
            "OPENAI_BASE_URL": "", "OPENAI_API_BASE": ""}


def authenticate(executable: str, settings: dict, *, dsh_settings: dict | None = None,
                 check_catalog: bool = False) -> dict:
    pool = generator_pool(settings)
    hosted = [item for item in pool if item["model"] != DSH_MODEL]
    has_dsh = any(item["model"] == DSH_MODEL for item in pool)
    if hosted:
        auth = subprocess.run([executable, "login", "status"], capture_output=True, text=True, timeout=30,
                              env={**os.environ, **environment(hosted[0]["model"])})
        if auth.returncode or "Logged in using ChatGPT" not in auth.stdout + auth.stderr:
            raise InfrastructureError("ChatGPT authentication is unavailable; sign in again")
        path = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "models_cache.json"
        if check_catalog and path.is_file():
            catalogue = json.loads(path.read_text(encoding="utf8"))
            for selected in hosted:
                entry = next((m for m in catalogue.get("models", []) if m.get("slug") == selected["model"]), None)
                if not entry or selected["reasoning_effort"] not in {
                    e["effort"] for e in entry.get("supported_reasoning_levels", [])
                }:
                    raise InfrastructureError("A selected model/effort is absent from the ROMEO Codex catalogue")
    if has_dsh:
        dsh_romeo.check_available(dsh_settings)
    return {"authentication": "ChatGPT + dsh-romeo" if hosted and has_dsh else
            "dsh-romeo API key" if has_dsh else "existing-local-ChatGPT",
            "model_weights_on_romeo": has_dsh, "weight_digest_available": False}
