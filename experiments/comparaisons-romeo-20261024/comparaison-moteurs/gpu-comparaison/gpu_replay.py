"""Replay archived CUDA programs on one allocated GPU with frozen validation.

No model calls and no source transformations. Compilation/checks/timings are
performed by the protected historical protocol. Every subprocess is bounded.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULT = ROOT / "results"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def call(label, command, timeout=240):
    started = time.time()
    output = RESULT / "logs" / (label + ".log")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        output.write_text(proc.stdout + proc.stderr, encoding="utf-8")
        payload = None
        for line in reversed(proc.stdout.splitlines()):
            try:
                payload = json.loads(line)
                break
            except json.JSONDecodeError:
                pass
        result = dict(exit_code=proc.returncode, payload=payload, started=started,
                      duration_seconds=time.time()-started, log=output.relative_to(RESULT).as_posix())
    except subprocess.TimeoutExpired as exc:
        output.write_text(str(exc), encoding="utf-8")
        result = dict(exit_code=70, timeout=True, started=started, duration_seconds=time.time()-started,
                      payload={"infrastructure_error":"subprocess timeout"}, log=output.relative_to(RESULT).as_posix())
    return result


def protocol(label, action, first, second):
    return call(label, [sys.executable, str(ROOT / "validation/protocol.py"), action, str(first), str(second)])


def passed(result):
    p = result.get("payload") or {}
    return result["exit_code"] == 0 and p.get("correct") is True


def main():
    RESULT.mkdir(exist_ok=False)
    manifest = json.loads((ROOT / "manifest.json").read_text())
    for name, expected in manifest.items():
        if sha(ROOT / name) != expected:
            raise RuntimeError("Payload digest mismatch: " + name)
    if not os.environ.get("CUDA_VISIBLE_DEVICES"):
        raise RuntimeError("No allocated GPU")
    environment = dict(started=time.time(), job_id=os.environ.get("SLURM_JOB_ID"),
                       hostname=platform.node(), machine=platform.machine(), python=sys.version,
                       cuda_visible_devices=os.environ.get("CUDA_VISIBLE_DEVICES"),
                       protocol_sha256=sha(ROOT / "validation/protocol.py"),
                       harness_binary_sha256=sha(Path(os.environ["FOREST_CUDA_HARNESS"])),
                       sequential_gpu=True, random_seed=20261023, timing_repetitions=5)
    environment["nvidia_smi"] = call("nvidia-smi", ["nvidia-smi", "-q"])
    environment["compiler"] = call("compiler", ["c++", "--version"])
    write(RESULT / "environment.json", environment)
    preflight = protocol("preflight", "preflight", ROOT / "validation", ROOT / "cache")
    write(RESULT / "preflight.json", preflight)
    if preflight["exit_code"] != 0:
        raise RuntimeError("Protected preflight failed")
    variants = json.loads((ROOT / "variants.json").read_text())
    records = {}
    for ordinal, variant in enumerate(variants):
        key = variant["id"]
        build = ROOT / "builds" / key
        record = dict(id=key, source_sha256=variant["source_sha256"], launch=variant["launch"], checks={}, samples=[])
        record["build"] = protocol(key + "/build", "build", ROOT / "sources" / key, build)
        if record["build"]["exit_code"] == 0:
            for phase in ("search", "confirmation"):
                record["checks"][phase] = protocol(key + "/check-" + phase, "check", build / "solution", phase)
        record["eligible"] = len(record["checks"]) == 2 and all(passed(v) for v in record["checks"].values())
        record["status"] = "correct" if record["eligible"] else "infrastructure_error" if any(
            x["exit_code"] == 70 for x in [record["build"], *record["checks"].values()]) else "incorrect"
        records[key] = record
        write(RESULT / "records" / (key + ".json"), record)
        write(RESULT / "progress.json", dict(phase="correctness", done=ordinal+1,total=len(variants),last=key))
        print(json.dumps({"phase":"correctness","done":ordinal+1,"total":len(variants),"id":key,"status":record["status"]}),flush=True)
    if not records["baseline-control"]["eligible"]:
        raise RuntimeError("Control baseline did not validate")
    rng = random.Random(20261023)
    eligible = [v["id"] for v in variants if v["id"] != "baseline-control" and records[v["id"]]["eligible"]]
    order = []
    controls = []
    for block in range(5):
        sequence = eligible.copy()
        rng.shuffle(sequence)
        sequence = ["baseline-control"] + sequence + ["baseline-control"]
        order.append(sequence)
        write(RESULT / "benchmark-order.json", order)
        for position, key in enumerate(sequence):
            sample = protocol(key + f"/sample-{block}-{position}", "benchmark", ROOT / "builds" / key / "solution", "confirmation")
            sample.update(block=block, position=position)
            records[key]["samples"].append(sample)
            if not passed(sample):
                records[key]["status"] = "infrastructure_error" if sample["exit_code"] == 70 else "incorrect"
            write(RESULT / "records" / (key + ".json"), records[key])
            write(RESULT / "progress.json", dict(phase="benchmark",block=block+1,done=position+1,total=len(sequence),last=key))
        a, b = records["baseline-control"]["samples"][-2:]
        control_times = [s["payload"].get("seconds") for s in (a,b) if passed(s)]
        controls.append({"block":block,"seconds":control_times})
        print(json.dumps({"phase":"benchmark","block_complete":block+1,"total_blocks":5}),flush=True)
    summary = []
    baseline_values = [s["payload"]["seconds"] for s in records["baseline-control"]["samples"] if passed(s)]
    baseline_mean = statistics.mean(baseline_values) if len(baseline_values) == 10 else None
    for key, record in records.items():
        times = [s["payload"]["seconds"] for s in record["samples"] if passed(s)]
        expected = 10 if key == "baseline-control" else 5
        fully_measured = record["eligible"] and len(times) == expected and record["status"] == "correct"
        row = dict(id=key,status=record["status"],correct=record["eligible"],fully_measured=fully_measured,
                   samples=times,mean_seconds=statistics.mean(times) if fully_measured else None,
                   median_seconds=statistics.median(times) if fully_measured else None,
                   min_seconds=min(times) if times else None,max_seconds=max(times) if times else None,
                   stdev_seconds=statistics.stdev(times) if len(times)>1 else None,
                   speedup=baseline_mean/statistics.mean(times) if fully_measured and baseline_mean else None,
                   launch=record["launch"], source_sha256=record["source_sha256"])
        summary.append(row)
    write(RESULT / "summary.json",dict(programs=summary,baseline_mean_seconds=baseline_mean,
                                      controls=controls,finished=time.time(),method="mean of 5 fresh geometric means; 3 sizes each; 10 warmups, 100 launches"))
    write(RESULT / "progress.json",dict(phase="complete",programs=len(summary),finished=time.time()))
    archive = ROOT / "replay-results.tar.gz"
    with tarfile.open(archive,"w:gz") as tar:
        for parent in (RESULT, ROOT / "cache"):
            for path in sorted(parent.rglob("*.json")):
                tar.add(path,arcname=path.relative_to(ROOT).as_posix())
        for path in sorted((RESULT/"logs").rglob("*.log")):
            tar.add(path,arcname=path.relative_to(ROOT).as_posix())
        for name in ("variants.json","manifest.json","gpu_replay.py"):
            tar.add(ROOT/name,arcname=name)
    write(ROOT / "delivery.json",dict(path=str(archive),sha256=sha(archive),bytes=archive.stat().st_size))
    print(json.dumps({"complete":True,"programs":len(summary),"archive":str(archive),"sha256":sha(archive)}),flush=True)


if __name__ == "__main__":
    main()
