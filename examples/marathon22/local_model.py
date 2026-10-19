"""Prepare pinned GGUF weights inside one owned, ephemeral compute-node cache."""

import concurrent.futures
import hashlib
import http.client
import json
import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from hpc_forest.core import atomic_json
from hpc_forest.ollama_backend import request_json, resolve_model

RANGE_THRESHOLD = 1024**3
RANGE_BYTES = 256 * 1024**2
RETRY_DELAYS = (1, 2, 4, 8)
DOWNLOAD_SECONDS = 3600


def read_spec(path):
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*:[a-z0-9_.-]+", spec["model"]):
        raise ValueError("Expected an explicit local model name and tag")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", spec["upstream"]):
        raise ValueError("Expected a Hugging Face repository")
    if not re.fullmatch(r"[0-9a-f]{40}", spec["revision"]):
        raise ValueError("Expected an immutable model repository revision")
    if not isinstance(spec["files"], list) or not 1 <= len(spec["files"]) <= 64:
        raise ValueError("Expected one to sixty-four pinned GGUF shards")
    names = set()
    for item in spec["files"]:
        name = item["name"]
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+\.gguf", name)
            or name in names
        ):
            raise ValueError("Invalid or repeated GGUF shard name")
        names.add(name)
        if (
            not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
            or type(item["bytes"]) is not int
            or item["bytes"] <= 0
        ):
            raise ValueError("Expected a full shard digest and positive size")
        expected = f"https://huggingface.co/{spec['upstream']}/resolve/{spec['revision']}/{name}"
        if item["url"] != expected:
            raise ValueError("Shard URL must use the declared immutable revision")
    return spec


def checksum(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(16 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def installed_manifest(cache, identity):
    digest = identity["model_digest"]
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise RuntimeError("Expected a full installed manifest digest")
    # New Ollama versions store named manifests through manifests-v2 links.
    # Read the content-addressed object, whose bytes the tags API identifies.
    path = cache / "models/blobs" / ("sha256-" + digest)
    if not path.is_file():
        path = (
            cache
            / "models/manifests/registry.ollama.ai/library"
            / identity["model"].replace(":", "/")
        )
    if not path.is_file() or path.stat().st_size > 1024**2:
        raise RuntimeError("Installed model manifest is missing or oversized")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise RuntimeError("Installed model manifest does not match the resolved identity")
    return raw, json.loads(raw)


def interface_smoke(url, model, output):
    """Check the JSON transport with a trivial acknowledgement, outside search."""
    schema = {
        "type": "object",
        "properties": {"ack": {"type": "string"}},
        "required": ["ack"],
        "additionalProperties": False,
    }
    payload = {
        "model": model,
        "stream": False,
        "format": schema,
        "messages": [
            {"role": "user", "content": "Return a JSON object with ack equal to romeo-ready."}
        ],
        "options": {"num_ctx": 32768, "num_predict": 256, "num_thread": 4, "temperature": 0},
        "keep_alive": "10m",
    }
    atomic_json(output / "interface-smoke-request.json", payload)
    response = request_json(url, "/api/chat", payload, 600)
    atomic_json(output / "interface-smoke-response.json", response)
    if (
        response.get("model") != model
        or response.get("done") is not True
        or json.loads(response["message"]["content"]) != {"ack": "romeo-ready"}
    ):
        raise RuntimeError("The local model did not pass its semantic JSON transport check")
    residents = request_json(url, "/api/ps", None, 15)
    atomic_json(output / "interface-smoke-residency.json", residents)
    if not any(
        m.get("name") == model and m.get("size_vram", 0) > 0 for m in residents.get("models", [])
    ):
        raise RuntimeError("GPU model residency not observed after the transport check")
    return {
        "semantic_json_verified": True,
        "gpu_residency_verified": True,
        "prompt_eval_count": response.get("prompt_eval_count"),
        "eval_count": response.get("eval_count"),
    }


def download(spec, destination):
    """Resume bounded ranges after transient disconnects; verify all final bytes."""
    size, url = spec["bytes"], spec["url"]
    started = time.monotonic()
    deadline = started + DOWNLOAD_SECONDS
    with destination.open("xb") as stream:
        stream.truncate(size)
    chunk_size = RANGE_BYTES if size > RANGE_THRESHOLD else size
    ranges = [(start, min(size, start + chunk_size) - 1) for start in range(0, size, chunk_size)]
    cancelled = threading.Event()
    lock = threading.Lock()
    progress = {"bytes": 0, "last": started}

    def part(bounds):
        start, stop = bounds
        count, errors = 0, []
        with destination.open("r+b", buffering=0) as out:
            out.seek(start)
            for attempt in range(len(RETRY_DELAYS) + 1):
                if cancelled.is_set():
                    raise InterruptedError("Weight download cancelled")
                if time.monotonic() >= deadline:
                    raise TimeoutError("Weight download deadline reached")
                current = start + count
                separator = "&" if "?" in url else "?"
                req = urllib.request.Request(
                    url
                    + separator
                    + f"download=true&hpcforest_range={current}-{stop}&attempt={attempt}",
                    headers={"Range": f"bytes={current}-{stop}", "User-Agent": "HPC-Forest"},
                )
                try:
                    with urllib.request.urlopen(req, timeout=90) as response:
                        content_range = response.headers.get("Content-Range", "")
                        full_file = (
                            current == 0
                            and stop == size - 1
                            and response.status == 200
                            and response.headers.get("Content-Length") == str(size)
                        )
                        if not full_file and (
                            response.status != 206
                            or content_range != f"bytes {current}-{stop}/{size}"
                        ):
                            raise RuntimeError(
                                f"Server did not honor bounded range: {response.status}, {content_range}"
                            )
                        while count < stop - start + 1:
                            if cancelled.is_set():
                                raise InterruptedError("Weight download cancelled")
                            if time.monotonic() >= deadline:
                                raise TimeoutError("Weight download deadline reached")
                            block = response.read(min(8 * 1024**2, stop - start + 1 - count))
                            if not block:
                                raise OSError("Truncated HTTP weight range")
                            written = out.write(block)
                            count += written
                            if written != len(block):
                                raise OSError("Short weight-file write")
                    break
                except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
                    if (
                        cancelled.is_set()
                        or time.monotonic() >= deadline
                        or attempt == len(RETRY_DELAYS)
                    ):
                        raise
                    errors.append(type(exc).__name__)
                    cancelled.wait(RETRY_DELAYS[attempt])
        with lock:
            progress["bytes"] += count
            now = time.monotonic()
            if now - progress["last"] >= 30 or progress["bytes"] == size:
                print(
                    json.dumps(
                        {
                            "event": "weight_download_progress",
                            "file": spec.get("name", destination.name),
                            "completed_bytes": progress["bytes"],
                            "total_bytes": size,
                        }
                    ),
                    flush=True,
                )
                progress["last"] = now
        return {
            "start": start,
            "end": stop,
            "bytes": count,
            "attempts": attempt + 1,
            "retry_errors": errors,
        }

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(ranges)))
    try:
        futures = {pool.submit(part, bounds): i for i, bounds in enumerate(ranges)}
        receipts = [None] * len(ranges)
        for future in concurrent.futures.as_completed(futures):
            receipts[futures[future]] = future.result()
    except BaseException:
        cancelled.set()
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    actual = checksum(destination)
    if actual != spec["sha256"] or destination.stat().st_size != size:
        raise RuntimeError("Downloaded weight identity mismatch")
    return {
        **spec,
        "verified_sha256": actual,
        "seconds": time.monotonic() - started,
        "ranges": receipts,
    }


