from __future__ import annotations

import csv
import hashlib
import json
import time
import zipfile
from pathlib import Path

from .core import FileLock, ForestError, atomic_json, digest, verify_protected
from .gitops import git
from .registry import Registry
from .search import Search


def report(root: Path, output: Path | None = None) -> Path:
    root = root.resolve()
    output = output or root / "report"
    output.mkdir(parents=True, exist_ok=True)
    db = Registry(root / "registry.sqlite3")
    try:
        rows = []
        for row in db.rows("SELECT * FROM trials ORDER BY created,id"):
            mission = json.loads(row["mission"])
            outcome = json.loads(row["result"]) if row["result"] else {}
            rows.append(
                {
                    "id": row["id"],
                    "epoch": row["epoch"],
                    "role": row["role"],
                    "tree_id": row["tree_id"],
                    "trial_id": row["trial_id"],
                    "search_parent": mission["parent_id"],
                    "delegation_parent": mission["delegation_parent"],
                    "base_commit": mission["base_commit"],
                    "sources": mission["sources"],
                    "source_commits": mission["source_commits"],
                    "transformations": mission["transformations"],
                    "hypothesis": mission["hypothesis"],
                    "worktree": mission["worktree"],
                    "state": outcome.get("status", row["state"]),
                    "commit": outcome.get("commit"),
                    "correct": outcome.get("correct"),
                    "mean_seconds": outcome.get("mean_seconds"),
                    "score": outcome.get("score"),
                    "reason": outcome.get("reason", ""),
                    "times": outcome.get("times", []),
                    "logs": outcome.get("logs", []),
                }
            )
        payload = {
            "config": db.get("config"),
            "identity": db.get("identity"),
            "protocol_id": db.get("protocol_id"),
            "costs": db.costs(),
            "status": db.get("status"),
            "best_confirmed": db.get("best_confirmed"),
            "experiments": rows,
            "evaluations": db.evaluations("search") + db.evaluations("confirmation"),
            "events": db.rows("SELECT * FROM events ORDER BY id"),
            "epochs": db.rows("SELECT * FROM epochs ORDER BY id"),
            "search_topology": Search(db).snapshot(),
        }
        atomic_json(output / "experiments.json", payload)
        fields = [
            "id",
            "epoch",
            "role",
            "tree_id",
            "trial_id",
            "search_parent",
            "delegation_parent",
            "base_commit",
            "commit",
            "sources",
            "state",
            "correct",
            "mean_seconds",
            "score",
            "reason",
        ]
        with (output / "experiments.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({**row, "sources": json.dumps(row["sources"])})
        best = db.get("best_confirmed")
        lines = [
            "# Rapport de campagne HPC Forest",
            "",
            f"État : `{payload['status']}`.",
            "",
            f"Méthode : `{payload['config']['method']}` ; génération : `{payload['config']['backend']}`.",
            f"Protocole : `{payload['protocol_id']}`.",
            "",
            "Ces mesures concernent uniquement cette machine et ce protocole. "
            "Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.",
            "",
            f"Coûts enregistrés : `{json.dumps(payload['costs'])}`.",
            "",
        ]
        if best:
            lines += [
                f"Commit retenu après confirmation : `{best['commit']}`.",
                f"Temps confirmé : {best['mean_seconds']:.6f} s ; "
                f"référence confirmée : {best['reference_seconds']:.6f} s.",
                f"Réduction mesurée : {best['improvement_fraction']:.1%}. "
                f"Référence conservée : {'oui' if best['is_baseline'] else 'non'}.",
                "",
            ]
        else:
            lines += ["Aucune version confirmée : aucun gain final n'est déclaré.", ""]
        if payload["search_topology"]["policy"] == "binary-greedy":
            lines += ["Recherche : `binary-greedy` ; au plus deux enfants par nœud. "
                      "La branche écartée reste archivée et n'est plus développée.", ""]
        lines += [
            "| Expérience | Rôle | État | Temps de recherche (s) | Commit |",
            "|---|---|---|---:|---|",
        ]
        for row in rows:
            seconds = "—" if row["mean_seconds"] is None else f"{row['mean_seconds']:.6f}"
            lines.append(
                f"| {row['id']} | {row['role']} | {row['state']} | {seconds} | {(row['commit'] or '')[:12]} |"
            )
        lines += [
            "",
            "Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. "
            "Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure "
            "gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.",
            "",
        ]
        (output / "rapport.md").write_text("\n".join(lines), encoding="utf-8")
        return output / "rapport.md"
    finally:
        db.close()


def package(root: Path, destination: Path) -> Path:
    root, destination = root.resolve(), destination.resolve()
    with FileLock(root / "campaign.lock"):
        db = Registry(root / "registry.sqlite3")
        try:
            best = db.get("best_confirmed")
            if not best:
                raise ForestError("Packaging requires an independently confirmed commit")
            verify_protected(root / "trusted", db.get("manifest"))
            row = db.one(
                "SELECT payload FROM evaluations WHERE experiment_id=? AND phase='confirmation'",
                (best["experiment_id"],),
            )
            if not row or digest(json.loads(row["payload"])) != best["evaluation_digest"]:
                raise ForestError("Confirmed evaluation receipt does not match the selected commit")
            outcome = json.loads(row["payload"])
            if outcome["correct"] is not True or outcome["commit"] != best["commit"]:
                raise ForestError("No valid exact-commit confirmation")
            raw = git(root / "repo", "archive", "--format=zip", best["commit"], binary=True)
            manifest = {
                "format": "hpc-forest-submission-v1",
                "created_unix": time.time(),
                **best,
                "target": db.get("identity"),
                "protocol": db.get("config")["protocol"],
                "search_policy": "binary-greedy" if Search(db).binary else "ab-mcts-a",
                "confirmation": outcome,
            }
            destination.parent.mkdir(parents=True, exist_ok=True)
            tmp = destination.with_suffix(destination.suffix + ".tmp")
            tmp.write_bytes(raw)
            with zipfile.ZipFile(tmp, "a", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "HPC_FOREST_MANIFEST.json", json.dumps(manifest, indent=2, ensure_ascii=False)
                )
            with zipfile.ZipFile(tmp) as archive:
                if archive.testzip() is not None:
                    raise ForestError("Submission archive integrity failed")
                names = set(archive.namelist())
                if not {"Makefile", "run.sh"}.issubset(names):
                    raise ForestError(
                        "Submission requires a Makefile and run.sh in the imported repository"
                    )
            tmp.replace(destination)
            sha = hashlib.sha256(destination.read_bytes()).hexdigest()
            destination.with_suffix(destination.suffix + ".sha256").write_text(
                f"{sha}  {destination.name}\n", encoding="ascii"
            )
            db.event(
                "packaged", {"commit": best["commit"], "path": str(destination), "sha256": sha}
            )
            return destination
        finally:
            db.close()
