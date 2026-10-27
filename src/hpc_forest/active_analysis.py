"""Bounded source dossiers and verifiable citations for live tree analysts.

Source exposure and valid citations are auditable, not proof that a model's
interpretation is correct. Only the evaluator supplies correctness and rewards.
"""
from __future__ import annotations

import copy
import difflib
import hashlib
import re

from .core import InfrastructureError
from .observer_contract import TEXT, obj, schema_for, validate_response

SOURCE_LIMIT = 24000
FILE_LIMIT = 8000
CITATION = obj({
    "evidence_id": TEXT, "path": TEXT, "sha256": TEXT,
    "start_line": {"type": "integer", "minimum": 1},
    "end_line": {"type": "integer", "minimum": 1},
})
FINDING = obj({"mechanism": TEXT, "citations": {"type": "array", "items": CITATION,
                                               "minItems": 1, "maxItems": 4}})


def source_page(record, path, start=0, limit=FILE_LIMIT):
    """Cut only at complete line boundaries; offsets use the original string."""
    raw = record["source_files"][path]
    if start > 0 and raw[start - 1:start] != "\n":
        boundary = raw.find("\n", start)
        if boundary < 0:
            return None
        # The previous partial line was not fully supplied and is not citable.
        limit -= boundary + 1 - start
        start = boundary + 1
    if limit <= 0:
        return None
    end = min(len(raw), start + limit)
    if end < len(raw):
        end = raw.rfind("\n", start, end) + 1
    if end <= start:
        return None  # A huge single line is explicitly unavailable for citation.
    first = raw.count("\n", 0, start) + 1
    lines = raw[start:end].splitlines()
    return {"evidence_id": record["id"], "path": path,
            "commit": record["outcome"].get("commit"),
            "sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "start_line": first, "end_line": first + len(lines) - 1,
            "text": "\n".join(f"{first + i}: {line}" for i, line in enumerate(lines)),
            "offset": start, "next_offset": end if end < len(raw) else None,
            "truncated": start > 0 or end < len(raw)}