def prepare(spec_path, url, cache, output):
    spec = read_spec(spec_path)
    if (
        cache.resolve().parent != Path("/dev/shm")
        or (cache / "OWNER").read_text() != os.environ["SLURM_JOB_ID"]
    ):
        raise RuntimeError("An owned ephemeral cache is required")
    blobs = cache / "models/blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    required = sum(s["bytes"] for s in spec["files"])
    available = shutil.disk_usage(cache).free
    atomic_json(
        output / "ephemeral-storage.json",
        {"required_bytes": required, "free_bytes": available, "duplicate_weight_copy": False},
    )
    if available < required + 4 * 1024**3:
        raise RuntimeError(
            f"Insufficient ephemeral space: {available} bytes free; {required} required plus reserve"
        )
    receipts = []
    for item in spec["files"]:
        name = item["name"]
        if Path(name).name != name or not name.endswith(".gguf"):
            raise RuntimeError("Invalid shard filename")
        print(
            json.dumps({"event": "weight_download_start", "file": name, "bytes": item["bytes"]}),
            flush=True,
        )
        receipts.append(download(item, blobs / ("sha256-" + item["sha256"])))
        atomic_json(output / "weight-downloads.json", receipts)
        print(
            json.dumps({"event": "weight_verified", "file": name, "sha256": item["sha256"]}),
            flush=True,
        )
    # The native split-GGUF API references verified content-addressed blobs.
    # It keeps every original shard and creates no second 155 GB weight copy.
    imported = request_json(
        url,
        "/api/create",
        {
            "model": spec["model"],
            "stream": False,
            "files": {s["name"]: "sha256:" + s["sha256"] for s in spec["files"]},
        },
        1200,
    )
    atomic_json(output / "model-import.json", imported)
    if imported.get("status") != "success":
        raise RuntimeError("Local GGUF import did not report success")
    identity = resolve_model({"base_url": url, "model": spec["model"]})
    raw_manifest, installed = installed_manifest(cache, identity)
    (output / "model-manifest-raw.json").write_bytes(raw_manifest)
    atomic_json(output / "model-manifest.json", installed)
    atomic_json(output / "model-specification.json", spec)
    for layer in installed["layers"]:
        if layer["mediaType"] == "application/vnd.ollama.image.model":
            blob = cache / "models/blobs" / layer["digest"].replace(":", "-")
            if checksum(blob) != layer["digest"].removeprefix("sha256:"):
                raise RuntimeError("Imported model blob identity mismatch")
    atomic_json(output / "model-identity.json", identity)
    atomic_json(
        output / "model-show.json", request_json(url, "/api/show", {"model": spec["model"]}, 30)
    )
    print(
        json.dumps(
            {
                "event": "local_model_prepared",
                "model": spec["model"],
                "digest": identity["model_digest"],
            }
        ),
        flush=True,
    )
    return identity
