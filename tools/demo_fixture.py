"""Synthetic presentation data, never a campaign, evaluation or benchmark result."""
from __future__ import annotations


def presentation_data() -> dict:
    trees = []
    specifications = [
        ("T1", "Vectorisation", [(.14, None), (.09, 0), (.072, 0), (.06, 1)]),
        ("T2", "Localité mémoire", [(.15, None), (.11, 0), (False, 0), (.08, 1)]),
        ("T3", "Réduction des calculs", [(.13, None), (.095, 0), (None, 0), (.07, 1)]),
    ]
    for role, subject, entries in specifications:
        nodes = []
        for index, (seconds, parent) in enumerate(entries):
            correct = None if seconds is None else seconds is not False
            nodes.append({
                "id": f"{role}-{index + 1:02}", "trial_id": f"{role}-{index + 1:02}",
                "role": role, "parent": f"{role}-{parent + 1:02}" if parent is not None else None,
                "delegation_parent": f"Mother/{role}", "sources": [],
                "state": "infrastructure_error" if correct is None else "valid" if correct else "incorrect",
                "correct": correct, "seconds": seconds if correct else None,
                "score": .18 / seconds if correct else 0 if correct is False else None,
            })
        trees.append({"id": role, "subject": subject, "nodes": nodes,
                      "correct_count": sum(node["correct"] is True for node in nodes)})
    integration = {"id": "G-01", "role": "G", "state": "valid", "correct": True,
                   "seconds": .045, "score": 4, "parent": None,
                   "sources": ["T1-04", "T2-04"], "base_source_id": "T1-04"}
    campaign = {
        "id": "presentation", "name": "Produit scalaire · démonstration", "state": "confirmed",
        "kind": "campaign", "started": 1793178000, "host": "ROMEO · exemple",
        "machine": "x86_64", "compiler": "GCC 14.2.0", "target": "cpu",
        "model": "GPT-6 Luna", "effort": "max", "trial_count": 13,
        "trees": trees, "integrations": [integration], "truncated": False,
        "reference_seconds": .18, "seconds": .045, "speedup": 4,
        "best_confirmed": {"mean_seconds": .045, "reference_seconds": .18, "is_baseline": False},
        "confirmation_repetitions": 5, "protocol_id": "synthetic-presentation-only",
        "final_g_status": "confirmed", "search_stop_reason": "budget_exhausted",
        "downloads": {"code": True, "report": True, "csv": True},
        "analyses": [{"role": role, "summary": "Exemple de bilan synthétique."}
                     for role, _, _ in specifications],
        "decisions": [{"action": "integration", "sources": ["T1-04", "T2-04"]}],
        "events": [], "closure_history": [],
        "search_diagnostics": {
            "policy": "AB-MCTS-A · gaussien", "trees": [
                {"root_trials": 1, "refinements": 3, "max_depth": 3} for _ in trees],
            "models": [{"model": "gpt-6-luna", "effort": "max", "admitted": 12,
                        "correct": 10, "unscored": 1, "best_seconds": .06}],
        },
    }
    trial = {**trees[0]["nodes"][-1], "phase": "search", "files": ["src/kernel.cpp"],
             "times": [.059, .061, .06, .06, .06], "commit": "demo-only",
             "generator": {"model": "gpt-6-luna", "reasoning_effort": "max"},
             "reason": "Scénario illustratif : vérification de la sortie et de la tolérance numérique.",
             "hypothesis": "Exemple : permettre la vectorisation de la réduction.",
             "evaluations": [{"phase": "correctness", "status": "passed",
                              "note": "Données synthétiques, aucune commande exécutée."}]}
    source = {
        "path": "src/kernel.cpp", "diff_available": True, "diff_truncated": False,
        "content": "// Exemple illustratif, non évalué.\n"
                   "double dot(const double* a, const double* b, int n) {\n"
                   "    double sum = 0.0;\n"
                   "    #pragma omp simd reduction(+:sum)\n"
                   "    for (int i = 0; i < n; ++i)\n"
                   "        sum += a[i] * b[i];\n"
                   "    return sum;\n}\n",
        "diff": "--- référence/src/kernel.cpp\n+++ variante/src/kernel.cpp\n"
                "@@ -1,6 +1,7 @@\n"
                " double dot(const double* a, const double* b, int n) {\n"
                "     double sum = 0.0;\n"
                "+    #pragma omp simd reduction(+:sum)\n"
                "     for (int i = 0; i < n; ++i)\n"
                "         sum += a[i] * b[i];\n"
                "     return sum;\n }\n",
    }
    return {
        "/api/info": {"version": "0.2.0", "models": [], "connection": {},
                      "submission_enabled": False, "limits": {"file_count": 2000,
                                                              "upload_bytes": 67108864}},
        "/api/projects": [], "/api/campaigns": [campaign],
        "/api/campaigns/presentation": campaign,
        "/api/campaigns/presentation/trials/T1-04": trial,
        "/api/campaigns/presentation/trials/T1-04/source": source,
    }
