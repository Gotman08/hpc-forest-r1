"""Operator prepares execution; AB-MCTS/local workers own every candidate edit."""

import argparse
import json
import sys
import time
import traceback
import zipfile
from pathlib import Path

import romeo_base as base
from hpc_forest import contracts
from hpc_forest.config import load_config
from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import atomic_json
from hpc_forest.knowledge import Knowledge
from hpc_forest.ollama_backend import request_json, resolve_model
from hpc_forest.reporting import package, report
from neutral_backend import NeutralBackend
from prepare_problem import prepare_problem

ROOT = Path(__file__).resolve().parent
MODEL = "qwen2.5-coder:14b"
DIGEST = "9ec8897f747e246e970bc5cfdda85d22f1123dc2e3d34978a010a75968716849"
LOCAL_MODEL_SPEC = None
PROBLEMS = ["knn", "sum", "nbody", "bucketsort"]
DECODING = {}
SCHEDULE = {"cycles": 2, "trials_per_role_per_cycle": 3, "integrations_per_cycle": 3}
LIMITS = {"wall_seconds": 1200, "tokens": 600000, "generation_seconds": 120}


def config_for(url, slug, target, prepared):
    c = load_config()
    c["completion"] = {"policy": "hard"}  # Historical finite comparison contract.
    c.update(problem=slug, backend="ollama", method="H", seed=23, target_id=target)
    c["budget"].update(
        search_slots=1 + SCHEDULE["cycles"] * (3 * SCHEDULE["trials_per_role_per_cycle"] + SCHEDULE["integrations_per_cycle"]),
        confirmation_slots=3,
        max_workers=1,
        max_depth=6,
        confirmation_seconds=120,
        infrastructure_retries=0,
    )
    c["budget"].update(LIMITS)
    c["schedule"].update(SCHEDULE)
    c["ollama"].update(
        base_url=url,
        model=MODEL,
        model_digest=DIGEST,
        temperature=0.0,
        context_tokens=32768,
        max_output_tokens=8192,
        num_threads=4,
    )
    c["ollama"].update(DECODING)
    c["budget"]["mission_tokens"] = c["ollama"]["context_tokens"] + c["ollama"]["max_output_tokens"]
    c["protocol"].update(
        build=[
            "{python}",
            "{trusted}/contract_tool.py",
            "build",
            "{worktree}",
            "{build}",
        ],
        check=[
            "{python}",
            "{trusted}/contract_tool.py",
            "check",
            "{binary}",
            "{phase}",
        ],
        benchmark=["/bin/sh", "{trusted}/benchmark.sh", "{binary}"],
        repetitions=3,
        confirmation_repetitions=5,
        warmups=1,
        timeout_seconds=prepared["protocol_timeout_seconds"],
        build_timeout_seconds=120,
        environment={
            "OMP_NUM_THREADS": "4",
            "OMP_DYNAMIC": "FALSE",
            "OMP_PROC_BIND": "TRUE",
            "CUDA_VISIBLE_DEVICES": "",
        },
    )
    return c


def extract_official(slug, output):
    dest = output / "official" / slug
    dest.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(ROOT / "sources-officielles" / (slug + ".zip")) as z:
        for item in z.infolist():
            name = contracts.relative(item.filename.rstrip("/"))
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError("Archive symlink is not supported")
            target = dest / name
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(item))
    return dest


class AutonomousController(Controller):
    def __init__(self, root, statement):
        super().__init__(root)
        self.backend = NeutralBackend()
        self.statement = statement

    def _context(self, mission, sources):
        context = super()._context(mission, sources)
        context["official_statement_as_data"] = self.statement
        context["runtime_as_data"] = {
            "cpu_cores": 4,
            "OMP_NUM_THREADS": 4,
            "architecture": "ARM64",
            "candidate_GPU": False,
            "comparison": "Exact output bytes against official reference",
        }
        return context


