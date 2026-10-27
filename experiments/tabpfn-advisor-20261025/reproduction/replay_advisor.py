"""Offline diagnostic on real frozen examples, never an online search benefit."""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import subprocess
import time
from contextlib import closing
from pathlib import Path

from hpc_forest.advisor import FEATURES, MODEL_VERSION, PACKAGE_VERSION, VERSION
from hpc_forest.advisor_worker import ranking_accuracy
from hpc_forest.core import atomic_json, digest


def select_examples(samples):
    """Last two valid distinct codes, with context strictly available before either capture."""
    unique = {r["source_sha256"]: r for r in sorted(samples, key=lambda r: (r["observed_at"], r["id"]))}
    ordered = sorted(unique.values(), key=lambda r: (r["observed_at"], r["id"]))
    if len(ordered) < 10:
        return [], []
    candidates = ordered[-2:]
    cutoff = min(r["captured_at"] for r in candidates)
    candidate_ids = {r["id"] for r in candidates}
    context = [r for r in ordered if r["id"] not in candidate_ids and r["observed_at"] < cutoff][-128:]
    return context, candidates


def read_database(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        return {key: json.loads(value) for key, value in db.execute("SELECT key,value FROM metadata")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    reports = []
    for pair in args.pairs:
        plan = json.loads((pair / "pair.json").read_text())
        if not (pair / "exit-code.txt").exists():
            raise RuntimeError("Read-only diagnostic requires terminated search pairs")
        arm = next(a for a in plan["arms"] if a["enabled"])
        root = pair / ("forest-app-" + arm["id"])
        meta = read_database((root / "campaign/registry.sqlite3").resolve())
        report = {"pair_id": plan["pair_id"], "case": plan["case"], "repeat": plan["repeat"],
            "diagnostic_only": True, "search_modified": False, "improvement_claim": False,
            "budget_separate_from_search": True, "live_calls": meta.get("advisor_totals", {}).get("calls", 0)}
        if report["live_calls"]:
            report["status"] = "live_calls_available_no_replay_needed"
            reports.append(report)
            continue
        samples = [v for k, v in meta.items() if k.startswith("advisor_sample:")
            and v["epoch"] == meta["current_epoch"] and v["protocol_id"] == meta["protocol_id"]
            and v["schema"] == VERSION]
        context, held = select_examples(samples)
        report.update(context_count=len(context), candidate_count=len(held))
        if len(context) < 8:
            report["status"] = "insufficient_strictly_earlier_context"
            reports.append(report)
            continue
        assert max(r["observed_at"] for r in context) < min(r["captured_at"] for r in held)
        runtime = meta["config"]["advisor_runtime"]
        request = {"schema": VERSION, "model_version": MODEL_VERSION, "package_version": PACKAGE_VERSION,
            "runtime": runtime, "feature_names": FEATURES, "seed": plan["seed"], "context": context,
            "candidates": [{"id": r["id"], "features": r["features"]} for r in held]}
        destination = args.output / plan["pair_id"]
        destination.mkdir()
        atomic_json(destination / "request.json", request)
        report.update(context_ids=[r["id"] for r in context], candidate_ids=[r["id"] for r in held],
            latest_context_observed_at=max(r["observed_at"] for r in context),
            earliest_candidate_captured_at=min(r["captured_at"] for r in held),
            labels_withheld_from_request=True, request_sha256=digest(request))
        started = time.monotonic()
        try:
            with (destination / "worker.log").open("wb") as log:
                process = subprocess.run([runtime["python"], "-m", "hpc_forest.advisor_worker",
                    str(destination / "request.json"), str(destination / "response.json")],
                    stdout=log, stderr=subprocess.STDOUT, timeout=20,
                    env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                         "MKL_NUM_THREADS": "1", "TABPFN_NO_BROWSER": "1", "HF_HUB_OFFLINE": "1",
                         "CUDA_VISIBLE_DEVICES": ""})
            response = json.loads((destination / "response.json").read_text())
            report.update(status=response["status"], exit_code=process.returncode,
                          internal_validation=response.get("validation"))
            if not process.returncode and (response.get("request_sha256") != digest(request)
                                           or response.get("model_version") != MODEL_VERSION):
                raise ValueError("Unbound replay response")
            if response["status"] == "validated":
                actual = [r["target"] for r in held]
                predicted = response["predictions"]
                if len(predicted) != 2 or not all(math.isfinite(v) for v in predicted):
                    raise ValueError("Invalid diagnostic predictions")
                report.update(actual_log_ratios=actual, predicted_log_ratios=predicted,
                    held_out_pairwise_accuracy=ranking_accuracy(actual, predicted))
        except Exception as exc:
            report.update(status="diagnostic_unavailable", error_type=type(exc).__name__)
        report["elapsed_seconds"] = time.monotonic() - started
        atomic_json(destination / "report.json", report)
        reports.append(report)
    atomic_json(args.output / "diagnostic.json", {"schema": "forest-tabpfn-offline-diagnostic-v1",
        "study_search_intervention": False, "reports": reports,
        "interpretation": "Small retrospective ranking check. No online speedup or causal gain is implied."})
    print(json.dumps([{"pair": r["pair_id"], "status": r["status"],
        "context": r["context_count"] if "context_count" in r else None,
        "seconds": r.get("elapsed_seconds"), "pair_accuracy": r.get("held_out_pairwise_accuracy")}
        for r in reports]))


if __name__ == "__main__":
    main()

