# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `b8d9b4964509eeef2d5738c1d85e692139872f28afd57142edeff7658e39051c`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 58, "tokens_used": 3733289, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3733289}`.
Coûts par phase : `{"search": {"slots": 50, "tokens_used": 2474136, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2474136}, "postprocess": {"slots": 5, "tokens_used": 1259153, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1259153}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "b1d2d2a69b6e485b", "outcome": {"binary_sha256": "7ff505d7246903aea046f50689955e724f8b46b948d5be7f92544d7362a017fe", "cache_key": "9fcc2573f7ce3dd822b7ab9eb313e919e7e1ad31c33742401d4cfe28e37ebf73", "commit": "2b630ac148c1d5551967c4342f49e6fc19f0fca6", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r2-5b84685714da/forest-app-16ecfe69803640b2bbbad102d62b76f9/campaign/logs/e1/b1d2d2a69b6e485b/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r2-5b84685714da/forest-app-16ecfe69803640b2bbbad102d62b76f9/campaign/logs/e1/b1d2d2a69b6e485b/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r2-5b84685714da/forest-app-16ecfe69803640b2bbbad102d62b76f9/campaign/logs/e1/b1d2d2a69b6e485b/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r2-5b84685714da/forest-app-16ecfe69803640b2bbbad102d62b76f9/campaign/logs/e1/b1d2d2a69b6e485b/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r2-5b84685714da/forest-app-16ecfe69803640b2bbbad102d62b76f9/campaign/logs/e1/b1d2d2a69b6e485b/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r2-5b84685714da/forest-app-16ecfe69803640b2bbbad102d62b76f9/campaign/logs/e1/b1d2d2a69b6e485b/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r2-5b84685714da/forest-app-16ecfe69803640b2bbbad102d62b76f9/campaign/logs/e1/b1d2d2a69b6e485b/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.064187498911579, "reason": "", "score": 0.8976807290856809, "status": "valid", "times": [0.06418579493095553, 0.06417583736730989, 0.0641634594257906, 0.06421642560754927, 0.0641959772262897], "tree_hash": "e701b12becfbcc7befa023da4f5304123d05b672"}, "status": "confirmed"}`.

Commit retenu après confirmation : `4ed993194257a6c344a7783aea92ffe40bf2d891`.
Temps confirmé : 0.062183 s ; référence confirmée : 0.563138 s.
Réduction mesurée : 89.0%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Thread-budgeted OpenMP decomposition and load balancing | Change only grid-level work decomposition around the existing scalar kernel. Respect threads as the maximum CPU thread budget; compare low-overhead static scheduling with appropriately chunked dynamic or guided row/tile scheduling to address uneven per-pixel iteration costs. Preserve the coordinate calculations, recurrence, and full output overwrite. Measure with one and four cores and validate shifted-bound checks. |
| T2 | Exact SIMD across independent pixels | Explore SIMD across independent adjacent pixels while leaving thread scheduling to other work. Preserve per-pixel float operation order, escape-test timing, and exact iteration counts; handle inactive and tail lanes without changing results. Use only ISA/compiler settings available under the official build, and validate all correctness checks including shifted bounds. Compare one- and four-core performance. |
| T3 | Safe exact cycle detection for bounded orbits | Explore exact periodic-state detection only inside the scalar recurrence. Compare a low-overhead checkpoint strategy against no detector, and record failed or slower variants. Terminate with maxIterations only when the full bit patterns of both float state components repeat at the loop top after the original escape check has established that the current state does not escape. Preserve the recurrence operations, escape-test timing, and count semantics; do not use approximate equality or analytic membership shortcuts. Validate shifted bounds and compare one- and four-core timings. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| bdf0a89941d34127 | T1 | search | valid | 0.304865 | e2f0c4114b14 |
| 2ae99b2bcfc74b4f | T2 | search | incorrect | — | 8cee3107715a |
| 017b3b3e09654dba | T3 | search | valid | 0.337140 | a7a40da7ee09 |
| ed5fb34c3ecb43a4 | T1 | search | valid | 0.364001 | 925cc2a5cc3e |
| 13ed80a50f5b4a27 | T3 | search | valid | 0.422137 | cf61d9515050 |
| 386650849007446b | T1 | search | valid | 0.282140 | 5750e825f1c5 |
| 65bd06a1694d4e17 | T3 | search | valid | 0.275182 | cdc62b615a63 |
| 8044ea2f70f44e56 | T1 | search | valid | 0.305114 | 3dd0ec3a2e66 |
| 894dff01b8ec4b8f | T3 | search | valid | 0.238444 | 3ad783b0f060 |
| 26e2870477c449cb | T1 | search | valid | 0.282259 | 9838dd2d6b82 |
| 99cc05357231421b | T3 | search | valid | 0.219563 | e5070ccdc2ad |
| 7af432964cf648ca | T1 | search | valid | 0.282246 | e192007a08c7 |
| c14f582536984293 | Gm1 | search | valid | 0.119441 | 17918c00def5 |
| 7af0a95e7f2748c9 | T2 | search | valid | 0.193363 | fc4db4464131 |
| 964aeef46dc34d29 | T3 | search | valid | 0.209619 | 142752ced42d |
| 4ab726abe89e4e67 | T1 | search | valid | 0.282789 | ed5e9897370d |
| 0eb0de716d89447b | T3 | search | valid | 0.322076 | 08036fa84a98 |
| 8f124726685f4eb0 | Gm2 | search | valid | 0.110783 | 2cd22e47adb2 |
| 1a8312ae744b4481 | T1 | search | valid | 0.284054 | 2a906ddd81d2 |
| 17687af529c34f2e | T3 | search | valid | 0.213136 | 914d3a0f0d10 |
| ac03e4cbe2fb43d3 | T1 | search | valid | 0.282215 | 5bc5519c6538 |
| 5fc2d95c38794f9d | T3 | search | valid | 0.204896 | e015ffd4ab19 |
| 05f5b1b197794235 | Gm3 | search | valid | 0.062162 | 4ed993194257 |
| 9994c24d3a004c08 | T3 | search | valid | 0.220979 | 8c8eb1b755d4 |
| 2f42ea7d06284529 | G | postprocess | valid | 0.074786 | 6a7e18894002 |
| b1d2d2a69b6e485b | G | postprocess | valid | 0.064159 | 2b630ac148c1 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
