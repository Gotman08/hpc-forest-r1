"""One-way source proposals through an owned mailbox; evaluation stays on ROMEO."""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path

from .backends import Generated
from .core import CandidateRejected, InfrastructureError, Mission, atomic_json
from .harness_research import extract_research
from .ollama_backend import validate_files
from .source_request import proposal_messages
from .support.budgets import generation_deadline

MODEL = "gpt-6.1-sol"
EFFORT = "max"
PROTOCOL = "hpc-forest-codex-mailbox-v1"
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
# Codex does not expose Ollama's num_predict. Reserve a conservative service ceiling.
TOKEN_CEILING = 65536 + 131072


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bounded_json(path: Path, maximum: int = MAX_RESPONSE_BYTES) -> dict:
    if path.is_symlink() or not path.is_file():
        raise InfrastructureError("Mailbox entry is not a regular file")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise InfrastructureError("Mailbox entry exceeds its size limit")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise InfrastructureError("Mailbox JSON must be an object")
    return data


def initialize_channel(root: Path, session_id: str, owner: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{32}", session_id):
        raise InfrastructureError("An explicit random channel session is required")
    root.mkdir(parents=True, exist_ok=False)
    for name in ["requests", "responses", "logs"]:
        (root / name).mkdir()
    marker = {"protocol": PROTOCOL, "session_id": session_id, "owner": owner,
              "model": MODEL, "reasoning_effort": EFFORT}
    atomic_json(root / "OWNER.json", marker)
    return marker


def check_channel(root: Path, session_id: str) -> dict:
    if root.is_symlink():
        raise InfrastructureError("Channel root must not be a symlink")
    marker = bounded_json(root / "OWNER.json", 4096)
    if any(marker.get(k) != v for k, v in {
        "protocol": PROTOCOL, "session_id": session_id, "model": MODEL,
        "reasoning_effort": EFFORT,
    }.items()):
        raise InfrastructureError("Mailbox ownership/model contract changed")
    return marker


def make_request(mission: Mission, context: dict, config: dict) -> dict:
    settings = config["codex"]
    if settings.get("model") != MODEL or settings.get("reasoning_effort") != EFFORT:
        raise InfrastructureError("This campaign requires exactly GPT-6.1 Sol MAX")
    if config["budget"]["mission_tokens"] < TOKEN_CEILING:
        raise InfrastructureError("Insufficient conservative Codex token reservation")
    rendered = proposal_messages(Path(mission.worktree), mission, context)
    return {
        "protocol": PROTOCOL, "kind": "source-proposal", "nonce": uuid.uuid4().hex,
        "session_id": settings["session_id"], "model": MODEL, "reasoning_effort": EFFORT,
        "mission_id": mission.id, "integration_source_ids": mission.sources,
        "expires_at": generation_deadline(context, config["budget"]["generation_seconds"]),
        "token_ceiling": TOKEN_CEILING, **rendered,
    }


def publish_request(channel: Path, request: dict) -> str:
    nonce = request["nonce"]
    if not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise InfrastructureError("Invalid request nonce")
    raw = json_bytes(request)
    if len(raw) > MAX_REQUEST_BYTES:
        raise InfrastructureError("Source context exceeds the mailbox limit")
    path = channel / "requests" / f"{nonce}.request.json"
    if path.exists():
        raise InfrastructureError("Refusing to reuse a request nonce")
    # Same-filesystem rename makes the completed request visible at once.
    temporary = path.with_suffix(".writing")
    temporary.write_bytes(raw)
    temporary.replace(path)
    return sha256(raw)


def response_envelope(request: dict, request_sha256: str, **values) -> dict:
    return {"protocol": PROTOCOL, "nonce": request["nonce"],
            "session_id": request["session_id"], "request_sha256": request_sha256,
            "model": MODEL, "reasoning_effort": EFFORT, **values}


def publish_response(channel: Path, response: dict) -> None:
    """Local transport implementation used by tests and the transport smoke only."""
    nonce = response["nonce"]
    if not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise InfrastructureError("Invalid response nonce")
    raw = json_bytes(response)
    (channel / "responses" / f"{nonce}.response.json").write_bytes(raw)
    atomic_json(channel / "responses" / f"{nonce}.ready.json",
                {"sha256": sha256(raw), "bytes": len(raw)})


def wait_response(channel: Path, request: dict, request_sha256: str, poll_seconds=0.25) -> dict:
    nonce = request["nonce"]
    ready_path = channel / "responses" / f"{nonce}.ready.json"
    while time.time() < request["expires_at"]:
        if ready_path.exists():
            ready = bounded_json(ready_path, 4096)
            path = channel / "responses" / f"{nonce}.response.json"
            response = bounded_json(path)
            raw = path.read_bytes()
            if ready.get("sha256") != sha256(raw) or ready.get("bytes") != len(raw):
                raise InfrastructureError("Response transfer is incomplete or changed")
            expected = response_envelope(request, request_sha256)
            if any(response.get(k) != v for k, v in expected.items()):
                raise InfrastructureError("Stale, replayed or mismatched mailbox response")
            return response
        time.sleep(min(poll_seconds, max(0, request["expires_at"] - time.time())))
    raise InfrastructureError("Local Codex worker did not finish before the mission deadline")


class CodexMailboxBackend:
    supports_harness_research = True

    def generate(self, mission: Mission, context: dict, config: dict, root: Path) -> Generated:
        if mission.role == "G" and not context.get("sources"):
            return Generated(error="No admissible integration sources")
        if time.time() >= generation_deadline(context):
            return Generated(0, {"llm_calls": 0, "generation_not_started": "search_deadline"},
                             error="Search generation deadline reached before invocation")
        settings = config["codex"]
        channel = Path(settings["mailbox_dir"])
        check_channel(channel, settings["session_id"])
        request = make_request(mission, context, config)
        logs = root / "logs" / mission.id
        atomic_json(logs / "codex-request.json", request)
        request_sha = publish_request(channel, request)
        try:
            response = wait_response(channel, request, request_sha)
        except (OSError, ValueError, InfrastructureError) as exc:
            # The worker may have sent a request before the connection failed.
            # Never replay it or invent an exact token count.
            return Generated(TOKEN_CEILING, {
                "backend": "codex-mailbox", "llm_calls": 1, "model": MODEL,
                "reasoning_effort": EFFORT, "request_sha256": request_sha,
                "token_accounting": "upper_bound", "exact_tokens": None,
            }, str(exc), infrastructure_error=True, tokens_upper_bound=True)
        atomic_json(logs / "codex-response.json", response)
        usage = response.get("usage", {})
        tokens = usage.get("tokens")
        if type(tokens) is not int or tokens < 0:
            return Generated(TOKEN_CEILING, {"backend": "codex-mailbox", "llm_calls": 1},
                             "Missing or excessive Codex usage", infrastructure_error=True,
                             tokens_upper_bound=True)
        generated = Generated(tokens, {"backend": "codex-mailbox", **usage,
                              "model": MODEL, "reasoning_effort": EFFORT,
                              "request_sha256": request_sha}, response.get("error"),
                              response.get("infrastructure_error", False),
                              usage.get("token_accounting") == "upper_bound")
        if tokens > TOKEN_CEILING:
            generated.error = "Observed usage exceeded the reserved token ceiling"
            generated.infrastructure_error = True
        if generated.error:
            return generated
        try:
            data = response["data"]
            data, research = extract_research(data, context)
            if research is not None:
                generated.usage["research_request"] = research
                atomic_json(logs / "agent-research-request.json", research)
                return generated
            worktree = Path(mission.worktree)
            edits = validate_files(worktree, data, mission.sources)
            for destination, content in edits:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content, encoding="utf8", newline="")
            mission.hypothesis = data["hypothesis"][:3000]
            mission.transformations = {"retained": data["transformations"],
                                      "files": [p.relative_to(worktree).as_posix() for p, _ in edits]}
            source_map = dict(zip(mission.sources, mission.source_commits, strict=True))
            mission.sources = data["sources_kept"]
            mission.source_commits = [source_map[s] for s in mission.sources]
            atomic_json(logs / "agent-result.json", data)
        except (CandidateRejected, ValueError, KeyError, TypeError) as exc:
            generated.error = f"Invalid Codex source proposal: {exc}"
        return generated
