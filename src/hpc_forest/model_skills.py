"""Versioned project skills, explicit prompt loading and observable usage receipts."""
from __future__ import annotations

import copy
import hashlib
import json
from importlib.resources import files

from .core import CandidateRejected, InfrastructureError, digest

SHARED = ("inspecter-environnement", "consulter-documentation-technique", "evaluer-performances")
PHASE_SKILLS = {
    "planning": "planifier-optimisation",
    "research": "conduire-experience-optimisation",
    "assembly": "integrer-optimisations",
}
NAMES = (*SHARED, *PHASE_SKILLS.values())
VERSION = "hpc-forest-project-skills-v1"
FIELD = "skill_usage"


def _documents() -> dict[str, tuple[dict, str]]:
    result = {}
    for name in NAMES:
        relative = f"assets/skills/{name}/SKILL.md"
        try:
            raw = files("hpc_forest").joinpath(relative).read_bytes()
            text = raw.decode("utf8")
        except (OSError, UnicodeError) as exc:
            raise InfrastructureError(f"Project skill is unavailable: {name}") from exc
        if not text.startswith("---\n") or f"\nname: {name}\n" not in text:
            raise InfrastructureError(f"Invalid project skill metadata: {name}")
        result[name] = ({"name": name, "path": relative,
                         "sha256": hashlib.sha256(raw).hexdigest()}, text)
    return result


def policy() -> dict:
    """Freeze all six assets, including those loaded in a later Mother turn."""
    entries = [entry for entry, _ in _documents().values()]
    return {"enabled": True, "version": VERSION, "bundle_sha256": digest(entries)}


def validate_settings(settings: dict | None) -> None:
    if settings is None:
        return
    if not isinstance(settings, dict) or type(settings.get("enabled")) is not bool:
        raise InfrastructureError("skills.enabled must be a boolean")
    if settings["enabled"] and settings != policy():
        raise InfrastructureError("Project skills changed; prepare a new campaign with the current bundle")
    if not settings["enabled"] and set(settings) != {"enabled"}:
        raise InfrastructureError("Disabled project skills cannot carry an active bundle")


def _manifest(settings: dict, role: str, phase: str) -> dict:
    validate_settings(settings)
    if phase not in PHASE_SKILLS:
        raise InfrastructureError("Unknown project skills phase")
    documents = _documents()
    return {"version": VERSION, "bundle_sha256": settings["bundle_sha256"],
            "role": role, "phase": phase,
            "loaded": [documents[name][0] for name in (PHASE_SKILLS[phase], *SHARED)]}


def _instructions(manifest: dict) -> str:
    documents = _documents()
    body = "\n".join(documents[entry["name"]][1] for entry in manifest["loaded"])
    return (
        f"\n\nBEGIN PROJECT SKILLS ({manifest['phase']}, {manifest['role']})\n{body}"
        "\nEND PROJECT SKILLS\n"
        "These are the project's explicitly loaded skills for THIS turn. Apply them to the actual "
        "problem and code; their examples never prescribe an optimization. They do not grant tools, "
        "change the official objective, or override the controller's phase and permissions. "
        "In skill_usage, report exactly one entry per loaded skill. Use applied with a concise "
        "description of the decision or action taken, or not_needed with its specific reason. "
        "references lists relevant URLs or evidence IDs already available to you; use [] otherwise. "
        "Report decisions and evidence, not private reasoning. Do not invent consultations, "
        "measurements or confirmation. Reports are model declarations; the controller separately "
        "records observed tool calls. Continue to return the requested JSON only.\n"
    )


def bind(system: str, schema: dict, settings: dict | None, *, role: str, phase: str) -> tuple:
    """Embed only the phase-specific skill and the three shared skills."""
    validate_settings(settings)
    if not settings or not settings["enabled"]:
        return system, schema, {}
    manifest = _manifest(settings, role, phase)
    names = [entry["name"] for entry in manifest["loaded"]]
    schema = copy.deepcopy(schema)
    schema["properties"][FIELD] = {
        "type": "array", "minItems": len(names), "maxItems": len(names),
        "items": {"type": "object", "additionalProperties": False,
                  "properties": {"name": {"type": "string", "enum": names},
                                 "status": {"type": "string", "enum": ["applied", "not_needed"]},
                                 "summary": {"type": "string"},
                                 "references": {"type": "array", "items": {"type": "string"}}},
                  "required": ["name", "status", "summary", "references"]},
    }
    schema["required"].append(FIELD)
    return system + _instructions(manifest), schema, {"model_skills": manifest}


