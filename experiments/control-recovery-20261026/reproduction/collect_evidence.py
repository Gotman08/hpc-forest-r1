"""Copy an explicit non-secret evidence allowlist from preserved local archives."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def copy_file(source, destination, manifest):
    if not source.is_file() or source.is_symlink():
        raise ValueError("Expected a regular evidence file: " + str(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if sha256(source) != sha256(destination):
        raise ValueError("Evidence copy changed: " + str(source))
    manifest.append({"source": str(source), "destination": str(destination),
                     "bytes": destination.stat().st_size, "sha256": sha256(destination)})


def frozen_config(root):
    path = (root / "campaign/registry.sqlite3").resolve()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        return json.loads(db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0])


def initial_mother_summary(root):
    path = (root / "campaign/registry.sqlite3").resolve()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        row = db.execute("SELECT value FROM metadata WHERE key='mother_plan:preparation:1'").fetchone()
    value = json.loads(row[0]) if row else {}
    return {**{key: value.get(key) for key in ("phase", "status", "error", "model_calls")},
            "structured_plan": value.get("response", {}).get("data"),
            "scope": "Initial Mother output and validation status; native transcripts and receipts omitted"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, nargs="+", required=True)
    parser.add_argument("--common", type=Path, required=True)
    parser.add_argument("--diagnostic", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    files, audits, missing_reports = [], [], []
    for pair in args.pairs:
        plan = read(pair / "pair.json")
        target = args.output / "pairs" / plan["pair_id"]
        for name in ("pair.json", "allocation.json", "allocation-cpu.txt", "files.json", "settings.json",
                     "pair-results.json", "paired-measurements.json", "exit-code.txt", "protocol-preflight.json"):
            copy_file(pair / name, target / name, files)
        for path in sorted((pair / "remeasure/logs").rglob("*.log")):
            if path.name in {"build.log", "correctness.log"} or path.name.startswith("sample-"):
                copy_file(path, target / "paired-measurement-logs" / path.relative_to(pair / "remeasure/logs"), files)
        configs = []
        for arm in plan["arms"]:
            root = pair / ("forest-app-" + arm["id"])
            arm_target = target / arm["condition"]
            config = frozen_config(root)
            (arm_target / "report").mkdir(parents=True)
            (arm_target / "frozen-config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf8")
            (arm_target / "initial-mother.json").write_text(
                json.dumps(initial_mother_summary(root), indent=2, ensure_ascii=False) + "\n", encoding="utf8")
            configs.append(config)
            for name in ("arm-result.json", "fresh-memory.json", "controller.log"):
                copy_file(root / name, arm_target / name, files)
            for name in ("advisor.json", "advisor-decisions.csv", "active-architecture.json", "active-control.csv",
                         "active-decisions.csv", "experiments.csv", "search-diagnostics.json", "rapport.md"):
                source = root / "campaign/report" / name
                if source.is_file():
                    copy_file(source, arm_target / "report" / name, files)
                elif read(root / "arm-result.json").get("pipeline_complete"):
                    raise ValueError("Completed arm lacks report: " + str(source))
                else:
                    missing_reports.append({"pair": plan["pair_id"], "arm": arm["condition"], "report": name,
                                            "reason": "pipeline failed before report export"})
            for path in sorted((root / "confirmed-code").rglob("*")):
                if path.is_file():
                    copy_file(path, arm_target / "confirmed-code" / path.relative_to(root / "confirmed-code"), files)
            for path in sorted((root / "campaign/advisor").rglob("*")):
                if path.is_file() and path.name in {"request.json", "response.json", "worker.log"}:
                    copy_file(path, arm_target / "advisor" / path.relative_to(root / "campaign/advisor"), files)
        for config in configs:
            config["advisor"]["enabled"] = False
            config["codex"].pop("mailbox_dir", None)
            config["codex"].pop("session_id", None)
        if configs[0] != configs[1]:
            raise ValueError("Paired configs differ beyond advisor flag and isolated sessions: " + plan["pair_id"])
        audits.append({"pair_id": plan["pair_id"], "config_match": True,
                       "excluded_fields": ["advisor.enabled", "codex.mailbox_dir", "codex.session_id"]})
    for name in ("common-measurements.json", "allocation.json", "allocation-cpu.txt", "exit-code.txt"):
        copy_file(args.common / name, args.output / "common-remeasurement" / name, files)
    for case in ("utf8", "mandelbrot"):
        for path in sorted((args.common / case / "logs").rglob("*.log")):
            if path.name in {"build.log", "correctness.log"} or path.name.startswith("sample-"):
                copy_file(path, args.output / "common-remeasurement" / case / "logs"
                          / path.relative_to(args.common / case / "logs"), files)
    for path in sorted(args.diagnostic.rglob("*")) if args.diagnostic else []:
        if path.is_file() and path.name in {"diagnostic.json", "report.json", "request.json", "response.json", "worker.log"}:
            copy_file(path, args.output / "offline-diagnostic" / path.relative_to(args.diagnostic), files)
    (args.output / "copy-manifest.json").write_text(json.dumps({"files": files, "paired_config_audits": audits,
        "missing_reports": missing_reports,
        "excluded": ["OAuth and Prior Labs credentials", "authorization receipts", "weights", "mailboxes",
                     "raw model transcripts", "Git workspaces", "SQLite databases"]},
        indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print(json.dumps({"copied_files": len(files), "config_audits": audits}))


if __name__ == "__main__":
    main()
