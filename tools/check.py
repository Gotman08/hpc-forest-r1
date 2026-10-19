"""Run local checks with this project's source in parent and child processes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    run = root / "artifacts" / datetime.now(UTC).strftime("checks-%Y%m%dT%H%M%S-%fZ")
    run.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    commands = [
        [sys.executable, "-B", "-m", "ruff", "check", "src", "tests", "tools"],
        [
            sys.executable, "-B", "-m", "pytest", "-q",
            "--basetemp", str(run / "tmp"),
            "-o", f"cache_dir={run / 'pytest-cache'}",
            "--junitxml", str(run / "tests.xml"),
        ],
    ]
    results = []
    for index, command in enumerate(commands, 1):
        completed = subprocess.run(
            command, cwd=root, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=900,
        )
        log = run / f"check-{index}.log"
        log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
        print(completed.stdout, end="")
        print(completed.stderr, end="", file=sys.stderr)
        results.append({"command": command, "exit_code": completed.returncode, "log": str(log)})
        if completed.returncode:
            break
    receipt = {
        "schema": "hpc-forest-r1-local-checks-v1",
        "source": str(root / "src"), "python": sys.executable,
        "passed": len(results) == len(commands) and all(r["exit_code"] == 0 for r in results),
        "checks": results,
        "scientific_campaign_launched": False,
    }
    (run / "result.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("Verification receipt:", run / "result.json")
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
