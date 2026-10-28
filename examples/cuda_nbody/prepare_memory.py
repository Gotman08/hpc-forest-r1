"""Prepare a NEW Luna Max memory campaign locally; never submit an allocation."""
from __future__ import annotations

import argparse
import copy
import json
import shlex
import shutil
import tarfile
import time
import uuid
from pathlib import Path

from hpc_forest.config import DEFAULT, validate
from hpc_forest.core import atomic_json, file_digest
from hpc_forest.memory.contract import POLICY
from hpc_forest.model_skills import policy

SCOPE = "cuda-nbody-luna-max-memory-v1"
STATEMENT = """Optimize the supplied one-step N-body CUDA kernel for one NVIDIA GH200 on ROMEO ARM.
All optimizations must be written as actual source files by the models and evaluated by the controller.
The only measurement allocation is one GPU and four CPU cores. C++17 device code is compiled with
NVRTC CUDA 12.6.3 for the actual GPU architecture, without a global fast-math option.
Preserve Particle as seven float32 x,y,z,vx,vy,vz,mass (28 bytes) and the entry:
extern "C" __global__ void nbody_step_naive(const Particle*,Particle*,int,float).
The input is read-only; output a complete state for each particle. G=1; float32 softening=0.001;
update velocity before position. Support all sizes, positive varying masses, nonzero velocities,
coincident positions and zero/negative dt. Nonfinite output is invalid. Preserve masses exactly.
GPU reference tolerance: atol=5e-5, rtol=2e-4. An independent FP64 CPU oracle checks the reference,
every small output and 32 distributed large rows. Search and confirmation use different input data.
No benchmark input detection or benchmark-specific constants. No changing the checker or protocol.
The objective is geometric mean CUDA-event kernel time for N=4096,8192,16384. Compilation, transfers
and startup are excluded. Each size has 10 warmups and 100 timed launches. Search uses three
timing repetitions and confirmation five fresh repetitions, alternating candidates.
Correctness also includes N=1,2,31,127,257,4095 and a single isolated particle with extreme mass.
Edit only src/nbody_kernel.cu and src/launch.json. Device helpers may reside in the kernel file.
The protected host launches exactly one kernel. Extra host preprocessing, buffers or launches
are outside this interface. launch.json has exactly block (1..1024), items_per_block (1..1048576),
shared_memory_bytes (0..49152). grid.x=ceil(N/items_per_block); block.x=block; other dimensions=1.
Choose all transformations yourself; these interface details are not optimization advice.
Mother chooses any useful number N of complementary topics. Independent real AB-MCTS trees write
and optimize code. The controller serializes GPU checks and measures to prevent interference.
Persistent memory stores measured facts and separately labelled fallible lessons, including slower
or incorrect attempts. Each tree reads only its own evidence and the reference. After research closes,
the original Mother retrieves evidence across trees, selects combinations, writes combined code and
examines the measured results. She may reuse older bases and ideas from slower trials. Every combined
program must be compiled and checked afresh. Never relaunch research during assembly. Confirm final G
independently and keep the best independently confirmed program. Never request extra allocations.
Original user source, supplied as data:
"""


