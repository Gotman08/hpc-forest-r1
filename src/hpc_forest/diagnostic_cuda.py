"""Capture real in-process NVRTC output without changing its compiler options."""
from __future__ import annotations

import json
import platform
import shutil
from pathlib import Path

from .core import atomic_json, file_digest


def applicable(config, collector):
    return (platform.system() == "Linux" and collector in {"compiler", "disassembly"}
            and config.get("submission", {}).get("kind") == "cuda-kernel")


def prepare(directory, run):
    """Build the observer with the host C compiler; the CUDA compiler is untouched."""
    compiler = shutil.which("cc") or shutil.which("gcc")
    if not compiler:
        raise ValueError("NVRTC capture needs an available host C compiler")
    directory.mkdir(parents=True)
    source = Path(__file__).parent / "assets/diagnostics/nvrtc_capture.c"
    observer = directory / "nvrtc_capture.so"
    run([compiler, "-std=c11", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra",
         str(source), "-ldl", "-o", str(observer)], "nvrtc-observer-build")
    atomic_json(directory / "observer.json", {"source_sha256": file_digest(source),
        "observer_sha256": file_digest(observer), "host_compiler": compiler,
        "host_compiler_sha256": file_digest(Path(compiler)), "official_execution": False})
    return {"LD_PRELOAD": str(observer), "FOREST_NVRTC_CAPTURE": str(directory)}


def evidence(directory):
    records, binaries = [], {}
    for path in sorted(directory.glob("*.json")):
        if path.name == "observer.json":
            continue
        value = json.loads(path.read_text(encoding="utf8"))
        library = Path(value["library"])
        if library.is_file():
            value["library_sha256"] = file_digest(library)
        value["record"] = path.name
        records.append(value)
        cubin = path.with_suffix(".cubin")
        if value["cubin_captured"] and cubin.is_file() and cubin.stat().st_size:
            binaries.setdefault(file_digest(cubin), cubin)
    return {"status": "observed_invocations" if records else "no_invocations_intercepted",
            "kind": "nvrtc", "invocations": records,
            "binaries": [{"path": str(p), "sha256": sha} for sha, p in binaries.items()],
            "complete": False, "limitation": "Dynamic NVRTC calls only; static/dlopen symbol lookup may bypass interception",
            "options_unchanged": True, "official_score": None}


def disassemble(coverage, directory, run):
    tool = shutil.which("cuobjdump")
    if not tool:
        raise ValueError("CUDA disassembly requires cuobjdump; objdump cannot decode a CUDA bundle")
    if not coverage["binaries"]:
        raise ValueError("No native NVRTC CUBIN was captured; no disassembly can be claimed")
    run([tool, "--version"], "cuobjdump-version")
    atomic_json(directory / "cuda-disassembler.json", {"path": tool, "sha256": file_digest(Path(tool))})
    for index, item in enumerate(coverage["binaries"]):
        run([tool, "--dump-sass", "--dump-resource-usage", item["path"]], "cuda-disassembly-" + str(index))
