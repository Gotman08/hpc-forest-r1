"""Read real Forest evidence without opening its writable Registry or unpickling trees."""
from __future__ import annotations

import csv
import difflib
import hashlib
import io
import json
import math
import sqlite3
from pathlib import Path

from ..search_diagnostics import diagnostics
from .paths import AppError, contained, relative_name
from .store import Store

TEXT_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".cu", ".cuh",
                 ".py", ".sh", ".md", ".txt", ".json", ".toml"}


def number(value):
    return value if type(value) in {int, float} and math.isfinite(value) else None


def decoded(value, default=None):
    if value is None:
        return default
    if len(value) > 8 * 1024 * 1024:
        raise AppError("Une pièce de preuve dépasse la limite de lecture.")
    try:
        return json.loads(value)
    except (ValueError, TypeError) as exc:
        raise AppError("Les preuves de cette campagne sont illisibles.") from exc


def _read(root: Path) -> dict:
    path = contained(root, "registry.sqlite3")
    if not path.is_file():
        raise AppError("Le registre de cette campagne n'est plus accessible.")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("BEGIN")
        base = ["current_epoch", "config", "identity", "best_confirmed", "status",
                "protocol_id", "started", "deadline", "advisor_totals"]
        placeholders = ",".join("?" for _ in base)
        metadata = {r["key"]: decoded(r["value"]) for r in connection.execute(
            f"SELECT key,value FROM metadata WHERE key IN ({placeholders})", base)}
        epoch = metadata.get("current_epoch", 1)
        suffixes = ["forest_plan", "active_forest", "final_g_confirmation", "postprocess",
                    "search_closed", "adaptive_budget", "pipeline_finished"]
        keys = [f"{name}:{epoch}" for name in suffixes]
        marks = ",".join("?" for _ in keys)
        metadata.update({r["key"].split(":")[0]: decoded(r["value"])
                         for r in connection.execute(
                             f"SELECT key,value FROM metadata WHERE key IN ({marks})", keys)})
        trials = [dict(r) for r in connection.execute(
            "SELECT id,trial_id,tree_id,role,state,mission,result,created FROM trials "
            "WHERE epoch=? ORDER BY created,id LIMIT 3001", (epoch,))]
        count = connection.execute("SELECT count(*) FROM trials WHERE epoch=?", (epoch,)).fetchone()[0]
        events = [dict(r) for r in connection.execute(
            "SELECT id,kind,payload,created FROM events ORDER BY id DESC LIMIT 100")]
        evaluations = [dict(r) for r in connection.execute(
            "SELECT experiment_id,phase,payload,created FROM evaluations "
            "WHERE epoch=? ORDER BY id DESC LIMIT 1000", (epoch,))]
        return {"metadata": metadata, "trials": trials[:3000], "trial_count": count,
                "events": events, "evaluations": evaluations}
    except sqlite3.DatabaseError as exc:
        raise AppError("Impossible de lire cette campagne Forest.") from exc
    finally:
        connection.close()


def _trial(row: dict) -> dict:
    mission = decoded(row["mission"], {})
    result = decoded(row["result"], {})
    return {
        "id": row["id"], "trial_id": row["trial_id"], "tree_id": row["tree_id"],
        "role": row["role"], "state": result.get("status", row["state"]),
        "parent": mission.get("parent_id"), "delegation_parent": mission.get("delegation_parent"),
        "base_source_id": mission.get("base_source_id"),
        "sources": mission.get("sources", []), "phase": mission.get("budget_phase", "search"),
        "kind": mission.get("kind", "research"), "hypothesis": mission.get("hypothesis", ""),
        "generator": mission.get("generator", {}), "search_action": mission.get("search_action", ""),
        "selection": mission.get("selection", {}),
        "transformations": mission.get("transformations", {}),
        "correct": result.get("correct"), "seconds": number(result.get("mean_seconds")),
        "score": number(result.get("score")), "reason": result.get("reason", ""),
        "commit": result.get("commit"), "base_commit": mission.get("base_commit"),
        "times": [n for v in result.get("times", []) if (n := number(v)) is not None],
        "advice_ids": mission.get("advice_ids", []),
        "control_decision_id": mission.get("control_decision_id"), "created": row["created"],
    }


def _values(value):
    return list(value.values()) if isinstance(value, dict) else value if isinstance(value, list) else []


def _research(trial: dict) -> bool:
    return (trial["phase"] == "search" and trial["kind"] != "intermediate_integration"
            and trial["role"] != "G")


