"""Portable compiler detection; never installs global software or changes the user's PATH."""

from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .core import InfrastructureError, file_digest


@functools.lru_cache(maxsize=1)
def compiler() -> tuple[str, dict[str, str]]:
    configured = os.environ.get("HPC_FOREST_CC")
    if configured:
        executable = shutil.which(configured) or configured
        if not Path(executable).is_file():
            raise InfrastructureError(f"HPC_FOREST_CC not found: {configured}")
        return str(executable), dict(os.environ)
    for name in ["cl", "gcc", "clang"] if os.name == "nt" else ["gcc", "cc", "clang"]:
        found = shutil.which(name)
        if found:
            return found, dict(os.environ)
    if os.name == "nt":
        root = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft Visual Studio"
        paths = sorted(root.glob("*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe"), reverse=True)
        for executable in paths:
            installation = executable.parents[7]
            setup = installation / "Common7" / "Tools" / "VsDevCmd.bat"
            if setup.exists():
                result = subprocess.run(
                    f'cmd.exe /d /s /c ""{setup}" -arch=x64 -host_arch=x64 >nul && set"',
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=60,
                    check=False,
                )
                if result.returncode == 0:
                    env = dict(os.environ)
                    for line in result.stdout.splitlines():
                        if "=" in line and not line.startswith("="):
                            key, value = line.split("=", 1)
                            env[key] = value
                    return str(executable), env
    raise InfrastructureError(
        "Install a C compiler with OpenMP, or set HPC_FOREST_CC in a developer shell"
    )


def compiler_identity() -> dict:
    executable, _ = compiler()
    return {
        "path": executable,
        "sha256": file_digest(Path(executable)),
        "flavor": "msvc" if Path(executable).name.lower() == "cl.exe" else "gcc-compatible",
    }


def build(worktree: Path, destination: Path) -> int:
    try:
        executable, env = compiler()
    except InfrastructureError as exc:
        print(str(exc), file=sys.stderr)
        return 70
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / ("solution.exe" if os.name == "nt" else "solution")
    source = worktree / "src" / "main.c"
    if Path(executable).name.lower() == "cl.exe":
        args = [
            executable,
            "/nologo",
            "/O2",
            "/std:c11",
            "/openmp:experimental",
            str(source),
            f"/Fe:{output}",
            f"/Fo:{destination}{os.sep}",
        ]
    else:
        args = [executable, "-O3", "-std=c11", "-fopenmp", str(source), "-o", str(output)]
    print("COMPILER", executable, flush=True)
    print("BUILD_ARGUMENTS", json.dumps(args), flush=True)
    result = subprocess.run(args, cwd=destination, env=env, check=False)
    return result.returncode
