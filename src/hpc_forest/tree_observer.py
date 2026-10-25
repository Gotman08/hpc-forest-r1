"""Isolated post-confirmation analysts; no import of Controller, Search or Registry."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from . import codex_process
from .codex_mailbox import PROTOCOL, json_bytes, sha256
from .core import FileLock, ForestError, InfrastructureError, digest
from .model_policy import require_identity
from .observer_contract import CHUNK_SIZE, PAGE_SIZE, VERSION, request_for, validate_response
from .observer_io import save


def view(dossier, read):
    """All reads are in-memory lookups: model paths never reach the filesystem."""
    records, offset = dossier["records"], read["offset"]
    if read["operation"] == "catalog":
        if offset >= len(records):
            raise InfrastructureError("Observer catalog offset is outside its records")
        page = records[offset:offset + PAGE_SIZE]
        return {"operation": "catalog", "total": len(records), "offset": offset,
                "next_offset": offset + len(page) if offset + len(page) < len(records) else None,
                "items": [{"id": r["id"], "kind": r["kind"],
                           "measured_outcome": {k: r["outcome"].get(k) for k in
                               ("status", "correct", "score", "mean_seconds", "commit")},
                           "source_paths": list(r["source_files"])} for r in page]}
    record = next((r for r in records if r["id"] == read["evidence_id"]), None)
    if record is None:
        raise InfrastructureError("Observer evidence is outside this tree")
    if read["operation"] == "source":
        if read["path"] not in record["source_files"]:
            raise InfrastructureError("Observer source is not in this evidence snapshot")
        raw = record["source_files"][read["path"]]
    elif read["operation"] == "evidence":
        raw = json.dumps({k: v for k, v in record.items() if k != "source_files"},
                         ensure_ascii=False, sort_keys=True)
    else:
        raise InfrastructureError("Unknown observation read operation")
    if offset > len(raw) or (offset == len(raw) and offset != 0):
        raise InfrastructureError("Observer text offset is outside its evidence")
    end = min(offset + CHUNK_SIZE, len(raw))
    return {**read, "total_characters": len(raw), "text": raw[offset:end],
            "next_offset": end if end < len(raw) else None, "sha256": sha256(raw.encode())}


def _read(path):
    if path.is_symlink() or not path.is_file():
        raise ForestError("Missing regular observation file: " + str(path))
    return json.loads(path.read_text(encoding="utf8"))


def _unknown_usage():
    return {"tokens": None, "token_accounting": "unknown", "llm_calls": None}


def _one(root, entry, manifest, dossier):
    directory = root / entry["directory"]
    state_path = directory / "state.json"
    if state_path.exists():
        state = _read(state_path)
        if state.get("snapshot_sha256") != entry["sha256"]:
            raise ForestError("Observer state belongs to a different snapshot")
        if state["status"] == "running":
            # The service may have completed. Do not guess its usage or replay it.
            state.update(status="interrupted_unknown", error="Interrupted observer; no automatic replay")
            for call in state["calls"]:
                if call["status"] == "running":
                    call.update(status="interrupted_unknown", usage=_unknown_usage())
            save(state_path, state)
        return state
    state = {"tree_id": entry["tree_id"], "role": entry["role"], "status": "running",
             "snapshot_sha256": entry["sha256"], "calls": [], "report": None,
             "coverage": {"catalog_ids": [], "reads": [], "total_records": len(dossier["records"])},
             "warnings": dossier["warnings"]}
    save(state_path, state)
    catalog = view(dossier, {"operation": "catalog", "offset": 0})
    visible = {item["id"] for item in catalog["items"]}
    state["coverage"]["catalog_ids"] = sorted(visible)
    history = [{"view": catalog}]
    maximum = manifest["max_calls_per_tree"]
    for index in range(1, maximum + 1):
        payload = {"mode": "observation-only", "tree": dossier["tree"],
                   "assignment": dossier["assignment"], "contract": dossier["contract"],
                   "warnings": dossier["warnings"], "history": history,
                   "call_number": index, "max_calls": maximum, "must_report": index == maximum}
        request = request_for(manifest["session_id"], entry["tree_id"], payload,
                              model=manifest["model"], effort=manifest["reasoning_effort"])
        request_hash = sha256(json_bytes(request))
        call_dir = directory / f"call-{index:02d}"
        save(call_dir / "request.json", request)
        call = {"number": index, "status": "running", "request_sha256": request_hash,
                "started": time.time(), "usage": _unknown_usage()}
        state["calls"].append(call)
        save(state_path, state)  # Durable claim BEFORE any service invocation.
        started = time.perf_counter()
        try:
            response = codex_process.run_observer(request, call_dir)
            identity = {"protocol": PROTOCOL, "session_id": request["session_id"],
                        "nonce": request["nonce"], "request_sha256": request_hash,
                        "model": manifest["model"], "reasoning_effort": manifest["reasoning_effort"]}
            if not isinstance(response, dict) or any(response.get(k) != v for k, v in identity.items()):
                raise InfrastructureError("Observer response does not match its exact request")
            call["usage"] = response.get("usage") or _unknown_usage()
            save(call_dir / "response.json", response)
            if response.get("error") or response.get("infrastructure_error"):
                raise InfrastructureError(response.get("error") or "Observer infrastructure failure")
            data = validate_response(response.get("data"), visible, final_call=index == maximum)
            call["status"] = "completed"
            if data["action"] == "report":
                state.update(status="complete", report=data)
            else:
                read = data["read"]
                page = view(dossier, read)
                if read["operation"] == "catalog":
                    visible.update(item["id"] for item in page["items"])
                    state["coverage"]["catalog_ids"] = sorted(visible)
                state["coverage"]["reads"].append({**read, "next_offset": page["next_offset"]})
                history.extend([{"analyst": data}, {"view": page}])
        except (ForestError, OSError, ValueError, TypeError) as exc:
            call.update(status="failed", error=str(exc))
            state.update(status="failed", error=str(exc))
        finally:
            call["elapsed_seconds"] = time.perf_counter() - started
            save(state_path, state)
        if state["status"] != "running":
            break
    return state


def _summary(root, manifest, states):
    calls = [call for state in states for call in state["calls"]]
    exact = [call["usage"].get("tokens") for call in calls
             if call["usage"].get("token_accounting") == "exact"
             and type(call["usage"].get("tokens")) is int and call["usage"]["tokens"] >= 0]
    value = {"schema": VERSION, "mode": "observation-only", "model": manifest["model"],
             "reasoning_effort": manifest["reasoning_effort"], "search_feedback_enabled": False,
             "complete": all(s["status"] == "complete" for s in states), "trees": states,
             "cost_scope": "Separate from search, assembly and independent confirmation",
             "usage": {"calls_claimed": len(calls), "known_tokens": sum(exact),
                       "unknown_usage_calls": len(calls) - len(exact),
                       "total_tokens": sum(exact) if len(exact) == len(calls) else None,
                       "elapsed_seconds": sum(c.get("elapsed_seconds", 0) for c in calls)}}
    save(root / "report.json", value)
    lines = ["# Analystes Forest — observation après confirmation", "",
             "Modèle : GPT-6 Luna, effort max. Ces avis ne modifient pas la recherche.", "",
             "Les constats cités restent des interprétations du modèle, à vérifier dans les preuves.",
             f"Appels revendiqués : {len(calls)} ; tokens connus : {sum(exact)} ; "
             f"appels de consommation inconnue : {len(calls) - len(exact)}.", ""]
    for state in states:
        coverage = state["coverage"]
        detailed_reads = sum(read["operation"] != "catalog" for read in coverage["reads"])
        lines += [f"## {state['role']} — {state['status']}", "",
                  f"Catalogue consulté : {len(coverage['catalog_ids'])}/{coverage['total_records']} "
                  f"preuves ; lectures détaillées : {detailed_reads}.", ""]
        if state.get("error"):
            lines += ["Erreur d’observation : " + state["error"], ""]
        report = state.get("report") or {}
        for claim in report.get("observations", []):
            lines += [f"- Constat : {claim['claim']} (preuves : {', '.join(claim['evidence_ids'])})"]
        for claim in report.get("hypotheses", []):
            lines += [f"- Hypothèse non testée : {claim['claim']} (preuves : {', '.join(claim['evidence_ids'])}). "
                      f"Test proposé : {claim['proposed_test']}. Arrêt : {claim['stop_condition']}."]
        lines += ["", *["- Limite : " + item for item in report.get("uncertainties", []) + state["warnings"]], ""]
    (root / "REPORT.md").write_text("\n".join(lines), encoding="utf8")
    return value


def run(destination: Path):
    """Run each fresh analyst once; finished or uncertain calls are never resubmitted."""
    root = destination.resolve(strict=True)
    manifest = _read(root / "manifest.json")
    require_identity(manifest)
    if (manifest.get("schema") != VERSION or manifest.get("mode") != "observation-only"
            or manifest.get("search_feedback_enabled") is not False
            or type(manifest.get("max_calls_per_tree")) is not int
            or not 1 <= manifest["max_calls_per_tree"] <= 16):
        raise ForestError("Invalid frozen observer manifest")
    if root.is_relative_to(Path(manifest["source_campaign"]).resolve()):
        raise ForestError("Observation must stay outside its source campaign")
    entries = manifest["trees"]
    if not entries or len({e["directory"] for e in entries}) != len(entries):
        raise ForestError("Invalid observer tree inventory")
    dossiers = []
    for entry in entries:
        if not re.fullmatch(r"tree-[0-9]{3,}", entry["directory"]):
            raise ForestError("Invalid observer directory")
        directory = root / entry["directory"]
        if directory.is_symlink() or directory.resolve().parent != root:
            raise ForestError("Observation directories cannot escape their batch")
        dossier = _read(directory / "snapshot.json")
        if (digest(dossier) != entry["sha256"] or dossier["tree"]["id"] != entry["tree_id"]
                or dossier["tree"]["role"] != entry["role"]):
            raise ForestError("Frozen observer evidence changed")
        dossiers.append(dossier)
    with FileLock(root / "observation.lock"):
        states = [_one(root, entry, manifest, dossier) for entry, dossier in zip(entries, dossiers, strict=True)]
        return _summary(root, manifest, states)
