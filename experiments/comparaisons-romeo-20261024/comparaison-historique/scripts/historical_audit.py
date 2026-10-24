"""Read-only audit of engine history and all measured CUDA variants.

All extracted data lives in this study. Archived hooks/configuration are never used.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import shutil
import sqlite3
import subprocess
import zipfile
from pathlib import Path


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE)


def git_object(store, spec):
    return subprocess.check_output(["git", "--git-dir=" + str(store), "show", spec], stderr=subprocess.PIPE)


def safe_extract(z, name, destination):
    rel = Path(name)
    if rel.is_absolute() or ".." in rel.parts or ":" in name:
        raise ValueError("Unsafe archive member")
    target = destination / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(z.read(name))


def make_object_store(campaign, scratch):
    store = scratch / "object-stores" / campaign.name
    if not store.exists():
        subprocess.run(["git", "init", "--bare", str(store)], check=True, capture_output=True)
    if campaign.name == "cuda-nbody-20261021":
        source = scratch / "772923-objects"
        if (source / "objects").is_dir():
            source = source / "objects"
        if source.is_dir():
            shutil.copytree(source, store / "objects", dirs_exist_ok=True)
    for bundle in campaign.rglob("*.bundle"):
        subprocess.run(["git", "--git-dir=" + str(store), "fetch", str(bundle), "+refs/*:refs/*"],
                       check=True, capture_output=True)
    archive = campaign / "evidence.zip"
    if archive.exists():
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if name.endswith("/"):
                    continue
                marker = ".git/objects/"
                if marker in name:
                    rel = "objects/" + name.split(marker, 1)[1]
                    if ".." in Path(rel).parts or ":" in rel:
                        raise ValueError("Unsafe git object")
                    target = store / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(name))
                elif name.endswith(".bundle"):
                    bundle = scratch / "bundles" / (campaign.name + ".bundle")
                    bundle.parent.mkdir(parents=True, exist_ok=True)
                    bundle.write_bytes(z.read(name))
                    subprocess.run(["git", "--git-dir=" + str(store), "fetch", str(bundle), "+refs/*:refs/*"],
                                   check=True, capture_output=True)
    check = subprocess.run(["git", "--git-dir=" + str(store), "fsck", "--full", "--no-reflogs"],
                           capture_output=True, text=True)
    write(scratch / "object-integrity" / (campaign.name + ".json"),
          {"exit_code":check.returncode,"stdout":check.stdout,"stderr":check.stderr})
    if check.returncode:
        raise RuntimeError("Git objects failed integrity verification: " + campaign.name)
    return store


def audit(repo, scratch, out):
    commits = []
    for line in git(repo, "log", "--all", "--reverse", "--format=%H%x09%aI%x09%s").decode().splitlines():
        sha, date, subject = line.split("\t", 2)
        files = git(repo, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", sha).decode().splitlines()
        code = [f for f in files if f.startswith(("src/", "examples/", "tests/", "tools/"))]
        src_tree = git(repo, "rev-parse", sha + ":src").decode().strip()
        commits.append(dict(commit=sha, date=date, subject=subject, changed_files=files,
                            code_or_test_change=bool(code), source_tree=src_tree))
    write(out / "data/commits.json", commits)

    variants, campaigns, missing = {}, [], []
    local_manifest = json.loads((repo / "experiments/local-evidence-manifest.json").read_text())
    integrity = []
    for row in local_manifest["archives"]:
        path = repo / row["path"]
        actual = digest(path.read_bytes())
        integrity.append({"path": row["path"], "sha256": actual, "expected": row["sha256"],
                          "matches": actual == row["sha256"]})
        if actual != row["sha256"]:
            raise RuntimeError("Archive hash mismatch: " + str(path))
    write(out / "data/archive-integrity.json", integrity)

    for campaign in sorted((repo / "experiments").glob("cuda*")):
        dbs = list(campaign.rglob("registry.sqlite3"))
        if not dbs:
            continue
        db = dbs[0]
        conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        metadata = {r["key"]: json.loads(r["value"]) for r in conn.execute("select * from metadata")}
        config = metadata["config"]
        trials = []
        for row in conn.execute("select id,role,mission,result,created,state from trials order by created,id"):
            row = dict(row)
            for key in ("mission", "result"):
                row[key] = json.loads(row[key]) if row[key] else {}
            trials.append(row)
        evaluations = []
        for row in conn.execute("select * from evaluations order by created,id"):
            row = dict(row)
            row["payload"] = json.loads(row["payload"])
            evaluations.append(row)
        events = []
        for row in conn.execute("select id,kind,payload,created from events order by created,id"):
            row = dict(row)
            row["payload"] = json.loads(row["payload"])
            events.append(row)
        conn.close()
        job = str(json.loads((campaign / "summary.json").read_text()).get("job_id", "")) if (campaign / "summary.json").exists() else ""
        if not job:
            job = str(json.loads((campaign / "results.json").read_text())["job_id"])
        report = dict(name=campaign.name, job_id=job, registry_sha256=digest(db.read_bytes()),
                      engine_identity=metadata.get("identity", {}).get("controller_implementation"),
                      forest_config=config.get("forest"), memory_config=config.get("memory"),
                      model=config.get("codex", {}).get("model"), effort=config.get("codex", {}).get("reasoning_effort"),
                      budget=config.get("budget"), seed=config.get("seed"),
                      trial_counts=dict(collections.Counter(t["result"].get("status", "absent") for t in trials)),
                      research_counts=dict(collections.Counter(t["result"].get("status", "absent") for t in trials if t["role"] != "G")),
                      event_counts=dict(collections.Counter(e["kind"] for e in events)),
                      best_confirmed=metadata.get("best_confirmed"),
                      started=metadata.get("started"), search_closed=metadata.get("search_closed:1"),
                      finished=metadata.get("pipeline_finished:1", metadata.get("confirmation_finished:1")),
                      forest_plan=metadata.get("forest_plan:1"),
                      mother_review=metadata.get("mother_review:1"),
                      final_g_confirmation=metadata.get("final_g_confirmation:1"))
        # Identity/config are observations. Never execute any serialized tree states.
        write(out / f"data/campaigns/{job}/summary.json", report)
        write(out / f"data/campaigns/{job}/trials.json", trials)
        write(out / f"data/campaigns/{job}/evaluations.json", evaluations)
        write(out / f"data/campaigns/{job}/events.json", events)
        selected_metadata = {k:v for k,v in metadata.items() if k not in {"config", "manifest", "identity"}}
        write(out / f"data/campaigns/{job}/decisions.json", selected_metadata)
        campaigns.append(report)
        store = make_object_store(campaign, scratch)
        for row in evaluations:
            v = row["payload"]
            seconds = v.get("mean_seconds")
            if not (v.get("status") == "valid" and v.get("correct") is True and
                    type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0):
                continue
            commit = v.get("commit")
            origin = dict(campaign=campaign.name, job_id=job, experiment_id=row["experiment_id"],
                          phase=row["phase"], created=row["created"], commit=commit,
                          tree_hash=v.get("tree_hash"), historical_seconds=seconds,
                          historical_times=v.get("times"), evaluation_id=row["id"])
            try:
                source = git_object(store, commit + ":src/nbody_kernel.cu")
                launch = git_object(store, commit + ":src/launch.json")
            except subprocess.CalledProcessError:
                missing.append(origin)
                continue
            key = digest(b"src/nbody_kernel.cu\0" + source + b"\0src/launch.json\0" + launch)
            if key not in variants:
                target = out / "sources" / key[:16] / "src"
                target.mkdir(parents=True, exist_ok=True)
                (target / "nbody_kernel.cu").write_bytes(source)
                (target / "launch.json").write_bytes(launch)
                variants[key] = dict(id=key[:16], sha256=key, source_sha256=digest(source),
                                     launch_sha256=digest(launch), launch=json.loads(launch), origins=[])
            variants[key]["origins"].append(origin)
        print(json.dumps({"campaign":job,"trials":len(trials),"evaluations":len(evaluations),
                          "unique_programs_so_far":len(variants),"missing_so_far":len(missing)}),flush=True)
    write(out / "data/campaigns.json", campaigns)
    write(out / "data/variants.json", sorted(variants.values(), key=lambda v:min(o["created"] for o in v["origins"])))
    write(out / "data/missing-sources.json", missing)
    summary = dict(repo=str(repo), head=git(repo,"rev-parse","HEAD").decode().strip(), commits=len(commits),
                   code_or_test_commits=sum(c["code_or_test_change"] for c in commits),
                   distinct_src_trees=len({c["source_tree"] for c in commits}), campaigns=len(campaigns),
                   distinct_valid_programs=len(variants), validated_occurrences=sum(len(v["origins"]) for v in variants.values()),
                   missing_sources=len(missing), original_repo_modified=False)
    write(out / "data/inventory.json", summary)
    print(json.dumps(summary),flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    audit(a.repo.resolve(), a.work.resolve(), a.output.resolve())
