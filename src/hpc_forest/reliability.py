"""Read-only, provenance-aware statistics over independently confirmed campaigns."""
from __future__ import annotations

import copy
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

from .core import ForestError, digest
from .search_policy import label as search_label


def positive(value):
    return type(value) in {int, float} and math.isfinite(value) and value > 0


def measured(outcome):
    samples = outcome.get("times", [])
    return (outcome.get("correct") is True and positive(outcome.get("mean_seconds"))
            and isinstance(samples, list) and bool(samples) and all(positive(v) for v in samples)
            and math.isclose(mean(samples), outcome["mean_seconds"], rel_tol=1e-9, abs_tol=0))


def strategy(config, identity):
    value = copy.deepcopy(config)
    for key in ("seed", "target_id", "protocol", "compiler"):
        value.pop(key, None)
    for key in ("session_id", "mailbox_dir"):
        value.get("codex", {}).pop(key, None)
    return digest({"config": value, "implementation": identity.get("controller_implementation")})


def read_campaign(path):
    path = Path(path).resolve(strict=True)
    database = path / "registry.sqlite3" if path.is_dir() else path
    try:
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")  # One consistent read snapshot; no schema migration.
        try:
            return _read(connection, database)
        finally:
            connection.close()
    except (sqlite3.Error, KeyError, TypeError, ValueError, StopIteration) as exc:
        raise ForestError(f"Invalid campaign registry {database}: {exc}") from exc


def _read(connection, database):
    def metadata(key, default=None):
        row = connection.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default
    config, identity = metadata("config"), metadata("identity", {})
    epoch = metadata("current_epoch", 1)
    epochs = connection.execute("SELECT * FROM epochs ORDER BY id").fetchall()
    current = next(row for row in epochs if row["id"] == epoch)
    baseline_id = current["baseline_id"] or f"baseline-e{epoch}"
    baseline_row = connection.execute("SELECT payload FROM evaluations WHERE experiment_id=? AND phase='search'",
                                      (baseline_id,)).fetchone()
    baseline_search = json.loads(baseline_row[0]) if baseline_row else {}
    source_identity = baseline_search.get("tree_hash")
    if not source_identity:
        # Commit IDs are conservative fallbacks, not proof of equal sources across imports.
        source_identity = "commit:" + current["base_commit"]
    protected = {key: value for key, value in metadata("manifest", {}).items() if key != "config.json"}
    target = {key: value for key, value in identity.items() if key != "controller_implementation"}
    benchmark = digest({"source": source_identity, "protocol": config["protocol"],
                        "validation": protected, "target": target, "submission": config.get("submission")})
    campaign_identity = digest({"first_epoch": dict(epochs[0]),
        "session_id": config.get("codex", {}).get("session_id"), "started": metadata("started")})
    confirmations = {row["experiment_id"]: json.loads(row["payload"]) for row in connection.execute(
        "SELECT experiment_id,payload FROM evaluations WHERE epoch=? AND phase='confirmation'", (epoch,))}
    best, baseline = metadata("best_confirmed") or {}, confirmations.get(baseline_id, {})
    winner = confirmations.get(best.get("experiment_id"), {})
    confirmed = bool(measured(baseline) and measured(winner) and best.get("epoch") == epoch
        and best.get("protocol_id") == current["protocol_id"] and best.get("commit") == winner.get("commit")
        and best.get("evaluation_digest") == digest(winner)
        and best.get("mean_seconds") == winner.get("mean_seconds")
        and best.get("reference_seconds") == baseline.get("mean_seconds"))
    speedup = baseline["mean_seconds"] / winner["mean_seconds"] if confirmed else None
    improvement = 1 - 1 / speedup if confirmed else None
    counts = {"trials": 0, "valid_measured": 0, "incorrect": 0, "unmeasured": 0}
    for row in connection.execute("SELECT result FROM trials WHERE epoch=? AND role<>'G'", (epoch,)):
        result = json.loads(row[0] or "{}")
        counts["trials"] += 1
        if result.get("correct") is False:
            counts["incorrect"] += 1
        elif result.get("correct") is True and positive(result.get("mean_seconds")):
            counts["valid_measured"] += 1
        else:
            counts["unmeasured"] += 1
    started = metadata("started")
    finished = metadata(f"pipeline_finished:{epoch}", metadata(f"confirmation_finished:{epoch}"))
    elapsed = finished - started if type(started) in {int, float} and type(finished) in {int, float} else None
    threshold = config["minimum_gain"]
    return {"registry": str(database), "campaign_id": campaign_identity, "epoch": epoch,
        "independent_start": epoch == 1 and len(epochs) == 1, "source_identity": source_identity,
        "benchmark_id": benchmark, "strategy_id": strategy(config, identity),
        "search_policy": search_label(config), "generator_pool": config.get("codex", {}).get("generator_pool", []),
        "evolution_archive": config.get("evolution", {}).get("enabled", False),
        "problem": config.get("problem"), "model": config.get("codex", {}).get("model")
            if config.get("backend") == "codex" else config.get("ollama", {}).get("model")
            if config.get("backend") == "ollama" else config.get("backend"),
        "implementation": identity.get("controller_implementation"), "seed": config.get("seed"),
        "minimum_gain": threshold, "confirmed": confirmed,
        "confirmation_status": "verified_receipt" if confirmed else "missing_or_inconsistent_receipt",
        "baseline_seconds": baseline.get("mean_seconds") if measured(baseline) else None,
        "selected_seconds": winner.get("mean_seconds") if confirmed else None,
        "speedup": speedup, "improved": bool(confirmed and improvement > 0 and improvement >= threshold),
        "research": counts, "elapsed_seconds": elapsed,
        "budget_seconds": config["budget"]["wall_seconds"],
        "budget_used_fraction": elapsed / config["budget"]["wall_seconds"] if elapsed is not None else None}


