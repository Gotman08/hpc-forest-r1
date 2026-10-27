"""Repeat both conditions from an immutable payload after a failed control arm."""
import argparse
import hashlib
import json
import shutil
import tarfile
import uuid
from pathlib import Path


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    original = json.loads((args.template / "pair.json").read_text(encoding="utf8"))
    manifest = json.loads((args.template / "files.json").read_text(encoding="utf8"))
    if original["case"] != "utf8" or original["repeat"] != 1:
        raise ValueError("The supplementary protocol repeats the failed UTF-8 r1 pair")
    if any(sha(args.template / name) != value for name, value in manifest.items()):
        raise ValueError("Frozen template changed")
    identity = "utf8-r3-" + uuid.uuid4().hex[:12]
    folder = args.output / identity
    folder.mkdir(parents=True)
    payload = folder / "payload"
    shutil.copytree(args.template, payload)
    remote = original["remote_root"].rsplit("/", 1)[0] + "/tabpfn-admission-" + identity
    plan = {**original, "pair_id": identity, "repeat": 3, "remote_root": remote,
            "cohort": "supplementary", "retry_of": original["pair_id"],
            "retry_reason": "The control arm failed on a forbidden native wait call; preserve it and repeat both conditions.",
            "arms": [{**arm, "id": uuid.uuid4().hex, "session_id": uuid.uuid4().hex}
                     for arm in original["arms"]]}
    config = json.loads((payload / "settings.json").read_text(encoding="utf8"))
    config["codex"]["mailbox_dir"] = remote + "/unused-before-arm-preparation"
    write(payload / "settings.json", config)
    write(payload / "pair.json", plan)
    frozen = {p.relative_to(payload).as_posix(): sha(p) for p in sorted(payload.rglob("*"))
              if p.is_file() and p.name != "files.json"}
    if any(value != frozen[name] for name, value in manifest.items() if name.startswith("engine/")):
        raise ValueError("The supplementary engine differs from the tested primary engine")
    write(payload / "files.json", frozen)
    archive = folder / "payload.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        for path in sorted(payload.rglob("*")):
            if path.is_file():
                stream.add(path, arcname=path.relative_to(payload).as_posix(), recursive=False)
    record = {**plan, "archive": str(archive), "sha256": sha(archive), "remote_archive": remote + ".tar.gz"}
    write(folder / "preparation.json", record)
    print(json.dumps(record))


if __name__ == "__main__":
    main()
