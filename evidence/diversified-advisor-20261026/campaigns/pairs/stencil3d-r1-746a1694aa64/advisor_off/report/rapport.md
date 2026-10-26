# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `3d96166e3d0c8107daa3f4b81f2b150be78238ea678ad10c0eb2296511a4e1c6`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 87, "tokens_used": 6927906, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 6927906}`.
Coûts par phase : `{"search": {"slots": 72, "tokens_used": 5090282, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 5090282}, "postprocess": {"slots": 11, "tokens_used": 1837624, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1837624}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "6ff1521e48bc4add", "outcome": {"binary_sha256": "d3086b0aef108b62b4e450c0fbd35ef8fbd5a7ac98a02ed30ead7c992d7ec6ae", "cache_key": "0df27120eb848cf547a248f0262a6759ab2a610ca833260b2d088943ad10e0f5", "commit": "2aceae600e388dc540d87dd295ea04a215762f52", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-stencil3d-r1-746a1694aa64/forest-app-01d4a0c1fdd54634a6506bf9d65aee28/campaign/logs/e1/6ff1521e48bc4add/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-stencil3d-r1-746a1694aa64/forest-app-01d4a0c1fdd54634a6506bf9d65aee28/campaign/logs/e1/6ff1521e48bc4add/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-stencil3d-r1-746a1694aa64/forest-app-01d4a0c1fdd54634a6506bf9d65aee28/campaign/logs/e1/6ff1521e48bc4add/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-stencil3d-r1-746a1694aa64/forest-app-01d4a0c1fdd54634a6506bf9d65aee28/campaign/logs/e1/6ff1521e48bc4add/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-stencil3d-r1-746a1694aa64/forest-app-01d4a0c1fdd54634a6506bf9d65aee28/campaign/logs/e1/6ff1521e48bc4add/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-stencil3d-r1-746a1694aa64/forest-app-01d4a0c1fdd54634a6506bf9d65aee28/campaign/logs/e1/6ff1521e48bc4add/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-stencil3d-r1-746a1694aa64/forest-app-01d4a0c1fdd54634a6506bf9d65aee28/campaign/logs/e1/6ff1521e48bc4add/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.004734278291316141, "reason": "", "score": 0.8949956142440397, "status": "valid", "times": [0.004671763451210668, 0.004552179852774696, 0.004706650275147748, 0.00510247742955544, 0.004638320447892155], "tree_hash": "d78bb6ab643102a6e8b05d0d998329279bf2fe74"}, "status": "confirmed"}`.

Commit retenu après confirmation : `5294f818c201baa08388d41ba7d5f09906703974`.
Temps confirmé : 0.004578 s ; référence confirmée : 0.040352 s.
Réduction mesurée : 88.7%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | OpenMP worksharing and persistent stencil-step region | Isolate the benefit of CPU worksharing across stencil rows or planes, using the run-time threads argument as the thread budget. Consider a persistent OpenMP parallel region around the six steps to avoid repeated team-startup overhead, while retaining the required global synchronization between steps and even/odd buffer semantics. Include initialization only if measurements justify it. Validate and compare repeated results at both sizes and both thread budgets; do not combine this track with temporal fusion or a new SIMD kernel. |
| T2 | GCC SIMD effectiveness in the single-step x kernel | Using the existing compiler configuration, first determine whether GCC already vectorizes the contiguous-x loop, then compare compiler-directed vectorization with an explicit SIMD implementation if appropriate. Handle all interior bounds and tails for every valid size, preserve results within tolerance, and do not change compiler options or restructure threading or timesteps. Compare correctness and repeated timings at every official size/thread combination. |
| T3 | Temporal blocking with complete two-buffer output preservation | Investigate spatial tiling across the six timesteps to reuse intermediate values and reduce full-volume traffic. Account for radius-three dependencies at each step, alternating buffers, and the initialized values of fixed boundary regions. The complete output must still contain both specified buffers with the correct final interior values and preserved boundaries; scratch-allocation cost is timed. Support every valid input size and compare correctness and repeated timings at every official size/thread combination. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| a40c0666023e4efa | T1 | search | valid | 0.021081 | 35e03e66fab6 |
| ab9091c5530d4cf9 | T2 | search | valid | 0.007884 | 4810f13c4a93 |
| e55ad926c2ef45d1 | T3 | search | valid | 0.105247 | ca50a52cb224 |
| 547333bad6184e3e | T1 | search | valid | 0.019140 | 3062d4ccabbe |
| d60bf2c21320476d | Gm1 | search | valid | 0.004556 | 1bbc2acc4186 |
| 4899d3a5ed63477c | T2 | search | valid | 0.011032 | 28d045b19ec6 |
| a1d77ec5650c47ee | Gm2 | search | valid | 0.004608 | 9a5f2f352e54 |
| 745c5ee4d8d94fb0 | T3 | search | valid | 0.045387 | b6749df8f73a |
| 6799124ccf994f49 | T1 | search | valid | 0.020465 | 86f0174fc25e |
| 6909d51205674125 | T2 | search | valid | 0.007770 | ba1400cbc0da |
| c353eaf2683140b7 | T3 | search | valid | 0.031890 | 4cf0abbdd8de |
| 704e67ab616c43f5 | T2 | search | valid | 0.008019 | d42c2e47f4e1 |
| 6fced5bdc14b4c63 | T1 | search | valid | 0.021016 | 3e4c6f59d7d7 |
| 7a5ad93268be4b03 | T3 | search | valid | 0.032831 | 1f8393317079 |
| 204c9f669bb94468 | T2 | search | valid | 0.007636 | 859cc210934a |
| e2cbccb527de4f97 | T1 | search | valid | 0.022580 | d5d1c1f67714 |
| cb9e6f5bce2c4143 | T3 | search | valid | 0.012781 | bd685c90271d |
| 52a42869f19242e8 | T2 | search | valid | 0.008314 | bfbbdede9cbd |
| 78b67360ae3946d5 | T2 | search | valid | 0.007708 | 1cfb57e60953 |
| 3f76eb33bc504f24 | T3 | search | valid | 0.010991 | 8ba205b297be |
| 47f24cbee9ba4718 | T3 | search | valid | 0.012200 | 51fb22684b2e |
| de1b72940a5b4c5c | T3 | search | valid | 0.010494 | 9da3e09e405a |
| e9caa0a9e8ec4433 | T3 | search | valid | 0.046248 | fce79dd4147f |
| 56963a09a8d04d36 | T3 | search | valid | 0.010577 | 082690e3efe4 |
| 334485658c4b4024 | G | postprocess | valid | 0.006401 | 6a8ad3c062dc |
| c10a71b6d4814a46 | G | postprocess | valid | 0.004548 | 5294f818c201 |
| 6ff1521e48bc4add | G | postprocess | valid | 0.004888 | 2aceae600e38 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
