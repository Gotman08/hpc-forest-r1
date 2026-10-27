"""Check native invocation settings against archived original requests, read-only."""
from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    invocations, requests = {}, {}
    with tarfile.open(args.archive, "r|gz") as archive:
        for member in archive:
            name = member.name.removeprefix("./")
            if not member.isfile() or not name.startswith("worker/"):
                continue
            parent, leaf = name.rsplit("/", 1)
            if leaf not in ("invocation.json", "downloaded-request.json"):
                continue
            with archive.extractfile(member) as stream:
                raw = stream.read()
            data = json.loads(raw)
            if leaf == "invocation.json":
                invocations[parent] = {"model": data["model"], "effort": data["reasoning_effort"],
                                       "argv": data["argv"], "request_sha256": data["request_sha256"],
                                       "invocation_sha256": hashlib.sha256(raw).hexdigest()}
            else:
                requests[parent] = {"model": data["model"], "effort": data["reasoning_effort"],
                                    "role": data.get("meta_role") or data["kind"],
                                    "phase": data.get("budget_phase"),
                                    "request_sha256": hashlib.sha256(raw).hexdigest()}
    rows, errors = [], []
    for key, invocation in sorted(invocations.items()):
        request = requests.get(key)
        argv = invocation["argv"]
        native_model = argv[argv.index("--model") + 1] if "--model" in argv else None
        checks = {"luna_max_requested": invocation["model"] == "gpt-6-luna" and invocation["effort"] == "max",
                  "cli_model_matches": native_model == invocation["model"],
                  "cli_effort_matches": 'model_reasoning_effort="max"' in argv,
                  "original_request_bound": request is not None and all(
                      request[field] == invocation[field] for field in ("model", "effort", "request_sha256"))}
        if not all(checks.values()):
            errors.append({"worker": key, "checks": checks})
        rows.append({"worker": key, "role": request["role"] if request else None,
                     "phase": request["phase"] if request else None,
                     "model": invocation["model"], "effort": invocation["effort"],
                     "request_sha256": invocation["request_sha256"],
                     "invocation_sha256": invocation["invocation_sha256"], "checks": checks})
    if not rows:
        errors.append({"reason": "No native invocation evidence"})
    with args.archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    result = {"archive": str(args.archive), "archive_sha256": digest,
              "native_invocations": len(rows), "downloaded_requests": len(requests),
              "role_counts": dict(Counter(row["role"] for row in rows)),
              "valid": not errors, "errors": errors, "rows": rows,
              "interpretation": "Audits requested model/effort and native CLI settings, not provider internals or successful completion of every invocation."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
