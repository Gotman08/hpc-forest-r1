"""Mechanical evidence checks for closure; semantic conclusions remain hypotheses."""
from __future__ import annotations

import hashlib
import math

from .core import InfrastructureError


def packet(snapshot):
    """Re-expose analyst-cited lines to Mother; a report is not a source page.

    Keep the envelope bounded. Omitted lines stay accessible through explicit
    reads, never become proof of absence, and never authorize invented citations.
    """
    from .active_analysis import SOURCE_LIMIT, source_page

    records = {r["id"]: r for r in snapshot["records"]}
    sources, selected, omitted, seen = [], {}, [], set()
    remaining = SOURCE_LIMIT
    for analyst in snapshot["reports_as_interpretations"].values():
        for finding in analyst.get("report", {}).get("code_findings", []):
            for ref in finding["citations"]:
                identity = (ref["evidence_id"], ref["path"], ref["sha256"], ref["start_line"], ref["end_line"])
                if identity in seen:
                    continue
                seen.add(identity)
                record = records.get(ref["evidence_id"], {})
                raw = record.get("source_files", {}).get(ref["path"])
                if not isinstance(raw, str) or hashlib.sha256(raw.encode()).hexdigest() != ref["sha256"]:
                    omitted.append({"evidence_id": ref["evidence_id"], "reason": "source_unavailable"})
                    continue
                lines = raw.splitlines(keepends=True)
                lo, hi = ref["start_line"], min(ref["end_line"], ref["start_line"] + 39)
                if not 1 <= lo <= hi <= len(lines):
                    omitted.append({"evidence_id": ref["evidence_id"], "reason": "lines_unavailable"})
                    continue
                start = sum(map(len, lines[:lo - 1]))
                size = sum(map(len, lines[lo - 1:hi]))
                page = source_page(record, ref["path"], start, size)
                if not page or len(page["text"]) > remaining or len(sources) >= 24:
                    omitted.append({"evidence_id": ref["evidence_id"], "reason": "excerpt_budget"})
                    continue
                sources.append(page)
                remaining -= len(page["text"])
                selected[record["id"]] = {"evidence_id": record["id"],
                    "measured_outcome": {k: record["outcome"].get(k)
                                         for k in ("status", "correct", "mean_seconds", "score", "commit")},
                    "performance_by_configuration": record.get("performance_by_configuration")}
    return {"sources": sources, "selected_ids": list(selected), "measurements": list(selected.values()),
            "omitted": omitted, "warning": "Source excerpts are supplied evidence, not validation of the analyst's "
                "interpretation. Omitted lines require explicit source reads, not guesses."}


def check_citations(review, snapshot):
    records = {r["id"]: r for r in snapshot["records"]}
    cited = set()
    for ref in review.get("source_citations", []):
        record = records.get(ref.get("evidence_id"), {})
        text = record.get("source_files", {}).get(ref.get("path"))
        lo, hi = ref.get("start_line"), ref.get("end_line")
        if (not isinstance(text, str) or ref.get("sha256") != hashlib.sha256(text.encode()).hexdigest()
                or type(lo) is not int or type(hi) is not int or not 1 <= lo <= hi <= len(text.splitlines())
                or hi - lo >= 40 or ref["evidence_id"] not in review["evidence_ids"]):
            raise InfrastructureError("Closure needs exact source citations of at most 40 supplied lines")
        cited.add(ref["evidence_id"])
    return cited


def measured_comparison(hypothesis, review, snapshot):
    records = {r["id"]: r for r in snapshot["records"]}
    anchors = set(hypothesis["evidence_ids"])
    references = set(review["evidence_ids"])
    for identity in references:
        record = records.get(identity, {})
        mission, outcome = record.get("mission") or {}, record.get("outcome", {})
        if record.get("kind") != "trial" or mission.get("role") != hypothesis["tree"]:
            continue
        parent = mission.get("parent_id") or mission.get("base_source_id") or f"baseline-e{snapshot['epoch']}"
        before = records.get(parent, {}).get("outcome", {})
        # The actual direct comparison must be cited. It must start from a source
        # named by the hypothesis, not an unrelated measurement in the same tree.
        if parent not in references or parent not in anchors or identity == parent:
            continue
        # An incorrect child scores 0 without measuring the mechanism: it tests nothing.
        if (outcome.get("commit") and outcome["commit"] != before.get("commit")
                and outcome.get("correct") is True
                and all(type(v.get("score")) in (int, float) and math.isfinite(v["score"])
                        for v in (before, outcome))):
            return {parent, identity}
    return set()


def validate_review(hypothesis, review, snapshot):
    basis = review.get("basis")
    if review["disposition"] == "budget":
        if basis != "budget" or review.get("source_citations"):
            raise InfrastructureError("A budget review must use the budget basis without invented source proof")
        return
    cited = check_citations(review, snapshot)
    if basis == "measured_comparison":
        pair = measured_comparison(hypothesis, review, snapshot)
        if not pair or not pair <= cited:
            raise InfrastructureError("A tested/rejected hypothesis needs its cited measured parent-child comparison and source change")
    elif basis == "source_or_contract" and review["disposition"] == "rejected":
        if not cited.intersection(hypothesis["evidence_ids"]):
            raise InfrastructureError("Rejecting an untested hypothesis needs explicit source/contract evidence from that hypothesis")
    else:
        raise InfrastructureError("A tested hypothesis requires measured_comparison; an opinion alone cannot close research")
