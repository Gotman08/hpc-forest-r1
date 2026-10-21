from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import shutil
import sys
import time
from pathlib import Path

from .adaptive_budget import parse_duration, record_timing
from .config import load_config
from .controller import Controller, create_workspace
from .core import ForestError, atomic_json
from .forest import model_selected
from .knowledge import Knowledge, serve_mcp
from .pilot import execute, prepare
from .registry import Registry
from .reporting import package, report
from .support.budgets import adaptive
from .toolchain import compiler_identity


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def complete_local(controller, root: Path) -> dict:
    """Publish a truthful completion receipt even when final delivery fails."""
    done = {"pipeline_complete": False, "target_deadline": controller.db.get("deadline")}
    try:
        done["best_confirmed"] = controller.confirm()
        started = time.time()
        done["report"] = str(report(root))
        done["package"] = str(package(root, root / "submission.zip"))
        record_timing(controller.db, "archive", time.time() - started)
        state = controller.status()
        done["final_g_confirmation"] = state.get("final_g_confirmation")
        done["pipeline_complete"] = ((state.get("postprocess") or {}).get("status") == "complete"
                                     and (done["final_g_confirmation"] or {}).get("status") in {"confirmed", "rejected"})
        if model_selected(controller.config):
            done["forest_plan"] = state["forest_plan"]
            tried = {row["role"] for row in controller.db.rows("SELECT role FROM trials WHERE epoch=?",
                                                             (state["epoch"],))}
            done["pipeline_complete"] &= bool(state["forest_plan"]) and all(
                child["role"] in tried for child in state["forest_plan"]["children"])
            done["pipeline_complete"] &= not any(json.loads(row["result"] or "{}").get("status")
                in {None, "infrastructure_error", "cancelled_budget", "cancelled_interrupted", "generation_failed"}
                for row in controller.db.rows("SELECT result FROM trials WHERE epoch=?", (state["epoch"],)))
        return done
    except (ForestError, OSError, ValueError) as exc:
        done["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        key = f"pipeline_finished:{controller.db.get('current_epoch')}"
        done["finished_at"] = controller.db.get(key) or time.time()
        if done["pipeline_complete"]:
            controller.db.set(key, done["finished_at"])
        done["overrun_seconds"] = max(0, done["finished_at"] - done["target_deadline"])
        atomic_json(root / "DONE.json", done)
        if model_selected(getattr(controller, "config", {})):
            atomic_json(Path(controller.config["codex"]["mailbox_dir"]) / "DONE.json",
                        {**done, "session_id": controller.config["codex"]["session_id"]})


def parser():
    p = argparse.ArgumentParser(
        description="Persistent AB-MCTS HPC experiments, with exact-commit evidence"
    )
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Inspect local prerequisites without contacting a service")
    init = sub.add_parser(
        "init", help="Create a new local campaign from an imported source snapshot"
    )
    init.add_argument("workspace", type=Path)
    init.add_argument("--config", type=Path)
    init.add_argument("--method", choices=["H", "U", "H-no-feedback", "H-enumeration"])
    init.add_argument("--backend", choices=["recipe", "codex", "ollama"])
    init.add_argument("--binary-tree", action=argparse.BooleanOptionalAction, default=None,
                      help="Enable/disable greedy binary trees in a new campaign")
    init.add_argument("--source", type=Path)
    init.add_argument("--validation", type=Path)
    init.add_argument("--duration", type=parse_duration,
                      help="Target duration: 30m, 2h, 5h, 24h; admitted work may finish later")
    init.add_argument("--mother-trees", action="store_true",
                      help="Mother chooses N subjects; all N AB-MCTS trees run concurrently")
    init.add_argument("--statement", type=Path, help="Problem text supplied to Mother as data")
    run = sub.add_parser("run", help="Run or resume bounded search")
    run.add_argument("workspace", type=Path)
    run.add_argument("--max-batches", type=int)
    run.add_argument("--confirm", action="store_true")
    for name in ["status", "confirm", "new-epoch"]:
        child = sub.add_parser(name)
        child.add_argument("workspace", type=Path)
    rep = sub.add_parser("report")
    rep.add_argument("workspace", type=Path)
    rep.add_argument("--output", type=Path)
    pack = sub.add_parser("package")
    pack.add_argument("workspace", type=Path)
    pack.add_argument("output", type=Path)
    docs = sub.add_parser("docs")
    docs.add_argument("workspace", type=Path)
    docs_sub = docs.add_subparsers(dest="docs_command", required=True)
    query = docs_sub.add_parser("query")
    query.add_argument("query")
    query.add_argument("--max-chars", type=int, default=6000)
    add = docs_sub.add_parser("add")
    add.add_argument("file", type=Path)
    add.add_argument("--title", required=True)
    add.add_argument("--url", required=True)
    add.add_argument("--version", required=True)
    add.add_argument("--preconditions", default="Verify on the configured target")
    mcp = sub.add_parser(
        "mcp", help="Serve source-labelled documentation and status over MCP stdio"
    )
    mcp.add_argument("workspace", type=Path)
    demo = sub.add_parser(
        "demo", help="Real local C build/test/search/confirmation/package; no LLM calls"
    )
    demo.add_argument("workspace", type=Path)
    demo.add_argument("--config", type=Path)
    pilot = sub.add_parser("pilot", help="Prepare matched U/H campaigns; execute only with --run")
    pilot.add_argument("destination", type=Path)
    pilot.add_argument("--config", type=Path)
    pilot.add_argument("--seeds", type=int, nargs="+", default=[23, 29, 31, 37, 41])
    pilot.add_argument(
        "--methods",
        nargs="+",
        choices=["U", "H", "H-no-feedback", "H-enumeration"],
        default=["U", "H"],
    )
    pilot.add_argument("--run", action="store_true")
    pilot_run = sub.add_parser("pilot-run", help="Run/resume a previously saved pilot plan")
    pilot_run.add_argument("plan", type=Path)
    return p


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            info = {
                "python": sys.version,
                "platform": platform.platform(),
                "git": shutil.which("git"),
                "codex": shutil.which("codex"),
                "treequest": importlib.metadata.version("treequest"),
            }
            try:
                info["compiler"] = compiler_identity()
            except ForestError as exc:
                info["compiler_error"] = str(exc)
            emit(info)
            return 0 if info.get("git") and info.get("compiler") else 1
        if args.command == "init":
            config = load_config(args.config)
            if args.binary_tree is not None:
                config["binary_tree"] = {"enabled": args.binary_tree}
            if args.method:
                config["method"] = args.method
            if args.backend:
                config["backend"] = args.backend
            if args.duration is not None:
                config["budget"].update(wall_seconds=args.duration, tokens=None,
                                        mission_tokens=None, search_slots=None, max_depth=0)
                config["schedule"]["cycles"] = None
                config["completion"].update(policy="finish-started", reserve_policy="adaptive",
                                             confirm_final_g=True, postprocess_tokens=None)
                config["harness"]["call_token_ceiling"] = None
            if args.mother_trees:
                from .model_skills import policy as skills_policy

                config["forest"] = {"policy": "mother", "conversation": "persistent", "integration": "pairwise"}
                config["skills"] = skills_policy()
                config["schedule"].update(trials_per_role_per_cycle=1, integrations_per_cycle=0)
            if args.statement:
                config.setdefault("forest", {})["statement"] = args.statement.read_text(encoding="utf-8")
            emit(
                {
                    "workspace": str(
                        create_workspace(args.workspace, config, args.source, args.validation)
                    )
                }
            )
        elif args.command in {"run", "status", "confirm", "new-epoch"}:
            with Controller(args.workspace) as controller:
                if args.command == "run":
                    if args.max_batches is not None and args.max_batches < 1:
                        raise ForestError("--max-batches must be positive")
                    state = controller.run(args.max_batches)
                    emit(state)
                    if args.confirm or (adaptive(controller.config) and state["status"] != "checkpointed"):
                        if adaptive(controller.config):
                            done = complete_local(controller, args.workspace)
                            emit(done)
                            return 0 if done["pipeline_complete"] else 1
                        emit(controller.confirm())
                elif args.command == "status":
                    emit(controller.status())
                elif args.command == "confirm":
                    emit(controller.confirm())
                else:
                    emit(controller.new_epoch())
        elif args.command == "report":
            emit({"report": str(report(args.workspace, args.output))})
        elif args.command == "package":
            emit({"package": str(package(args.workspace, args.output))})
        elif args.command == "docs":
            if not (args.workspace / "registry.sqlite3").is_file():
                raise ForestError("Initialize the campaign first")
            db = Registry(args.workspace / "registry.sqlite3")
            try:
                knowledge = Knowledge(db)
                if args.docs_command == "query":
                    emit(knowledge.query(args.query, args.max_chars))
                else:
                    emit(
                        {
                            "document_id": knowledge.add(
                                args.title,
                                args.url,
                                args.version,
                                args.file.read_text(encoding="utf-8"),
                                args.preconditions,
                            )
                        }
                    )
            finally:
                db.close()
        elif args.command == "mcp":
            if not (args.workspace / "registry.sqlite3").is_file():
                raise ForestError("Initialize the campaign first")
            serve_mcp(args.workspace.resolve())
        elif args.command == "demo":
            config = load_config(args.config)
            config["backend"] = "recipe"
            create_workspace(args.workspace, config)
            with Controller(args.workspace) as controller:
                controller.run()
                emit(controller.confirm())
            emit(
                {
                    "report": str(report(args.workspace)),
                    "package": str(package(args.workspace, args.workspace / "submission.zip")),
                }
            )
        elif args.command == "pilot":
            plan = prepare(
                args.destination.resolve(), load_config(args.config), args.seeds, args.methods
            )
            emit({"plan": str(plan)})
            if args.run:
                emit({"results": str(execute(plan))})
        elif args.command == "pilot-run":
            emit({"results": str(execute(args.plan.resolve()))})
        return 0
    except (ForestError, OSError, ValueError) as exc:
        print(f"hpc-forest: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(
            "Interrupted. Reserved slots and pending trials remain in the registry for bounded recovery.",
            file=sys.stderr,
        )
        return 130
