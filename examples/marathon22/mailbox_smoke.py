"""Allocation-side file-transport check: zero model calls, no problem or algorithm."""
import argparse
import json
import os
import platform
import tarfile
import time
import uuid
from pathlib import Path

from hpc_forest.codex_mailbox import (
    EFFORT,
    MODEL,
    PROTOCOL,
    initialize_channel,
    publish_request,
    sha256,
    wait_response,
)
from hpc_forest.core import atomic_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()
    job = os.environ.get("SLURM_JOB_ID", "")
    if not job.isdigit():
        parser.error("The transport check needs its own Slurm allocation")
    output = args.root / f"results-{job}"
    output.mkdir(exist_ok=False)
    channel = output / "mailbox"
    initialize_channel(channel, args.session_id, job)
    metadata = {"channel": str(channel), "session_id": args.session_id, "job_id": job}
    atomic_json(output / "channel.json", metadata)
    print(json.dumps({"event": "mailbox_smoke_ready", **metadata}), flush=True)
    request = {"protocol": PROTOCOL, "kind": "transport-smoke", "nonce": uuid.uuid4().hex,
               "session_id": args.session_id, "model": MODEL, "reasoning_effort": EFFORT,
               "expires_at": time.time() + 180}
    result = {"job_id": job, "verified": False, "model_calls": 0,
              "test": "file_transport_only", "machine": platform.machine()}
    try:
        request_sha = publish_request(channel, request)
        response = wait_response(channel, request, request_sha)
        assert response["data"]["ack"] == request["nonce"]
        assert response["usage"]["tokens"] == 0 and response["usage"]["llm_calls"] == 0
        result.update(verified=True, request_sha256=request_sha,
                      response_sha256=sha256((channel / "responses" / f"{request['nonce']}.response.json").read_bytes()))
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        atomic_json(output / "smoke-result.json", result)
        archive = args.root / f"results-{job}.tar.gz"
        with tarfile.open(archive, "w:gz") as package:
            package.add(output, arcname=output.name)
        print(json.dumps({"event": "runner_end", "complete": result["verified"],
                          "model_calls": 0, "archive": str(archive),
                          "sha256": sha256(archive.read_bytes())}), flush=True)
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
