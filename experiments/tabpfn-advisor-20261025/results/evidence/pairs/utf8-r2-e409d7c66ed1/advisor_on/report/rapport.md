# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `4f844a7d9110879a4a07131b5b5aad61862c8117f85e47a0d419c884b2729c6e`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 52, "tokens_used": 4246296, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 4246296}`.
Coûts par phase : `{"search": {"slots": 44, "tokens_used": 3276159, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3276159}, "postprocess": {"slots": 5, "tokens_used": 970137, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 970137}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "34f5233ef89e4c13", "outcome": {"binary_sha256": "bf59118a7ef2edbcea96cdec1cae84d2fab5f665799a9f016eef4185203c7b48", "cache_key": "d21d65683e07c559e09c44cd713c2805fce6c0a4d420ea9edec8a427f8892c67", "commit": "05248e5d3881b2e8eb289a6b59ab55c47feead77", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r2-e409d7c66ed1/forest-app-f967ef6310154844a1c835adf3d607a7/campaign/logs/e1/34f5233ef89e4c13/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r2-e409d7c66ed1/forest-app-f967ef6310154844a1c835adf3d607a7/campaign/logs/e1/34f5233ef89e4c13/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r2-e409d7c66ed1/forest-app-f967ef6310154844a1c835adf3d607a7/campaign/logs/e1/34f5233ef89e4c13/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r2-e409d7c66ed1/forest-app-f967ef6310154844a1c835adf3d607a7/campaign/logs/e1/34f5233ef89e4c13/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r2-e409d7c66ed1/forest-app-f967ef6310154844a1c835adf3d607a7/campaign/logs/e1/34f5233ef89e4c13/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r2-e409d7c66ed1/forest-app-f967ef6310154844a1c835adf3d607a7/campaign/logs/e1/34f5233ef89e4c13/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r2-e409d7c66ed1/forest-app-f967ef6310154844a1c835adf3d607a7/campaign/logs/e1/34f5233ef89e4c13/confirmation/attempt-001/sample-4.log"], "mean_seconds": 2.3925516128810733e-05, "reason": "", "score": 0.6737706528694393, "status": "valid", "times": [2.3923964314036467e-05, 2.3966742538281873e-05, 2.3919761953993263e-05, 2.390745511377846e-05, 2.3909656723963602e-05], "tree_hash": "13456fcc4a32430a5e9cbe71219f321e88aebf7b"}, "status": "confirmed"}`.

Commit retenu après confirmation : `05248e5d3881b2e8eb289a6b59ab55c47feead77`.
Temps confirmé : 0.000024 s ; référence confirmée : 0.000049 s.
Réduction mesurée : 51.6%. Référence conservée : non.

Mother a choisi **2 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | SIMD blockwise UTF-8 validation | Explore a blockwise SIMD validator that classifies UTF-8 byte roles and checks continuation structure and restricted lead/continuation pairs in masks. Use only instructions supported by the actual build and runner; process full blocks without over-reading, handle sequences crossing block boundaries, and validate the remainder safely. Preserve the run interface, output, and thread budget. Record unsuccessful variants; judge by correctness on all required input classes and repeated official mixed-width timings. |
| T2 | Scalar ASCII scanning and decoder alternatives | Explore scalar UTF-8 validation alternatives. First compare the existing byte-at-a-time ASCII scan with safe word-at-a-time high-bit tests while keeping the non-ASCII decoder fixed; then, separately, test a compact branch-reduced decoder. Use defined loads, do not over-read, and handle tails safely. Preserve exact UTF-8 validity rules, the run interface, output, and thread budget. Record unsuccessful variants and compare correctness on all required input classes and repeated official mixed-width timings; do not specialize to assumed input composition. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| bb7742a84e724c6e | T1 | search | valid | 0.000362 | 3bdeed22f4f3 |
| f5c1c74b4b614412 | T2 | search | valid | 0.000051 | 82cb6eb36617 |
| 7f3a92e655f24489 | T2 | search | valid | 0.000046 | a163ccd0bddc |
| ea0307d778864379 | T1 | search | valid | 0.000050 | 4e86a9c57dd9 |
| 5537ed4eab1e488e | T1 | search | valid | 0.000169 | 415503512ee5 |
| b7c315acae664127 | T2 | search | valid | 0.000057 | 961253d31ccd |
| 934a0254041b4eea | T1 | search | valid | 0.000025 | 7abaadb5bbfb |
| d6f87dc14e1e40a8 | T2 | search | valid | 0.000081 | 92227bb8dac2 |
| 926f8bbd7a5642ad | T1 | search | valid | 0.000025 | ffa403670773 |
| ca0e81cad5ba48aa | T1 | search | infrastructure_error | — |  |
| 34f5233ef89e4c13 | G | postprocess | valid | 0.000024 | 05248e5d3881 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
