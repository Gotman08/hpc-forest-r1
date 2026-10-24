"""Durable, budgeted live analysts and sequential Mother decisions.

Only exchange() runs in worker threads. The controller owns snapshots, usage,
receipts, state transitions and application; uncertain invocations never replay.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from . import codex_mailbox as mailbox
from .active_contract import VERSION, rendered, settings, validate_decision
from .active_snapshot import freeze, watermark
from .active_state import apply, key, state
from .adaptive_budget import admit, record_timing
from .codex_conversation import next_turn, verify_receipt
from .core import BudgetExhausted, InfrastructureError, atomic_json, digest
from .observer_contract import validate_response
from .tree_observer import view


def job_key(identity):
    return "active_control:" + identity


def save(controller, job):
    controller.db.set(job_key(job["id"]), job)
    atomic_json(controller.root / "logs" / job["id"] / "state.json", job)


def snapshot(controller, job):
    value = json.loads((controller.root / "logs" / job["id"] / "snapshot.json").read_text(encoding="utf8"))
    if value["snapshot_id"] != job["snapshot_id"] or digest({k: v for k, v in value.items() if k != "snapshot_id"}) != value["snapshot_id"]:
        raise InfrastructureError("An active control snapshot changed")
    return value


def create(controller, epoch, kind, role=None):
    dossier = freeze(controller, epoch, role)
    initial = view(dossier, {"operation": "catalog", "offset": 0})
    identity = "active-" + kind + "-" + uuid.uuid4().hex
    job = {"id": identity, "epoch": epoch, "kind": kind, "role": role,
           "budget_role": "@" + kind + (":" + role if role else ""),
           "snapshot_id": dossier["snapshot_id"], "status": "ready", "calls": [],
           "visible_ids": sorted({item["id"] for item in initial["items"]} | {
               item["id"] for tree in dossier["trees"].values() for item in tree["measured_examples"]}),
           "history": [{"view": initial}], "coverage": {"reads": [], "total_records": len(dossier["records"])},
           "maximum": settings(controller.config)["analysis_calls" if kind == "analyst" else "steering_calls"]}
    if kind == "mother" and controller.db.get(f"active_mother_rejection:{epoch}"):
        job["history"].append({"controller_rejection": controller.db.get(f"active_mother_rejection:{epoch}")})
    atomic_json(controller.root / "logs" / identity / "snapshot.json", dossier)
    current = state(controller.db, epoch)
    current["jobs"].append(identity)
    if kind == "analyst":
        previous = current["analysts"].get(role, {})
        current["analysts"][role] = {**previous, "watermark": watermark(controller.db, epoch, role),
                                    "last_job": identity, "status": "running"}
    else:
        current["mother_watermark"] = report_watermark(current)
    save(controller, job)
    controller.db.set(key(epoch), current)
    return job


def report_watermark(current):
    return digest({role: item.get("report_id") for role, item in current["analysts"].items()
                   if item.get("report_id")})


def begin_call(controller, job):
    """Claim before publishing, once per native call; every read needs admission."""
    db, role = controller.db, job["budget_role"]
    admit(db, [role])
    slot = db.reserve("search", role)
    dossier = snapshot(controller, job)
    number = len(job["calls"]) + 1
    # If there is room for only one nominal call, ask for a report immediately.
    from .independent_budget import forecast_independent

    estimate = forecast_independent(db, [role])
    nominal = estimate["next_work_seconds"]
    last = (number == job["maximum"] or estimate["remaining_seconds"] is not None
            and estimate["remaining_seconds"] < estimate["reserve_seconds"] + 2 * nominal)
    payload = {k: dossier[k] for k in ("snapshot_id", "plan_revision", "trees", "contract", "warnings",
                                      "reports_as_interpretations", "inflight")}
    payload.update(mode=settings(controller.config)["mode"], budget=estimate, history=job["history"],
                   visible_evidence_ids=job["visible_ids"],
                   call_number=number, max_calls=job["maximum"], must_finish=last)
    cfg = controller.config["codex"]
    request = {"protocol": mailbox.PROTOCOL, "kind": "source-proposal", "nonce": uuid.uuid4().hex,
               "session_id": cfg["session_id"], "model": cfg["model"], "reasoning_effort": cfg["reasoning_effort"],
               "mission_id": job["id"] + f"-call-{number:02d}", "integration_source_ids": [],
               "expires_at": None, "token_ceiling": None, "token_policy": "observe-only",
               "deadline_policy": "finish-started", "budget_phase": "search",
               "archive_request_after_response": True,
               "active_control": {"version": VERSION, "kind": job["kind"], "snapshot_id": job["snapshot_id"]},
               "meta_role": "active-" + job["kind"], **rendered(job["kind"], payload)}
    if job["kind"] == "mother":
        request["conversation"] = next_turn(db.get(f"mother_conversation:{job['epoch']}"), phase="steering")
    directory = controller.root / "logs" / job["id"] / f"call-{number:02d}"
    atomic_json(directory / "request.json", request)
    sha = mailbox.sha256(mailbox.json_bytes(request))
    call = {"number": number, "slot_id": slot, "request_sha256": sha, "request": request,
            "status": "claimed", "started_at": time.time(), "must_finish": last}
    job["calls"].append(call)
    job["status"] = "running"
    save(controller, job)
    try:
        actual = mailbox.publish_request(Path(cfg["mailbox_dir"]), request)
        if actual != sha:
            raise InfrastructureError("Control request identity changed on publication")
    except (OSError, ValueError, InfrastructureError) as exc:
        finish_call(controller, job, exc, time.time())
        return None
    return request, sha, directory


def exchange(channel, request, sha, directory):
    try:
        response = mailbox.wait_response(channel, request, sha)
        atomic_json(directory / "response.json", response)
    except Exception as exc:
        response = exc
    return response, time.time()


def finish_call(controller, job, response, finished):
    db, epoch = controller.db, job["epoch"]
    call = job["calls"][-1]
    request, sha = call["request"], call["request_sha256"]
    expected = mailbox.response_envelope(request, sha)
    bound = isinstance(response, dict) and all(response.get(k) == v for k, v in expected.items())
    usage = (response.get("usage") or {}) if bound else {}
    if not isinstance(usage, dict):
        usage = {}
    tokens = usage.get("tokens")
    exact = usage.get("token_accounting") == "exact" and type(tokens) is int and tokens >= 0
    db.settle_tokens(call["slot_id"], tokens if exact else None)
    call.update(usage=usage or mailbox.unavailable_usage(request), elapsed_seconds=max(0, finished - call["started_at"]))
    record_timing(db, "generation:" + job["budget_role"], call["elapsed_seconds"])
    receipt, rejected_data = None, None
    try:
        if isinstance(response, Exception):
            raise InfrastructureError(str(response))
        if not bound:
            raise InfrastructureError("Active response is unrelated to its claimed request")
        if response.get("error") or response.get("infrastructure_error"):
            raise InfrastructureError(response.get("error") or "Active model infrastructure failure")
        if job["kind"] == "mother":
            receipt = verify_receipt(request, sha, response)
            db.set(f"mother_conversation:{epoch}", receipt)
        dossier = snapshot(controller, job)
        try:
            data = (validate_response(response.get("data"), set(job["visible_ids"]), final_call=call["must_finish"])
                    if job["kind"] == "analyst" else
                    validate_decision(response.get("data"), dossier, set(job["visible_ids"]), final_call=call["must_finish"]))
        except InfrastructureError:
            rejected_data = {"rejected_response": response.get("data")}
            raise
        if job["kind"] == "mother":
            db.set(f"active_mother_rejection:{epoch}", None)
        job.pop("error", None)
        call["status"] = "complete"
        if data["action"] == "read":
            page = view(dossier, data["read"])
            if data["read"]["operation"] == "catalog":
                job["visible_ids"] = sorted(set(job["visible_ids"]) | {r["id"] for r in page["items"]})
            job["coverage"]["reads"].append({**data["read"], "next_offset": page["next_offset"]})
            job["history"].extend([{job["kind"]: data}, {"view": page}])
            job["status"] = "ready"
        else:
            job.update(status="complete", report=data)
            if job["kind"] == "mother":
                job["application"] = apply(db, epoch, job["id"], dossier, data)
            else:
                current = state(db, epoch)
                previous = current["analysts"][job["role"]]
                previous.update(status="complete", report_id=job["id"], report=data,
                                coverage={**job["coverage"], "visible_ids": job["visible_ids"]})
                db.set(key(epoch), current)
    except (InfrastructureError, OSError, ValueError, TypeError, KeyError) as exc:
        job.update(status="unavailable", error=str(exc))
        call.update(status="failed", error=str(exc))
        if rejected_data is not None:
            rejection = {"job_id": job["id"], "reason": str(exc),
                         "instruction": "No action was applied. Correct the response within the existing contract and call allowance."}
            job["history"].append({**rejected_data, "controller_rejection": rejection})
            if job["kind"] == "mother":
                db.set(f"active_mother_rejection:{epoch}", rejection)
            if not call["must_finish"] and len(job["calls"]) < job["maximum"]:
                job["status"] = "ready"
        if job["kind"] == "mother" and receipt is None:
            db.set(f"active_mother_broken:{epoch}", {"job_id": job["id"], "error": str(exc)})
        if job["kind"] == "analyst" and job["status"] == "unavailable":
            current = state(db, epoch)
            current["analysts"][job["role"]]["status"] = "unavailable"
            db.set(key(epoch), current)
    save(controller, job)
    db.event("active_control_call", {"job_id": job["id"], "role": job["role"], "kind": job["kind"],
        "snapshot_id": job["snapshot_id"], **{k: v for k, v in call.items() if k != "request"}})


def stop_unadmitted(controller, job):
    job.update(status="unavailable", error="No remaining admission budget for the requested read/report")
    if job["kind"] == "analyst":
        current = state(controller.db, job["epoch"])
        current["analysts"][job["role"]]["status"] = "unavailable"
        controller.db.set(key(job["epoch"]), current)
    save(controller, job)


def recover(controller, epoch):
    """Recover durable replies once; never re-publish a claimed invocation."""
    ready = []
    for identity in state(controller.db, epoch)["jobs"]:
        job = controller.db.get(job_key(identity))
        if not job:
            raise InfrastructureError("Active control ledger has a missing job")
        if job["status"] == "running":
            call = job["calls"][-1]
            directory = controller.root / "logs" / identity / f"call-{call['number']:02d}"
            path = directory / "response.json"
            channel = Path(controller.config["codex"]["mailbox_dir"])
            try:
                if path.exists():
                    response = mailbox.bounded_json(path)
                elif (channel / "responses" / (call["request"]["nonce"] + ".ready.json")).exists():
                    response = mailbox.wait_response(channel, call["request"], call["request_sha256"])
                    atomic_json(path, response)
                else:
                    raise InfrastructureError("Interrupted control call; usage unknown, no automatic replay")
            except (OSError, ValueError, InfrastructureError) as exc:
                response = exc
            finish_call(controller, job, response, time.time())
        if job["status"] == "ready":
            ready.append(job)
    return ready


def admit_call(controller, job):
    try:
        return begin_call(controller, job)
    except BudgetExhausted:
        stop_unadmitted(controller, job)
        return None