def campaign(url, slug, output, target):
    root = output / slug
    started = time.monotonic()
    result = {"problem": slug, "model": MODEL, "campaign": str(root), "complete": False}
    try:
        official = extract_official(slug, output)
        base.emit("operator_preparation_start", problem=slug)
        prepared = prepare_problem(slug, official, output)
        result["preparation"] = prepared
        base.emit(
            "operator_preparation_ready",
            problem=slug,
            benchmark_seconds=prepared["benchmark_reference_seconds"],
            search_cases=prepared["search_cases"],
            confirmation_cases=prepared["confirmation_cases"],
        )
        settings = config_for(url, slug, target, prepared)
        pulled = (
            {"status": "success", "source": "verified-local-GGUF-import"}
            if LOCAL_MODEL_SPEC is not None
            else request_json(url, "/api/pull", {"model": MODEL, "stream": False}, 600)
        )
        atomic_json(output / f"{slug}-pull.json", pulled)
        if pulled.get("status") != "success":
            raise RuntimeError("Local model pull failed")
        result["identity"] = resolve_model(settings["ollama"])
        loaded = request_json(
            url,
            "/api/generate",
            {
                "model": MODEL,
                "keep_alive": "10m",
                "stream": False,
                "options": {"num_ctx": settings["ollama"]["context_tokens"], "num_thread": settings["ollama"]["num_threads"]},
            },
            180,
        )
        atomic_json(output / f"{slug}-load.json", loaded)
        residents = request_json(url, "/api/ps", None, 15)
        atomic_json(output / f"{slug}-gpu-before.json", residents)
        if not any(
            (m.get("name") == MODEL or m.get("model") == MODEL)
            and m.get("size_vram", 0) > 0
            for m in residents.get("models", [])
        ):
            raise RuntimeError("GPU model residency not observed")
        statement = (ROOT / "sources-officielles/problemset.txt").read_text(
            encoding="utf-8"
        )
        create_workspace(
            root,
            settings,
            source=Path(prepared["source"]),
            validation=Path(prepared["validation"]),
        )
        with AutonomousController(root, statement) as controller:
            with controller.db.connection:
                controller.db.connection.execute(
                    "DELETE FROM documents WHERE url=?", ("local:matmul-training-task",)
                )
            Knowledge(controller.db).add(
                "Official problem statement",
                "http://lspd.mackenzie.br/marathon/22/problemset.pdf",
                "downloaded-2026-10-15",
                statement,
                "Official source material. Operator supplies execution only.",
            )
            controller.db.event(
                "neutral_adapter",
                {
                    "files": {
                        p.name: base.sha256(p)
                        for p in [
                            ROOT / "romeo_marathon.py",
                            ROOT / "neutral_backend.py",
                            ROOT / "prepare_problem.py",
                        ]
                    },
                    "operator_algorithm_changes": 0,
                    "manual_candidate_repairs": 0,
                    "operator_prepared": True,
                },
            )
            while True:
                result["search"] = controller.run(max_batches=1)
                topology = base.tree_snapshot(controller)
                topology["problem"] = slug
                atomic_json(output / f"{slug}-progress.json", topology)
                with (output / "topology-events.jsonl").open(
                    "a", encoding="utf-8"
                ) as stream:
                    stream.write(json.dumps(topology) + "\n")
                base.emit(
                    "tree_progress",
                    problem=slug,
                    **{
                        k: topology[k]
                        for k in [
                            "status",
                            "cursor",
                            "trials",
                            "scored_nodes",
                            "max_depth",
                            "max_children",
                            "tokens_used",
                        ]
                    },
                )
                if result["search"]["status"] != "checkpointed":
                    break
            result["best_confirmed"] = controller.confirm()
            result["search_complete"] = result["search"]["status"] == "search_complete"
            result["costs"] = controller.db.costs()
            result["generation_usage"] = [
                json.loads(r["payload"])
                for r in controller.db.rows(
                    "SELECT payload FROM events WHERE kind='generation_usage' ORDER BY id"
                )
            ]
            result["trials"] = [
                {
                    "id": r["id"],
                    "role": r["role"],
                    "outcome": json.loads(r["result"]) if r["result"] else None,
                }
                for r in controller.db.rows(
                    "SELECT id,role,result FROM trials ORDER BY created,id"
                )
            ]
        result["report"] = str(report(root))
        result["package"] = str(package(root, root / "submission.zip"))
        result["package_sha256"] = base.sha256(root / "submission.zip")
        result["pipeline_complete"] = True
        result["complete"] = result["search_complete"]
    except Exception as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
        result["traceback"] = traceback.format_exc()
        if (root / "registry.sqlite3").is_file():
            try:
                report(root)
            except Exception:
                result["report_error"] = traceback.format_exc()
    finally:
        result["elapsed_seconds"] = time.monotonic() - started
        atomic_json(output / f"{slug}-summary.json", result)
        base.emit(
            "problem_end",
            problem=slug,
            complete=result["complete"],
            error=result.get("error"),
            best=result.get("best_confirmed"),
        )
    return result


