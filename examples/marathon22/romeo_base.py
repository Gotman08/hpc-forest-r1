#!/usr/bin/env python3
"""Longer Ollama AB-MCTS campaign; run inside a fresh ROMEO GPU allocation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback
import zipfile
from pathlib import Path

import hpc_forest
import evidence_pack
from hpc_forest.config import load_config
from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import atomic_json
from hpc_forest.ollama_backend import request_json, resolve_model
from hpc_forest.reporting import package, report
from hpc_forest.search import unpack

MODELS = ["qwen2.5-coder:14b"]
PREPARE_MODEL = None


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(command: list[str]) -> dict:
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def emit(event: str, **values) -> None:
    print(
        json.dumps(
            {"event": event, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **values},
            ensure_ascii=False,
        ),
        flush=True,
    )


def tree_snapshot(controller):
    labels = {}
    for row in controller.db.rows("SELECT mission FROM trials ORDER BY created,id"):
        mission = json.loads(row["mission"])
        labels[mission["id"]] = mission["role"] + str(mission["ordinal"])
    trees, scored, max_depth, max_children = [], 0, 0, 0
    for row in controller.db.rows("SELECT * FROM trees ORDER BY role"):
        if row["version"] != "0.3.2":
            raise RuntimeError("Unexpected checkpoint version")
        state, _ = unpack(row["checkpoint"], row["sha256"])
        nodes, queue = [], [(state.tree.root, None, 0)]
        while queue:
            node, parent, depth = queue.pop(0)
            node_id = node.state["experiment_id"] if node.state else row["id"]
            item = {"id": node_id, "label": labels.get(node_id, row["role"]),
                    "parent": parent, "depth": depth, "score": node.score,
                    "child_count": len(node.children)}
            nodes.append(item)
            max_depth = max(max_depth, depth)
            max_children = max(max_children, len(node.children))
            scored += int(node.state is not None)
            queue.extend((child, node_id, depth + 1) for child in node.children)
        trees.append({"role": row["role"], "checkpoint_sha256": row["sha256"], "nodes": nodes})
    return {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": controller.db.get("status"),
            "cursor": controller.db.get("plan_cursor:1", 0), "trials": len(labels),
            "scored_nodes": scored, "max_depth": max_depth, "max_children": max_children,
            "tokens_used": controller.db.costs()["tokens_used"], "trees": trees}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--ollama", type=Path, required=True)
    parser.add_argument("--detector", type=Path, required=True)
    args = parser.parse_args()
    job = os.environ.get("SLURM_JOB_ID", "")
    if not job.isdigit() or not os.environ.get("CUDA_VISIBLE_DEVICES"):
        parser.error("This runner requires its own Slurm GPU allocation")
    base = args.root.resolve(strict=True)
    output = base / f"results-{job}"
    output.mkdir(exist_ok=False)
    started = time.monotonic()
    overall = {
        "format": "hpc-forest-marathon22-32b-v10b",
        "job_id": job,
        "problems": [],
        "complete": False,
    }
    process = None
    cache = None
    server_log = None
    try:
        source = Path(hpc_forest.__file__).parent
        wheel = base / "payload-r4/hpc_forest-0.1.0-py3-none-any.whl"
        if sha256(wheel) != "e065b4b138ba927748616b1da402514f186fae669c58246fda47de7b96e5b6fd":
            raise RuntimeError("Tested wheel identity changed")
        with zipfile.ZipFile(wheel) as wheel_zip:
            checked = 0
            for member in wheel_zip.namelist():
                if member.startswith("hpc_forest/") and not member.endswith("/"):
                    installed = source / member.removeprefix("hpc_forest/")
                    if installed.read_bytes() != wheel_zip.read(member):
                        raise RuntimeError("Installed source differs from the tested wheel: " + member)
                    checked += 1
        if importlib.metadata.version("treequest") != "0.3.2":
            raise RuntimeError("Unexpected TreeQuest version")
        atomic_json(output / "software-verification.json", {"wheel_sha256": sha256(wheel), "verified_package_files": checked, "treequest": "0.3.2", "controller_modified": False})
        atomic_json(
            output / "source-manifest.json",
            {
                p.relative_to(source).as_posix(): sha256(p)
                for p in sorted(source.rglob("*"))
                if p.is_file() and "__pycache__" not in p.parts
            },
        )
        metadata = {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": sys.version,
            "python_executable": sys.executable,
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "slurm": {k: v for k, v in os.environ.items() if k.startswith("SLURM_")},
            "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
            "ollama_binary": str(args.ollama.resolve()),
            "ollama_sha256": sha256(args.ollama),
            "runner_sha256": sha256(Path(__file__)),
            "resource_detector_sha256": sha256(args.detector),
            "dependencies": {
                name: importlib.metadata.version(name)
                for name in ["hpc-forest", "treequest", "numpy", "scipy", "psutil"]
            },
            "gpu": capture(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,uuid,memory.total,driver_version",
                    "--format=csv,noheader",
                ]
            ),
            "packages": capture([sys.executable, "-m", "pip", "freeze"]),
        }
        atomic_json(output / "allocation.json", metadata)
        shutil.copyfile(base / "preflight-tests.log", output / "preflight-tests.log")
        shutil.copyfile(base / "timer-probe.json", output / "timer-probe.json")
        shutil.copyfile(base / "assistance-protocol.json", output / "assistance-protocol.json")
        detector = capture(
            [sys.executable, str(args.detector), "--output", str(output / "resources.json")]
        )
        atomic_json(output / "resource-detection-log.json", detector)
        if detector["returncode"]:
            raise RuntimeError("Resource detector failed")
        # Kernel-selected loopback port; this process owns the only server it starts.
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        cache = Path(tempfile.mkdtemp(prefix=f"hpc-forest-{job}-", dir="/dev/shm"))
        (cache / "OWNER").write_text(job, encoding="ascii")
        env = os.environ.copy()
        env.update(
            HOME=str(cache),
            XDG_CACHE_HOME=str(cache / "cache"),
            GOMAXPROCS=str(len(os.sched_getaffinity(0))),
            OLLAMA_HOST=f"127.0.0.1:{port}",
            OLLAMA_MODELS=str(cache / "models"),
            OLLAMA_NO_CLOUD="1",
            OLLAMA_NUM_PARALLEL="1",
            OLLAMA_MAX_LOADED_MODELS="1",
            LLAMA_ARG_CACHE_RAM="0",
            OLLAMA_CONTEXT_LENGTH="32768",
            OLLAMA_KEEP_ALIVE="5m",
            OLLAMA_FLASH_ATTENTION="1",
        )
        server_log = (output / "ollama-server.log").open("w", encoding="utf-8")
        process = subprocess.Popen(
            [str(args.ollama.resolve()), "serve"],
            env=env,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        atomic_json(
            output / "server.json",
            {
                "pid": process.pid,
                "pgid": os.getpgid(process.pid),
                "base_url": url,
                "cache": str(cache),
                "environment": {
                    k: v
                    for k, v in env.items()
                    if k.startswith("OLLAMA_") or k == "LLAMA_ARG_CACHE_RAM"
                },
            },
        )
        readiness = time.monotonic() + 30
        while True:
            if process.poll() is not None:
                raise RuntimeError(f"Owned Ollama server exited with {process.returncode}")
            try:
                version = request_json(url, "/api/version", None, 2)
                if version.get("version") != "0.40.4":
                    raise RuntimeError(f"Unexpected Ollama version: {version}")
                atomic_json(output / "server-version.json", version)
                break
            except Exception:
                if time.monotonic() >= readiness:
                    raise
                time.sleep(0.5)
        target = f"romeo:{socket.gethostname()}:slurm-{job}:cpu-marathon22"
        if PREPARE_MODEL is not None:
            PREPARE_MODEL(url, cache, output)
        for model in MODELS:
            overall["problems"].append(campaign(url, model, output, target))
            atomic_json(output / "results.json", overall)
        overall["complete"] = all(m["complete"] for m in overall["problems"])
    except Exception as exc:
        overall["error"] = f"{type(exc).__name__}: {exc}"
        overall["traceback"] = traceback.format_exc()
        emit("runner_error", error=overall["error"])
    finally:
        cleanup = {"owned_server_stopped": process is None, "owned_cache_removed": cache is None}
        if process is not None:
            try:
                if process.poll() is None:
                    if os.getpgid(process.pid) != process.pid:
                        raise RuntimeError("Owned server process-group identity changed")
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=10)
                cleanup["owned_server_stopped"] = True
                cleanup["server_returncode"] = process.returncode
            except Exception as exc:
                cleanup["server_error"] = str(exc)
        if server_log:
            server_log.close()
        if cache is not None:
            try:
                if (
                    cache.is_symlink()
                    or cache.resolve().parent != Path("/dev/shm")
                    or not cache.name.startswith(f"hpc-forest-{job}-")
                    or (cache / "OWNER").read_text(encoding="ascii") != job
                ):
                    raise RuntimeError("Refusing cleanup of an unowned model directory")
                shutil.rmtree(cache)
                cleanup["owned_cache_removed"] = not cache.exists()
            except Exception as exc:
                cleanup["cache_error"] = str(exc)
        overall["elapsed_seconds"] = time.monotonic() - started
        atomic_json(output / "cleanup.json", cleanup)
        atomic_json(output / "results.json", overall)
        archive = base / f"results-{job}.tar.gz"
        evidence_pack.make(output, base / "sources-officielles", archive)
        archive.with_suffix(archive.suffix + ".sha256").write_text(
            f"{sha256(archive)}  {archive.name}\n", encoding="ascii"
        )
        emit(
            "runner_end",
            complete=overall["complete"],
            archive=str(archive),
            sha256=sha256(archive),
            cleanup=cleanup,
        )
    return 0 if overall["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
