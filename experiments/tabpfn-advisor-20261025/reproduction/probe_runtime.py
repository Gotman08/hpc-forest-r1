"""Exercise the real bounded advisor subprocess on explicitly synthetic data."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

from hpc_forest.advisor import FEATURES, MODEL_VERSION, PACKAGE_VERSION, VERSION
from hpc_forest.core import atomic_json, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    runtime = json.loads(args.runtime.read_text())
    context = []
    for i in range(32):
        features = [((i * (j + 3) + j * 7) % 37) / 37 for j in range(len(FEATURES))]
        context.append({"id": "synthetic-" + str(i), "features": features,
                        "target": 2 * features[0] - 0.1 * features[1]})
    request = {"schema": VERSION, "model_version": MODEL_VERSION,
               "package_version": PACKAGE_VERSION, "feature_names": FEATURES,
               "runtime": runtime, "seed": 23, "context": context,
               "candidates": [{"id": "synthetic-candidate-" + str(i),
                               "features": context[i]["features"]} for i in (3, 14, 25)]}
    request_path, response_path = args.output / "request.json", args.output / "response.json"
    atomic_json(request_path, request)
    started = time.monotonic()
    with (args.output / "worker.log").open("wb") as log:
        result = subprocess.run([runtime["python"], "-m", "hpc_forest.advisor_worker",
            str(request_path), str(response_path)], stdout=log, stderr=subprocess.STDOUT,
            timeout=20, env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                             "TABPFN_NO_BROWSER": "1", "HF_HUB_OFFLINE": "1",
                             "CUDA_VISIBLE_DEVICES": ""})
    response = json.loads(response_path.read_text())
    proof = {"synthetic_only": True, "forest_performance_claim": False,
             "elapsed_seconds": time.monotonic() - started, "exit_code": result.returncode,
             "status": response.get("status"), "request_matches": response.get("request_sha256") == digest(request),
             "model_version": response.get("model_version"), "validation": response.get("validation"),
             "predictions": response.get("predictions")}
    atomic_json(args.output / "proof.json", proof)
    print(json.dumps(proof))
    if result.returncode or not proof["request_matches"] or response["status"] != "validated":
        raise RuntimeError("Real bounded advisor probe did not validate")


if __name__ == "__main__":
    main()

