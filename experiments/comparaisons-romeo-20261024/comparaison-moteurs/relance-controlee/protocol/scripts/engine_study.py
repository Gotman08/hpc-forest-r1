"""Reproduce the seven deployed engines without modifying their frozen sources."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
OLD = Path(r"C:\Users\nicol\Documents\Codex\2026-10-20\new-chat")
REPO = OLD / "outputs/hpc-forest-r1"
OUT = Path(os.environ.get("FOREST_STUDY_OUT",str(ROOT / "outputs/comparaison-moteurs")))
STUDY = Path(os.environ.get("FOREST_STUDY_DIR",str(ROOT / "work/engine-study")))
PYTHON = OLD / "work/hpc-forest-mcp-venv/Scripts/python.exe"
CONFIG = OLD / "work/romeo-worker-config.toml"
CONDITIONS = {
    "772923": "cuda-nbody-campaign-20261021/artifact/payload",
    "774157": "cuda-nbody-independent-20261021-8a47d2e6/artifact/payload",
    "775521": "cuda-memory-20261022-r2-81dd7bce/payload",
    "775815": "cuda-memory-budget-20261022-09d09f94/payload",
    "776048": "cuda-memory-budget-final-20261022-5f2930cb/payload",
    "776290": "cuda-memory-budget-decision-20261022-402d6d6d-run/payload",
    "780448": "cuda-memory-reliability-20261023/payload",
}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def inspect():
    result = []
    for key, relative in CONDITIONS.items():
        payload = OLD / "work" / relative
        plan = read(payload / "plan.json")
        cfg = read(payload / "settings.json")
        result.append({"condition": key, "payload": str(payload), "plan": plan,
            "budget": cfg["budget"], "forest": {k:v for k,v in cfg["forest"].items() if k != "statement"},
            "codex": cfg["codex"], "memory": cfg.get("memory"),
            "completion": cfg["completion"], "protocol": cfg["protocol"],
            "statement_sha": sha(payload / "statement.txt"),
            "pilot_sha": sha(payload / "pilot.py"), "evaluator_sha": sha(payload / "cuda_evaluator.py"),
            "source_sha": sha(payload / "source/src/nbody_kernel.cu"),
            "launch_sha": sha(payload / "source/src/launch.json"),
            "validation_protocol_sha": sha(payload / "validation/protocol.py")})
    write(STUDY / "historical-settings.json", result)
    for item in result:
        print(json.dumps({k:v for k,v in item.items() if k not in {"protocol", "plan", "codex"}}, ensure_ascii=True))

def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    STUDY.mkdir(parents=True, exist_ok=True)
    preparations = []
    for key, relative in CONDITIONS.items():
        original = OLD / "work" / relative
        artifact = STUDY / key
        artifact.mkdir(exist_ok=False)
        payload = artifact / "payload"
        shutil.copytree(original, payload, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        plan = read(payload / "plan.json")
        old_root, old_session = plan["remote_root"], plan["session_id"]
        session = uuid.uuid4().hex
        remote = "/scratch_p/nimarano/forest-engine-history-" + key + "-" + session
        plan.update(session_id=session, remote_root=remote, created_at=time.time(),
                    comparison_condition=key, old_candidates_imported=False)
        settings = read(payload / "settings.json")
        settings = json.loads(json.dumps(settings).replace(old_root, remote).replace(old_session, session))
        assert settings["budget"]["wall_seconds"] == 1800
        assert settings["codex"]["model"] == "gpt-6-luna"
        assert settings["codex"]["reasoning_effort"] == "max"
        write(payload / "plan.json", plan)
        write(payload / "settings.json", settings)
        for name in ("plan.json", "settings.json", "statement.txt"):
            shutil.copyfile(payload / name, artifact / name)
        protected = {}
        for source in sorted(original.rglob("*")):
            if not source.is_file() or "__pycache__" in source.parts or source.suffix == ".pyc":
                continue
            rel = source.relative_to(original).as_posix()
            if rel in {"plan.json", "settings.json", "runtime-manifest.json"}:
                continue
            assert sha(source) == sha(payload / rel), rel
            protected[rel] = sha(source)
        assert sha(payload / "validation/protocol.py") == "3311797eec4fec382991af5fe8f8fedb76bdaa068facfe1258f688e051ffeb74"
        assert sha(payload / "source/src/nbody_kernel.cu") == "ab22e9f1e077f75420e407b68a4285d97a5912340297d1a700f98f40697b00bc"
        manifest = {p.relative_to(payload).as_posix():sha(p) for p in sorted(payload.rglob("*"))
                    if p.is_file() and p.name != "runtime-manifest.json"}
        write(payload / "runtime-manifest.json", manifest)
        write(artifact / "source-identity.json", {"historical_payload": str(original),
              "identical_files": protected, "changed_metadata": ["plan.json", "settings.json", "runtime-manifest.json"],
              "engine_changed": False, "pilot_changed": False})
        env = {**os.environ, "PYTHONPATH": str(payload / "project/src"), "PYTHONDONTWRITEBYTECODE": "1"}
        check = subprocess.run([str(PYTHON), "-c", "import sys; from pathlib import Path; from hpc_forest.config import load_config; from hpc_forest import codex_worker, request_pool; load_config(Path(sys.argv[1])); print('frozen_config_and_relay_import_ok')", str(payload / "settings.json")],
                               env=env, text=True, capture_output=True)
        write(artifact / "local-validation.json", {"exit_code": check.returncode, "stdout": check.stdout, "stderr": check.stderr})
        if check.returncode:
            raise RuntimeError(check.stderr)
        with tarfile.open(artifact / "payload.tar.gz", "w:gz") as archive:
            for p in sorted(payload.iterdir()):
                archive.add(p, arcname=p.name)
        payload_sha = sha(artifact / "payload.tar.gz")
        remote_archive = remote + ".tar.gz"
        py = "/scratch_p/nimarano/hpc-forest-localmodels-20261015-r1/venv-r3/bin/python"
        command = "\n".join([
            "set -euo pipefail",
            "export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1",
            'test -n "${CUDA_VISIBLE_DEVICES:-}"',
            f"test ! -e {remote}",
            f"printf '%s  %s\\n' {payload_sha} {remote_archive} | sha256sum -c -",
            f"mkdir {remote}", f"tar -xzf {remote_archive} -C {remote}",
            f"export PYTHONPATH={remote}/project/src",
            f"export FOREST_CUDA_HARNESS={remote}/harness-build/cuda_test_harness",
            f"export FOREST_CUDA_CACHE={remote}/cache",
            'export TMPDIR="${SLURM_TMPDIR:-/tmp}/forest-history-${SLURM_JOB_ID}"',
            'mkdir -p "$TMPDIR"', f"cd {remote}",
            "cmake -S cuda_test_harness -B harness-build -DCMAKE_BUILD_TYPE=Release",
            "cmake --build harness-build --parallel 4",
            f"{py} validation/protocol.py preflight validation cache > gpu-preflight.log",
            "cat gpu-preflight.log", "set +e",
            f"{py} -u pilot.py --root {remote}", "engine_status=$?",
            'printf "%s\\n" "$engine_status" > engine-exit-code.txt',
            f'tar -czf {remote}.results.tar.gz "results-${{SLURM_JOB_ID}}" gpu-preflight.log engine-exit-code.txt',
            f"sha256sum {remote}.results.tar.gz", 'exit "$engine_status"', ""])
        prep = {"condition": key, "artifact": str(artifact), "remote_root": remote,
                "remote_payload": remote_archive, "payload_sha256": payload_sha,
                "remote_results": remote + ".results.tar.gz", "session_id": session,
                "batch_command": "bash -lc " + shlex.quote(command),
                "model_mcp": key in {"772923", "774157"},
                "hosting": {"arch": "armgpu", "cpus_per_task": 4, "gpus_per_node": 1,
                            "mem_gb": 16, "time_limit": "02:00:00"}}
        write(artifact / "preparation.json", prep)
        target = OUT / "protocol" / key
        target.mkdir(parents=True, exist_ok=True)
        for name in ("plan.json", "settings.json", "statement.txt", "source-identity.json", "local-validation.json", "preparation.json"):
            shutil.copyfile(artifact / name, target / name)
        preparations.append(prep)
        print(json.dumps({"condition": key, "payload_sha256": payload_sha, "files_identical": len(protected), "prepared": True}))
    write(STUDY / "preparations.json", preparations)
    write(OUT / "protocol/study-design.json", {"created_at": time.time(), "conditions": list(CONDITIONS),
        "replicates_per_condition": 1, "seed": 23, "wall_seconds": 1800, "model": "gpt-6-luna", "effort": "max",
        "seed_controls_model_sampling": False, "fresh_sessions_and_memory": True,
        "prior_optimized_candidates_imported": False, "engine_source_modified": False,
        "native_model_cli": shutil.which("codex"),
        "scope": "Seven deployed working engine states with their frozen historical settings and prompts",
        "transport_adapter": "Own historical Worker/RequestPool; immutable forest width cached after one verified download; bounded listing retries; no model retry or deadline reset",
        "limitations": ["One new stochastic campaign per engine; not an estimate of probability of success", "Historical prompt, feature settings and ROMEO tool availability remain part of each condition", "Independent GPUs; final selected programs will be remeasured together if available"]})

def authorize(key, job):
    artifact = STUDY / key
    plan = read(artifact / "plan.json")
    write(artifact / "authorization.json", {
        "scope": plan["scope"], "session_id": plan["session_id"], "model": "gpt-6-luna", "effort": "max",
        "wall_seconds": 1800, "completion": plan["completion"], "job_id": job,
        "channel": plan["remote_root"] + "/results-" + job + "/mailbox", "gpus": 1, "tokens": None,
        "hpc_allocation_authorized": True, "plan_sha256": sha(artifact / "plan.json"),
        "payload_sha256": sha(artifact / "payload.tar.gz"),
        "user_request": "Prendre tous les codes qui ont fonctionne, les lancer independamment et comparer resultats, comportements et diagnostics. Precision explicite : Les deux : moteur et programmes CUDA.",
        "authorized_at": time.time()})
    shutil.copyfile(artifact / "authorization.json", OUT / "protocol" / key / "authorization.json")

def start(key):
    artifact = STUDY / key
    assert (artifact / "authorization.json").is_file()
    if (artifact / "relay-process.json").exists():
        raise RuntimeError("Do not duplicate an existing relay")
    env = {**os.environ, "PYTHONPATH": str(artifact / "payload/project/src"),
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    command = [str(PYTHON), "-u", str(ROOT / "work/engine_relay.py"), "--artifact", str(artifact), "--config", str(CONFIG)]
    launch_sources = {}
    for name in ["engine_relay.py", "engine_broker_client.py"]:
        if (ROOT / "work" / name).exists():
            launch_sources[name] = sha(ROOT / "work" / name)
            shutil.copyfile(ROOT / "work" / name, artifact / name)
    with (artifact / "relay.stdout.log").open("wb") as stdout, (artifact / "relay.stderr.log").open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    record = {"pid": process.pid, "started_at": time.time(), "command": command, "launcher_sources": launch_sources,
              "shared_transport": bool(os.environ.get("FOREST_STUDY_BROKER"))}
    write(artifact / "relay-process.json", record)
    print(json.dumps(record))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["inspect", "prepare", "authorize", "start"], nargs="?", default="inspect")
    parser.add_argument("--condition")
    parser.add_argument("--job")
    args = parser.parse_args()
    if args.action == "inspect": inspect()
    elif args.action == "prepare": prepare()
    elif args.action == "authorize": authorize(args.condition, args.job)
    elif args.action == "start": start(args.condition)
