"""Build from a fresh staging directory so stale modules cannot enter a wheel."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory for source, distributions and receipt")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    staging = output / "source"
    staging.mkdir()
    for name in ("pyproject.toml", "MANIFEST.in", "README.md", "AGENTS.md", "CHANGELOG.md", "CONTRIBUTING.md"):
        shutil.copy2(root / name, staging / name)
    for path in root.glob("requirements-*.lock"):
        shutil.copy2(path, staging / path.name)
    for name in ("src", "configs", "scripts", "docs"):
        shutil.copytree(root / name, staging / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.egg-info", "images", "evidence", "reference"))
    environment = dict(os.environ)
    epoch = environment.get("SOURCE_DATE_EPOCH") or subprocess.check_output(
        ["git", "show", "-s", "--format=%ct", "HEAD"], cwd=root, text=True).strip()
    if not epoch.isdecimal():
        raise ValueError("SOURCE_DATE_EPOCH must contain a Unix timestamp")
    environment["SOURCE_DATE_EPOCH"] = epoch
    command = [sys.executable, "-m", "build", str(staging), "--no-isolation", "--outdir", str(output / "dist")]
    subprocess.run(command, check=True, env=environment)
    wheel, = (output / "dist").glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if any("advisor" in name.lower() for name in names):
            raise RuntimeError("Retired advisor entered the distribution")
        expected = {p.relative_to(root / "src").as_posix(): p for p in (root / "src/hpc_forest").rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts}
        actual = {n for n in names if n.startswith("hpc_forest/") and not n.endswith("/")}
        if set(expected) != actual:
            raise RuntimeError("Wheel source inventory mismatch: " + str(set(expected) ^ actual))
        if any(archive.read(name) != path.read_bytes() for name, path in expected.items()):
            raise RuntimeError("Wheel differs from the validated source")
    receipt = {"wheel": wheel.name, "source_files_verified": len(expected), "source_date_epoch": int(epoch),
               "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(), "publication": False}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
