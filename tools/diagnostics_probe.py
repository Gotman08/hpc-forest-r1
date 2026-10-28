"""Explicit validation on an existing allocation, or an explicitly selected local CPU.

Creates a NEW synthetic validation campaign. Never submits, installs, edits a
campaign, invokes a model or reports an optimization gain.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

from hpc_forest.config import load_config
from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import InfrastructureError, atomic_json
from hpc_forest.diagnostic_collectors import COLLECTORS
from hpc_forest.diagnostics import Diagnostics
from hpc_forest.diagnostics_contract import authorize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory, never an existing campaign")
    parser.add_argument("--local", action="store_true", help="Explicit local CPU validation instead of Slurm")
    parser.add_argument("--collector", action="append", choices=sorted(COLLECTORS), default=[])
    args = parser.parse_args()
    if not args.local and not os.environ.get("SLURM_JOB_ID", "").isdigit():
        parser.error("Use an already authorized compute allocation; execution on the ROMEO login is forbidden")
    output = args.output.resolve()
    if output.exists():
        parser.error("Output already exists; preserve it and choose a new validation directory")
    selected = args.collector or ["runtime", "compiler", "disassembly", "perf-stat", "perf-record"]
    config = load_config()
    config.update(backend="codex", forest={"policy": "mother"},
                  target_id="diagnostic-validation-" + uuid.uuid4().hex,
                  investigation={"enabled": True, "require_allocation": not args.local,
                                 "max_collections": min(24, len(selected)), "request_seconds": 1800})
    config["codex"].update(session_id=uuid.uuid4().hex, transport="codex-mailbox",
                           mailbox_dir=str(output / "mailbox"))
    config["budget"]["wall_seconds"] = 1800
    config["protocol"].update(repetitions=1, warmups=0, benchmark=["{binary}", "192", "17", "4"])
    create_workspace(output, config)
    with Controller(output) as controller:
        controller._start()
        baseline = controller._baseline(controller.epoch())
        if baseline["correct"] is not True:
            raise InfrastructureError("Validation reference is not correct")
        request = {"nonce": uuid.uuid4().hex, "session_id": config["codex"]["session_id"],
                   "mission_id": "explicit-diagnostic-validation", "meta_role": "mother-investigation",
                   "expires_at": time.time() + 1800}
        authorize(output, request)
        atomic_json(output / "diagnostic-validation-request.json", request)
        service = Diagnostics(output, request["diagnostics"], request)
        discovery = service.audit("capabilities", {"probe": True}, lambda: service.capabilities(True))
        results = [service.audit("collect", {"collector": name}, lambda name=name:
            service.collect("baseline-e1", name, "Validate this collector on the synthetic CPU workload",
                            request_key="validate-" + name)) for name in selected]
        result = {"synthetic_cpu_workload": True, "official_reference": baseline,
                  "capabilities": discovery, "collections": results, "optimization_gain_claimed": False,
                  "jobs_submitted": False, "models_invoked": False}
        atomic_json(output / "diagnostic-validation.json", result)
        print(json.dumps({"output": str(output), "collectors": {
            row["collector"]: row["status"] for row in results}}, indent=2))
    return 0 if all(row["status"] in {"complete", "partial"} for row in results) else 2


if __name__ == "__main__":
    sys.exit(main())
