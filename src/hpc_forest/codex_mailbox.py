"""One-way source proposals through an owned mailbox; evaluation stays on ROMEO."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path

from hpc_forest.memory.contract import extract_memory

from .backends import Generated
from .codex_conversation import next_turn, verify_receipt
from .core import CandidateRejected, InfrastructureError, Mission, atomic_json
from .forest import persistent_mother
from .harness_research import extract_research
from .model_policy import (
    EFFORT,
    MODEL,
    generator_pool,
    mission_identity,
    require_identity,
    require_request_identity,
)
from .ollama_backend import validate_files
from .source_request import proposal_messages
from .support.budgets import (
    FINISH_STARTED,
    NATIVE_TOKEN_CEILING,
    OBSERVE_TOKENS,
    adaptive,
    expired,
    generation_deadline,
    time_left,
    unlimited_tokens,
)

PROTOCOL = "hpc-forest-codex-mailbox-v1"
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
HEARTBEAT_GRACE_SECONDS = 180
# Windows can briefly deny reads while an atomic rename closes its handle.
# Persistent denial still fails; no permissions or content checks are relaxed.
_FILE_READ_RETRY_DELAYS = (0.02, 0.05, 0.1, 0.2) if os.name == "nt" else ()
# Historical budgeted campaigns used this accounting reservation. New requests
# have no application ceiling and never present this estimate as a real bound.
TOKEN_CEILING = NATIVE_TOKEN_CEILING


def unavailable_usage(request: dict) -> dict:
    observe_only = request.get("token_policy") == OBSERVE_TOKENS
    return {"tokens": None if observe_only else TOKEN_CEILING,
            "token_accounting": "unknown" if observe_only else "upper_bound",
            "exact_tokens": None, "llm_calls": 1}


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bounded_json(path: Path, maximum: int = MAX_RESPONSE_BYTES) -> dict:
    for attempt in range(len(_FILE_READ_RETRY_DELAYS) + 1):
        if path.is_symlink() or not path.is_file():
            raise InfrastructureError("Mailbox entry is not a regular file")
        try:
            with path.open("rb") as stream:
                raw = stream.read(maximum + 1)
            break
        except PermissionError:
            if attempt == len(_FILE_READ_RETRY_DELAYS):
                raise
            time.sleep(_FILE_READ_RETRY_DELAYS[attempt])
    if len(raw) > maximum:
        raise InfrastructureError("Mailbox entry exceeds its size limit")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise InfrastructureError("Mailbox JSON must be an object")
    return data


def initialize_channel(root: Path, session_id: str, owner: str, *, model=MODEL, effort=EFFORT, generators=None) -> dict:
    selected = {"model": model, "reasoning_effort": effort, "generator_pool": generators or []}
    pool = generator_pool(selected)
    if not re.fullmatch(r"[0-9a-f]{32}", session_id):
        raise InfrastructureError("An explicit random channel session is required")
    root.mkdir(parents=True, exist_ok=False)
    for name in ["requests", "responses", "logs"]:
        (root / name).mkdir()
    marker = {"protocol": PROTOCOL, "session_id": session_id, "owner": owner,
              "model": model, "reasoning_effort": effort}
    if generators:
        marker["generator_pool"] = pool
    atomic_json(root / "OWNER.json", marker)
    return marker


def check_channel(root: Path, session_id: str, *, model=MODEL, effort=EFFORT, generators=None) -> dict:
    if root.is_symlink():
        raise InfrastructureError("Channel root must not be a symlink")
    marker = bounded_json(root / "OWNER.json", 4096)
    if any(marker.get(k) != v for k, v in {
        "protocol": PROTOCOL, "session_id": session_id, "model": model,
        "reasoning_effort": effort,
    }.items()):
        raise InfrastructureError("Mailbox ownership/model contract changed")
    expected = generator_pool({"model": model, "reasoning_effort": effort, "generator_pool": generators or []})
    if generator_pool(marker) != expected:
        raise InfrastructureError("Mailbox generator pool changed")
    return marker


def make_request(mission: Mission, context: dict, config: dict) -> dict:
    settings = config["codex"]
    selected = mission_identity(config, mission)
    if not unlimited_tokens(config) and config["budget"]["mission_tokens"] < TOKEN_CEILING:
        raise InfrastructureError("Insufficient conservative Codex token reservation")
    if context.get("assembly_selection"):
        from .integration_policy import selection_messages

        rendered = selection_messages(context, config)
    else:
        rendered = proposal_messages(Path(mission.worktree), mission, context, skills=config.get("skills"))
    request = {
        "protocol": PROTOCOL, "kind": "source-proposal", "nonce": uuid.uuid4().hex,
        "session_id": settings["session_id"], **selected,
        "mission_id": mission.id, "integration_source_ids": mission.sources,
        "expires_at": generation_deadline(context, config["budget"]["generation_seconds"]),
        "token_ceiling": None if unlimited_tokens(config) else TOKEN_CEILING, **rendered,
    }
    if mission.generator:
        request.update(budget_phase="search", generator_selection={
            "identity": selected, "role": mission.role, "action": mission.search_action})
    if unlimited_tokens(config):
        request["token_policy"] = OBSERVE_TOKENS
    if adaptive(config):
        request["archive_request_after_response"] = True
    if context.get("deadline_policy") == FINISH_STARTED:
        request.update(deadline_policy=FINISH_STARTED, budget_phase=context.get("budget_phase", "search"))
    if persistent_mother(config) and mission.role == "G":
        if not context.get("mother_assembly") or mission.budget_phase != "postprocess":
            raise InfrastructureError("G must be assembled by the original Mother after research closes")
        request["conversation"] = next_turn(context["mother_conversation"])
        request["meta_role"] = "mother-final-assembly"
        if not context.get("assembly_selection"):
            request["messages"][0]["content"] += (
                " You are the SAME Mother continuing your original conversation after your N research trees. "
                "Research is permanently closed. Assemble the code yourself from their returned source "
                "programs and measurements. Do not create, launch, restart, replace or request any research "
                "tree or other model. Return the source proposal schema for G, never a decomposition or "
                "guidance-only response. The controller measures your proposal and independently confirms final G."
            )
        if context.get("assembly_selection"):
            request["meta_role"] = "mother-memory-selection"
        if context.get("integration_pair"):
            request["messages"][0]["content"] += (
                " This is one step of a pairwise reduction. Assemble only the supplied input programs. "
                "The controller measures each intermediate result and preserves the better input "
                "when that result regresses. Continue in this same conversation; its history is "
                "managed by the native Codex CLI, including automatic compaction. "
                "Do not attempt to compact, restart or replace your conversation yourself."
            )
    return request


def publish_request(channel: Path, request: dict) -> str:
    require_identity(request)
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
            "model": request["model"], "reasoning_effort": request["reasoning_effort"], **values}


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
    last_heartbeat, last_alive = None, time.monotonic()
    while not expired(request["expires_at"]):
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
            if request.get("archive_request_after_response"):
                # Keep the active inbox below the remote listing limit on long
                # campaigns. Preserve every original request, rather than delete it.
                original = channel / "requests" / f"{nonce}.request.json"
                archived = channel / "archive" / "requests" / original.name
                if original.exists():
                    if sha256(original.read_bytes()) != request_sha256:
                        raise InfrastructureError("The delivered request changed before archival")
                    archived.parent.mkdir(parents=True, exist_ok=True)
                    if archived.exists() and sha256(archived.read_bytes()) != request_sha256:
                        raise InfrastructureError("An archived request has a different identity")
                    original.replace(archived)
            return response
        if request["expires_at"] is None:
            heartbeat_path = channel / "worker-heartbeat.json"
            if heartbeat_path.exists():
                heartbeat = bounded_json(heartbeat_path, 4096)
                if heartbeat.get("session_id") != request["session_id"]:
                    raise InfrastructureError("The worker heartbeat belongs to another session or model")
                require_request_identity(request, heartbeat)
                stamp = sha256(heartbeat_path.read_bytes())
                if stamp != last_heartbeat:
                    last_heartbeat, last_alive = stamp, time.monotonic()
            if time.monotonic() - last_alive >= HEARTBEAT_GRACE_SECONDS:
                raise InfrastructureError("The local model worker stopped sending heartbeats")
        time.sleep(max(0, time_left(request["expires_at"], poll_seconds)))
    raise InfrastructureError("Local Codex worker did not finish before the mission deadline")


class CodexMailboxBackend:
    supports_harness_research = True

    def generate(self, mission: Mission, context: dict, config: dict, root: Path) -> Generated:
        if persistent_mother(config):
            from .registry import Registry

            db = Registry(root / "registry.sqlite3")
            try:
                if mission.role == "G":
                    if (db.get(f"search_closed:{mission.epoch}") is None
                            or db.get(f"mother_assembly_started:{mission.epoch}") is None):
                        raise InfrastructureError("Research must be permanently closed before Mother assembly")
                    # Harness repairs resume the next turn, not the stale turn in a copied context.
                    context = {**context, "mother_conversation": db.get(f"mother_conversation:{mission.epoch}")}
                elif db.get(f"mother_assembly_started:{mission.epoch}") is not None:
                    raise InfrastructureError("Mother cannot relaunch research after assembly starts")
            finally:
                db.close()
        if mission.role == "G" and not context.get("sources") and not context.get("assembly_selection"):
            return Generated(error="No admissible integration sources")
        if expired(generation_deadline(context)):
            return Generated(0, {"llm_calls": 0, "generation_not_started": "search_deadline"},
                             error="Search generation deadline reached before invocation")
        settings = config["codex"]
        channel = Path(settings["mailbox_dir"])
        check_channel(channel, settings["session_id"], model=settings["model"], effort=settings["reasoning_effort"],
                      generators=settings.get("generator_pool"))
        request = make_request(mission, context, config)
        from .diagnostics_contract import authorize

        authorize(root, request, config=config)
        selected = mission_identity(config, mission)
        logs = root / "logs" / mission.id
        atomic_json(logs / "codex-request.json", request)
        request_sha = publish_request(channel, request)
        try:
            response = wait_response(channel, request, request_sha)
        except (OSError, ValueError, InfrastructureError) as exc:
            # The worker may have sent a request before the connection failed.
            # Never replay it or invent an exact token count.
            missing = unavailable_usage(request)
            return Generated(missing["tokens"], {
                "backend": "codex-mailbox", "llm_calls": 1, **selected, "request_sha256": request_sha,
                **missing,
            }, str(exc), infrastructure_error=True,
                tokens_upper_bound=missing["token_accounting"] == "upper_bound")
        atomic_json(logs / "codex-response.json", response)
        usage = response.get("usage") or {}
        tokens = usage.get("tokens")
        if unlimited_tokens(config) and usage.get("token_accounting") != "exact":
            tokens = None
        if type(tokens) is not int or tokens < 0:
            if not unlimited_tokens(config):
                return Generated(TOKEN_CEILING, {"backend": "codex-mailbox", "llm_calls": 1},
                                 "Missing or excessive Codex usage", infrastructure_error=True,
                                 tokens_upper_bound=True)
            tokens = None
            usage = {**usage, "tokens": None, "token_accounting": "unknown"}
        generated = Generated(tokens, {"backend": "codex-mailbox", **usage,
                              **selected,
                              "request_sha256": request_sha}, response.get("error"),
                              response.get("infrastructure_error", False),
                              not unlimited_tokens(config) and usage.get("token_accounting") == "upper_bound")
        if not unlimited_tokens(config) and tokens > TOKEN_CEILING:
            generated.error = "Observed usage exceeded the reserved token ceiling"
            generated.infrastructure_error = True
        if generated.error:
            return generated
        if request.get("conversation") is not None:
            from .registry import Registry

            try:
                receipt = verify_receipt(request, request_sha, response)
                db = Registry(root / "registry.sqlite3")
                try:
                    db.set(f"mother_conversation:{mission.epoch}", receipt)
                    # Selection and memory reads advance the same conversation but are not code.
                    if not context.get("memory", {}).get("enabled"):
                        db.set(f"mother_plan:final_synthesis:{mission.epoch}", {
                            "status": "complete", "phase": "assembly", "final_synthesis": True,
                            "budget_phase": "postprocess", "request_sha256": request_sha,
                            "conversation": receipt, "model_calls": usage.get("llm_calls", 1),
                            "usage_charged_to_g_mission": mission.id,
                        })
                finally:
                    db.close()
                generated.usage["conversation"] = receipt
                generated.usage["mother_assembly"] = True
            except InfrastructureError as exc:
                generated.error, generated.infrastructure_error = str(exc), True
                return generated
        try:
            data = response["data"]
            if context.get("assembly_selection"):
                generated.usage["assembly_decision"] = data
                atomic_json(logs / "agent-selection.json", data)
                return generated
            rejected_lessons = []
            data, memory_read, lessons = extract_memory(data, context, rejected_lessons=rejected_lessons)
            data, research = extract_research(data, context)
            if context.get("memory", {}).get("enabled"):
                generated.usage["memory_lessons"] = lessons
                generated.usage["rejected_memory_lessons"] = rejected_lessons
            if memory_read is not None:
                generated.usage["memory_request"] = memory_read
                atomic_json(logs / "agent-memory-request.json", memory_read)
                return generated
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
            if request.get("conversation") and context.get("memory", {}).get("enabled"):
                db = Registry(root / "registry.sqlite3")
                try:
                    db.set(f"mother_plan:final_synthesis:{mission.epoch}", {
                        "status": "complete", "phase": "assembly", "final_synthesis": True,
                        "budget_phase": "postprocess", "request_sha256": request_sha,
                        "conversation": generated.usage["conversation"],
                        "model_calls": usage.get("llm_calls", 1), "usage_charged_to_g_mission": mission.id})
                finally:
                    db.close()
        except (CandidateRejected, ValueError, KeyError, TypeError) as exc:
            generated.error = f"Invalid Codex source proposal: {exc}"
        return generated