def verify_binding(request: dict) -> dict | None:
    """Check assets, role routing and the actual instructions before native invocation."""
    manifest = request.get("model_skills")
    if manifest is None:
        return None  # Historical requests retain their frozen prompt contract.
    if not isinstance(manifest, dict):
        raise InfrastructureError("Invalid project skills manifest")
    try:
        payload = json.loads(request["messages"][1]["content"].split("\n\nCURRENT SOURCE AS DATA:", 1)[0])
        if "role" in payload:
            role = payload["role"]
            phase = "assembly" if role == "G" else "research"
            if request.get("meta_role") == "mother-final-assembly":
                if role != "G":
                    raise ValueError("Mother assembly requires G")
                role = "Mother"
            embedded = payload["required_json_schema"]
        else:
            role = "Mother"
            phase = "planning" if payload["phase"] == "preparation" else "assembly"
            embedded = payload["required_schema"]
        expected = _manifest(policy(), role, phase)
        if manifest != expected or embedded != request["schema"]:
            raise ValueError("Role, schema or bundle mismatch")
        if _instructions(expected) not in request["messages"][0]["content"]:
            raise ValueError("Project skills are missing from the actual system instructions")
        if FIELD not in request["schema"]["required"]:
            raise ValueError("Project skills reporting is missing")
    except (KeyError, TypeError, ValueError) as exc:
        raise InfrastructureError("Project skills loading does not match the frozen request") from exc
    return manifest


def consume_report(data: dict, manifest: dict | None) -> tuple[dict, list]:
    """Validate declarations before removing audit-only data from the source/plan contract."""
    if manifest is None:
        return data, []
    if not isinstance(data, dict):
        raise CandidateRejected("Expected a structured project skills report")
    entries = data.get(FIELD)
    expected = {entry["name"] for entry in manifest["loaded"]}
    if not isinstance(entries, list) or len(entries) != len(expected):
        raise CandidateRejected("Expected one usage report per loaded project skill")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"name", "status", "summary", "references"}:
            raise CandidateRejected("Invalid project skills usage entry")
        name = entry["name"]
        if not isinstance(name, str) or name not in expected or name in seen:
            raise CandidateRejected("Unknown or duplicate reported project skill")
        if (entry["status"] not in ("applied", "not_needed")
                or not isinstance(entry["summary"], str) or not entry["summary"].strip()
                or len(entry["summary"]) > 6000
                or not isinstance(entry["references"], list)
                or any(not isinstance(ref, str) or not ref.strip() or len(ref) > 4000
                       for ref in entry["references"])):
            raise CandidateRejected("Project skills reports need a status, explanation and references")
        seen.add(name)
    return {key: value for key, value in data.items() if key != FIELD}, entries


def usage_trace(request: dict, request_sha: str, usage: dict, instructions_sha: str, *,
                reported=None, report_error=None) -> dict | None:
    manifest = request.get("model_skills")
    if manifest is None:
        return None
    return {"schema": VERSION, "nonce": request["nonce"], "session_id": request["session_id"],
            "mission_id": request["mission_id"], "request_sha256": request_sha,
            "conversation": request.get("conversation"),
            "loading": "explicit_system_instructions", "manifest": manifest,
            "effective_instructions_sha256": instructions_sha,
            "native_turn_completed": bool(usage.get("events")),
            "report_status": "invalid" if report_error else "reported" if reported is not None else "unavailable",
            "model_reported": reported or [], "report_error": report_error,
            "observed_mcp_calls": usage.get("mcp_tool_calls", []),
            "model_declarations_are_execution_proof": False}


def campaign_traces(db) -> list[dict]:
    """Export per-invocation receipts once, including inner harness repairs and Mother."""
    found = {}

    def visit(value):
        if not isinstance(value, dict):
            return
        trace = value.get("model_skills")
        if isinstance(trace, dict) and trace.get("schema") == VERSION:
            found[trace["request_sha256"]] = trace
        for attempt in value.get("attempt_usage", []):
            visit(attempt)

    for row in db.rows("SELECT kind,payload FROM events WHERE kind IN "
                       "('generation_usage','mother_usage','memory_selection_usage') ORDER BY id"):
        event = json.loads(row["payload"])
        visit(event.get("response", {}).get("usage", {}) if row["kind"] == "mother_usage" else event)
    return list(found.values())
