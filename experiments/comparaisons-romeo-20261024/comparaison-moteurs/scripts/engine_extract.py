"""Read new campaign evidence and reconstruct CUDA sources without running archives."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tarfile
from engine_study import ROOT, STUDY, OUT, CONDITIONS, read, write, sha

def table(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for row in rows for k in row))
    if not keys:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})

def object_read(store, commit, path):
    return subprocess.check_output(["git", "--git-dir="+str(store), "show", commit+":"+path], stderr=subprocess.PIPE)

def extract(condition):
    artifact = STUDY / condition
    archive = artifact / "results.tar.gz"
    receipt = read(artifact / "results-transfer.json")
    assert receipt["verifie"] is True and sha(archive) == receipt["remote_sha256"]
    auth = read(artifact / "authorization.json")
    job = auth["job_id"]
    target = ROOT / "work/e" / condition
    target.mkdir(parents=True, exist_ok=True)
    store = ROOT / "work/g" / condition
    if not store.exists():
        subprocess.run(["git","init","--bare",str(store)], check=True, capture_output=True)
    extracted, skipped, objects = [], [], 0
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            rel = Path(member.name)
            if rel.is_absolute() or ".." in rel.parts or ":" in member.name or "\\" in member.name:
                raise ValueError("Unsafe member: " + member.name)
            if member.isdir():
                continue
            if not member.isfile():
                skipped.append({"path":member.name,"type":str(member.type)})
                continue
            data = tar.extractfile(member).read()
            path = target / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            extracted.append({"path":member.name,"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)})
            if ".git/objects/" in member.name:
                obj = store / "objects" / member.name.split(".git/objects/",1)[1]
                obj.parent.mkdir(parents=True, exist_ok=True)
                obj.write_bytes(data)
                objects += 1
    write(OUT / "protocol" / condition / "extraction.json", {"archive_sha256":sha(archive),"files":extracted,"skipped":skipped,"git_object_files":objects})
    root = target / ("results-"+job)
    result = read(root / "results.json")
    assert result["session_id"] == auth["session_id"]
    dbs = list(root.rglob("registry.sqlite3"))
    if len(dbs) != 1:
        raise RuntimeError("Expected one owned registry")
    db = dbs[0]
    conn = sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True)
    conn.row_factory = sqlite3.Row
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    metadata = {r["key"]:json.loads(r["value"]) for r in conn.execute("select * from metadata")}
    trials = []
    for row in conn.execute("select id,role,state,mission,result,created from trials order by created,id"):
        row = dict(row)
        for key in ["mission","result"]:
            row[key] = json.loads(row[key]) if row[key] else {}
        trials.append(row)
    evaluations, events = [], []
    for name, rows in [("evaluations",evaluations),("events",events)]:
        for row in conn.execute("select * from "+name+" order by created,id"):
            row = dict(row)
            row["payload"] = json.loads(row["payload"])
            rows.append(row)
    conn.close()
    data_out = OUT / "data" / condition
    for name, value in [("results",result),("trials",trials),("evaluations",evaluations),("events",events),("metadata",metadata)]:
        write(data_out / (name+".json"),value)
    original = read(ROOT / "outputs/comparaison-historique/data/campaigns" / condition / "summary.json")
    baseline = next(e["payload"] for e in evaluations if e["experiment_id"].startswith("baseline-") and e["phase"]=="search")
    best = metadata.get("best_confirmed") or result.get("best_confirmed")
    plan = metadata.get("forest_plan:1") or {}
    final = metadata.get("final_g_confirmation:1") or {}
    post = metadata.get("postprocess:1") or result.get("postprocess") or {}
    started = metadata.get("started")
    closed = metadata.get("search_closed:1")
    finished = metadata.get("pipeline_finished:1") or metadata.get("confirmation_finished:1")
    summary = {"condition":condition,"job_id":job,"original_job_id":condition,
        "engine_identity":metadata.get("identity",{}).get("controller_implementation"),
        "baseline_seconds":baseline.get("mean_seconds"),"best_confirmed":best,
        "old_best_confirmed":original.get("best_confirmed"),"forest_plan":plan,"forest_width":len(plan.get("children",[])),
        "research_counts":dict(Counter(t["result"].get("status","absent") for t in trials if t["role"]!="G")),
        "integration_counts":dict(Counter(t["result"].get("status","absent") for t in trials if t["role"]=="G")),
        "trial_counts":dict(Counter(t["result"].get("status","absent") for t in trials)),
        "event_counts":dict(Counter(e["kind"] for e in events)),
        "started":started,"search_closed":closed,"finished":finished,
        "search_elapsed_seconds":closed-started if isinstance(closed,(float,int)) and started else None,
        "total_elapsed_seconds":finished-started if finished and started else None,
        "pipeline_complete":result.get("pipeline_complete"),"pipeline_error":result.get("error"),
        "search_status":result.get("search",{}).get("status"),"final_controller_status":metadata.get("status"),"final_g_confirmation":final,"postprocess":post,
        "mother_review":metadata.get("mother_plan_review:1"),"costs":result.get("costs"),"phase_costs":result.get("phase_costs"),
        "timing":result.get("timing"),"registry_sha256":sha(db),"archive_sha256":sha(archive)}
    if isinstance(best,dict):
        summary["speedup"] = baseline["mean_seconds"]/best["mean_seconds"] if best.get("mean_seconds") else None
    write(data_out / "summary.json",summary)
    fsck = subprocess.run(["git","--git-dir="+str(store),"fsck","--full","--no-reflogs"],capture_output=True,text=True)
    write(OUT / "protocol" / condition / "object-integrity.json", {"exit_code":fsck.returncode,"stdout":fsck.stdout,"stderr":fsck.stderr})
    if fsck.returncode:
        raise RuntimeError("Invalid git object store")
    variants, sources, lineage = {}, {}, []
    def source(commit):
        if not commit:
            return None
        if commit not in sources:
            try:
                sources[commit] = {name:object_read(store,commit,name) for name in ["src/nbody_kernel.cu","src/launch.json"]}
            except subprocess.CalledProcessError:
                sources[commit] = None
        return sources[commit]
    for e in evaluations:
        value=e["payload"]
        commit=value.get("commit")
        files=source(commit)
        if not files:
            continue
        identity=hashlib.sha256(files["src/nbody_kernel.cu"]+b"\0"+files["src/launch.json"]).hexdigest()[:16]
        if identity not in variants:
            variants[identity]={"id":identity,"source_sha256":hashlib.sha256(files["src/nbody_kernel.cu"]).hexdigest(),
                "launch_sha256":hashlib.sha256(files["src/launch.json"]).hexdigest(),"launch":json.loads(files["src/launch.json"]),"origins":[]}
            for name, body in files.items():
                p=OUT / "sources" / identity / name
                p.parent.mkdir(parents=True,exist_ok=True)
                if p.exists():assert p.read_bytes()==body
                else:p.write_bytes(body)
        variants[identity]["origins"].append({"condition":condition,"job_id":job,"experiment_id":e["experiment_id"],"phase":e["phase"],
             "status":value.get("status"),"correct":value.get("correct"),"seconds":value.get("mean_seconds"),"commit":commit})
    # Early engines record G under postprocess; later ones use search.
    # Exclude confirmation to retain the time when the program first became available.
    by_commit={e["payload"].get("commit"):e["payload"] for e in evaluations if e["phase"]!="confirmation" and e["payload"].get("commit")}
    by_trial={e["experiment_id"]:e for e in evaluations if e["phase"]!="confirmation"}
    best_research=baseline.get("mean_seconds")
    for index,t in enumerate(trials,1):
        res,mission=t["result"],t["mission"]
        commit,base=res.get("commit"),mission.get("base_commit")
        current,parent=source(commit),source(base)
        changed=[n for n in current if current[n]!=parent.get(n)] if current and parent else None
        kind="indisponible" if changed is None else "copie exacte" if not changed else "lancement seul" if changed==["src/launch.json"] else "noyau seul" if changed==["src/nbody_kernel.cu"] else "noyau et lancement"
        measured=res.get("mean_seconds") if res.get("status")=="valid" else None
        baseline_time=by_commit.get(base,{}).get("mean_seconds")
        patch=None
        if current and parent:
            diff=subprocess.check_output(["git","--git-dir="+str(store),"diff","--no-ext-diff",base,commit,"--","src/nbody_kernel.cu","src/launch.json"])
            patch=OUT / "diffs" / condition / (t["id"]+".patch")
            patch.parent.mkdir(parents=True,exist_ok=True)
            patch.write_bytes(diff)
        prior=best_research
        if measured and t["role"]!="G":best_research=min(best_research,measured)
        evaluated=by_trial.get(t["id"],{}).get("created")
        identity=hashlib.sha256(current["src/nbody_kernel.cu"]+b"\0"+current["src/launch.json"]).hexdigest()[:16] if current else None
        row={"condition":condition,"job_id":job,"ordinal":index,"id":t["id"],"role":t["role"],"status":res.get("status"),"reason":res.get("reason"),
            "created":t["created"],"elapsed_seconds":t["created"]-started,"evaluated_at":evaluated,
            "measured_elapsed_seconds":evaluated-started if evaluated else None,"seconds":measured,"score":res.get("score"),
            "base_search_seconds":baseline_time,"gain_vs_base_pct":100*(1-measured/baseline_time) if measured and baseline_time else None,
            "best_research_before_seconds":prior,"best_research_after_seconds":best_research,"change_kind":kind,"changed_paths":changed,
            "commit":commit,"base_commit":base,"variant_id":identity,"patch":patch.relative_to(OUT).as_posix() if patch else None,
            "hypothesis":mission.get("hypothesis"),"transformations":mission.get("transformations"),"parent_id":mission.get("parent_id"),
            "sources":mission.get("sources"),"source_commits":mission.get("source_commits"),"depth":mission.get("depth")}
        lineage.append(row)
    write(data_out / "variants.json",list(variants.values()))
    write(data_out / "lineage.json",lineage)
    table(OUT / "tables" / (condition+"-trials.csv"),lineage)
    table(OUT / "tables" / (condition+"-events.csv"), [{"condition":condition,"elapsed_seconds":e["created"]-started,**e} for e in events])
    evidence=OUT / "evidence" / condition
    evidence.mkdir(parents=True,exist_ok=True)
    campaign=db.parent
    if (campaign/'logs').is_dir():
        shutil.copytree(campaign/'logs',evidence/'logs',dirs_exist_ok=True)
    for p in [archive,db,root/"results.json",root/"allocation.json",target/"gpu-preflight.log"]:
        if p.exists():shutil.copyfile(p,evidence / p.name)
    for name in ["mcp-plan.json","mcp-submission.json","upload.json","results-transfer.json","relay-process.json","relay-exit.json","worker-finished.json","relay-failure.json","relay-transfer-errors.jsonl"]:
        if (artifact / name).exists():shutil.copyfile(artifact/name,OUT/"protocol"/condition/name)
    print(json.dumps({"condition":condition,"job_id":job,"trials":len(trials),"events":len(events),"variants":len(variants),"research":summary["research_counts"],"complete":summary["pipeline_complete"],"error":summary["pipeline_error"]}))

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("condition",choices=list(CONDITIONS))
    extract(parser.parse_args().condition)
