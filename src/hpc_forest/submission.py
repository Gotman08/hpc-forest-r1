"""Explicit delivery contracts for executable programs and NVRTC CUDA bundles."""
from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import PurePosixPath

from .core import ForestError


def validate_submission(config):
    settings = config.get("submission", {"kind": "executable"})
    if (not isinstance(settings, dict) or not isinstance(settings.get("kind"), str)
            or settings["kind"] not in {"executable", "cuda-kernel"}):
        raise ForestError("submission.kind must be executable or cuda-kernel")
    if settings["kind"] == "executable":
        if set(settings) != {"kind"}:
            raise ForestError("Executable submission accepts only its kind")
        return
    if set(settings) != {"kind", "source", "launch", "kernel"}:
        raise ForestError("CUDA submission requires kind, source, launch and kernel")
    for key, suffix in (("source", ".cu"), ("launch", ".json")):
        name = settings[key]
        if (not isinstance(name, str) or "\\" in name or ":" in name
                or not name.startswith("src/") or not name.endswith(suffix)
                or any(part in {"", ".", ".."} for part in name.split("/"))
                or PurePosixPath(name).is_absolute()):
            raise ForestError("CUDA submission paths must be relative files inside src/")
    if not isinstance(settings["kernel"], str) or not re.fullmatch(r"[A-Za-z_]\w*", settings["kernel"]):
        raise ForestError("CUDA submission kernel must be a C identifier")


def resolve_submission(config, source):
    """Pin the imported artifact type before any model is called."""
    if "submission" in config:
        return config["submission"]
    if (source / "Makefile").is_file() or (source / "run.sh").is_file():
        return {"kind": "executable"}
    kernels = list((source / "src").glob("*.cu"))
    launch = source / "src/launch.json"
    if len(kernels) == 1 and launch.is_file():
        entries = re.findall(r'extern\s+"C"\s+__global__\s+void\s+(\w+)\s*\(',
                             kernels[0].read_text(encoding="utf8"))
        if len(entries) == 1:
            return {"kind": "cuda-kernel", "source": kernels[0].relative_to(source).as_posix(),
                    "launch": "src/launch.json", "kernel": entries[0]}
    return {"kind": "executable"}


def validate_launch(value):
    if not isinstance(value, dict) or set(value) != {"block", "items_per_block", "shared_memory_bytes"}:
        raise ForestError("CUDA launch requires block, items_per_block and shared_memory_bytes")
    for key, minimum, maximum in (("block", 1, 1024), ("items_per_block", 1, 1048576),
                                  ("shared_memory_bytes", 0, 49152)):
        if type(value[key]) is not int or not minimum <= value[key] <= maximum:
            raise ForestError("Invalid CUDA launch field: " + key)
    return value


def delivery_manifest(archive, config):
    validate_submission(config)
    settings = config.get("submission", {"kind": "executable"})
    names = set(archive.namelist())
    if settings["kind"] == "executable":
        if not {"Makefile", "run.sh"}.issubset(names):
            raise ForestError("Submission requires a Makefile and run.sh in the imported repository")
        return {"kind": "executable", "entrypoint": "run.sh"}
    files = {}
    for key in ("source", "launch"):
        name = settings[key]
        if name not in names:
            raise ForestError("CUDA submission is missing its confirmed " + key + ": " + name)
        info = archive.getinfo(name)
        if stat.S_ISLNK(info.external_attr >> 16) or info.is_dir():
            raise ForestError("CUDA submission requires regular files")
        data = archive.read(name)
        files[key] = {"path": name, "sha256": hashlib.sha256(data).hexdigest()}
    try:
        launch = validate_launch(json.loads(archive.read(settings["launch"])))
        source = archive.read(settings["source"]).decode("utf8")
    except (ValueError, UnicodeError) as exc:
        raise ForestError("Malformed confirmed CUDA source or launch settings") from exc
    if not re.search(r"\b" + re.escape(settings["kernel"]) + r"\s*\(", source):
        raise ForestError("Confirmed CUDA source does not contain its declared kernel")
    return {"kind": "cuda-kernel", "format": "hpc-forest-cuda-kernel-v1", "kernel": settings["kernel"],
            "files": files, "launch": launch,
            "grid_rule": "grid.x = ceil(N / items_per_block); grid.y = grid.z = 1",
            "block_rule": "block.x = block; block.y = block.z = 1",
            "execution": "NVRTC device source and launch configuration for the declared host interface"}
