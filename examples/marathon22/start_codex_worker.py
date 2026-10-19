"""Start only the owned local worker; keep the parent chat and other processes intact."""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from hpc_forest.codex_process import check_dependencies
from hpc_forest.core import atomic_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--codex-config", type=Path, required=True)
    parser.add_argument("--dependency-receipt", type=Path, required=True)
    parser.add_argument("--required-jobs", nargs="+", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    check_dependencies(args.dependency_receipt, set(args.required_jobs))
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    record = args.output / "process-identity.json"
    if record.exists() and not args.resume:
        parser.error("An identity record already exists: inspect that exact process before resuming")
    if args.resume:
        record = args.output / f"process-identity-resume-{time.time_ns()}.json"
    argv = [sys.executable, "-m", "hpc_forest.codex_worker", "--channel", args.channel,
            "--session-id", args.session_id, "--output", str(args.output),
            "--codex-config", str(args.codex_config.resolve()),
            "--dependency-receipt", str(args.dependency_receipt.resolve()),
            "--required-jobs", *args.required_jobs]
    flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
    log_mode = "ab" if args.resume else "xb"
    with (args.output / "worker.stdout.log").open(log_mode) as out, (args.output / "worker.stderr.log").open(log_mode) as err:
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                   creationflags=flags, start_new_session=os.name != "nt")
    atomic_json(record, {"pid": process.pid, "started_at": time.time(), "executable": sys.executable,
                        "argv": argv, "channel": args.channel, "session_id": args.session_id})
    print(f"Owned worker started: {process.pid}; identity stored in {record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
