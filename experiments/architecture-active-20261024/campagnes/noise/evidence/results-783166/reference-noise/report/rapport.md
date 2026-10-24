# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `847e1b4777b9706a295a784a777f04331cdd5eb94462e0b14d33fd85e4bc6615`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 37, "tokens_used": 2526778, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2526778}`.
Coûts par phase : `{"search": {"slots": 23, "tokens_used": 1168335, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1168335}, "postprocess": {"slots": 10, "tokens_used": 1358443, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1358443}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "335743d5b9224f62", "outcome": {"binary_sha256": "68f810c72456ba35b88bd130949bf9da8733d853d6b5fa530de7d91a0d589415", "cache_key": "e03c0b87ee48a65dfcc410caf46c7ffcacf0df9a806cf212241cea94dc96f6c7", "commit": "a9aea1b5dd3cac87685fe46cb58bdc51d629b676", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-noise-1c53c72ddc504cd2b73f04f536b57538/results-783166/reference-noise/logs/e1/335743d5b9224f62/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-noise-1c53c72ddc504cd2b73f04f536b57538/results-783166/reference-noise/logs/e1/335743d5b9224f62/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-noise-1c53c72ddc504cd2b73f04f536b57538/results-783166/reference-noise/logs/e1/335743d5b9224f62/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-noise-1c53c72ddc504cd2b73f04f536b57538/results-783166/reference-noise/logs/e1/335743d5b9224f62/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-noise-1c53c72ddc504cd2b73f04f536b57538/results-783166/reference-noise/logs/e1/335743d5b9224f62/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-noise-1c53c72ddc504cd2b73f04f536b57538/results-783166/reference-noise/logs/e1/335743d5b9224f62/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-noise-1c53c72ddc504cd2b73f04f536b57538/results-783166/reference-noise/logs/e1/335743d5b9224f62/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.20939580160000001, "reason": "", "score": 0.598184822837115, "status": "valid", "times": [0.209067525, 0.209386746, 0.209635436, 0.209024184, 0.209865117], "tree_hash": "be7603d33d36d221e1789c348fafe4eb954501ed"}, "status": "confirmed"}`.

Commit retenu après confirmation : `f4a2d5314ed0d7171aa47334b0d1c3b24f28d3c5`.
Temps confirmé : 0.145927 s ; référence confirmée : 0.311729 s.
Réduction mesurée : 53.2%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Per-axis, per-octave coordinate-state reuse | Test whether per-axis, per-octave state reuse reduces total runtime enough to justify its scratch traffic. Compare the scalar baseline with staged variants—for example, storing only lattice/fraction state, then additionally storing smooth weights and shared z state. Preserve the original coordinate-expression order and octave progression. Include allocation and state access in timing; validate n=768 and smaller/shifted bounds at the fixed tolerance. Keep hybrid variants separately identified and measured, and record unsuccessful layouts or attempts. |
| T2 | Scalar Perlin hash, gradient, and interpolation kernel | Test scalar-only restructuring of the per-pixel Noise/Grad path. Measure hash-addressing/gradient-selection changes separately from interpolation-polynomial and octave-control-flow changes, so the source of any gain or regression is visible. Use the original scalar implementation as the controlled comparison; correctness-preserving combinations remain possible but should be measured separately. Validate all specified checks and the fixed tolerance, and record failed approaches. Do not assume arithmetic rewrites or table changes will be faster. |
| T3 | SIMD across independent image pixels | Test whether mapping adjacent output pixels to SIMD lanes improves end-to-end time on the frozen build and target. Compare explicit SIMD—including the cost of dependent permutation-table gathers—with a simpler compiler-vectorizable formulation where feasible; first preserve the scalar per-lane math to isolate vectorization, then label any further kernel rewrites as separate variants. Do not assume the manual’s vectorization defaults match the actual build flags or that a wider vector is faster. Include tails and full-call costs, validate all specified bounds and sizes at the fixed tolerance, and record failed implementations. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| f8565db2c7904f50 | T1 | search | valid | 0.381330 | a05d4ac33cb7 |
| 2f9bc29e0efa4ac4 | T2 | search | valid | 0.289468 | 1a7b792ec004 |
| 99c51b4e9a1b475c | T3 | search | valid | 0.312326 | 0fc6bd0c2dc4 |
| fba5465da6c842be | T2 | search | valid | 0.305087 | fb87a8f473d7 |
| 33201dde37014ad4 | T1 | search | valid | 0.179011 | ffb7bfa4d093 |
| 4b7489ce6fff40f2 | T2 | search | valid | 0.303170 | 7cdc99786dd6 |
| 044489e1e11b4f04 | T3 | search | incorrect | — | a40fa047cdf3 |
| 1da2cef3d5514c23 | T2 | search | valid | 0.304182 | 4a1a0c307dff |
| e30450b7653a49d0 | T1 | search | valid | 0.287800 | afb51ac87abf |
| c57618f08b9f4c0f | T2 | search | valid | 0.278320 | 95750ab5791d |
| 17450092744d4144 | T1 | search | valid | 0.305796 | 61dab514bf2e |
| b176f5d6f71d42be | Gm1 | search | valid | 0.146710 | f4a2d5314ed0 |
| 005e1d8ee0464c28 | T1 | search | valid | 0.375222 | 80685d7905b8 |
| cc3f07bac82542ac | G | postprocess | valid | 0.239294 | 06fccab378d0 |
| 335743d5b9224f62 | G | postprocess | valid | 0.209609 | a9aea1b5dd3c |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
