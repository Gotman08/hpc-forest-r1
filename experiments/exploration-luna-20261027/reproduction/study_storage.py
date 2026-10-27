"""Persistent storage guards and verified preservation for the controlled study."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tarfile
import time
from pathlib import Path

GIB = 1024 ** 3

def read(path, default=None):
    return json.loads(Path(path).read_text(encoding="utf8")) if Path(path).exists() else default

def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)

def quota_rows(output):
    header, rows = None, {}
    for line in output.splitlines():
        cols = line.split(":")
        if len(cols) < 4 or cols[:2] != ["mmlsquota", "user"]:
            continue
        if cols[2] == "HEADER":
            header = cols
        elif header:
            row = dict(zip(header, cols, strict=True))
            rows[row["filesetname"]] = row
    if not rows:
        raise RuntimeError("GPFS quota response could not be parsed")
    return rows

def available(row):
    def remaining(prefix):
        used = int(row[prefix + "Usage"]) + int(row[prefix + "InDoubt"])
        hard, soft = int(row[prefix + "Limit"]), int(row[prefix + "Quota"])
        grace = row[prefix + "Grace"].strip().lower()
        limit = hard
        if grace in {"expired", "expired!", "none"} and soft and used >= soft:
            limit = min(hard, soft) if hard else soft
        return max(0, limit - used) if limit else None
    blocks, files = remaining("block"), remaining("files")
    return {"bytes": blocks * 1024 if blocks is not None else None, "files": files,
            "block_grace": row["blockGrace"], "files_grace": row["filesGrace"]}

def storage_check(path, *, fileset="scratch", min_bytes=2 * GIB, min_files=30000):
    path = Path(path).resolve(strict=True)
    info = os.statvfs(path)
    filesystem = {"bytes": info.f_bavail * info.f_frsize, "files": info.f_favail}
    result = subprocess.run(
        ["/usr/lpp/mmfs/bin/mmlsquota", "-Y", "-u", str(os.getuid()), "gpfs"],
        capture_output=True, text=True, timeout=30, check=True)
    quotas = quota_rows(result.stdout)
    if fileset not in quotas:
        raise RuntimeError("Required GPFS fileset quota missing")
    quota = available(quotas[fileset])
    result = {"checked_at": time.time(), "path": str(path), "fileset": fileset,
              "filesystem": filesystem, "quota": quota}
    for name, minimum in (("bytes", min_bytes), ("files", min_files)):
        if filesystem[name] < minimum or (quota[name] is not None and quota[name] < minimum):
            raise RuntimeError("Insufficient storage margin: " + json.dumps(result))
    return result

def inventory(root):
    root = Path(root)
    records = {}
    for folder, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(folder) / name
            relative = path.relative_to(root).as_posix()
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                records[relative] = {"kind": "link", "target": os.readlink(path)}
            elif stat.S_ISDIR(info.st_mode):
                records[relative] = {"kind": "directory"}
            elif stat.S_ISREG(info.st_mode):
                records[relative] = {"kind": "file", "size": info.st_size, "sha256": sha(path)}
            else:
                raise RuntimeError("Unsupported evidence file: " + str(path))
    return records

def verify_archive(archive, expected):
    observed = {}
    # Stream once: seeking backwards for thousands of Git hard links makes gzip
    # verification quadratic. A hard link must match a previously verified file.
    with tarfile.open(archive, "r|gz") as stream:
        for member in stream:
            name = member.name.removeprefix("./").rstrip("/")
            if name in {"", "."}:
                continue
            if member.isdir():
                observed[name] = {"kind": "directory"}
            elif member.issym():
                observed[name] = {"kind": "link", "target": member.linkname}
            elif member.islnk():
                linked = observed.get(member.linkname.removeprefix('./').rstrip('/'))
                if not linked or linked['kind'] != 'file':
                    raise RuntimeError('Archive hard link has no verified earlier file')
                observed[name] = dict(linked)
            elif member.isfile():
                with stream.extractfile(member) as source:
                    data_sha = hashlib.file_digest(source, "sha256").hexdigest()
                observed[name] = {"kind": "file", "size": member.size, "sha256": data_sha}
            else:
                raise RuntimeError("Unsupported evidence archive member")
    if observed != expected:
        raise RuntimeError("Evidence archive differs from source inventory")

def preserve(source, destination, archive, *, allowed_root):
    """Archive, verify, copy and verify before replacing a settled directory by a link."""
    source, destination, archive = map(Path, (source, destination, archive))
    allowed_root = Path(allowed_root).resolve(strict=True)
    if source.is_symlink() or not source.is_dir():
        raise RuntimeError("Preservation requires a real settled directory")
    actual = source.resolve(strict=True)
    if actual == allowed_root or allowed_root not in actual.parents:
        raise RuntimeError("Preservation source outside permitted study root")
    if destination.exists() or destination.is_symlink() or archive.exists():
        raise RuntimeError("Preservation destination already exists")
    if actual in destination.resolve().parents or actual in archive.resolve().parents:
        raise RuntimeError("Preservation destinations must be outside the source")
    expected = inventory(actual)
    destination.parent.mkdir(parents=True, exist_ok=True)
    archive.parent.mkdir(parents=True, exist_ok=True)
    partial = archive.with_name(archive.name + ".partial")
    if os.name == 'posix':
        subprocess.run(['tar', '--numeric-owner', '-czf', str(partial), '-C', str(actual), '.'],
                       check=True, timeout=1200)
    else:
        with tarfile.open(partial, "w:gz", dereference=False) as stream:
            stream.add(actual, arcname=".", recursive=True)
    verify_archive(partial, expected)
    os.replace(partial, archive)
    archive_sha = sha(archive)
    shutil.copytree(actual, destination, symlinks=True)
    if inventory(destination) != expected or inventory(actual) != expected:
        raise RuntimeError("Preservation source changed or copy verification failed; source retained")
    receipt = {"source": str(source), "destination": str(destination),
               "archive": str(archive), "archive_sha256": archive_sha,
               "entries": len(expected), "verified": True, "relocated": False}
    atomic(archive.with_suffix(archive.suffix + ".json"), receipt)
    # Only a verified, settled, explicitly bounded source is retired; old paths keep working.
    shutil.rmtree(actual)
    source.symlink_to(destination, target_is_directory=True)
    receipt["relocated"] = True
    atomic(archive.with_suffix(archive.suffix + ".json"), receipt)
    return receipt

def external_state(pair):
    value = os.environ.get("FOREST_STUDY_STATE")
    if not value:
        return None
    root = Path(value).resolve()
    if root == pair.resolve() or pair.resolve() in root.parents:
        raise RuntimeError("Independent state must be outside the working directory")
    root.mkdir(parents=True, exist_ok=True)
    return root

def record_state(pair, name, value):
    root = external_state(pair)
    if root:
        atomic(root / name, value)

def guard(pair, *, start=False):
    if not os.environ.get("FOREST_STORAGE_GUARD"):
        return None
    state = external_state(pair)
    result = storage_check(pair, min_files=60000 if start else 25000)
    if state:
        result["independent_state"] = storage_check(state, fileset="home",
                                                   min_bytes=2 * GIB, min_files=50000)
    return result