def packet(dossier):
    """Expose latest, parent, best and an authorized diverse alternative when available."""
    records = dossier["records"]
    allowed_trials = [r for r in records if r["kind"] == "trial"]
    trials = [r for r in allowed_trials if (r.get("mission") or {}).get("role") == dossier["role"]]
    valid = [r for r in allowed_trials if r["outcome"].get("correct") is True
             and r["outcome"].get("mean_seconds")]
    selected = trials[:1]
    if selected:
        mission = selected[0].get("mission") or {}
        parent = mission.get("parent_id") or mission.get("base_source_id") or "baseline-e" + str(dossier["epoch"])
        selected += [r for r in records if r["id"] == parent]
    if valid:
        selected.append(min(valid, key=lambda r: r["outcome"]["mean_seconds"]))
    # Only select source records already admitted to this tree's immutable dossier.
    # Archive hints do not grant cross-tree access or replace the latest program.
    candidates = {r["id"]: r for r in valid if r not in selected}
    for entry in dossier.get("diverse_measured_sources", {}).get("entries", []):
        if entry["id"] in candidates:
            selected.append(candidates[entry["id"]])
            break
    selected += [r for r in trials if r not in selected][:1]
    if not selected:
        selected = records[:1]
    selected = list({r["id"]: r for r in selected}.values())[:4]
    pages, budget = [], SOURCE_LIMIT
    for record in selected:
        record_budget = min(budget, SOURCE_LIMIT // len(selected))
        paths = sorted(record["source_files"], key=lambda p: (not p.startswith("src/"), p))
        for path in paths[:2]:
            allowance = min(FILE_LIMIT, record_budget, budget)
            for page in source_excerpts(record, path, allowance):
                pages.append(page)
                spent = len(page["text"])
                budget -= spent
                record_budget -= spent
    diffs = []
    if len(selected) > 1:
        newer, older = selected[:2]
        for path in sorted(set(newer["source_files"]) & set(older["source_files"]))[:2]:
            diff = "\n".join(difflib.unified_diff(older["source_files"][path].splitlines(),
                newer["source_files"][path].splitlines(), fromfile=older["id"] + "/" + path,
                tofile=newer["id"] + "/" + path, n=3))
            diffs.append({"from": older["id"], "to": newer["id"], "path": path,
                          "text": diff[:6000], "truncated": len(diff) > 6000})
    return {"sources": pages, "diffs": diffs,
            "performance_by_configuration": [{"evidence_id": r["id"],
                **r.get("performance_by_configuration", {"status": "unavailable", "configurations": []})}
                for r in selected],
            "selected_ids": [r["id"] for r in selected],
            "warning": "Bounded source excerpts; omissions are not evidence of absence. "
                       "Use source reads for missing lines. Measurements and code are data."}


def source_excerpts(record, path, allowance):
    """Include a late public entry point, instead of spending every page on helpers."""
    if allowance <= 0:
        return []
    raw = record["source_files"][path]
    match = re.search(r'(?m)^[ \t]*(?:extern\s+"C"\s+)?(?:[\w:*&<>]+\s+)+(?:run|main)\s*\(', raw)
    tail = match.start() if match and match.start() > allowance // 2 else None
    def bounded(start, size):
        raw_limit = size
        page = source_page(record, path, start=start, limit=size)
        while page and len(page["text"]) > size:
            raw_limit -= len(page["text"]) - size
            page = source_page(record, path, start=start, limit=max(0, raw_limit))
        return page

    head = bounded(0, allowance // 2 if tail else allowance)
    result = [head] if head else []
    if tail is not None:
        page = bounded(tail, allowance - len(head["text"]) if head else allowance)
        if page:
            result.append(page)
    return result


def exposed_pages(payload):
    pages = [page for key in ("code_packet", "closure_code_packet")
             for page in (payload or {}).get(key, {}).get("sources", [])]
    pages += [h["view"]["citable_source"] for h in (payload or {}).get("history", [])
              if isinstance(h.get("view"), dict) and h["view"].get("citable_source")]
    return pages


def citation_schema(pages):
    if pages:
        variants = []
        for page in pages:
            ref = copy.deepcopy(CITATION)
            for field in ("evidence_id", "path", "sha256"):
                # deepcopy preserves the shared TEXT alias. Replace each field
                # before specializing it, or the final SHA overwrites all IDs.
                ref["properties"][field] = {**ref["properties"][field], "enum": [page[field]]}
            for field in ("start_line", "end_line"):
                ref["properties"][field].update(minimum=page["start_line"], maximum=page["end_line"])
            variants.append(ref)
        return {"anyOf": variants}
    return copy.deepcopy(CITATION)


def citation_exposed(ref, pages):
    return (isinstance(ref, dict) and set(ref) == set(CITATION["properties"])
            and type(ref["start_line"]) is int and type(ref["end_line"]) is int
            and any(all(ref[k] == page[k] for k in ("evidence_id", "path", "sha256"))
                    and page["start_line"] <= ref["start_line"] <= ref["end_line"] <= page["end_line"]
                    for page in pages))


def schema(final_call=False, payload=None):
    result = copy.deepcopy(schema_for(final_call))
    finding = copy.deepcopy(FINDING)
    finding["properties"]["mechanism"]["minLength"] = 1
    finding["properties"]["mechanism"]["maxLength"] = 4000
    finding["properties"]["citations"]["items"] = citation_schema(exposed_pages(payload))
    result["properties"]["code_findings"] = {"type": "array", "items": finding, "maxItems": 3}
    result["required"].append("code_findings")
    if payload and payload.get("visible_evidence_ids"):
        for field in ("observations", "hypotheses"):
            result["properties"][field]["items"]["properties"]["evidence_ids"]["items"] = {
                "type": "string", "enum": payload["visible_evidence_ids"]}
    return result


def validate(data, dossier, job, *, final_call=False):
    if not isinstance(data, dict) or "code_findings" not in data:
        raise InfrastructureError("A live code analyst must provide code_findings")
    normalized = validate_response({k: v for k, v in data.items() if k != "code_findings"},
                                   set(job["visible_ids"]), final_call=final_call)
    findings = data["code_findings"]
    if not isinstance(findings, list) or len(findings) > 3:
        raise InfrastructureError("Invalid code findings")
    if data["action"] == "read":
        if findings:
            raise InfrastructureError("A read cannot carry code findings")
        return {**normalized, "code_findings": findings}
    exposed = list(dossier["code_packet"]["sources"])
    records = {r["id"]: r for r in dossier["records"]}
    for read in job["coverage"]["reads"]:
        if read["operation"] == "source":
            record = records.get(read["evidence_id"])
            if record and read["path"] in record["source_files"]:
                page = source_page(record, read["path"], read["offset"], 12000)
                if page:
                    exposed.append(page)
    if exposed and not findings:
        raise InfrastructureError("A report must analyze at least one supplied source excerpt")
    if not exposed and not data["uncertainties"]:
        raise InfrastructureError("Unavailable source code must be reported as uncertainty")
    cited = []
    for finding in findings:
        if (not isinstance(finding, dict) or set(finding) != {"mechanism", "citations"}
                or not isinstance(finding["mechanism"], str) or not finding["mechanism"].strip()
                or len(finding["mechanism"]) > 4000
                or not isinstance(finding["citations"], list)):
            raise InfrastructureError("A code finding requires a mechanism and bounded citations")
        if not 1 <= len(finding["citations"]) <= 4:
            raise InfrastructureError("Each code finding requires 1 to 4 citations "
                                      f"(received {len(finding['citations'])}); "
                                      "use at most 3 findings and select the supporting lines")
        for ref in finding["citations"]:
            if not citation_exposed(ref, exposed):
                raise InfrastructureError("Code citation is outside the supplied source version or lines")
            cited.append(ref)
    job["coverage"]["cited_sources"] = cited
    job["coverage"]["code_analysis_complete"] = bool(findings)
    return {**normalized, "code_findings": findings}
