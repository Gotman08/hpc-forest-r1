"""Compile only official references and freeze shared inputs inside a Slurm allocation."""
from __future__ import annotations

import argparse
import json
import os
import platform
import time
import traceback
from pathlib import Path

from archive_preparation import SUBJECTS, prepare

from hpc_forest.core import atomic_json, file_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if not os.environ.get("SLURM_JOB_ID", "").isdigit() or platform.machine() != "aarch64":
        parser.error("Reference compilation requires a real ARM64 Slurm allocation")
    output = root / "prepared"
    output.mkdir(exist_ok=False)
    records = {}
    for key, title in SUBJECTS.items():
        start = time.monotonic()
        try:
            prepared = prepare(key, root / "sources-officielles", output)
            records[key] = {"status": "ready", "title": title, "prepared": prepared}
        except Exception as exc:
            records[key] = {"status": "preparation_failed_no_model_called", "title": title,
                            "error": type(exc).__name__ + ": " + str(exc),
                            "traceback": traceback.format_exc()}
        records[key]["elapsed_seconds"] = time.monotonic() - start
        atomic_json(output / "preparation-progress.json", records)
        print(json.dumps({"event": "official_preparation", "subject": key,
                          "status": records[key]["status"], "error": records[key].get("error")}), flush=True)
    files = {p.relative_to(output).as_posix(): file_digest(p) for p in output.rglob("*") if p.is_file()}
    atomic_json(output / "prepared-manifest.json", {"schema": "hpc-forest-shared-official-preparation-v1",
                "job_id": os.environ["SLURM_JOB_ID"], "records": records, "files": files,
                "model_calls": 0, "candidate_source_changes": 0,
                "same_inputs_for_every_model_and_effort": True})
    return 0 if any(item["status"] == "ready" for item in records.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
