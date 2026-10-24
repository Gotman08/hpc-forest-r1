# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `fc2c46859783d64748999309381d3a53911500175caeec8d8dd5042b6c6b8c46`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 60, "tokens_used": 3764602, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3764602}`.
Coûts par phase : `{"search": {"slots": 47, "tokens_used": 2053347, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2053347}, "postprocess": {"slots": 10, "tokens_used": 1711255, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1711255}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "3e3be5d00ee74f6f", "outcome": {"binary_sha256": "aa16fd3a500c094f1f904eb59f77e4f4bbc1295844b34f2bc5a279700b638d18", "cache_key": "1f063268d52a8098634be2965a0145b7682aa089912732c98f3fe7846b1d44ab", "commit": "ba3752c6a9af266035f544a766c9fa43ad91a0ee", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-stencil3d_retry1-ee3486276ded474fbd843e027019ebce/results-783172/reference-stencil3d/logs/e1/3e3be5d00ee74f6f/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-stencil3d_retry1-ee3486276ded474fbd843e027019ebce/results-783172/reference-stencil3d/logs/e1/3e3be5d00ee74f6f/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-stencil3d_retry1-ee3486276ded474fbd843e027019ebce/results-783172/reference-stencil3d/logs/e1/3e3be5d00ee74f6f/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-stencil3d_retry1-ee3486276ded474fbd843e027019ebce/results-783172/reference-stencil3d/logs/e1/3e3be5d00ee74f6f/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-stencil3d_retry1-ee3486276ded474fbd843e027019ebce/results-783172/reference-stencil3d/logs/e1/3e3be5d00ee74f6f/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-stencil3d_retry1-ee3486276ded474fbd843e027019ebce/results-783172/reference-stencil3d/logs/e1/3e3be5d00ee74f6f/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-stencil3d_retry1-ee3486276ded474fbd843e027019ebce/results-783172/reference-stencil3d/logs/e1/3e3be5d00ee74f6f/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.05401875637146966, "reason": "", "score": 0.8954270541886685, "status": "valid", "times": [0.05502880584309401, 0.05263886583665264, 0.05334702516266847, 0.0546189409977332, 0.05446014401719997], "tree_hash": "636de927d2ce6080cfc1efe21bb8d726656e761a"}, "status": "confirmed"}`.

Commit retenu après confirmation : `ba3752c6a9af266035f544a766c9fa43ad91a0ee`.
Temps confirmé : 0.054019 s ; référence confirmée : 0.462547 s.
Réduction mesurée : 88.3%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Compare per-step and persistent OpenMP teams | Replace the serial sweeps with OpenMP work over disjoint rows or slabs, honoring the threads argument as a CPU budget. Compare a team created for each timestep with a persistent team spanning all six steps, measuring any fork/join savings against synchronization and buffer-parity handling. Ensure workers finish each timestep before the next reads its output. Preserve full initialization, update bounds, and boundaries. Test correctness and native wall time at one and four cores, including initialization and overhead. |
| T2 | Contrast compiler auto-vectorization and target-supported SIMD | Optimize the contiguous-x radius-3 update, contrasting a compiler-vectorizable loop with explicit SIMD only when supported by the frozen target configuration. Do not change compiler settings or assume row alignment; handle tails and generic n. Preserve the recurrence, full initialization, and boundaries, and validate the fixed tolerance. Measure both core budgets and include any setup costs. |
| T3 | Isolate temporal blocking from spatial-only cache blocking | Focus on temporal reuse across the six dependent steps. Compare a spatial-only tiled control with a halo-aware multi-step tile, holding the spatial kernel and threading strategy fixed within the comparison to isolate temporal reuse. Respect radius-three dependencies, produce both full output buffers with baseline initialization and boundaries, and include scratch allocation in timing. Avoid benchmark-size specialization; validate correctness and measure one- and four-core wall time. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 806fdef9ee5b4dc6 | T1 | search | valid | 0.241645 | 0955fad48d97 |
| 164618338efd47c5 | T2 | search | valid | 0.081288 | 9ad4e02526e0 |
| 742099d9de4a4e96 | T3 | search | valid | 0.296346 | ec0e2f1c9d33 |
| 6baf5bc15a4d4cf2 | T1 | search | valid | 0.241145 | 8620852ecc03 |
| 2d936b92faa04fe4 | T2 | search | valid | 0.449431 | 140df480885b |
| df71afd84d004711 | T1 | search | valid | 0.237933 | 3749dd3b0faf |
| c421325b10a842c0 | T3 | search | valid | 0.370022 | b37ffada5677 |
| e2786cc8e1da48a4 | T2 | search | valid | 0.082253 | 4c6fe289481f |
| 706023237bb74691 | Gm1 | search | valid | 0.054595 | 3d310fb015d0 |
| 656a1525ddcd4893 | T3 | search | valid | 0.318260 | 40974b7f8e3a |
| e2e68740f1064099 | T1 | search | valid | 0.219892 | b3244455b50c |
| d778cedbd6b24386 | T2 | search | valid | 0.461277 | 98596884b235 |
| d96afbb4e38d4370 | T2 | search | valid | 0.080044 | c4a3af2c3be2 |
| 2023bb8ffc8349d8 | T2 | search | valid | 0.079497 | 485acfa2836b |
| cfc3f5a47c6d45d4 | T4 | search | valid | 0.176740 | 31d9d90b449d |
| 469de416c9dc42cf | T2 | search | valid | 0.084099 | e5b1e1b46558 |
| f7e171e736ed48bd | Gm2 | search | valid | 0.055090 | c2a806307aa7 |
| 2def311db7e94f13 | T4 | search | valid | 0.058612 | 36090756ac08 |
| f76874959fde4159 | T4 | search | valid | 0.145017 | fcde997c5256 |
| 9415562af9d14d64 | G | postprocess | valid | 0.054370 | 25691a3ad937 |
| 3e3be5d00ee74f6f | G | postprocess | valid | 0.054208 | ba3752c6a9af |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