class Campaigns:
    def __init__(self, store: Store):
        self.store = store

    def register(self, root: Path, name: str | None = None) -> dict:
        root = root.resolve(strict=True)
        _read(root)
        identifier = hashlib.sha256(str(root).encode()).hexdigest()[:32]
        for record in self.store.list("campaign"):
            if record["id"] == identifier:
                return record
        return self.store.create("campaign", {
            "name": name or root.name, "source_root": str(root), "access": "read_only",
        }, identifier)

    def root(self, identifier: str) -> Path:
        return Path(self.store.get(identifier, "campaign")["source_root"])

    def snapshot(self, identifier: str) -> dict:
        record = self.store.get(identifier, "campaign")
        data = _read(Path(record["source_root"]))
        m = data["metadata"]
        config = m.get("config") or {}
        epoch = m.get("current_epoch", 1)
        best = m.get("best_confirmed")
        if best and (best.get("epoch") != epoch
                     or best.get("protocol_id") != m.get("protocol_id")):
            best = None
        reference = number(best.get("reference_seconds")) if best else None
        optimized = number(best.get("mean_seconds")) if best else None
        confirmed = bool(reference and optimized and reference > 0 and optimized > 0)
        if not confirmed:
            best, reference, optimized = None, None, None
        raw_state = m.get("status", "unknown")
        active_state = {
            "running": "running", "searching": "running", "initialized": "initialized",
            "checkpointed": "checkpointed", "failed": "failed",
            "confirming": "confirming", "postprocessing": "confirming",
        }.get(raw_state)
        state = active_state or (
            ("no_gain" if best.get("is_baseline") or optimized >= reference else "confirmed")
            if best else "unconfirmed")
        trials = [_trial(row) for row in data["trials"]]
        active = m.get("active_forest") or {}
        plan = m.get("forest_plan") or {}
        children = list(plan.get("children") or [])
        children += [item for item in _values(active.get("children"))
                     if item.get("kind") != "intermediate_integration"]
        roles = [item["role"] for item in children]
        roles += [row["role"] for row in trials
                  if _research(row) and row["role"] not in roles]
        roles = list(dict.fromkeys(roles))
        trees = []
        for index, role in enumerate(roles):
            child = next((item for item in children if item["role"] == role), {})
            nodes = [trial for trial in trials if trial["role"] == role and _research(trial)]
            trees.append({
                "id": role, "index": index, "subject": child.get("subject", role),
                "objective": child.get("objective", ""), "nodes": nodes,
                "correct_count": sum(node["correct"] is True for node in nodes),
                "best_seconds": min((n["seconds"] for n in nodes
                                     if n["correct"] and n["seconds"] is not None), default=None),
            })
        identity = m.get("identity") or {}
        analyses = [{"role": role, **item} for role, item in (active.get("analysts") or {}).items()
                    if item.get("report_id") and isinstance(item.get("report"), dict)]
        decisions = _values(active.get("decisions"))
        final_g = m.get("final_g_confirmation") or {}
        postprocess = m.get("postprocess") or {}
        pipeline_complete = (postprocess.get("status") == "complete"
                             and final_g.get("status") in {"confirmed", "rejected"})
        return {
            "id": identifier, "kind": "campaign", "name": record["name"], "state": state,
            "mission_id": record.get("mission_id"), "project_id": record.get("project_id"),
            "raw_state": raw_state, "read_only": True, "epoch": epoch,
            "created": record["created"], "started": m.get("started"), "deadline": m.get("deadline"),
            "finished": m.get("pipeline_finished"),
            "model": (config.get("codex") or {}).get("model"),
            "effort": (config.get("codex") or {}).get("reasoning_effort"),
            "backend": config.get("backend"), "problem": config.get("problem"),
            "search_diagnostics": diagnostics(config, data["trials"]),
            "advisor": {"enabled": config.get("advisor", {}).get("enabled", False),
                        "model": "TabPFN-3.5", **m.get("advisor_totals", {})},
            "target": identity.get("target", config.get("target_id", "")),
            "host": identity.get("hostname", ""), "machine": identity.get("machine", ""),
            "compiler": (identity.get("compiler") or {}).get("flavor", ""),
            "protocol_id": m.get("protocol_id"), "confirmation_repetitions":
                (config.get("protocol") or {}).get("confirmation_repetitions"),
            "seconds": optimized, "reference_seconds": reference,
            "speedup": reference / optimized if confirmed else None,
            "best_confirmed": best, "final_g_status": final_g.get("status"),
            "pipeline_complete": pipeline_complete,
            "trees": trees, "trial_count": data["trial_count"],
            "truncated": data["trial_count"] > len(trials),
            "integrations": [t for t in trials if not _research(t)],
            "analyses": analyses, "decisions": decisions,
            "analyst_mode": (config.get("forest", {}).get("active") or {}).get("mode", "off"),
            "closure": (active.get("lifecycle") or {}).get("closing"),
            "closure_history": (active.get("lifecycle") or {}).get("closure_history", []),
            "search_stop_reason": postprocess.get("search_stop_reason"),
            "budget": m.get("adaptive_budget"),
            "events": [{**row, "payload": decoded(row["payload"], {})} for row in data["events"]],
            "downloads": {
                "code": confirmed and pipeline_complete
                    and (Path(record["source_root"]) / "submission.zip").is_file(),
                "report": (Path(record["source_root"]) / "report/rapport.md").is_file(),
                "csv": data["trial_count"] <= len(trials),
            },
        }

    def list(self) -> list[dict]:
        result = []
        for record in self.store.list("campaign"):
            try:
                snapshot = self.snapshot(record["id"])
                result.append({key: snapshot[key] for key in [
                    "id", "kind", "name", "state", "created", "started", "host", "target",
                    "speedup", "seconds", "reference_seconds", "trial_count", "read_only",
                    "mission_id", "project_id"]})
            except (AppError, OSError):
                result.append({"id": record["id"], "kind": "campaign", "name": record["name"],
                               "state": "unavailable", "created": record["created"],
                               "read_only": True, "speedup": None,
                               "mission_id": record.get("mission_id"),
                               "project_id": record.get("project_id")})
        return result

    def trial(self, identifier: str, trial_id: str) -> dict:
        data = _read(self.root(identifier))
        row = next((row for row in data["trials"] if row["id"] == trial_id), None)
        if row is None:
            raise AppError("Cette variante n'est pas dans la campagne affichée.")
        trial = _trial(row)
        root = self.root(identifier)
        folder = contained(root, "worktrees/" + relative_name(trial_id))
        paths = []
        if folder.is_dir():
            for path in folder.rglob("*"):
                if len(paths) >= 200:
                    break
                if (path.is_file() and not path.is_symlink()
                        and (path.suffix.lower() in TEXT_SUFFIXES or path.name == "Makefile")):
                    name = path.relative_to(folder).as_posix()
                    contained(folder, name)
                    if path.stat().st_size <= 256 * 1024:
                        paths.append(name)
        trial["files"] = sorted(paths)
        trial["evaluations"] = [{**row, "payload": decoded(row["payload"], {})}
                                for row in data["evaluations"] if row["experiment_id"] == trial_id]
        return trial

    def source(self, identifier: str, trial_id: str, name: str) -> dict:
        trial = self.trial(identifier, trial_id)
        name = relative_name(name)
        if name not in trial["files"]:
            raise AppError("Ce fichier n'est pas disponible dans cette variante.")
        root = self.root(identifier)
        file = contained(root, "worktrees/" + relative_name(trial_id) + "/" + name)
        content = file.read_text(encoding="utf-8", errors="replace")
        # The imported repo contains the initial snapshot; report the comparison's scope.
        baseline = contained(root / "repo", name)
        diff_available = not baseline.is_file() or baseline.stat().st_size <= 256 * 1024
        before = baseline.read_text(encoding="utf-8", errors="replace") if (
            baseline.is_file() and diff_available) else ""
        diff = "".join(difflib.unified_diff(
            before.splitlines(keepends=True), content.splitlines(keepends=True),
            fromfile="reference/" + name, tofile=trial_id + "/" + name)) if diff_available else ""
        return {"path": name, "content": content, "diff": diff[:256 * 1024],
                "diff_available": diff_available,
                "diff_truncated": len(diff) > 256 * 1024,
                "comparison": "reference", "commit": trial["commit"]}

    def download(self, identifier: str, kind: str) -> Path:
        snapshot = self.snapshot(identifier)
        names = {"code": "submission.zip", "report": "report/rapport.md"}
        if kind not in names or not snapshot["downloads"].get(kind):
            raise AppError("Ce livrable n'est pas disponible ou n'a pas été confirmé.")
        return contained(self.root(identifier), names[kind])

    def csv(self, identifier: str) -> str:
        data = _read(self.root(identifier))
        if data["trial_count"] > len(data["trials"]):
            raise AppError("Cette campagne dépasse 3 000 essais ; utilisez son export Forest complet.")
        output = io.StringIO()
        fields = ["id", "tree_id", "role", "parent", "phase", "state", "correct", "seconds", "commit", "reason",
                  "generator_model", "generator_effort", "search_action", "expansion", "selection_seconds"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        config = data["metadata"].get("config", {})
        for row in data["trials"]:
            trial = _trial(row)
            selected = (trial["generator"] or config.get("codex", {})) if config.get("backend") == "codex" else {}
            trial.update(generator_model=selected.get("model"), generator_effort=selected.get("reasoning_effort"),
                         expansion=trial["selection"].get("expansion"), selection_seconds=trial["selection"].get("seconds"))
            for key, value in trial.items():
                if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                    trial[key] = "'" + value
            writer.writerow(trial)
        return "\ufeff" + output.getvalue()
