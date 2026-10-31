"""Frozen execution requirements and independently collected runtime evidence.

Allocation, thread participation and semantic correctness are different claims.
The GNU OpenMP probe observes CPU work outside intercepted synchronization; it
does not prove that every instruction contributes to the answer. Final source
review must reject padding, sleeps and artificial work. Probe runs are never
performance samples.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from pathlib import Path

from .core import ForestError, InfrastructureError, atomic_json, file_digest


def requirements(value: object) -> dict | None:
    """Validate an optional explicit contract, without upgrading historical runs."""
    if value is None:
        return None
    defaults = {"nodes": 1, "sockets_per_node": None, "cpus_per_task": 2,
                "threads_per_core": 1, "parallelism": "not_required",
                "required_threads": 2, "min_work_cpu_ns": 5000,
                "min_parallel_cpu_ratio": 1.01, "omp_proc_bind": "close",
                "omp_places": "cores", "omp_wait_policy": "active"}
    if not isinstance(value, dict) or set(value) - set(defaults):
        raise ForestError("Configuration de validation inconnue.")
    result = defaults | value
    if "required_threads" not in value:
        result["required_threads"] = result["cpus_per_task"]
    for key, low, high in (("nodes", 1, 1), ("cpus_per_task", 1, 4096),
                           ("threads_per_core", 1, 8), ("required_threads", 1, 4096),
                           ("min_work_cpu_ns", 1000, 1000000000)):
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ForestError(f"Validation : {key} doit être compris entre {low} et {high}.")
    sockets = result["sockets_per_node"]
    if sockets is not None and (type(sockets) is not int or not 1 <= sockets <= 64):
        raise ForestError("Le nombre de processeurs physiques est invalide.")
    if result["parallelism"] not in {"not_required", "gnu_openmp_required"}:
        raise ForestError("Méthode de validation du parallélisme inconnue.")
    if result["required_threads"] > result["cpus_per_task"]:
        raise ForestError("Les threads requis dépassent les CPU réservés.")
    if result["parallelism"] == "gnu_openmp_required" and result["required_threads"] < 2:
        raise ForestError("Le calcul parallèle exige au moins deux threads.")
    if sockets and sockets > result["cpus_per_task"]:
        raise ForestError("Le nombre de processeurs dépasse celui des CPU réservés.")
    ratio = result["min_parallel_cpu_ratio"]
    if type(ratio) not in {int, float} or not 1 < ratio <= 4096:
        raise ForestError("Le seuil de travail CPU simultané doit être supérieur à un.")
    if (result["omp_proc_bind"] not in {"close", "spread"}
            or result["omp_places"] not in {"cores", "threads"}
            or result["omp_wait_policy"] not in {"active", "passive"}):
        raise ForestError("Placement OpenMP invalide.")
    return result


def environment(contract: dict | None) -> dict[str, str]:
    if contract is None:
        return {}
    return {"OMP_NUM_THREADS": str(contract["required_threads"]),
            "OMP_THREAD_LIMIT": str(contract["required_threads"]), "OMP_DYNAMIC": "FALSE",
            "OMP_PROC_BIND": contract["omp_proc_bind"], "OMP_PLACES": contract["omp_places"],
            "OMP_WAIT_POLICY": contract["omp_wait_policy"]}


def allocation_evidence(contract: dict, *, affinity=None, topology=None, environ=None) -> dict:
    """Check actual allowed CPUs and their physical topology, not env claims alone."""
    contract = requirements(contract)
    env = os.environ if environ is None else environ
    if affinity is None:
        if platform.system() != "Linux" or not hasattr(os, "sched_getaffinity"):
            raise InfrastructureError("Allocation validation requires Linux CPU affinity")
        affinity = sorted(os.sched_getaffinity(0))
    if topology is None:
        result = subprocess.run(["lscpu", "--parse=CPU,CORE,SOCKET,ONLINE"],
                                capture_output=True, text=True, timeout=15, check=False)
        if result.returncode:
            raise InfrastructureError("Cannot read CPU topology")
        topology = []
        for line in result.stdout.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            cpu, core, socket, online = line.split(",")
            if online == "Y":
                topology.append({"cpu": int(cpu), "core": int(core), "socket": int(socket)})
    selected = [row for row in topology if row["cpu"] in affinity]
    sockets = sorted({row["socket"] for row in selected})
    core_counts = {}
    for row in selected:
        key = (row["socket"], row["core"])
        core_counts[key] = core_counts.get(key, 0) + 1
    reasons = []
    if (not str(env.get("SLURM_JOB_ID", "")).isdigit()
            or env.get("SLURM_JOB_NUM_NODES", env.get("SLURM_NNODES")) != str(contract["nodes"])):
        reasons.append("SLURM allocation/node count mismatch")
    if len(affinity) != contract["cpus_per_task"] or len(selected) != len(affinity):
        reasons.append("Allowed CPU count/topology mismatch")
    if contract["sockets_per_node"] is not None and len(sockets) != contract["sockets_per_node"]:
        reasons.append("Physical socket count mismatch")
    if not core_counts or max(core_counts.values()) > contract["threads_per_core"]:
        reasons.append("Hardware threads per core mismatch")
    return {"schema": "forest-allocation-evidence-v1", "status": "failed" if reasons else "passed",
            "observed_at": time.time(), "job_id": env.get("SLURM_JOB_ID"),
            "host": platform.node(), "architecture": platform.machine(),
            "required": contract, "allowed_cpus": sorted(affinity), "topology": selected,
            "physical_cores": len(core_counts), "sockets": sockets, "reasons": reasons}


def assess_parallelism(contract: dict, records: list[dict], allocation: dict) -> dict:
    """Require one real team with enough work on each required physical CPU."""
    contract = requirements(contract)
    if allocation.get("status") != "passed":
        raise InfrastructureError("Allocation evidence is not valid")
    topology = {row["cpu"]: row for row in allocation["topology"]}
    summaries = []
    for record in records:
        if not isinstance(record, dict) or record.get("schema") != "forest-gomp-region-v1" or record.get("error"):
            raise InfrastructureError("Incomplete or unsupported parallelism probe")
        rows = record.get("threads")
        if not isinstance(rows, list) or len(rows) > 4096:
            raise InfrastructureError("Malformed parallelism evidence")
        active = []
        for row in rows:
            fields = ("tid", "team", "index", "cpu", "end_cpu", "affinity_count",
                      "work_cpu_ns", "start_ns", "end_ns")
            if any(type(row.get(k)) is not int or row[k] < 0 for k in fields):
                raise InfrastructureError("Invalid worker observation")
            if row["work_cpu_ns"] >= contract["min_work_cpu_ns"]:
                active.append(row)
        cpus = {row["cpu"] for row in active}
        core_capacity = {}
        for cpu in topology.values():
            key = (cpu["socket"], cpu["core"])
            core_capacity[key] = core_capacity.get(key, 0) + 1
        core_workers = {}
        placed = True
        for row in active:
            start, end = topology.get(row["cpu"]), topology.get(row["end_cpu"])
            if start is None or end is None:
                placed = False
                continue
            key = (start["socket"], start["core"])
            core_workers[key] = core_workers.get(key, 0) + 1
            if contract["omp_places"] == "threads":
                placed &= row["cpu"] == row["end_cpu"] and row["affinity_count"] == 1
            else:
                placed &= ((end["socket"], end["core"]) == key
                           and 1 <= row["affinity_count"] <= core_capacity[key])
        placed &= all(count <= core_capacity[key] for key, count in core_workers.items())
        if contract["omp_places"] == "threads":
            placed &= len(cpus) == len(active)
        sockets = {topology[cpu]["socket"] for cpu in cpus if cpu in topology}
        span = max((r["end_ns"] for r in rows), default=0) - min(
            (r["start_ns"] for r in rows), default=0)
        cpu_ns = sum(r["work_cpu_ns"] for r in active)
        ratio = cpu_ns / span if span > 0 else 0
        required = contract["required_threads"]
        passed = (len(active) == len(rows) == required and placed
                  and len({r["tid"] for r in rows}) == required
                  and {r["index"] for r in rows} == set(range(required))
                  and all(r["team"] == required for r in rows)
                  and ratio >= contract["min_parallel_cpu_ratio"])
        summaries.append({"passed": passed, "team_size": len(rows), "active_threads": len(active),
                          "distinct_cpus": len(cpus), "sockets": sorted(sockets),
                          "physical_cores": len(core_workers),
                          "work_cpu_ns": cpu_ns, "parallel_cpu_ratio": ratio, "placement_ok": placed})
    return {"schema": "forest-parallel-evidence-v1", "status": "passed" if any(
        r["passed"] for r in summaries) else "failed", "required": contract,
        "regions": summaries, "method": "gnu-openmp-callback-cpu-excluding-synchronization-v1",
        "scope": "Separate instrumented workload; never an official timing sample",
        "limitations": "CPU work is not proof of output contribution. Artificial work requires source review."}


def build_probe(folder: Path) -> Path:
    """Build trusted instrumentation once per evaluator directory."""
    library = folder / "forest-parallel-probe.so"
    source = Path(__file__).parent / "assets" / "parallel_probe.c"
    result = subprocess.run(["gcc", "-std=gnu11", "-O2", "-fPIC", "-shared", str(source),
                             "-o", str(library), "-ldl", "-pthread"],
                            capture_output=True, text=True, timeout=120, check=False)
    (folder / "parallel-probe-build.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise InfrastructureError("Cannot build trusted parallelism probe")
    return library


def probe_environment(binary: Path, library: Path, trace: Path, env: dict) -> dict:
    return env | {"LD_PRELOAD": str(library.resolve()), "FOREST_PARALLEL_TRACE": str(trace.resolve()),
                  "FOREST_PARALLEL_BINARY": str(binary.resolve())}


def read_probe(contract: dict, trace: Path, allocation: dict, binary: Path,
               binary_sha256: str, destination: Path) -> dict:
    if file_digest(binary) != binary_sha256:
        raise InfrastructureError("Executable changed during parallel validation")
    if not trace.is_file() or trace.stat().st_size > 64 * 1024 * 1024:
        raise InfrastructureError("Missing or oversized runtime parallelism evidence")
    try:
        records = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
        if not records or records[0] != {"schema": "forest-gomp-probe-v1", "loaded": True}:
            raise ValueError("probe receipt")
        if not all(isinstance(row, dict) for row in records):
            raise ValueError("probe record")
        unsupported = [row.get("api") for row in records[1:]
                       if row.get("schema") == "forest-gomp-unsupported-v1"]
        if unsupported:
            raise InfrastructureError("Unsupported GNU OpenMP observation entry point: " + repr(unsupported))
        truncated = any(row.get("schema") == "forest-gomp-limit-v1" for row in records[1:])
        result = assess_parallelism(contract, [row for row in records[1:]
            if row.get("schema") != "forest-gomp-limit-v1"], allocation)
        result["trace_truncated"] = truncated
        if truncated and result["status"] != "passed":
            raise InfrastructureError("Probe observation limit reached before proving required parallelism")
    except (ValueError, TypeError, KeyError) as exc:
        raise InfrastructureError("Unreadable runtime parallelism evidence") from exc
    result.update(binary_sha256=binary_sha256, trace_sha256=file_digest(trace))
    atomic_json(destination, result)
    return result
