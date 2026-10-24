# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `de2c9407d9de7199819c1dbf43ec89e9d88492f8943be90b0ad2f1782dc89249`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 44, "tokens_used": 3320027, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3320027}`.
Coûts par phase : `{"search": {"slots": 32, "tokens_used": 1985370, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1985370}, "postprocess": {"slots": 9, "tokens_used": 1334657, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1334657}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "ac6f92b8def44472", "outcome": {"binary_sha256": "4fd7db93fd591e3420c31ede4cc30ff07bf461b5a1f4769ffe65e5b0387d373c", "cache_key": "eb5b4807b19c227eac0e8e08463260032dc180b7d9c164c1aa71067d5624d780", "commit": "3a521a3da6db35be3a3ac0177a01e7dfe1b5f0e3", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-deferred-e7bab867f3574146b46dcbf30ea22915/results-783043/reference-deferred/logs/e1/ac6f92b8def44472/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-deferred-e7bab867f3574146b46dcbf30ea22915/results-783043/reference-deferred/logs/e1/ac6f92b8def44472/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-deferred-e7bab867f3574146b46dcbf30ea22915/results-783043/reference-deferred/logs/e1/ac6f92b8def44472/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-deferred-e7bab867f3574146b46dcbf30ea22915/results-783043/reference-deferred/logs/e1/ac6f92b8def44472/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-deferred-e7bab867f3574146b46dcbf30ea22915/results-783043/reference-deferred/logs/e1/ac6f92b8def44472/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-deferred-e7bab867f3574146b46dcbf30ea22915/results-783043/reference-deferred/logs/e1/ac6f92b8def44472/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-deferred-e7bab867f3574146b46dcbf30ea22915/results-783043/reference-deferred/logs/e1/ac6f92b8def44472/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.05284317356708677, "reason": "", "score": 0.6853322541864224, "status": "valid", "times": [0.05278118582531089, 0.05280859408095837, 0.05290446211007531, 0.05280664261801653, 0.052914983201072734], "tree_hash": "4aa05a3d7beaecb4bf27a28cf296f609518ffed4"}, "status": "confirmed"}`.

Commit retenu après confirmation : `3a521a3da6db35be3a3ac0177a01e7dfe1b5f0e3`.
Temps confirmé : 0.052843 s ; référence confirmée : 0.115090 s.
Réduction mesurée : 54.1%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Parallelize independent coarse tiles within the requested thread budget | In src/candidate.cpp, compare parallel work decomposition while preserving the requested thread budget: worksharing the independent coarse-root tiles (including static versus dynamic scheduling) and parallelizing the independent base-level depth-bound rows in MinMaxZTree::Update. Measure each approach independently and, if useful, measure a combination rather than assuming additive gains; higher tree levels still depend on completed lower levels. Keep culling and shading algorithms unchanged, pass run()'s thread count as an upper bound, avoid unnecessary overhead at one thread, and preserve disjoint writes. Validate full output and correctness at 1 and 4 cores, including altered light colors. |
| T2 | Reduce recursive hierarchy and conservative light-culling overhead | In src/candidate.cpp, investigate reducing recursive culling and hierarchy work in MinMaxZTree, SplitTileMinMax, IntersectLightsWithTileMinMax, and traversal. In addition to tile granularity and conservative plane-test optimizations, compare stopping subdivision for tiles with small nonzero light lists against continuing to the leaves; measure saved traversal/culling against the added per-pixel light work. Preserve conservative culling, current-frame depth-bound recomputation, and correctness for dimensions not supported by a chosen tile layout. Do not add parallelism or change ShadeTileC in this branch. Validate both core counts and altered light colors. |
| T3 | Optimize per-pixel shading math and row-wise vectorization | In src/candidate.cpp, focus on ShadeTileC's per-pixel BRDF evaluation: investigate safe reuse of pixel and light values, reducing expensive normalization/pow work, and/or row-wise compiler vectorization. Preserve the original shading semantics closely; any approximation must meet the one-intensity-level tolerance on all correctness checks, including altered light colors, and must not rely on a single expected frame. Do not change the tile-culling strategy or introduce threading in this branch; measure both 1- and 4-core cases and retain a portable path unless the frozen build proves a specific ISA is available. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 5fbc3e3ee21f4957 | T1 | search | valid | 0.062578 | 3d9434d0f58d |
| 62d9dd98f7aa43ad | T2 | search | valid | 0.115535 | 0519aaa01a33 |
| ce94cd49a4fc4828 | T3 | search | valid | 0.111008 | 154f8c42e708 |
| bc187c3d22c34a8e | T1 | search | valid | 0.114733 | e1c89e76d2d8 |
| b77c83f1d5914260 | T3 | search | valid | 0.109200 | a1d87bad9567 |
| d7bc10f22e9e4083 | T2 | search | valid | 0.115080 | 5da2d1521508 |
| 5e8ab3c71ac54c6d | Gm1 | search | valid | 0.060567 | b8f8a1752c09 |
| 1ab6b709485b4847 | T1 | search | build_failed | — | 60ebe3e4a8c8 |
| 32c246a5fab64e82 | T3 | search | valid | 0.105185 | a773266834fa |
| 1f43154a52dc4fb5 | T3 | search | valid | 0.104136 | 3743c37a1268 |
| cb0abfe70fb44f68 | Gm2 | search | valid | 0.057065 | 4654e9360674 |
| f01722dbb8d047f2 | T3 | search | valid | 0.115802 | 5b83d86fa5f3 |
| baa96433775440e0 | T1 | search | valid | 0.062029 | 48b8b894faf9 |
| e0c0f6b0a61e484e | Gm3 | search | valid | 0.054035 | 0b421dbca546 |
| b9f682abe3d4489e | T3 | search | valid | 0.110257 | 135cb6ee240c |
| 50e47ad2a00e4d1b | T3 | search | valid | 0.113574 | 4ba9d5b9aaac |
| 4246b59c45384fc2 | G | postprocess | valid | 0.053461 | e2b5c34f1173 |
| ac6f92b8def44472 | G | postprocess | valid | 0.052859 | 3a521a3da6db |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
