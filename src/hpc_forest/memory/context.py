"""Bounded views assembled from durable memory, never the entire forest history."""
from __future__ import annotations

import copy

from hpc_forest.core import atomic_json, canonical
from hpc_forest.memory.contract import VERSION, active, settings
from hpc_forest.memory.retrieval import MemoryReader, evidence_ids, text_digest
from hpc_forest.support.sources import source_snapshot


def attach_memory(controller, mission, context):
    if not active(controller.config):
        return context
    cfg = settings(controller.config)
    query = context.get("research_tree", {}).get("objective", "")
    with MemoryReader(controller.root, mission, controller.config, context["protocol_id"]) as reader:
        page = reader.search(query)
        catalog = reader.catalog()
    view = {"schema": VERSION, "enabled": True, "scope": {
                "epoch": mission.epoch, "protocol_id": context["protocol_id"],
                "tree_id": mission.tree_id if mission.role != "G" else None},
            "page": page, "catalog": catalog,
            "evidence_ids": list(dict.fromkeys([*evidence_ids(page), *evidence_ids(catalog)])),
            "remaining_reads": cfg["reads_per_mission"],
            "max_result_characters": cfg["context_characters"],
            "provenance": "controller facts and separately labelled model interpretations",
            "current_base_commit": mission.base_commit, "selected_parent_id": mission.parent_id}
    atomic_json(controller.root / "logs" / mission.id / "memory-context.json", view)
    return {**context, "memory": view}


def bounded_history(history, maximum):
    """Latest compiler/checker feedback stays visible; full episodes remain on disk."""
    result = []
    for item in reversed(history):
        entry = {k: copy.deepcopy(v) for k, v in item.items() if k in {
            "attempt", "generation_id", "state", "generation_error", "development_outcome",
            "measured_diagnostics", "research_results", "memory_result"}}
        if len(canonical([entry, *result])) > maximum:
            if not result:
                entry = {k: v for k, v in entry.items() if k not in {"research_results", "memory_result"}}
                while len(canonical([entry])) > maximum:
                    before = canonical(entry)
                    for diagnostic in entry.get("measured_diagnostics", []):
                        diagnostic["text"] = diagnostic.get("text", "")[:len(diagnostic.get("text", "")) // 2]
                        diagnostic["truncated"] = True
                    outcome = entry.get("development_outcome", {})
                    outcome["reason"] = str(outcome.get("reason") or "")[:len(str(outcome.get("reason") or "")) // 2]
                    outcome["logs"] = outcome.get("logs", [])[:len(outcome.get("logs", [])) // 2]
                    if "generation_error" in entry:
                        value = str(entry["generation_error"] or "")
                        entry["generation_error"] = value[:len(value) // 2]
                    entry["details_truncated"] = True
                    if canonical(entry) == before:
                        entry = {"generation_id": item["generation_id"], "state": item["state"],
                                 "details_truncated": True}
                        break
                result.append(entry)
            break
        result.insert(0, entry)
    return result


def source_view(worktree, context):
    """Keep exact files when they fit, otherwise expose a manifest and paged reads."""
    if not context.get("memory", {}).get("enabled"):
        return source_snapshot(worktree, max_characters=32000), context
    files = source_snapshot(worktree)
    limit = context["memory"]["max_result_characters"]
    if len(canonical(files)) <= limit:
        return files, context
    context = copy.deepcopy(context)
    from hpc_forest.memory.retrieval import bounded_page

    manifest = [{"path": path, "characters": len(content), "sha256": text_digest(content)}
                for path, content in files.items()]
    context["memory"]["current_source_manifest"] = bounded_page(
        manifest, offset=0, total=len(manifest), maximum=limit)
    context["memory"]["source_read_required"] = True
    return {}, context
