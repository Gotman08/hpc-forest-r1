"""Bounded configuration timings from existing evaluator diagnostics, never rewards.

Source code and log text remain data. Missing/partial diagnostics cannot establish
that a configuration, scalar path or fallback is absent.
"""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from statistics import mean, stdev

from .core import canonical

AXES = ("n", "size", "width", "height", "rows", "cols", "batch", "threads", "shape",
        "seed", "pattern", "input_sha256")
MAX_CONFIGURATIONS = 32


def positive(value):
    return type(value) in (int, float) and 0 < value < 1e300 and math.isfinite(value)


def profile(diagnostics):
    groups, provenance = defaultdict(list), defaultdict(list)
    partial = len(diagnostics) > 32
    for log in diagnostics[:32]:
        if not re.search(r"(?:^|[\\/])sample-\d+\.log$", log.get("path", "")):
            continue  # Correctness/build time is not a kernel timing sample.
        partial |= bool(log.get("truncated") or log.get("unavailable"))
        for line in log.get("preview", "").splitlines():
            try:
                sample = json.loads(line)
            except (ValueError, RecursionError):
                continue
            if not isinstance(sample, dict) or sample.get("correct") is not True:
                continue
            details = sample.get("details")
            if not isinstance(details, list):
                continue
            partial |= len(details) > MAX_CONFIGURATIONS
            for detail in details[:MAX_CONFIGURATIONS]:
                if not isinstance(detail, dict) or not positive(detail.get("seconds")):
                    continue
                config = {k: detail[k] for k in AXES if k in detail}
                # Only bounded, typed configuration data; never arbitrary log fields.
                if not config or any(not _axis(v) for v in config.values()):
                    continue
                identity = canonical(config)
                if identity not in groups and len(groups) >= MAX_CONFIGURATIONS:
                    partial = True
                    continue
                if len(groups[identity]) >= 64:
                    partial = True
                    continue
                groups[identity].append(float(detail["seconds"]))
                ref = {k: log[k] for k in ("path", "sha256") if k in log}
                if ref not in provenance[identity]:
                    provenance[identity].append(ref)
    return {"status": "partial" if partial else "available" if groups else "unavailable",
            "interpretation": "Diagnostic timing details; evaluator outcome alone defines reward and correctness",
            "configurations": [{"configuration": json.loads(k), "samples": len(v),
                "mean_seconds": mean(v), "min_seconds": min(v), "max_seconds": max(v),
                "cv": stdev(v) / mean(v) if len(v) > 1 else None, "logs": provenance[k]}
                for k, v in sorted(groups.items())]}


def _axis(value):
    if type(value) is int:
        return -(2**63) <= value < 2**63
    if type(value) is float:
        return math.isfinite(value)
    if isinstance(value, str):
        return len(value) <= 160
    return (isinstance(value, list) and len(value) <= 8
            and all(type(x) is int and 0 <= x < 2**63 for x in value))


def compared(current, baseline):
    """Compare only exactly matching inputs/configurations; never impute a timing."""
    reference = {canonical(r["configuration"]): r for r in baseline.get("configurations", [])}
    rows = []
    for row in current.get("configurations", []):
        before = reference.get(canonical(row["configuration"]))
        comparison = {}
        if before:
            speedup = before["mean_seconds"] / row["mean_seconds"]
            comparison = {"baseline_seconds": before["mean_seconds"]}
            if math.isfinite(speedup) and speedup > 0:
                comparison["speedup_vs_baseline"] = speedup
            else:
                comparison["speedup_unavailable"] = "unrepresentable_ratio"
        rows.append({**row, **comparison})
    return {**current, "configurations": rows}


FEATURES = ["timing_configurations", "timing_matched_configurations", "timing_partial",
            "timing_max_cv", "timing_min_log_speedup", "timing_mean_log_speedup",
            "timing_max_log_speedup", "timing_serial_parallel_gap"]


def features(current, baseline):
    rows = compared(current, baseline)["configurations"]
    measured = [r for r in rows if positive(r.get("speedup_vs_baseline"))]
    logs = [math.log(r["speedup_vs_baseline"]) for r in measured]
    serial = [math.log(r["speedup_vs_baseline"]) for r in measured if r["configuration"].get("threads") == 1]
    parallel = [math.log(r["speedup_vs_baseline"]) for r in measured
                if type(r["configuration"].get("threads")) is int and r["configuration"]["threads"] > 1]
    return [float(len(rows)), float(len(logs)), float(current.get("status") != "available"),
            max((r.get("cv") or 0 for r in rows), default=0), min(logs, default=0),
            mean(logs) if logs else 0, max(logs, default=0),
            mean(parallel) - mean(serial) if parallel and serial else 0]
