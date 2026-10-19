from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import shutil
import sys
from pathlib import Path

from .config import load_config
from .controller import Controller, create_workspace
from .core import ForestError
from .knowledge import Knowledge, serve_mcp
from .pilot import execute, prepare
from .registry import Registry
from .reporting import package, report
from .toolchain import compiler_identity


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


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
                    emit(controller.run(args.max_batches))
                    if args.confirm:
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
