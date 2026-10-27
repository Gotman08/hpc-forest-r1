"""Bounded advice over real TreeQuest parent proposals before generation.

Only measured rewards update Forest. TabPFN estimates the NEXT child's runtime
value gain from the parent's code and trajectory, never from the child's result.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import time
import uuid
from contextlib import ExitStack, contextmanager
from pathlib import Path, PurePosixPath, PureWindowsPath

from .adaptive_budget import admission_deadline
from .advisor_features import FEATURES, HISTORY, feature_vector, trajectory
from .advisor_value import POLICY as RUNTIME_POLICY
from .advisor_value import TARGET as RUNTIME_TARGET
from .advisor_value import from_log_ratio, measured
from .core import FileLock, ForestError, InfrastructureError, atomic_json, digest, run_process
from .support.sources import committed_source_snapshot

VERSION = "forest-tabpfn-advisor-v3-runtime-evidence"
PACKAGE_VERSION = "9.2.0"
MODEL_VERSION = "v3.5"
DEFAULT = {"enabled": False, "min_samples": 8, "max_samples": 128,
           "exploration_every": 4, "max_call_seconds": 20, "max_budget_fraction": 0.05,
           "context_scope": "campaign", "validation_policy": RUNTIME_POLICY}


def settings(config):
    value = config.get("advisor", {})
    if not isinstance(value, dict) or set(value) - set(DEFAULT):
        raise ForestError("Invalid TabPFN advisor settings")
    result = {**DEFAULT, **value}
    if type(result["enabled"]) is not bool:
        raise ForestError("advisor.enabled must be boolean")
    if result["context_scope"] not in ("campaign", "tree"):
        raise ForestError("advisor.context_scope must be campaign or tree")
    if result["validation_policy"] not in ("gain_rank_v2", "decision_calibrated_v1", RUNTIME_POLICY):
        raise ForestError("Unknown advisor.validation_policy")
    for name, low, high in (("min_samples", 8, 1000), ("max_samples", 8, 1000),
                            ("exploration_every", 2, 10), ("max_call_seconds", 1, 120)):
        if type(result[name]) is not int or not low <= result[name] <= high:
            raise ForestError(f"advisor.{name} must be an integer in [{low},{high}]")
    if result["max_samples"] < result["min_samples"]:
        raise ForestError("Advisor context must hold at least min_samples")
    fraction = result["max_budget_fraction"]
    if type(fraction) not in (int, float) or not math.isfinite(fraction) or not 0 < fraction <= 0.1:
        raise ForestError("advisor.max_budget_fraction must be in (0,0.1]")
    return result


def runtime(config):
    value = config.get("advisor_runtime", {})
    if (not isinstance(value, dict) or set(value) - {"python", "model_path", "model_sha256"}
            or any(not isinstance(v, str) or not v for v in value.values())):
        raise ForestError("Invalid controller-owned advisor runtime")
    if value and (set(value) != {"python", "model_path", "model_sha256"}
                  or not re.fullmatch(r"[0-9a-f]{64}", value["model_sha256"])):
        raise ForestError("Pin the advisor interpreter, checkpoint and SHA-256")
    for name in ("python", "model_path"):
        path = value.get(name)
        if path and (any(c in path for c in "\r\n\x00")
                     or not (PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute())
                     or ".." in PurePosixPath(path.replace("\\", "/")).parts):
            raise ForestError("Advisor runtime requires absolute paths without parent traversal")
    return value


def _baseline(db, epoch):
    row = db.one("SELECT payload FROM evaluations WHERE experiment_id=? AND phase='search'",
                 (f"baseline-e{epoch}",))
    return json.loads(row["payload"]).get("mean_seconds") if row else None


def _normalized_sources(files):
    # Git autocrlf may normalize text on commit; use the same representation on
    # both sides. Other source changes must still invalidate the example.
    return {name: text.replace("\r\n", "\n") for name, text in files.items()}


def target_kind(config):
    return RUNTIME_TARGET if settings(config)["validation_policy"] == RUNTIME_POLICY else "child_minus_parent_measured_score"


def _timing_features(controller, mission):
    from .observer_snapshot import _diagnostics
    from .performance_evidence import features, profile

    db = controller.db
    base = db.one("SELECT payload FROM evaluations WHERE experiment_id=? AND phase='search'",
                  (f"baseline-e{mission.epoch}",))
    baseline = json.loads(base["payload"]) if base else {}
    epoch = db.one("SELECT base_commit FROM epochs WHERE id=?", (mission.epoch,))
    fallback = baseline if epoch and mission.base_commit == epoch["base_commit"] else {}
    parent = next((json.loads(r["result"]) for r in db.rows(
        "SELECT result FROM trials WHERE epoch=? AND state<>'pending' ORDER BY created DESC,id",
        (mission.epoch,)) if json.loads(r["result"] or "{}").get("commit") == mission.base_commit), fallback)
    # Inputs are immutable measured parent/baseline artifacts, never candidate files.
    profiles = [profile(_diagnostics(controller.root, item)) for item in (parent, baseline)]
    return features(*profiles)


def capture(controller, mission, *, persist=True):
    """Freeze the immutable PARENT and trajectory before any child is generated."""
    if (not settings(controller.config)["enabled"] or mission.budget_phase != "search"
            or mission.role == "G" or mission.role.startswith("Gm")):
        return None
    key = "advisor_features:" + mission.id
    existing = controller.db.get(key)
    if existing:
        if existing.get("schema") != VERSION or existing.get("target_kind") != target_kind(controller.config):
            raise ForestError("Advisor feature contract changed; start a new campaign")
        return existing
    files = _normalized_sources(committed_source_snapshot(controller.root / "repo", mission.base_commit))
    deadline = admission_deadline(controller.db)
    remaining = max(0.0, min(1.0, (deadline - time.time()) / controller.config["budget"]["wall_seconds"])) \
        if deadline is not None else 1.0
    ratio, history = trajectory(controller.db, mission, _baseline(controller.db, mission.epoch), remaining)
    features = feature_vector(files, mission, ratio)
    from .performance_evidence import FEATURES as TIMINGS

    features[-len(HISTORY) - len(TIMINGS):-len(HISTORY)] = _timing_features(controller, mission)
    features[-len(HISTORY):] = history
    entry = {"id": mission.id, "epoch": mission.epoch, "role": mission.role,
             "protocol_id": controller.db.get("protocol_id"), "schema": VERSION,
             "source_sha256": digest(files), "captured_at": time.time(), "parent_id": mission.parent_id,
             "parent_commit": mission.base_commit, "parent_score": history[0],
             "feature_stage": "before_generation", "target_kind": target_kind(controller.config),
             "parent_value": from_log_ratio(ratio) if history[1] else 0.0,
             "features": features}
    if persist:
        controller.db.set(key, entry)
    return entry


def observe(controller, mission, outcome):
    if not settings(controller.config)["enabled"]:
        return
    entry = controller.db.get("advisor_features:" + mission.id)
    if (not entry or outcome.correct not in (True, False)
            or type(outcome.score) not in (int, float) or not math.isfinite(outcome.score)
            or not 0 <= outcome.score <= 1
            or outcome.status in {"duplicate", "infrastructure_error", "cancelled_budget"}
            or (outcome.correct is True and (outcome.status != "valid" or not outcome.commit
                or type(outcome.mean_seconds) not in (int, float)
                or not math.isfinite(outcome.mean_seconds) or outcome.mean_seconds <= 0))
            or (outcome.correct is False and outcome.score != 0)):
        return
    # Check lineage, not equality of parent and child code. Failed candidates with
    # an actual zero reward are informative; infrastructure has no training label.
    if mission.base_commit != entry["parent_commit"] or mission.parent_id != entry["parent_id"]:
        controller.db.event("advisor_sample_rejected", {"id": mission.id, "reason": "lineage_changed"})
        return
    value = None
    if entry["target_kind"] == RUNTIME_TARGET:
        try:
            value = measured(_baseline(controller.db, mission.epoch), outcome.mean_seconds, outcome.correct)
        except ValueError:
            controller.db.event("advisor_sample_rejected", {"id": mission.id, "reason": "missing_runtime_value"})
            return
    sample = {**entry, "commit": outcome.commit, "mean_seconds": outcome.mean_seconds,
              "correct": outcome.correct, "status": outcome.status, "measured_score": outcome.score,
              "target": value - entry["parent_value"] if value is not None else outcome.score - entry["parent_score"],
              "observed_at": time.time()}
    if value is not None:
        sample["measured_value"] = value
    controller.db.set("advisor_sample:" + mission.id, sample)


def samples(db, epoch, maximum, *, role=None, target=None, schema=VERSION):
    entries = [json.loads(r["value"]) for r in db.rows(
        "SELECT value FROM metadata WHERE key LIKE 'advisor_sample:%'")]
    entries = sorted((e for e in entries if e["epoch"] == epoch and e["schema"] == schema
                      and e["protocol_id"] == db.get("protocol_id")
                      and (target is None or e.get("target_kind") == target)
                      and (role is None or e.get("role") == role)), key=lambda e: (e["observed_at"], e["id"]))
    # Multiple children are distinct transitions, NOT independent parent evidence.
    # Collapse only identical completed child commits, never all parent features.
    unique = {e.get("commit") or e["id"]: e for e in entries}
    return sorted(unique.values(), key=lambda e: (e["observed_at"], e["id"]))[-maximum:]


def summary(db):
    config = db.get("config", {})
    cfg = settings(config)
    totals = db.get("advisor_totals", {})
    recorded = [json.loads(r["value"]) for r in db.rows("SELECT value FROM metadata WHERE key LIKE 'advisor_sample:%'")]
    stored_schema = db.get("control_contracts", {}).get("advisor")
    schemas = sorted({e.get("schema", "unknown") for e in recorded})
    version = stored_schema or (schemas[0] if len(schemas) == 1 else "mixed" if schemas else VERSION)
    if version == "forest-tabpfn-advisor-v2-parent-value" and "validation_policy" not in config.get("advisor", {}):
        cfg["validation_policy"] = "gain_rank_v2"
    target = RUNTIME_TARGET if cfg["validation_policy"] == RUNTIME_POLICY else "child_minus_parent_measured_score"
    feature_count = len(recorded[-1]["features"]) if recorded and "features" in recorded[-1] else len(FEATURES)
    return {"enabled": cfg["enabled"], "schema": version, "recorded_schemas": schemas, "model": "TabPFN-3.5",
            "package_version": PACKAGE_VERSION, "settings": cfg, **totals,
            "samples": len(samples(db, db.get("current_epoch", 1), cfg["max_samples"],
                                   target=target, schema=version)) if cfg["enabled"] else 0,
            "scope": "treequest_parent_proposals", "target": target,
            "feature_count": feature_count, "weights_updated": False}


@contextmanager
def account_context(controller):
    """Include feature capture and measured-example bookkeeping in advice cost."""
    enabled = settings(controller.config)["enabled"]
    started = time.perf_counter()
    try:
        yield
    finally:
        if enabled:
            seconds = time.perf_counter() - started
            totals = controller.db.get("advisor_totals", {})
            totals["seconds"] = totals.get("seconds", 0) + seconds
            totals["context_seconds"] = totals.get("context_seconds", 0) + seconds
            controller.db.set("advisor_totals", totals)


def _record(db, decision):
    totals = db.get("advisor_totals", {})
    for key, amount in (("opportunities", 1), ("calls", int(decision.get("called", False))),
                        ("reorders", int(decision.get("reordered", False))),
                        ("seconds", decision.get("seconds", 0))):
        totals[key] = totals.get(key, 0) + amount
    totals["last_status"] = decision["status"]
    db.set("advisor_totals", totals)
    db.event("advisor_decision", decision)


def choose(controller, missions):
    """Select a genuine TreeQuest proposal, or preserve its first unmodified ask."""
    if not missions:
        raise ForestError("Cannot advise an empty queue")
    first, db, cfg = missions[0], controller.db, settings(controller.config)
    if not cfg["enabled"]:
        return first.id
    decision = {"id": uuid.uuid4().hex, "candidate_ids": [m.id for m in missions],
                "parent_ids": [m.parent_id for m in missions], "tree_id": first.tree_id,
                "scope": "treequest_parent_proposals", "prediction_target": target_kind(controller.config),
                "chosen_id": first.id, "status": "warmup", "called": False, "seconds": 0.0}
    decision.update(context_scope=cfg["context_scope"], validation_policy=cfg["validation_policy"])
    started = time.perf_counter()
    try:
        if len({m.epoch for m in missions}) != 1:
            decision["status"] = "incomparable_epochs"
            return first.id
        if len({(m.tree_id, m.role) for m in missions}) != 1:
            decision["status"] = "incomparable_trees"
            return first.id
        # Capture even during warmup; no child exists at this decision point.
        candidates = [capture(controller, mission, persist=False) for mission in missions]
        if any(not c for c in candidates):
            decision["status"] = "features_unavailable"
            return first.id
        controller.db.set("advisor_features:" + first.id, candidates[0])
        if len(missions) < 2:
            decision["status"] = "single_proposal"
            return first.id
        cfg_runtime = runtime(controller.config)
        context = samples(db, first.epoch, cfg["max_samples"],
                          role=first.role if cfg["context_scope"] == "tree" else None,
                          target=target_kind(controller.config))
        decision["context_ids"] = [e["id"] for e in context]
        if len(context) < cfg["min_samples"]:
            return first.id
        count = db.get("advisor_totals", {}).get("opportunities", 0)
        if count % cfg["exploration_every"] == cfg["exploration_every"] - 1:
            decision["status"] = "exploration_treequest"
            return first.id
        if not cfg_runtime:
            decision["status"] = "runtime_unavailable"
            return first.id
        remaining = cfg["max_budget_fraction"] * controller.config["budget"]["wall_seconds"] \
            - db.get("advisor_totals", {}).get("seconds", 0)
        deadline = admission_deadline(db)
        if deadline is not None:
            remaining = min(remaining, deadline - time.time())
        timeout = min(cfg["max_call_seconds"], remaining)
        if timeout < 1:
            decision["status"] = "advisor_budget_exhausted"
            return first.id
        if cfg["validation_policy"] in ("decision_calibrated_v1", RUNTIME_POLICY):
            from .advisor_validation import validation_split

            _, _, evidence = validation_split(context, first.role, policy=cfg["validation_policy"])
            if evidence.get("reason"):
                decision.update(status="validation_preflight_rejected", validation=evidence)
                return first.id
        directory = controller.root / "advisor" / decision["id"]
        request = {"schema": VERSION, "model_version": MODEL_VERSION,
                   "package_version": PACKAGE_VERSION, "runtime": cfg_runtime,
                   "feature_names": FEATURES, "seed": controller.config["seed"],
                   "context": context, "candidates": candidates,
                   "context_scope": cfg["context_scope"], "validation_policy": cfg["validation_policy"]}
        atomic_json(directory / "request.json", request)
        with ExitStack() as locks:
            try:
                # Other trees can run harness checks while generation is in flight.
                # Never consume benchmark CPU concurrently with those measurements.
                # Nonblocking acquisition also avoids a new scheduling barrier.
                locks.enter_context(FileLock(controller.evaluator.lock_path))
            except InfrastructureError:
                decision["status"] = "target_busy"
                return first.id
            decision.update(called=True, request_sha256=digest(request), timeout_seconds=timeout)
            result = run_process(
                [cfg_runtime["python"], "-m", "hpc_forest.advisor_worker", str(directory / "request.json"),
                 str(directory / "response.json")], cwd=controller.root, log=directory / "worker.log", timeout=timeout,
                env={"PYTHONPATH": str(Path(__file__).resolve().parent.parent) + os.pathsep + os.environ.get("PYTHONPATH", ""),
                     "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                     "MKL_NUM_THREADS": "1", "CUDA_VISIBLE_DEVICES": "", "TABPFN_NO_BROWSER": "1",
                     "HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
        if result.timed_out or result.returncode:
            decision["status"] = "timeout" if result.timed_out else "model_unavailable"
            return first.id
        response = json.loads((directory / "response.json").read_text(encoding="utf8"))
        if response.get("request_sha256") != digest(request) or response.get("model_version") != MODEL_VERSION:
            raise ForestError("Unbound advisor response")
        decision["validation"] = response.get("validation", {})
        if response.get("status") != "validated":
            decision["status"] = "validation_rejected"
            return first.id
        predictions = response["predictions"]
        if (not isinstance(predictions, list) or len(predictions) != len(missions)
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in predictions)):
            raise ForestError("Invalid advisor predictions")
        # Predict a gain, select the resulting value. Ranking gains alone would
        # systematically favor improving a slow parent over an already fast one.
        if cfg["validation_policy"] in ("decision_calibrated_v1", RUNTIME_POLICY):
            from .advisor_validation import calibrated_choice

            chosen, expected_scores, guard = calibrated_choice(candidates, predictions, decision["validation"])
            decision["decision_guard"] = guard
        else:
            expected_scores = [min(1.0, max(0.0, c["parent_score"] + gain))
                               for c, gain in zip(candidates, predictions, strict=True)]
            chosen = max(range(len(missions)), key=lambda i: expected_scores[i])
            if expected_scores[chosen] <= expected_scores[0] + 0.005:
                chosen = 0
        controller.db.set("advisor_features:" + missions[chosen].id, candidates[chosen])
        prediction_key = "expected_child_values" if cfg["validation_policy"] == RUNTIME_POLICY else "expected_child_scores"
        decision.update(status="advised", predictions=predictions, **{prediction_key: expected_scores},
                        chosen_id=missions[chosen].id, reordered=chosen != 0)
        return missions[chosen].id
    except (ForestError, OSError, ValueError, TypeError, KeyError) as exc:
        decision.update(status="advisor_unavailable", error=type(exc).__name__)
        return first.id
    finally:
        decision["seconds"] = time.perf_counter() - started + first.selection.get("proposal_seconds", 0.0)
        _record(db, decision)


def next_completed(controller, completed, pending, ready):
    """Identical callback order with advice on/off; never hold ready measurements."""
    return completed.get()


def export(db, output):
    result = summary(db)
    decisions = [json.loads(r["payload"]) for r in db.rows(
        "SELECT payload FROM events WHERE kind='advisor_decision' ORDER BY id")]
    atomic_json(output / "advisor.json", {"summary": result, "decisions": decisions})
    with (output / "advisor-decisions.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        columns = ["id", "scope", "tree_id", "status", "chosen_id", "called", "reordered", "seconds",
                   "candidate_ids", "parent_ids", "context_ids", "prediction_target", "validation_policy",
                   "decision_guard", "preflight_reason", "predictions", "expected_child_values"]
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for d in decisions:
            row = {**d, "preflight_reason": d.get("validation", {}).get("reason")
                   if d.get("status") == "validation_preflight_rejected" else None}
            writer.writerow({k: json.dumps(row.get(k)) if isinstance(row.get(k), list)
                             else row.get(k) for k in columns})
    return result
