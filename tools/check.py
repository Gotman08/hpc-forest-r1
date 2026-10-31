"""Run local checks with this project's source in parent and child processes."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    run = root / "artifacts" / datetime.now(UTC).strftime("checks-%Y%m%dT%H%M%S-%fZ")
    run.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if os.name == "nt" and not shutil.which("gcc") and Path("C:/msys64/ucrt64/bin/gcc.exe").is_file():
        env["PATH"] = "C:/msys64/ucrt64/bin;" + env.get("PATH", "")
    def hashes():
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (root / "src").rglob("*") if p.is_file() and "__pycache__" not in p.parts
                and not any(part.endswith(".egg-info") for part in p.parts)}
    before = hashes()
    # Bundle extraction adds long package paths; keep Windows below MAX_PATH.
    temporary = Path(tempfile.mkdtemp(prefix="forest-check-"))
    commands = [
        [sys.executable, "-B", "-m", "ruff", "check", "src", "tests", "tools"],
        [
            sys.executable, "-B", "-m", "pytest", "-q",
            "--basetemp", str(temporary),
            "-o", f"cache_dir={run / 'pytest-cache'}",
            "--junitxml", str(run / "tests.xml"),
        ],
    ]
    node = shutil.which("node")
    if not node and Path("C:/Program Files/nodejs/node.exe").is_file():
        node = "C:/Program Files/nodejs/node.exe"
    if node:
        # List every interface test explicitly; older Node versions do not expand globs.
        commands.append([node, "--test", *sorted(p.relative_to(root).as_posix()
                                                  for p in (root / "tests").glob("*.mjs"))])
    results = []
    for index, command in enumerate(commands, 1):
        completed = subprocess.run(
            command, cwd=root, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=3600,
        )
        log = run / f"check-{index}.log"
        log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
        print(completed.stdout, end="")
        print(completed.stderr, end="", file=sys.stderr)
        results.append({"command": command, "exit_code": completed.returncode, "log": str(log)})
        if completed.returncode:
            break
    unchanged = before == hashes()
    counts = {}
    if (run / "tests.xml").is_file():
        cases = list(ElementTree.parse(run / "tests.xml").iter("testcase"))
        counts = {"tests": len(cases), "failures": sum(c.find("failure") is not None for c in cases),
                  "errors": sum(c.find("error") is not None for c in cases),
                  "skipped": sum(c.find("skipped") is not None for c in cases)}
    receipt = {
        "schema": "hpc-forest-r1-local-checks-v1",
        "source": str(root / "src"), "python": sys.executable,
        "passed": unchanged and bool(node) and len(results) == len(commands) and all(r["exit_code"] == 0 for r in results),
        "source_unchanged": unchanged, "source_hashes": before, "counts": counts,
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
