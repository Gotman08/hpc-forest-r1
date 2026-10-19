"""Lossless evidence archive with content reuse, retaining every result file."""

import hashlib
import io
import json
import stat
import tarfile
import zipfile
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def make(root, official, destination):
    original, archives = {}, {}
    for p in sorted(official.glob("*.zip")):
        archives[p.name] = sha(p)
        with zipfile.ZipFile(p) as z:
            for entry in z.infolist():
                if not entry.is_dir():
                    original.setdefault(
                        hashlib.sha256(z.read(entry)).hexdigest(),
                        {"archive": p.name, "member": entry.filename},
                    )
    manifest = {
        "format": "marathon22-lossless-evidence-v1",
        "official_archives": archives,
        "runs": [{"name": root.name, "remote_path": str(root)}],
        "files": [],
        "statistics": {
            "raw_bytes": 0,
            "official_reuse_bytes": 0,
            "unique_blob_bytes": 0,
        },
    }
    stored = set()
    with tarfile.open(destination, "w:gz") as t:
        for p in sorted(root.rglob("*")):
            if p.is_symlink():
                raise RuntimeError("Refusing evidence symlink")
            if not p.is_file():
                continue
            before = p.stat()
            checksum = sha(p)
            after = p.stat()
            if (before.st_size, before.st_mtime_ns) != (
                after.st_size,
                after.st_mtime_ns,
            ):
                raise RuntimeError("Evidence changed during capture")
            item = {
                "path": root.name + "/" + p.relative_to(root).as_posix(),
                "bytes": before.st_size,
                "sha256": checksum,
                "mode": stat.S_IMODE(before.st_mode),
            }
            manifest["statistics"]["raw_bytes"] += before.st_size
            if checksum in original:
                item["official"] = original[checksum]
                manifest["statistics"]["official_reuse_bytes"] += before.st_size
            else:
                item["blob"] = "blobs/" + checksum
                if checksum not in stored:
                    t.add(p, arcname=item["blob"], recursive=False)
                    manifest["statistics"]["unique_blob_bytes"] += before.st_size
                    stored.add(checksum)
            manifest["files"].append(item)
        raw = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(raw)
        t.addfile(info, io.BytesIO(raw))
    return manifest["statistics"]
