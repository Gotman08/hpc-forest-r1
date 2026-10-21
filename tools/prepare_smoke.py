"""Prepare a fresh local payload; neither submits a job nor calls a model."""
from __future__ import annotations

import argparse
import json
import tarfile
import time
import uuid
from pathlib import Path

from native_smoke import (
    ADAPTIVE_SCOPE,
    EFFORT,
    FINISH_SCOPE,
    FOREST_SCOPE,
    MODEL,
    OFFICIAL_SCOPE,
    OFFICIAL_SHARED_ROOT,
    PILOTS,
    SCOPE,
    adaptive_contract,
    depth_contract,
    forest_contract,
    validate_depth_plan,
)

from hpc_forest.adaptive_budget import parse_duration
from hpc_forest.core import InfrastructureError, atomic_json, file_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", choices=("2023-count", "matmul"), default="2023-count",
                        help="An official subject is the default; matmul is only a synthetic example")
    parser.add_argument("--binary-tree", action="store_true",
                        help="Prepare the optional binary policy on the official subject")
    parser.add_argument("--depth-comparison", action="store_true",
                        help="Fresh matched campaign, with unlimited depth/tokens and a search admission timer")
    parser.add_argument("--trials-per-role", type=int, default=16,
                        help="Even maximum per A/B/C/G role in the depth campaign (default: 16)")
    parser.add_argument("--wall-seconds", type=int, default=1800,
                        help="Nominal admission window, with confirmation reserve deducted; final work may exceed it")
    parser.add_argument("--adaptive", action="store_true",
                        help="Repeat cycles within an adaptive duration, then confirm final G; no token quota")
    parser.add_argument("--mother-trees", action="store_true",
                        help="Mother chooses N AB-MCTS research trees; all N run concurrently")
    parser.add_argument("--duration", type=parse_duration,
                        help="Target total duration, e.g. 30m, 2h, 5h or 24h (implies --adaptive)")
    args = parser.parse_args()
    adaptive = args.adaptive or args.duration is not None or args.mother_trees
    if args.duration is not None:
        args.wall_seconds = args.duration
    official = args.subject == "2023-count"
    if args.binary_tree and not official:
        parser.error("Use an official subject to compare search policies")
    if args.mother_trees and args.binary_tree:
        parser.error("Mother-selected research trees use AB-MCTS")
    if (args.depth_comparison or adaptive) and not official:
        parser.error("The depth comparison requires the frozen official 2023-count subject")
    if adaptive and (args.depth_comparison or args.trials_per_role != 16):
        parser.error("The adaptive profile has no trial ceiling; do not combine it with finite depth limits")
    if not (args.depth_comparison or adaptive) and (args.trials_per_role != 16 or args.wall_seconds != 1800):
        parser.error("Custom limits require the separate --depth-comparison scope")
    contract = None
    if args.depth_comparison or adaptive:
        try:
            contract = (forest_contract(args.wall_seconds) if args.mother_trees else
                        adaptive_contract(args.wall_seconds) if adaptive else
                        depth_contract(args.trials_per_role, args.wall_seconds, None, completion=True))
        except InfrastructureError as exc:
            parser.error(str(exc))
    scope = FOREST_SCOPE if args.mother_trees else ADAPTIVE_SCOPE if adaptive else FINISH_SCOPE if args.depth_comparison else OFFICIAL_SCOPE if official else SCOPE
    project = Path(__file__).resolve().parent.parent
    session = uuid.uuid4().hex
    prefix = "official-forest-" if args.mother_trees else "official-adaptive-" if adaptive else "official-depth-" if args.depth_comparison else "official-count-" if official else "luna-smoke-"
    destination = project / "artifacts" / (prefix + session[:8])
    destination.mkdir(exist_ok=False)
    remote_root = "/scratch_p/nimarano/" + PILOTS[scope][2] + session
    plan = {"scope": scope, "session_id": session, "model": MODEL, "effort": EFFORT,
            "subject": args.subject, "child_missions": 8 if official else 4, "mother_calls": 2,
            "wall_seconds": 1800 if official else 900, "token_budget": 1500000, "seed": 23,
            "maximum_calls_including_repairs": 26 if official else 14, "cores": 4, "gpus": 0,
            "remote_root": remote_root, "created_at": time.time(),
            "purpose": "official R1 matched protocol" if official else "synthetic mechanical smoke",
            "historical_candidates_imported": False}
    plan["binary_tree"] = {"enabled": args.binary_tree}
    if contract:
        plan.update(contract, depth_comparison=True, trials_per_role=None if adaptive else args.trials_per_role,
                    max_depth=0, wall_seconds=args.wall_seconds, token_budget=None,
                    purpose="matched search admission windows; drain active nodes, then final Mother and G")
    if args.mother_trees:
        plan["purpose"] = "Mother chooses N concurrent AB-MCTS trees, then resumes her original conversation to assemble G; no research restart"
        from hpc_forest.documentation_mcp import DOCUMENTATION_POLICY
        from hpc_forest.model_mcp import MODEL_MCP_POLICY
        from hpc_forest.model_skills import policy as skills_policy

        plan["model_mcp"] = dict(MODEL_MCP_POLICY)
        plan["documentation"] = dict(DOCUMENTATION_POLICY)
        plan["skills"] = skills_policy()
    if official:
        prepared = project / "artifacts/official-prepared-manifest.json"
        statement = project / "artifacts/official-2023-statement.txt"
        shared = OFFICIAL_SHARED_ROOT
        plan["preparation_manifest"] = {"path": shared + "/prepared/prepared-manifest.json",
                                        "sha256": file_digest(prepared)}
        plan["statement"] = {"path": shared + "/statements/2023.txt", "sha256": file_digest(statement)}
    if contract:
        validate_depth_plan(plan)
    atomic_json(destination / "plan.json", plan)
    files = []
    for relative in ("src", "tests", "tools", "examples/marathon22" if official else "examples/matmul"):
        files.extend(path for path in (project / relative).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts)
    files.extend(project / name for name in ("pyproject.toml", "AGENTS.md", "README.md"))
    manifest = {path.relative_to(project).as_posix(): file_digest(path)
                for path in sorted(files)}
    atomic_json(destination / "runtime-manifest.json", manifest)
    payload = destination / "payload.tar.gz"
    with tarfile.open(payload, "w:gz") as archive:
        for path in sorted(files):
            archive.add(path, arcname="project/" + path.relative_to(project).as_posix())
        for name in ("plan.json", "runtime-manifest.json"):
            archive.add(destination / name, arcname=name)
    remote_payload = remote_root + ".tar.gz"
    receipt = {"scope": scope, "model": MODEL, "effort": EFFORT,
               "session_id": session, "expires_at": time.time() + (
                   args.wall_seconds + 3600 if args.depth_comparison or adaptive else 3600),
               "historical_campaign_resumption": False,
               "user_request": ("Comparer binaire et AB-MCTS avec Luna MAX, profondeur sans limite ; "
                                "terminer les missions admises puis Mother et G hors timer, "
                                "sans aucun plafond applicatif de tokens") if args.depth_comparison or adaptive else
                               "Tester Luna MAX sur un des sujets officiels precedemment etudies" if official
                               else "Un exemple synthetique distinct et explicitement selectionne",
               "plan": {"path": str(destination / "plan.json"),
                        "sha256": file_digest(destination / "plan.json")},
               "payload": {"path": str(payload), "sha256": file_digest(payload)},
               "remote_payload": remote_payload, "channel": None}
    if contract:
        receipt["completion"] = contract["completion"]
    if args.mother_trees:
        receipt["user_request"] = "Mother choisit N arbres AB-MCTS selon le sujet et le code ; tous les N arbres " \
            "travaillent en parallele, sans plafond de tokens ; Mother reprend la meme conversation pour assembler " \
            "G sans pouvoir relancer les arbres ; confirmation de G final obligatoire ; " \
            "Mother et les enfants ont acces au MCP-ROMEO et au profil local existants ; " \
            "references officielles NVIDIA, OpenMP, MPI, SIMD et compilateurs disponibles pendant toute la campagne ; " \
            "six skills generiques charges selon le role et la phase, avec traces de chargement et d'utilisation"
    atomic_json(destination / "authorization-pending.json", receipt)
    print(json.dumps({"destination": str(destination), "remote_root": remote_root,
                      "remote_payload": remote_payload, "sha256": file_digest(payload)}))


if __name__ == "__main__":
    main()
