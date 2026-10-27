# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `f91e453dd8f1af33112f0febd512666c2249763378c2ed5c03d33ce85560747f`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 46, "tokens_used": 2105024, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2105024}`.
Coûts par phase : `{"search": {"slots": 38, "tokens_used": 1447003, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1447003}, "postprocess": {"slots": 5, "tokens_used": 658021, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 658021}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "7d77b8896d4f4d01", "outcome": {"binary_sha256": "f745efe95782741888dea78334906d219ab66e5618e42ac018cfe122ffdc4702", "cache_key": "629e51dc712b412c498956af0c512f330657551ffebcc4e5f72ecb3d8f74d8f8", "commit": "31330f7710fee507eff69f993e5840d13196be96", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r1-6455d1b842aa/forest-app-9a4b37a0ed2e4ade82584fec40e1a4ae/campaign/logs/e1/7d77b8896d4f4d01/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r1-6455d1b842aa/forest-app-9a4b37a0ed2e4ade82584fec40e1a4ae/campaign/logs/e1/7d77b8896d4f4d01/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r1-6455d1b842aa/forest-app-9a4b37a0ed2e4ade82584fec40e1a4ae/campaign/logs/e1/7d77b8896d4f4d01/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r1-6455d1b842aa/forest-app-9a4b37a0ed2e4ade82584fec40e1a4ae/campaign/logs/e1/7d77b8896d4f4d01/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r1-6455d1b842aa/forest-app-9a4b37a0ed2e4ade82584fec40e1a4ae/campaign/logs/e1/7d77b8896d4f4d01/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r1-6455d1b842aa/forest-app-9a4b37a0ed2e4ade82584fec40e1a4ae/campaign/logs/e1/7d77b8896d4f4d01/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r1-6455d1b842aa/forest-app-9a4b37a0ed2e4ade82584fec40e1a4ae/campaign/logs/e1/7d77b8896d4f4d01/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.14624736666986302, "reason": "", "score": 0.7938819775665018, "status": "valid", "times": [0.14625747340994402, 0.14620336878822993, 0.1462541196011171, 0.14621834702847197, 0.14630352452155213], "tree_hash": "62180b8a0876f5673840e8ccad5d7586e1dee4d1"}, "status": "confirmed"}`.

Commit retenu après confirmation : `31330f7710fee507eff69f993e5840d13196be96`.
Temps confirmé : 0.146247 s ; référence confirmée : 0.563285 s.
Réduction mesurée : 74.0%. Référence conservée : non.

Mother a choisi **2 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Scalar OpenMP row scheduling | Explore OpenMP parallelization of the existing scalar row traversal, respecting threads as the CPU-thread budget. Compare sensible row scheduling/chunk choices for uneven escape workloads while leaving the coordinate expressions and mandel recurrence unchanged. Validate exact output, including shifted bounds, and compare one- and four-thread wall time against the baseline; retain scheduling overhead or regressions as failed attempts. |
| T2 | Exact SIMD pixel kernel | Explore exact SIMD across adjacent x pixels, comparing compiler-generated vectorization with explicit independently masked lanes where supported by the actual target and toolchain. Preserve the supplied coordinate calculation and float recurrence, including the starting z and pre-update escape test; any shortcut must be proven to return the same count as that recurrence for all valid inputs, with no approximation. Handle tails and shifted bounds without specializing to benchmark values. First isolate the kernel with one thread; then, if useful, measure it with a simple fixed static OpenMP row wrapper at one and four threads, leaving schedule tuning to T1. Validate exact outputs and report wall time against the baseline. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 87c1c044e2a14c16 | T1 | search | valid | 0.282140 | 1b930b7d244f |
| 428b92611784469c | T2 | search | valid | 0.742209 | a3016b438da6 |
| 35fed434fcab4819 | T2 | search | valid | 0.564296 | 1095aca57581 |
| 307451417dbe457b | T1 | search | valid | 0.305150 | f2ef43b70bcf |
| c82356c670984514 | T1 | search | valid | 0.364016 | 9b516a911f34 |
| 69284a57402849b1 | T2 | search | valid | 0.563277 | 25da6e4d52e2 |
| 30b7fb3e9c0c40bb | T1 | search | valid | 0.282144 | 63d7864b1587 |
| 848de313dc294ba0 | T2 | search | valid | 0.362200 | 150ff6555058 |
| 5745a366f9e64f85 | Gm1 | search | valid | 0.282418 | 23e09e7274eb |
| 710879e2c0e049f8 | T1 | search | valid | 0.284244 | 8fbf729afbbe |
| a5416b4b2dd84e51 | T2 | search | valid | 0.479676 | 3dab680c151e |
| e792442d65ab4ebc | T1 | search | valid | 0.282336 | c94a240c0456 |
| a6a39e4f885b4e8c | T1 | search | valid | 0.305188 | 777c55aa361f |
| 8c0dff02c3c84ab2 | T2 | search | valid | 0.186884 | 038f5b6dfd00 |
| 1b9a12e5f8a04509 | T1 | search | valid | 0.282358 | 1a7c0c47c1e8 |
| 812dfa3cf7754dea | T1 | search | valid | 0.282558 | 5005a26c9d57 |
| 5b180c6f78a74fe1 | T2 | search | valid | 0.362590 | a015447c4318 |
| 236b41b44dd84420 | T1 | search | valid | 0.282036 | 56f5439b4e20 |
| a4a24f8a75ea4bb7 | T2 | search | valid | 0.191767 | 655da47a00b9 |
| d7838956713b4f52 | T1 | search | valid | 0.282136 | 97c9a5e5bfb8 |
| a781e52cb6074a20 | T1 | search | valid | 0.283545 | cfc5c439186b |
| 7d77b8896d4f4d01 | G | postprocess | valid | 0.146336 | 31330f7710fe |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