def positive_integer(value):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Expected a positive integer")
    return parsed


def prepare_local_model(url, cache, output):
    global DIGEST
    from local_model import interface_smoke, prepare

    identity = prepare(LOCAL_MODEL_SPEC, url, cache, output)
    if identity["model"] != MODEL:
        raise RuntimeError("Prepared local model differs from the requested model")
    DIGEST = identity["model_digest"]
    checked = interface_smoke(url, MODEL, output)
    base.emit("model_interface_ready", model=MODEL, digest=DIGEST, **checked)


if __name__ == "__main__":
    selection = argparse.ArgumentParser(add_help=False)
    selection.add_argument("--problems", nargs="+", choices=PROBLEMS, default=PROBLEMS)
    selection.add_argument("--model", default=MODEL)
    selection.add_argument("--model-digest")
    selection.add_argument("--local-model-spec", type=Path)
    selection.add_argument("--cycles", type=positive_integer)
    selection.add_argument("--trials-per-role", type=positive_integer)
    selection.add_argument("--integrations", type=positive_integer)
    selection.add_argument("--wall-seconds", type=positive_integer)
    selection.add_argument("--tokens", type=positive_integer)
    selection.add_argument("--generation-seconds", type=positive_integer)
    selection.add_argument("--temperature", type=float)
    selection.add_argument("--repeat-penalty", type=float)
    selection.add_argument("--repeat-last-n", type=int)
    selection.add_argument("--context-tokens", type=positive_integer)
    selection.add_argument("--max-output-tokens", type=positive_integer)
    selected, remaining = selection.parse_known_args()
    if selected.model_digest and selected.local_model_spec:
        selection.error("Choose either a registry digest or a pinned local GGUF specification")
    if selected.model != MODEL and not (selected.model_digest or selected.local_model_spec):
        selection.error("A different model requires its full --model-digest")
    MODEL = selected.model
    DIGEST = selected.model_digest or DIGEST
    if selected.local_model_spec:
        from local_model import read_spec

        LOCAL_MODEL_SPEC = selected.local_model_spec.resolve(strict=True)
        if read_spec(LOCAL_MODEL_SPEC)["model"] != MODEL:
            selection.error("The local GGUF specification must declare the requested model")
        base.PREPARE_MODEL = prepare_local_model
    for argument, key in [("cycles", "cycles"), ("trials_per_role", "trials_per_role_per_cycle"), ("integrations", "integrations_per_cycle")]:
        if getattr(selected, argument) is not None:
            SCHEDULE[key] = getattr(selected, argument)
    for key in LIMITS:
        if getattr(selected, key) is not None:
            LIMITS[key] = getattr(selected, key)
    if selected.temperature is not None:
        DECODING["temperature"] = selected.temperature
    if selected.repeat_penalty is not None:
        DECODING["repeat_penalty"] = selected.repeat_penalty
    if selected.repeat_last_n is not None:
        DECODING["repeat_last_n"] = selected.repeat_last_n
    for argument, key in [("context_tokens", "context_tokens"), ("max_output_tokens", "max_output_tokens")]:
        if getattr(selected, argument) is not None:
            DECODING[key] = getattr(selected, argument)
    sys.argv = [sys.argv[0], *remaining]
    base.MODELS = selected.problems
    base.campaign = campaign
    raise SystemExit(base.main())