def prepare(source, destination, repository, *, wall_seconds=1800, plan_review_calls=2):
    source, destination, repository = source.resolve(strict=True), destination.resolve(), repository.resolve(strict=True)
    original = source.read_text(encoding="utf8")
    if original.count("__global__ void nbody_step_naive(") != 1 or "int main()" not in original:
        raise ValueError("This example expects the supplied naive N-body entry and host main")
    kernel = original[original.index("// Structure"):original.index("int main()")]
    kernel = kernel.replace("__global__ void nbody_step_naive(", 'extern "C" __global__ void nbody_step_naive(', 1)
    destination.mkdir(parents=True, exist_ok=False)
    payload = destination / "payload"
    src, trusted = payload / "source/src", payload / "validation"
    src.mkdir(parents=True)
    trusted.mkdir()
    (src / "nbody_kernel.cu").write_text(kernel, encoding="utf8", newline="\n")
    atomic_json(src / "launch.json", {"block": 256, "items_per_block": 256, "shared_memory_bytes": 0})
    shutil.copyfile(source, trusted / "original.cu")
    shutil.copyfile(src / "nbody_kernel.cu", trusted / "reference.cu")
    example = repository / "examples/cuda_nbody"
    shutil.copyfile(example / "protocol.py", trusted / "protocol.py")
    optimizer = source.parent / "optimizer"
    shutil.copyfile(optimizer / "optimizer_agent/use_harness.py", trusted / "use_harness.py")
    shutil.copyfile(optimizer / "SOURCE_COMMIT.txt", trusted / "evaluator-source-commit.txt")
    shutil.copytree(optimizer / "cuda_test_harness", payload / "cuda_test_harness",
        ignore=shutil.ignore_patterns("build*", "cmake-build*", "__pycache__", ".git", "out", "CMakeFiles"))
    shutil.copytree(repository / "src", payload / "project/src",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("pilot.py", "cuda_evaluator.py"):
        shutil.copyfile(example / name, payload / name)
    session = uuid.uuid4().hex
    remote = "/scratch_p/nimarano/hpc-forest-cuda-memory-" + session
    statement = STATEMENT + original
    config = copy.deepcopy(DEFAULT)
    config.update(problem="cuda-nbody", method="H", backend="codex", skills=policy(),
        forest={"policy": "mother", "conversation": "persistent", "integration": POLICY,
                "plan_review_calls": plan_review_calls, "statement": statement},
        memory={"mode": "active", "assembly_rounds": 16, "selection_calls": 4, "reads_per_mission": 3,
                "page_size": 6, "context_characters": 12000, "sources_per_integration": 3},
        schedule={"cycles": None, "trials_per_role_per_cycle": 1, "integrations_per_cycle": 0})
    config["completion"]["token_policy"] = "observe-only"
    config["budget"].update(wall_seconds=wall_seconds, max_workers=1, generation_seconds=600,
                            confirmation_seconds=120, infrastructure_retries=0)
    config["codex"] = {"model": "gpt-6-luna", "reasoning_effort": "max", "transport": "codex-mailbox",
                       "mailbox_dir": remote + "/pending/mailbox", "session_id": session}
    config["protocol"] = {
        "build": ["{python}", "{trusted}/protocol.py", "build", "{worktree}", "{build}"],
        "check": ["{python}", "{trusted}/protocol.py", "check", "{binary}", "{phase}"],
        "benchmark": ["{python}", "{trusted}/protocol.py", "benchmark", "{binary}", "{phase}"],
        "repetitions": 3, "confirmation_repetitions": 5, "warmups": 0,
        "timeout_seconds": 240, "build_timeout_seconds": 120,
        "environment": {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                        "FOREST_CUDA_HARNESS": remote + "/harness-build/cuda_test_harness",
                        "FOREST_CUDA_CACHE": remote + "/cache", "PYTHONDONTWRITEBYTECODE": "1",
                        "FOREST_GPU_TARGET": "NVIDIA GH200; NVRTC CUDA 12.6.3"}}
    config["harness"] = {"enabled": True, "max_attempts": 3, "call_token_ceiling": None,
        "research": {"enabled": True, "corpus": None, "corpus_sha256": None,
                     "allowed_hosts": ["docs.nvidia.com", "developer.nvidia.com", "gcc.gnu.org", "clang.llvm.org"]}}
    validate(config)
    plan = {"scope": SCOPE, "session_id": session, "model": "gpt-6-luna", "effort": "max",
            "subject": "cuda-nbody", "remote_root": remote, "wall_seconds": wall_seconds,
            "token_budget": None, "source_path": str(source), "source_sha256": file_digest(source),
            "completion": config["completion"], "memory": config["memory"], "forest": {
                k: v for k, v in config["forest"].items() if k != "statement"},
            "gpus": 1, "cpus": 4, "created_at": time.time(), "old_candidates_imported": False}
    atomic_json(payload / "plan.json", plan)
    atomic_json(payload / "settings.json", config)
    (payload / "statement.txt").write_text(statement, encoding="utf8", newline="\n")
    manifest = {p.relative_to(payload).as_posix(): file_digest(p)
                for p in sorted(payload.rglob("*")) if p.is_file()}
    atomic_json(payload / "runtime-manifest.json", manifest)
    for name in ("plan.json", "settings.json", "runtime-manifest.json", "statement.txt"):
        shutil.copyfile(payload / name, destination / name)
    archive = destination / "payload.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in sorted(payload.rglob("*")):
            if path.is_file():
                tar.add(path, arcname=path.relative_to(payload).as_posix(), recursive=False)
    q = shlex.quote
    remote_python = "/scratch_p/nimarano/hpc-forest-localmodels-20261015-r1/venv-r3/bin/python"
    command = "\n".join([
        "set -euo pipefail", "export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1",
        'test -n "${CUDA_VISIBLE_DEVICES:-}"', "test ! -e " + q(remote),
        "printf '%s  %s\\n' " + file_digest(archive) + " " + q(remote + ".tar.gz") + " | sha256sum -c -",
        "mkdir " + q(remote), "tar -xzf " + q(remote + ".tar.gz") + " -C " + q(remote),
        "export PYTHONPATH=" + q(remote + "/project/src"),
        "export FOREST_CUDA_HARNESS=" + q(remote + "/harness-build/cuda_test_harness"),
        "export FOREST_CUDA_CACHE=" + q(remote + "/cache"),
        'export TMPDIR="${SLURM_TMPDIR:-/tmp}/forest-memory-${SLURM_JOB_ID}"', 'mkdir -p "$TMPDIR"',
        "cd " + q(remote), "cmake -S cuda_test_harness -B harness-build -DCMAKE_BUILD_TYPE=Release",
        "cmake --build harness-build --parallel 4",
        q(remote_python) + " validation/protocol.py preflight validation cache > gpu-preflight.log",
        "cat gpu-preflight.log", "exec " + q(remote_python) + " -u pilot.py --root " + q(remote), ""])
    state = {"scope": SCOPE, "repository": str(repository), "artifact": str(destination),
             "session_id": session, "remote_root": remote, "remote_payload": remote + ".tar.gz",
             "payload_sha256": file_digest(archive), "source_sha256": file_digest(source),
             "batch_command": "bash -lc " + q(command), "wall_seconds": wall_seconds,
             "hosting": {"arch": "armgpu", "cpus_per_task": 4, "gpus_per_node": 1,
                         "mem_gb": 16, "time_limit": "02:00:00"},
             "allocation_submitted": False}
    atomic_json(destination / "preparation.json", state)
    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--wall-seconds", type=int, default=1800)
    parser.add_argument("--plan-review-calls", type=int, default=2,
                        help="Budgeted critique turns before research; use 0 for a comparison without critique")
    args = parser.parse_args()
    value = prepare(args.source, args.output, args.repository, wall_seconds=args.wall_seconds,
                    plan_review_calls=args.plan_review_calls)
    print(json.dumps({key: value[key] for key in ("artifact", "session_id", "payload_sha256", "allocation_submitted")}))
