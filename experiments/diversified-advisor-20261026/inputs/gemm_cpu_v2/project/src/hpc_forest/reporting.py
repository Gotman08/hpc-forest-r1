from __future__ import annotations

import csv
import hashlib
import io
import json
import time
import zipfile
from pathlib import Path

from .adaptive_budget import admission_deadline
from .core import FileLock, ForestError, atomic_json, digest, verify_protected
from .forest import forest_plan, research_roles
from .gitops import git
from .memory_store import memory_summary
from .model_skills import campaign_traces
from .registry import Registry
from .search import Search
from .submission import delivery_manifest
from .support.budgets import mandatory_final_g


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
                    "research_assignment": next((child for child in (forest_plan(db, row["epoch"]) or {}).get("children", [])
                                                 if child["role"] == row["role"]), None),
                    "budget_phase": mission.get("budget_phase", "search"),
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
        config = db.get("config")
        started, deadline = db.get("started"), db.get("deadline")
        search_end = db.get(f"search_closed:{db.get('current_epoch')}")
        decision = db.get(f"adaptive_budget:{db.get('current_epoch')}")
        admission_end = decision["search_admission_deadline"] if decision else admission_deadline(db)
        postprocess = db.get(f"postprocess:{db.get('current_epoch')}")
        payload = {
            "config": db.get("config"),
            "identity": db.get("identity"),
            "protocol_id": db.get("protocol_id"),
            "costs": db.costs(),
            "phase_costs": {phase: db.costs(phase) for phase in ("search", "postprocess", "confirmation")},
            "postprocess": postprocess,
            "final_g_confirmation": db.get(f"final_g_confirmation:{db.get('current_epoch')}"),
            "forest_plan": forest_plan(db),
            "mother_plan_review": db.get(f"mother_plan_review:{db.get('current_epoch')}"),
            "mother_conversation": db.get(f"mother_conversation:{db.get('current_epoch')}"),
            "model_skills": campaign_traces(db),
            "memory": memory_summary(db),
            "research_roles": research_roles(db),
            "research_scheduler": db.get(f"research_scheduler:{db.get('current_epoch')}"),
            "research_forests": [json.loads(row["value"]) for row in db.rows(
                "SELECT value FROM metadata WHERE key LIKE 'forest_plan:%' ORDER BY key")],
            "timing": {
                "started_at": started, "search_admission_deadline": admission_end,
                "search_finished_at": search_end,
                "search_elapsed_seconds": search_end - started if search_end is not None and started is not None else None,
                "drain_seconds": max(0, search_end - admission_end) if search_end is not None and admission_end is not None else None,
                "postprocess_elapsed_seconds": postprocess.get("elapsed_seconds") if postprocess else None,
                "confirmation_deadline": db.get(f"confirmation_deadline:{db.get('current_epoch')}"),
                "target_deadline": deadline,
                "target_seconds": config["budget"]["wall_seconds"],
                "adaptive_reserve": decision,
                "samples": db.get("timing_samples", {}),
                "confirmation_finished_at": db.get(f"confirmation_finished:{db.get('current_epoch')}"),
                "pipeline_finished_at": db.get(f"pipeline_finished:{db.get('current_epoch')}"),
                "overrun_seconds": max(0, (db.get(f"pipeline_finished:{db.get('current_epoch')}")
                                          or time.time()) - deadline) if deadline is not None else None,
            },
            "status": db.get("status"),
            "best_confirmed": db.get("best_confirmed"),
            "experiments": rows,
            "evaluations": db.evaluations("search") + db.evaluations("postprocess") + db.evaluations("confirmation"),
            "events": db.rows("SELECT * FROM events ORDER BY id"),
            "epochs": db.rows("SELECT * FROM epochs ORDER BY id"),
            "search_topology": Search(db).snapshot(),
        }
        atomic_json(output / "experiments.json", payload)
        fields = [
            "id",
            "epoch",
            "role",
            "budget_phase",
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
            f"Coûts par phase : `{json.dumps(payload['phase_costs'])}`.",
            f"Confirmation obligatoire de G final : `{json.dumps(payload['final_g_confirmation'], ensure_ascii=False)}`.",
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
        if payload["forest_plan"]:
            selected = payload["forest_plan"]
            lines += [f"Mother a choisi **{len(selected['children'])} arbres AB-MCTS**, "
                      "exécutés tous en parallèle à chaque passe.", "",
                      "| Arbre | Sujet | Objectif Mother |", "|---|---|---|"]
            for child in selected["children"]:
                subject, objective = (child[key].replace("|", "\\|").replace("\n", " ") for key in ("subject", "objective"))
                lines += [f"| {child['role']} | {subject} | {objective} |"]
            lines += [""]
        if payload["search_topology"]["policy"] == "binary-greedy":
            lines += ["Recherche : `binary-greedy` ; au plus deux enfants par nœud. "
                      "La branche écartée reste archivée et n'est plus développée.", ""]
        lines += [
            "| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |",
            "|---|---|---|---|---:|---|",
        ]
        for row in rows:
            seconds = "—" if row["mean_seconds"] is None else f"{row['mean_seconds']:.6f}"
            lines.append(
                f"| {row['id']} | {row['role']} | {row['budget_phase']} | {row['state']} | {seconds} | {(row['commit'] or '')[:12]} |"
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
            final = db.get(f"final_g_confirmation:{db.get('current_epoch')}")
            if mandatory_final_g(db.get("config")) and (
                    not final or final.get("status") not in {"confirmed", "rejected"}):
                raise ForestError("Packaging requires the mandatory final G confirmation")
            if mandatory_final_g(db.get("config")):
                final_evaluation = db.one("SELECT payload FROM evaluations WHERE experiment_id=? AND phase='confirmation'",
                                          (final["experiment_id"],))
                post = db.get(f"postprocess:{db.get('current_epoch')}", {})
                if (not final_evaluation or json.loads(final_evaluation["payload"]) != final["outcome"]
                        or final["experiment_id"] != post.get("mission_id")
                        or final["outcome"].get("commit") != post.get("outcome", {}).get("commit")):
                    raise ForestError("Mandatory final G confirmation receipt does not match its committed program")
            raw = git(root / "repo", "archive", "--format=zip", best["commit"], binary=True)
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                delivery = delivery_manifest(archive, db.get("config"))
            manifest = {
                "format": "hpc-forest-submission-v1",
                "created_unix": time.time(),
                **best,
                "target": db.get("identity"),
                "protocol": db.get("config")["protocol"],
                "search_policy": "binary-greedy" if Search(db).binary else "ab-mcts-a",
                "confirmation": outcome,
                "delivery": delivery,
                "final_g_confirmation": final,
                "forest_plan": forest_plan(db),
                "mother_conversation": db.get(f"mother_conversation:{db.get('current_epoch')}"),
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
                if delivery_manifest(archive, db.get("config")) != delivery:
                    raise ForestError("Submission delivery differs from the confirmed source archive")
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
