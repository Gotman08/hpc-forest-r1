# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `92fb1e67da2eeadc8cf8124859d6522413dcc2f2368204fd861bf25dddee7bf6`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 50, "tokens_used": 2870631, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2870631}`.
Coûts par phase : `{"search": {"slots": 43, "tokens_used": 2336321, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2336321}, "postprocess": {"slots": 4, "tokens_used": 534310, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 534310}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "bcdbfadc42844d72", "outcome": {"binary_sha256": "9db0d014d8cffbcf90f7108e3c605518e6e1ba0e0b76832b3753cb86455dfd20", "cache_key": "bce5af6fbe1284da92d41de6d42af9a2d3c2234e677b0c4a577ab246661dd1df", "commit": "cd8944984e66ace2ec3415afe0605e5811ca2480", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r1-6455d1b842aa/forest-app-706937614c3f4d3e8f0b25168961eac7/campaign/logs/e1/bcdbfadc42844d72/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r1-6455d1b842aa/forest-app-706937614c3f4d3e8f0b25168961eac7/campaign/logs/e1/bcdbfadc42844d72/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r1-6455d1b842aa/forest-app-706937614c3f4d3e8f0b25168961eac7/campaign/logs/e1/bcdbfadc42844d72/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r1-6455d1b842aa/forest-app-706937614c3f4d3e8f0b25168961eac7/campaign/logs/e1/bcdbfadc42844d72/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r1-6455d1b842aa/forest-app-706937614c3f4d3e8f0b25168961eac7/campaign/logs/e1/bcdbfadc42844d72/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r1-6455d1b842aa/forest-app-706937614c3f4d3e8f0b25168961eac7/campaign/logs/e1/bcdbfadc42844d72/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-mandelbrot-r1-6455d1b842aa/forest-app-706937614c3f4d3e8f0b25168961eac7/campaign/logs/e1/bcdbfadc42844d72/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.079794453075262, "reason": "", "score": 0.8759863649252523, "status": "valid", "times": [0.07973080382794945, 0.07977607220495539, 0.07973877186394375, 0.07982136568829827, 0.07990525179116319], "tree_hash": "97acdc36b17d888f897e86cc873816e3cd604595"}, "status": "confirmed"}`.

Commit retenu après confirmation : `fc8b065a8d13f95d64aa92ac3bc3ce0c28f003e3`.
Temps confirmé : 0.079766 s ; référence confirmée : 0.563638 s.
Réduction mesurée : 85.8%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | OpenMP scheduling and load balancing | Compare contiguous static row scheduling with guided or dynamic scheduling over smaller row chunks to test whether balancing uneven pixel iteration work offsets dispatch overhead. Parallelize only the existing pixel computation, write each output exactly once, and honor `threads` as an upper bound; avoid parallel-region overhead for the one-thread case. Validate full outputs and compare the official one- and four-core measurements. |
| T2 | Exact SIMD strategy and lane control | Contrast compiler-generated SIMD over independent pixels with an explicit masked x86 SIMD path if the supplied build and target support it, retaining a scalar fallback. Do not assume a vector width or ISA enablement. Preserve baseline coordinate expressions, check-before-update semantics, per-lane iteration counts, and the scalar-equivalent float operation sequence; avoid reassociation or fused operations that can change counts, and handle tails correctly. Validate full outputs and measure one- and four-core performance. |
| T3 | Scalar interleaving for instruction-level parallelism | On the scalar path, compare the baseline pixel-at-a-time recurrence with a small group of independent scalar pixel states interleaved to test whether it hides recurrence latency. Do not add OpenMP or explicit SIMD intrinsics in this tree. Preserve each pixel’s coordinate expressions, recurrence, bailout order, and result exactly. Validate full outputs and measure under both official core settings; distinguish this scalar experiment from deliberate SIMD vectorization. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| acce4ca2530c4b27 | T1 | search | valid | 0.282306 | cc2b899d2e6d |
| 3e6c4aa7068747cc | T2 | search | build_failed | — | cbff7bb0dea7 |
| c69aaa09d0234b3e | T3 | search | valid | 0.207967 | f678cfa6f582 |
| e3dac6a581c2435b | T1 | search | valid | 0.305078 | c600558b7903 |
| 386ac985022744ee | T3 | search | valid | 0.172293 | d24ab24d2a04 |
| a92282fb40ed4d27 | Gm1 | search | valid | 0.104082 | cd9b90dbed5c |
| e5bb751d864d412d | T1 | search | valid | 0.362871 | df8a266a4b77 |
| 4213fa0d7d634ac3 | T2 | search | build_failed | — | d9baf7872fcb |
| e150c575fa584dfa | T3 | search | valid | 0.290243 | 6a7b0a681c1c |
| 039928e5fc494bf6 | T1 | search | valid | 0.305126 | a6b3f1070555 |
| f5023da3fb794a02 | T3 | search | valid | 0.154912 | 6822924d873c |
| 901b1c918b6a4223 | T1 | search | valid | 0.282187 | 89c208b4e4fc |
| 55e65e37e4a048c4 | Gm2 | search | valid | 0.085684 | 49cd0eff0b41 |
| b72b89738dd84313 | T3 | search | valid | 0.328496 | d97250634416 |
| 6eb2b95f024d41f3 | T2 | search | build_failed | — | f4aa429003c5 |
| cb8edf593ca543d4 | Gm3 | search | valid | 0.079760 | fc8b065a8d13 |
| 9a7119ea5ea8407b | T3 | search | valid | 0.154949 | 2e2abcef009e |
| 0346df3b8c1142fd | T3 | search | valid | 0.159810 | 0638e3b80018 |
| bcdbfadc42844d72 | G | postprocess | valid | 0.079724 | cd8944984e66 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
