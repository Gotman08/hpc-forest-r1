"""Execute each historical revision's own checks in a separate immutable snapshot."""
from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[3] if Path(__file__).parent.name == "scripts" else Path(__file__).resolve().parents[1]
REPO = Path(r"C:\Users\nicol\Documents\Codex\2026-10-20\new-chat\outputs\hpc-forest-r1")
OUTPUT = ROOT / "outputs/comparaison-historique"
WORK = ROOT / "work/engine-snapshots"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def check_revision(row):
    sha = row["commit"]
    snapshot = WORK / sha[:7]
    logs = OUTPUT / "engine-tests-isolated" / sha[:7]
    logs.mkdir(parents=True, exist_ok=True)
    if (logs / "result.json").exists():
        return json.loads((logs / "result.json").read_text())
    snapshot.mkdir(parents=True, exist_ok=True)
    archive = WORK / (sha[:7] + ".zip")
    subprocess.run(["git", "-C", str(REPO), "archive", "--format=zip", "--output=" + str(archive), sha],
                   check=True, capture_output=True)
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            p = Path(item.filename)
            if p.is_absolute() or ".." in p.parts or ":" in item.filename:
                raise ValueError("Unsafe git archive path")
        # Archived model diagnostics can exceed Windows MAX_PATH. Tests use
        # synthetic fixtures; immutable historical campaign evidence stays in
        # the source repository and is audited separately by historical_audit.
        for item in z.infolist():
            if not item.filename.startswith("experiments/") or item.filename == "experiments/cuda-nbody-20261021/input/reference.cu":
                z.extract(item,snapshot)
    env = os.environ.copy()
    temporary = WORK / ("os-tmp-" + sha[:7])
    temporary.mkdir(exist_ok=True)
    env.update(PYTHONPATH=str(snapshot / "src"), PYTHONDONTWRITEBYTECODE="1",
               PYTHONIOENCODING="utf-8", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
               TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary))
    result = dict(commit=sha, subject=row["subject"], source_tree=row["source_tree"],
                  python=sys.executable, python_version=sys.version, tests="own historical tests, unmodified",
                  concurrency=6, excluded_from_snapshot=["experiments/ except the exact reference.cu test fixture"], started=time.time(), commands=[])
    for label, command in [
        ("pytest", [sys.executable, "-m", "pytest", "-q", "--junitxml=" + str(logs / "pytest.xml"),
                    "--basetemp=" + str(WORK / ("tests-" + sha[:7]))]),
        ("ruff", [sys.executable, "-m", "ruff", "check", "src", "tests"]),
    ]:
        start = time.time()
        try:
            with (logs / (label + ".log")).open("w", encoding="utf-8") as stream:
                proc = subprocess.run(command, cwd=snapshot, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                      timeout=1800, check=False)
            entry = dict(check=label, exit_code=proc.returncode, elapsed_seconds=time.time()-start, command=command)
        except subprocess.TimeoutExpired:
            entry = dict(check=label, exit_code=None, timeout=True, elapsed_seconds=time.time()-start, command=command)
        result["commands"].append(entry)
        print(json.dumps({"commit":sha[:7],**entry}),flush=True)
    xml = logs / "pytest.xml"
    if xml.exists():
        root = ElementTree.parse(xml).getroot()
        result["test_suites"] = [s.attrib for s in root.iter("testsuite")]
        result["failures"] = [dict(classname=c.get("classname"), name=c.get("name"),
            diagnostic="\n".join((x.text or "") for x in c if x.tag in {"failure","error"}))
            for c in root.iter("testcase") if any(x.tag in {"failure","error"} for x in c)]
        result["skips"] = [dict(classname=c.get("classname"),name=c.get("name"),reason=c.find("skipped").get("message"))
            for c in root.iter("testcase") if c.find("skipped") is not None]
    result["finished"] = time.time()
    write(logs / "result.json", result)
    return result


if __name__ == "__main__":
    WORK.mkdir(parents=True, exist_ok=True)
    lines = subprocess.check_output(["git","-C",str(REPO),"log","--all","--reverse",
                                    "--format=%H%x09%s","--","src","tests","examples","tools"],text=True).splitlines()
    rows=[]
    for line in lines:
        sha,subject=line.split("\t",1)
        tree=subprocess.check_output(["git","-C",str(REPO),"rev-parse",sha+":src"],text=True).strip()
        rows.append(dict(commit=sha,subject=subject,source_tree=tree))
    write(OUTPUT / "engine-tests-isolated/plan.json",rows)
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(check_revision,row):row for row in rows}
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({"commit":futures[future]["commit"],"runner_error":repr(exc)})
            write(OUTPUT / "engine-tests-isolated/results.json",results)
    print("ALL_ENGINE_CHECKS_COMPLETE",len(results),flush=True)
