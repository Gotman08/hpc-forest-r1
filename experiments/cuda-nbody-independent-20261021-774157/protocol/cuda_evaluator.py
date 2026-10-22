"""Campaign-specific GPU metric adapter; common selection/confirmation remain unchanged."""

import json
import math
from pathlib import Path

from hpc_forest.core import InfrastructureError, file_digest
from hpc_forest.evaluator import Evaluator


def gpu_seconds(data):
    if (
        data.get("metric") != "geomean_cuda_event_seconds"
        or data.get("correct") is not True
        or data.get("cases") != 3
        or data.get("timed_launches_per_size") != 100
        or data.get("warmup_launches") != 10
    ):
        raise InfrastructureError("Wrong GPU metric contract")
    rows = data.get("details", [])
    if [r.get("n") for r in rows] != [4096, 8192, 16384] or any(
        r.get("ok") is not True for r in rows
    ):
        raise InfrastructureError("Wrong GPU metric cases")
    values = [r["latency_ms"] for r in rows]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in values):
        raise InfrastructureError("Invalid CUDA event latency")
    seconds = math.exp(sum(math.log(v / 1000) for v in values) / 3)
    if not math.isclose(seconds, data["seconds"], rel_tol=1e-12, abs_tol=0):
        raise InfrastructureError("GPU aggregate does not match per-size event measurements")
    return seconds


class CudaEvaluator(Evaluator):
    def _sample(self, item, index):
        outcome, variables, logs = item
        binary = Path(variables["binary"])
        if file_digest(binary) != outcome.binary_sha256:
            raise InfrastructureError("Candidate bundle changed after build")
        result = self._run("benchmark", variables, logs / f"sample-{index}.log")
        outcome.logs.append(result.log)
        if file_digest(binary) != outcome.binary_sha256:
            raise InfrastructureError("Candidate bundle changed during GPU measurement")
        if result.returncode == 70:
            raise InfrastructureError("GPU timing infrastructure failed; inspect benchmark log")
        if result.returncode or result.timed_out:
            outcome.status, outcome.correct, outcome.score = "runtime_failed", False, 0.0
            outcome.times.clear()
            return
        try:
            data = json.loads(Path(result.log).read_text(encoding="utf8"))
            seconds = gpu_seconds(data)
        except (ValueError, KeyError, TypeError) as exc:
            raise InfrastructureError("Malformed trusted GPU metric") from exc
        outcome.times.append(seconds)