def summarize(campaigns):
    seen, groups, excluded = set(), defaultdict(list), []
    for run in campaigns:
        if run["campaign_id"] in seen or not run["independent_start"]:
            excluded.append({"registry": run["registry"], "reason": "duplicate_campaign" if run["campaign_id"] in seen
                             else "continued_epoch_not_an_independent_restart"})
            continue
        seen.add(run["campaign_id"])
        groups[(run["benchmark_id"], run["strategy_id"])].append(run)
    result = []
    for (benchmark, method), runs in sorted(groups.items()):
        speeds = [run["speedup"] for run in runs if run["confirmed"]]
        result.append({"benchmark_id": benchmark, "strategy_id": method, "problem": runs[0]["problem"],
            "source_identity": runs[0]["source_identity"], "independent_campaigns": len(runs),
            "confirmed_campaigns": len(speeds), "unconfirmed_campaigns": len(runs) - len(speeds),
            "improved_campaigns": sum(run["improved"] for run in runs),
            "improvement_frequency": sum(run["improved"] for run in runs) / len(runs),
            "median_speedup": median(speeds) if speeds else None,
            "worst_speedup": min(speeds) if speeds else None,
            "best_speedup": max(speeds) if speeds else None,
            "repeated_campaigns_observed": len(runs) > 1, "campaigns": runs})
    return {"schema": "hpc-forest-reliability-v1", "groups": result, "excluded": excluded,
        "distinct_programs": len({run["source_identity"] for runs in groups.values() for run in runs}),
        "interpretation": [
            "Statistics describe the supplied campaigns, not a guarantee of future gains.",
            "Unconfirmed independent campaigns remain in the improvement-frequency denominator; timing summaries use confirmed receipts only.",
            "Grouping is strict: source, validation, protocol, target, model, engine and budget differences remain separate.",
            "Unknown path/target equivalences are never assumed. A singleton group cannot establish regularity.",
            "Distinct campaign receipts exclude obvious copies and continuations, but cannot prove absence of external hints.",
            "No pooling of absolute runtimes across programs and no inference from functional test counts."]}


def compare(paths):
    return summarize([read_campaign(path) for path in paths])
