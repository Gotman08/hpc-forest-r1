# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `36020d0d1976f15f5285db0d9490b8e5a4f3a3ae6de866c863cd3494ba11fab4`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 56, "tokens_used": 3696035, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3696035}`.
Coûts par phase : `{"search": {"slots": 44, "tokens_used": 2529335, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2529335}, "postprocess": {"slots": 8, "tokens_used": 1166700, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1166700}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "dc216c72cbaf464a", "outcome": {"binary_sha256": "a656e490902e795b613607ad4b5fab9fc3723c5b313e1b6cd5a96937bbb5897a", "cache_key": "b53c5c4abc6e3f78f9f241344f97e5ec45f0616f66ed4be5aeeb502b95827cb0", "commit": "26a5948840cbf14309c9958bcbbd52c3de379c62", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r2-5b84685714da/forest-app-3dd49c6339b048ca8bced88cbde62d47/campaign/logs/e1/dc216c72cbaf464a/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r2-5b84685714da/forest-app-3dd49c6339b048ca8bced88cbde62d47/campaign/logs/e1/dc216c72cbaf464a/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r2-5b84685714da/forest-app-3dd49c6339b048ca8bced88cbde62d47/campaign/logs/e1/dc216c72cbaf464a/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r2-5b84685714da/forest-app-3dd49c6339b048ca8bced88cbde62d47/campaign/logs/e1/dc216c72cbaf464a/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r2-5b84685714da/forest-app-3dd49c6339b048ca8bced88cbde62d47/campaign/logs/e1/dc216c72cbaf464a/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r2-5b84685714da/forest-app-3dd49c6339b048ca8bced88cbde62d47/campaign/logs/e1/dc216c72cbaf464a/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r2-5b84685714da/forest-app-3dd49c6339b048ca8bced88cbde62d47/campaign/logs/e1/dc216c72cbaf464a/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.04123028249290252, "reason": "", "score": 0.9318460255458367, "status": "valid", "times": [0.0410978599738577, 0.04125530382292741, 0.04129897767562369, 0.041258605331907915, 0.04124066566019587], "tree_hash": "82fa71c258c69bee20af8c3aae090667f540f063"}, "status": "confirmed"}`.

Commit retenu après confirmation : `13c7c84a2e50694f4811fa9ffe27171e2009e064`.
Temps confirmé : 0.038253 s ; référence confirmée : 0.563728 s.
Réduction mesurée : 93.2%. Référence conservée : non.

Mother a choisi **2 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Exact OpenMP parallelization and row-load balance | Keep the scalar Mandelbrot kernel and coordinate calculation unchanged; isolate OpenMP parallelism. Compare contiguous static row blocks against dynamic or guided row chunks to test the trade-off between low scheduling overhead and uneven per-row iteration work. Use no more workers than `threads`, overwrite every specified output, and preserve the exact bailout and recurrence. Measure with requested thread budgets of one and four using compatible inputs and protocol; report correctness and wall time for each schedule so the scaling and load-balance effect are distinguishable. |
| T2 | Exact SIMD evaluation across pixels | Isolate the SIMD pixel kernel from OpenMP so its effect can be measured separately and later considered for integration with T1. Preserve independent lane exit counts, the pre-update `> 4.f` test, and the full output overwrite. Do not assume source-level expression order guarantees oracle-equivalent floating-point behavior: validate iteration counts against the supplied correctness checks, including shifted bounds and escape-boundary cases, with the actual compiler/build target. Use only instructions supported by that target and retain a correct scalar fallback; do not change compiler flags. Measure at both requested thread budgets, explicitly recording that this isolated kernel uses at most one worker, and compare against the scalar kernel under compatible conditions. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| b7b459a879314f39 | T1 | search | valid | 0.282081 | be0e0b9399ee |
| a3562c5547fd47d0 | T2 | search | valid | 0.144199 | 07db90e114fd |
| 7301f047fdc34fe7 | T1 | search | valid | 0.364102 | 730aacb45629 |
| 4ab6d041fa4f455b | T2 | search | valid | 0.147223 | 2cda62c3e5b1 |
| 68b24cdd92af4918 | Gm1 | search | valid | 0.072592 | 9caa6888f1b6 |
| fef8a8ca6f1e4f74 | T1 | search | valid | 0.304907 | 29ed83e1f7c5 |
| 441598b572a644bc | T2 | search | valid | 0.076655 | 067e4fb5f3a0 |
| 7969febcd72841bb | T1 | search | valid | 0.282128 | 919804d077f4 |
| 1ba86cf767f24f15 | T1 | search | valid | 0.304818 | a533948a6b92 |
| 6d6b1893c6114dc6 | T2 | search | valid | 0.068414 | dc53cfd6447a |
| ed1cb178ca944bdf | T1 | search | valid | 0.282050 | 4168b3ec5dba |
| 6f909059688c4f31 | Gm2 | search | valid | 0.038277 | 13c7c84a2e50 |
| fa336bada37343db | T2 | search | valid | 0.149424 | 7cb2810a97cc |
| ed26018608aa4f2e | T1 | search | valid | 0.284432 | c50456ef3df4 |
| bd14f8987a9e4381 | T1 | search | valid | 0.282515 | 04a4715705ae |
| c2c5a30854da4ea8 | G | postprocess | valid | 0.039431 | c83955bb7a0d |
| dc216c72cbaf464a | G | postprocess | valid | 0.041093 | 26a5948840cb |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
