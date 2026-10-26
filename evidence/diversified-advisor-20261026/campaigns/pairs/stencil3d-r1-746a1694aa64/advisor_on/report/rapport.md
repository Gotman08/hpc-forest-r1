# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `b8e2c4019d5d6c546d0723317cca073bddf98c1c4038df8a33c09e7004e70846`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 67, "tokens_used": 4734628, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 4734628}`.
Coûts par phase : `{"search": {"slots": 55, "tokens_used": 3179877, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3179877}, "postprocess": {"slots": 8, "tokens_used": 1554751, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1554751}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "3675ae9b47364eee", "outcome": {"binary_sha256": "1f75aeb50b12233c3fb19e4245e1f7d8f25e3dc4d11497c0b94062e928cbf812", "cache_key": "8e336cfbca2a8d5ef78dd127e2ef16c057282855bf930ff0ad5e99bbc7826d6b", "commit": "980e8aaececdea220bd148bcb069a3f63954d7c2", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-stencil3d-r1-746a1694aa64/forest-app-71bbe18deddd4ce9afa23df892729c4c/campaign/logs/e1/3675ae9b47364eee/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-stencil3d-r1-746a1694aa64/forest-app-71bbe18deddd4ce9afa23df892729c4c/campaign/logs/e1/3675ae9b47364eee/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-stencil3d-r1-746a1694aa64/forest-app-71bbe18deddd4ce9afa23df892729c4c/campaign/logs/e1/3675ae9b47364eee/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-stencil3d-r1-746a1694aa64/forest-app-71bbe18deddd4ce9afa23df892729c4c/campaign/logs/e1/3675ae9b47364eee/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-stencil3d-r1-746a1694aa64/forest-app-71bbe18deddd4ce9afa23df892729c4c/campaign/logs/e1/3675ae9b47364eee/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-stencil3d-r1-746a1694aa64/forest-app-71bbe18deddd4ce9afa23df892729c4c/campaign/logs/e1/3675ae9b47364eee/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-stencil3d-r1-746a1694aa64/forest-app-71bbe18deddd4ce9afa23df892729c4c/campaign/logs/e1/3675ae9b47364eee/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.004802182020100472, "reason": "", "score": 0.8914760295631506, "status": "valid", "times": [0.0048091880762524165, 0.004984579319596831, 0.004711720848566554, 0.004752087243753813, 0.004753334612332746], "tree_hash": "6475ed58a377dd2e96521a08c4804151d869e709"}, "status": "confirmed"}`.

Commit retenu après confirmation : `bb23bd95bb48ed29eff650231ea9c49be911d4de`.
Temps confirmé : 0.004731 s ; référence confirmée : 0.039448 s.
Réduction mesurée : 88.0%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Thread-budgeted OpenMP parallelism across independent stencil points | Compare a persistent OpenMP team with per-step parallel regions, and include a serial fast path where appropriate, while honoring the threads budget. Workshare independent interior rows or slabs; retain the required barrier between time steps and correct buffer swaps. Preserve initialization and boundaries for arbitrary valid n. Measure correctness and native wall-clock time at both thread budgets, including one-thread overhead and the four-thread result. |
| T2 | Per-core SIMD/vectorization of the row-major stencil kernel | Isolate the per-core x-direction SIMD kernel: contrast compiler-autovectorized code with explicit intrinsics where useful, without adding an independent OpenMP work-sharing scheme or temporal blocking. The x start and shifted neighbor addresses need not be aligned, so do not assume alignment beyond the input contract. Handle tails and arbitrary valid n, preserve the numerical tolerance, and retain a correct implementation under the supplied thread budget. Compare correctness and timing; do not assume wider vectors or reassociation are faster or sufficiently accurate. |
| T3 | Temporal fusion and working-set reuse across stencil steps | Focus on reuse across the six time steps: compare an unfused spatially tiled control with one or more correctly fused temporal depths, so any fusion benefit is distinguishable from spatial tiling alone. Account for the radius-3 dependency halo at each fused step, the fixed active interior and unchanged inactive cells, buffer parity, arbitrary dimensions and tails, full output initialization, and scratch-allocation cost. Do not spend the objective on a separate SIMD kernel; structure a successful tile body for later combination. Measure correctness and native wall-clock time under the official protocol, and keep any useful slower intermediate as a potential integration component. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 49193a8213d44d71 | T1 | search | valid | 0.020477 | cd4d009bb7f6 |
| 4a40745231ce4669 | T2 | search | valid | 0.007967 | 17c823cdd89d |
| a8e3985369064bc1 | T3 | search | incorrect | — | 07cadbaa864c |
| 161929a325894304 | T2 | search | valid | 0.011314 | dd10676956dd |
| 7d2280cf8e794f6c | Gm1 | search | valid | 0.004521 | 1b74708d623a |
| 3665517bdd6440d7 | T1 | search | valid | 0.020758 | 66827e3e27d6 |
| e06de4db16c14d5b | T2 | search | valid | 0.007709 | 336a6e538162 |
| cacd20285fff468b | T2 | search | valid | 0.007649 | 70819f6a125b |
| 92f519a08aa042b9 | T1 | search | valid | 0.021487 | d3a20761b278 |
| c8289c88326f4438 | T2 | search | valid | 0.007845 | 8d70bc0266e4 |
| 72e4d8001ad54f38 | T3 | search | valid | 0.027366 | d5300349acfe |
| 6cb4fe4bdd464b65 | T2 | search | valid | 0.008184 | 799c4b44fbd1 |
| ef7e21ca8f1c498f | T1 | search | valid | 0.022129 | e0387d1e40e4 |
| 2bf4cda2100f42ea | T2 | search | valid | 0.009341 | 65194cb15a92 |
| 9e26010952684ddd | T1 | search | valid | 0.020730 | 6ea9105dad99 |
| f8c97e17b29e4965 | T2 | search | valid | 0.008318 | f096dcb3c912 |
| 78e6e271bf414ecd | T3 | search | valid | 0.047736 | 9318f251f51a |
| cbc8511b4276452f | T3 | search | valid | 0.063274 | fe75ccaf697d |
| e3b908b11cb64e3e | Gm2 | search | valid | 0.052386 | 4c0b7efd2166 |
| 580086457139480f | G | postprocess | valid | 0.004574 | bb23bd95bb48 |
| 3675ae9b47364eee | G | postprocess | valid | 0.004671 | 980e8aaececd |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
