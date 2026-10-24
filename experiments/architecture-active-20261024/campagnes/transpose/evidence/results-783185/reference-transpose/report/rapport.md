# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `890e61fde2073f79a1047764e06b2498b9cca063aec4f5109eae336ba016ae3f`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 35, "tokens_used": 2156999, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2156999}`.
Coûts par phase : `{"search": {"slots": 27, "tokens_used": 1553549, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1553549}, "postprocess": {"slots": 4, "tokens_used": 603450, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 603450}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "26ece17080a44458", "outcome": {"binary_sha256": "00af39e336e53fa010dede2f03ae6897b3163f1d7eafe75c6aff7c32739e8b9a", "cache_key": "1f7469063784162839f18c4a44ec6fca99a9798c34aa9a4d4abab05bef25104f", "commit": "99419f81ba43a195d3dbe86a98d57a7bed66b810", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-transpose_retry1-3a10134cf1434d5c895b1aa89a5f6416/results-783185/reference-transpose/logs/e1/26ece17080a44458/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-transpose_retry1-3a10134cf1434d5c895b1aa89a5f6416/results-783185/reference-transpose/logs/e1/26ece17080a44458/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-transpose_retry1-3a10134cf1434d5c895b1aa89a5f6416/results-783185/reference-transpose/logs/e1/26ece17080a44458/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-transpose_retry1-3a10134cf1434d5c895b1aa89a5f6416/results-783185/reference-transpose/logs/e1/26ece17080a44458/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-transpose_retry1-3a10134cf1434d5c895b1aa89a5f6416/results-783185/reference-transpose/logs/e1/26ece17080a44458/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-transpose_retry1-3a10134cf1434d5c895b1aa89a5f6416/results-783185/reference-transpose/logs/e1/26ece17080a44458/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-transpose_retry1-3a10134cf1434d5c895b1aa89a5f6416/results-783185/reference-transpose/logs/e1/26ece17080a44458/confirmation/attempt-001/sample-4.log"], "mean_seconds": 3.3967359457159998e-06, "reason": "", "score": 0.8312362650931511, "status": "valid", "times": [3.45535995439e-06, 3.3187197987e-06, 3.4211201127599997e-06, 3.3833598718e-06, 3.40511999093e-06], "tree_hash": "71d2bbc90cfe57617ae8a2cdb8c9fba8e4d59a09"}, "status": "confirmed"}`.

Commit retenu après confirmation : `0dbfeef7b88d7cfaacb9387b41a42607b2d5267d`.
Temps confirmé : 0.000003 s ; référence confirmée : 0.000017 s.
Réduction mesurée : 80.9%. Référence conservée : non.

Mother a choisi **2 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Shared-memory transpose layouts and ownership | Own only src/candidate.cu. Replace the baseline's strided global stores with a single-pass shared-memory tiled transpose: load input rows coalesced, exchange tile orientation in shared memory, then store output rows coalesced. Compare the padded 32x33 scalar tile with at least one meaningfully different shared-memory layout or multi-element/vectorized thread-ownership variant; do not presume the padded scalar layout is fastest on this target. Measure the complete run at n=1024. Preserve the run entry point and exact bit patterns; produce every C element for every positive n multiple of 32, pass correctness at n=32, 64, 256, and 1024, use no new allocation or other file edits, and report build, correctness, and repeated timing evidence. |
| T2 | Warp-local register/shuffle transpose | Own only src/candidate.cu. Independently explore a warp-register transpose using warp lane permutations/shuffles to turn coalesced input loads into coalesced output stores, aiming to avoid CTA shared-memory staging and its block-wide synchronization. Design and describe element ownership so each shuffle exchange uses data held by participating lanes in the same warp; do not assume a warp shuffle exchanges data across warps. Tune the warp's element ownership and tile mapping, and report register/spill evidence if present in the ordinary build output. Preserve exact bitwise copies and the run entry point, produce all output for every positive n multiple of 32, pass the required correctness sizes, allocate no new storage, and report repeated full-run n=1024 timing evidence. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 5f05ca36bcd347ee | T1 | search | valid | 0.000003 | dce421e91cb9 |
| 5c066fd51f984909 | T2 | search | valid | 0.000003 | 236325323b87 |
| e8b5e81f11b14f29 | T1 | search | valid | 0.000003 | f86359bb59fa |
| 51ce1da6ff424257 | T2 | search | valid | 0.000003 | 771f60d59939 |
| cef4bbb63e3e49cf | T1 | search | valid | 0.000003 | 0dbfeef7b88d |
| 1a4f3ff518c24ac0 | T2 | search | valid | 0.000004 | f88a3b36b4ea |
| 677cd6c7769f4f38 | T1 | search | valid | 0.000004 | 74f14a8faadc |
| 3163c605270145ae | T2 | search | valid | 0.000005 | 8d5bbe473f90 |
| ec3d8a5007b045ac | T1 | search | valid | 0.000004 | 82e262d2f2f7 |
| 24f22d4034d8481e | T1 | search | valid | 0.000003 | 2268ee45f482 |
| 26ece17080a44458 | G | postprocess | valid | 0.000003 | 99419f81ba43 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
