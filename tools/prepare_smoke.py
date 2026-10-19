"""Prepare a fresh local payload; neither submits a job nor calls a model."""
from __future__ import annotations

import argparse
import json
import tarfile
import time
import uuid
from pathlib import Path

from native_smoke import EFFORT, MODEL, OFFICIAL_SCOPE, PILOTS, SCOPE

from hpc_forest.core import atomic_json, file_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", choices=("2023-count", "matmul"), default="2023-count",
                        help="An official subject is the default; matmul is only a synthetic example")
    parser.add_argument("--binary-tree", action="store_true",
                        help="Prepare the optional binary policy on the official subject")
    args = parser.parse_args()
    official = args.subject == "2023-count"
    if args.binary_tree and not official:
        parser.error("Use an official subject to compare search policies")
    scope = OFFICIAL_SCOPE if official else SCOPE
    project = Path(__file__).resolve().parent.parent
    session = uuid.uuid4().hex
    destination = project / "artifacts" / (("official-count-" if official else "luna-smoke-") + session[:8])
    destination.mkdir(exist_ok=False)
    remote_root = "/scratch_p/nimarano/" + PILOTS[scope][2] + session
    plan = {"scope": scope, "session_id": session, "model": MODEL, "effort": EFFORT,
            "subject": args.subject, "child_missions": 8 if official else 4, "mother_calls": 2,
            "wall_seconds": 1800 if official else 900, "token_budget": 1500000, "seed": 23,
            "maximum_calls_including_repairs": 26 if official else 14, "cores": 4, "gpus": 0,
            "remote_root": remote_root, "created_at": time.time(),
            "purpose": "official R1 matched protocol" if official else "synthetic mechanical smoke",
            "historical_candidates_imported": False}
    plan["binary_tree"] = {"enabled": args.binary_tree}
    if official:
        prepared = project / "artifacts/official-prepared-manifest.json"
        statement = project / "artifacts/official-2023-statement.txt"
        shared = "/gpfs/scratch/nimarano/hpc-forest-native-matrix-20261015-r1-launchfix1"
        plan["preparation_manifest"] = {"path": shared + "/prepared/prepared-manifest.json",
                                        "sha256": file_digest(prepared)}
        plan["statement"] = {"path": shared + "/statements/2023.txt", "sha256": file_digest(statement)}
    atomic_json(destination / "plan.json", plan)
    files = []
    for relative in ("src", "tests", "tools", "examples/marathon22" if official else "examples/matmul"):
        files.extend(path for path in (project / relative).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts)
    files.extend(project / name for name in ("pyproject.toml", "AGENTS.md", "README.md"))
    manifest = {path.relative_to(project).as_posix(): file_digest(path)
                for path in sorted(files)}
    atomic_json(destination / "runtime-manifest.json", manifest)
    payload = destination / "payload.tar.gz"
    with tarfile.open(payload, "w:gz") as archive:
        for path in sorted(files):
            archive.add(path, arcname="project/" + path.relative_to(project).as_posix())
        for name in ("plan.json", "runtime-manifest.json"):
            archive.add(destination / name, arcname=name)
    remote_payload = remote_root + ".tar.gz"
    receipt = {"scope": scope, "model": MODEL, "effort": EFFORT,
               "session_id": session, "expires_at": time.time() + 3600,
               "historical_campaign_resumption": False,
               "user_request": "Tester Luna MAX sur un des sujets officiels precedemment etudies" if official
                               else "Un exemple synthetique distinct et explicitement selectionne",
               "plan": {"path": str(destination / "plan.json"),
                        "sha256": file_digest(destination / "plan.json")},
               "payload": {"path": str(payload), "sha256": file_digest(payload)},
               "remote_payload": remote_payload, "channel": None}
    atomic_json(destination / "authorization-pending.json", receipt)
    print(json.dumps({"destination": str(destination), "remote_root": remote_root,
                      "remote_payload": remote_payload, "sha256": file_digest(payload)}))


if __name__ == "__main__":
    main()
