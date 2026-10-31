"""Diagnostic-only compiler interception; never used by the official evaluator."""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .core import atomic_json, file_digest

NAMES = ("cc", "c++", "gcc", "g++", "clang", "clang++", "gfortran", "flang",
         "nvcc", "nvc", "nvc++", "nvfortran", "mpicc", "mpicxx", "mpifort")


def diagnostic_flags(family, mode):
    if mode == "capture":
        return []
    if mode in {"symbols", "scorep", "scalasca"}:
        return ["-lineinfo"] if family == "nvcc" else ["-g"] if family in {"gcc", "clang", "nvhpc"} else []
    if family == "gcc":
        return ["-g", "-fopt-info-all", "-save-temps=obj", "-fdump-tree-optimized"]
    if family == "clang":
        return ["-g", "-Rpass=.*", "-Rpass-missed=.*", "-Rpass-analysis=.*",
                "-fsave-optimization-record", "-save-temps=obj"]
    if family == "nvcc":
        return ["-lineinfo", "--keep"]
    if family == "nvhpc":
        return ["-g", "-Minfo=all"]
    return []


def family_for(version):
    value = version.lower()
    if "cuda compilation tools" in value:
        return "nvcc"
    if "clang" in value or "flang" in value:
        return "clang"
    if "gcc" in value or "free software foundation" in value or "gfortran" in value:
        return "gcc"
    if any(n in value for n in ("nvc ", "nvc++", "nvfortran")):
        return "nvhpc"
    return "unknown"


def prepare(directory, config, mode, run):
    """Capture actual versions and hashes; unknown compilers never receive guessed flags."""
    directory.mkdir(parents=True)
    records = directory / "records"
    records.mkdir()
    compilers, aliases = {}, {}
    candidates = {name: shutil.which(name) for name in NAMES}
    configured = config.get("compiler", {}).get("path")
    if configured:
        candidates[Path(configured).name] = configured
    for name, path in candidates.items():
        if not path or not Path(path).is_file():
            continue
        resolved = str(Path(path).resolve())
        if resolved not in compilers:
            result = run([resolved, "--version"], "compiler-version-" + str(len(compilers)), optional=True)
            version = Path(result["log"]).read_text(errors="replace") if result else "unavailable"
            compilers[resolved] = {"path": resolved, "sha256": file_digest(Path(resolved)),
                                   "version": version[:12000], "family": family_for(version)}
        aliases[name] = compilers[resolved]
    atomic_json(directory / "compilers.json", aliases)
    env = {"FOREST_DIAGNOSTIC_COMPILERS": str(directory / "compilers.json"),
           "FOREST_DIAGNOSTIC_RECORDS": str(records), "FOREST_DIAGNOSTIC_MODE": mode}
    if os.name != "posix":
        return env, {"status": "unavailable", "reason": "Compiler interception currently requires POSIX", "compilers": aliases}
    for name in aliases:
        wrapper = directory / name
        wrapper.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable)
                           + " -m hpc_forest.diagnostic_compiler " + shlex.quote(name) + ' "$@"\n', encoding="utf8")
        wrapper.chmod(0o700)
    env["PATH"] = str(directory) + os.pathsep + os.environ.get("PATH", "")
    if configured and Path(configured).name in aliases:
        env["HPC_FOREST_CC"] = str(directory / Path(configured).name)
    return env, {"status": "interception_prepared", "compilers": aliases,
                 "limitation": "Absolute paths, compiler caches and toolchains outside this list may bypass interception"}


def main():
    name, *arguments = sys.argv[1:]
    compiler = json.loads(Path(os.environ["FOREST_DIAGNOSTIC_COMPILERS"]).read_text(encoding="utf8"))[name]
    mode = os.environ["FOREST_DIAGNOSTIC_MODE"]
    # Compiler discovery and configure probes must not gain compilation-only flags.
    compiles = any(Path(arg).suffix.lower() in {".c", ".cc", ".cpp", ".cxx", ".cu", ".f", ".f90"}
                   for arg in arguments) or any(arg.startswith("@") for arg in arguments)
    flags = diagnostic_flags(compiler["family"], mode) if compiles else []
    command = [compiler["path"], *arguments, *flags]
    instrumented = mode in {"scorep", "scalasca"} and not any(a in arguments for a in ("--version", "-v", "-E"))
    if instrumented:
        command.insert(0, os.environ["FOREST_DIAGNOSTIC_SCOREP"])
    record = {"compiler": compiler, "original_arguments": arguments, "diagnostic_flags": flags,
              "argv": command, "cwd": os.getcwd(), "mode": mode, "scorep_instrumented": instrumented,
              "started_at": time.time(), "returncode": None}
    path = Path(os.environ["FOREST_DIAGNOSTIC_RECORDS"]) / (uuid.uuid4().hex + ".json")
    atomic_json(path, record)
    result = subprocess.run(command, check=False)
    atomic_json(path, {**record, "returncode": result.returncode, "finished_at": time.time()})
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
