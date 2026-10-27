"""Verified, sequential native Mother turns; never fork or silently start over."""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from .core import FileLock, InfrastructureError, atomic_json
from .native_usage import conversation_usage

OUTPUT_LIMIT = "Incomplete response returned, reason: max_output_tokens"


def recoverable_output_limit(request, response, events):
    """Only a terminal, side-effect-free steering failure may advance the chain."""
    terminal = [e for e in events if e.get("type") in {"turn.failed", "turn.completed"}]
    usage = response.get("usage") or {}
    return (request.get("active_control", {}).get("kind") == "mother"
            and request["conversation"]["phase"] == "steering"
            and response.get("error") is not None and not response.get("infrastructure_error")
            and response.get("data") is None
            and usage.get("turn_failure_messages") == [OUTPUT_LIMIT]
            and not usage.get("forbidden_tool_events") and not usage.get("tool_runtime_errors")
            and len(terminal) == 1 and terminal[0].get("type") == "turn.failed"
            and isinstance(terminal[0].get("error"), dict)
            and terminal[0]["error"].get("message") == OUTPUT_LIMIT)


def _thread_id(value) -> bool:
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except ValueError:
        return False


def validate_turn(turn: dict) -> None:
    keys = {"id", "turn", "phase", "thread_id", "previous_request_sha256"}
    if (not isinstance(turn, dict) or set(turn) != keys
            or not isinstance(turn["id"], str) or not re.fullmatch(r"[a-f0-9]{32}", turn["id"])
            or type(turn["turn"]) is not int or turn["turn"] < 0):
        raise InfrastructureError("Invalid Mother conversation turn")
    if turn["turn"] == 0:
        valid = (turn["phase"] == "planning" and turn["thread_id"] is None
                 and turn["previous_request_sha256"] is None)
    else:
        valid = (turn["phase"] in {"plan-review", "steering", "assembly"} and _thread_id(turn["thread_id"])
                 and isinstance(turn["previous_request_sha256"], str)
                 and re.fullmatch(r"[a-f0-9]{64}", turn["previous_request_sha256"]))
    if not valid:
        raise InfrastructureError("Mother may plan once, then only assemble in the same conversation")


def first_turn() -> dict:
    return {"id": uuid.uuid4().hex, "turn": 0, "phase": "planning", "thread_id": None,
            "previous_request_sha256": None}


def next_turn(receipt: dict, *, phase="assembly") -> dict:
    if (not isinstance(receipt, dict) or type(receipt.get("turn")) is not int
            or not {"id", "thread_id", "request_sha256"}.issubset(receipt)):
        raise InfrastructureError("Mother continuation requires the preceding native receipt")
    if phase in {"plan-review", "steering"} and receipt.get("phase") == "assembly":
        raise InfrastructureError("Mother cannot review the plan after assembly starts")
    if phase == "plan-review" and receipt.get("phase") == "steering":
        raise InfrastructureError("Mother cannot revise the initial plan after steering starts")
    turn = {"id": receipt["id"], "turn": receipt["turn"] + 1, "phase": phase,
            "thread_id": receipt["thread_id"], "previous_request_sha256": receipt["request_sha256"]}
    validate_turn(turn)
    return turn


def verify_receipt(request: dict, request_sha: str, response: dict) -> dict:
    turn, receipt = request["conversation"], response.get("conversation")
    validate_turn(turn)
    expected = {key: turn[key] for key in ("id", "turn", "phase")}
    if (not isinstance(receipt, dict) or set(receipt) != {*expected, "thread_id", "request_sha256"}
            or any(receipt.get(key) != value for key, value in expected.items())
            or receipt.get("request_sha256") != request_sha or not _thread_id(receipt.get("thread_id"))
            or turn["thread_id"] is not None and receipt["thread_id"] != turn["thread_id"]):
        raise InfrastructureError("Missing or mismatched native Mother conversation receipt")
    return receipt


def workspace_for(request: dict, output: Path) -> Path:
    validate_turn(request["conversation"])
    return output.parent / "conversations" / request["conversation"]["id"] / "workspace"


def run_turn(request: dict, request_sha: str, output: Path, invoke) -> dict:
    """Bind the native UUID to this channel and the exact previous successful turn."""
    turn = request["conversation"]
    validate_turn(turn)
    directory = workspace_for(request, output).parent
    with FileLock(directory / "conversation.lock"):
        path = directory / "state.json"
        previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        identity = {key: request[key] for key in ("session_id", "model", "reasoning_effort")}
        if turn["turn"] == 0:
            if previous is not None:
                raise InfrastructureError("Mother planning was already claimed; never restart its conversation")
        elif (not previous or previous.get("status") != "complete"
                or previous.get("identity") != identity or previous.get("id") != turn["id"]
                or previous.get("turn") != turn["turn"] - 1
                or previous.get("thread_id") != turn["thread_id"]
                or previous.get("request_sha256") != turn["previous_request_sha256"]):
            raise InfrastructureError("Mother continuation has no matching completed native conversation")
        if previous and previous.get("phase") == "assembly" and turn["phase"] in {"plan-review", "steering"}:
            raise InfrastructureError("Mother cannot return to planning after assembly")
        if previous and previous.get("phase") == "steering" and turn["phase"] == "plan-review":
            raise InfrastructureError("Mother cannot revise the initial plan after steering")
        state = {**turn, "identity": identity, "request_sha256": request_sha, "status": "started"}
        atomic_json(path, state)
        try:
            response = invoke()
            state["usage_cumulative"] = conversation_usage(response, previous, turn["turn"])
            events = []
            log = output / "codex.jsonl"
            for line in log.read_text(encoding="utf-8").splitlines() if log.is_file() else []:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict):
                    events.append(event)
            recoverable = recoverable_output_limit(request, response, events)
            if (not response.get("error") and not response.get("infrastructure_error")) or recoverable:
                threads = {e.get("thread_id") for e in events if e.get("type") == "thread.started"}
                try:
                    if len(threads) != 1 or not _thread_id(next(iter(threads))):
                        raise InfrastructureError("Native Mother did not identify one persisted conversation")
                    receipt = {**{key: turn[key] for key in ("id", "turn", "phase")},
                               "thread_id": threads.pop(), "request_sha256": request_sha}
                    response["conversation"] = receipt
                    verify_receipt(request, request_sha, response)
                    state.update(receipt, status="complete")
                    if recoverable:
                        # A completed native turn is not an accepted proposal.
                        # The next call uses a new nonce in this same thread.
                        state["last_outcome"] = "incomplete_output"
                        response["recovery"] = {"reason": "model_output_limit",
                                                "continuation": "same_native_thread"}
                except InfrastructureError as exc:
                    # Generation already finished: retain its measured token usage.
                    response.pop("conversation", None)
                    response.update(error=str(exc), infrastructure_error=True)
                    state["status"] = "failed"
            else:
                state["status"] = "failed"
        except BaseException:
            state["status"] = "interrupted"
            atomic_json(path, state)
            raise
        atomic_json(path, state)
        atomic_json(output / "response.json", response)
        return response
