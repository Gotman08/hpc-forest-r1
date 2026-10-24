# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `2d33d81cdcfbbc0125107dd390bec575ba5a2ce3cdcf202e3523a21b61c661cb`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 37, "tokens_used": 2211096, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2211096}`.
Coûts par phase : `{"search": {"slots": 29, "tokens_used": 1520916, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1520916}, "postprocess": {"slots": 5, "tokens_used": 690180, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 690180}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "3a50734b97d648c3", "outcome": {"binary_sha256": "356b855f75374f79465b1f527101180f20eae1c32fa3d9830258c13a9395cbfa", "cache_key": "4948dec5ea369a68d4f19bbecec6459b3badcd756472b34b9de6d2e87916f645", "commit": "bbab494ddfb379bbce22606a12573868018bb1da", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-gemm_cpu_retry1-d02fc9631732486bb3394c1f89d10ba0/results-783048/reference-gemm_cpu/logs/e1/3a50734b97d648c3/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-gemm_cpu_retry1-d02fc9631732486bb3394c1f89d10ba0/results-783048/reference-gemm_cpu/logs/e1/3a50734b97d648c3/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-gemm_cpu_retry1-d02fc9631732486bb3394c1f89d10ba0/results-783048/reference-gemm_cpu/logs/e1/3a50734b97d648c3/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-gemm_cpu_retry1-d02fc9631732486bb3394c1f89d10ba0/results-783048/reference-gemm_cpu/logs/e1/3a50734b97d648c3/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-gemm_cpu_retry1-d02fc9631732486bb3394c1f89d10ba0/results-783048/reference-gemm_cpu/logs/e1/3a50734b97d648c3/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-gemm_cpu_retry1-d02fc9631732486bb3394c1f89d10ba0/results-783048/reference-gemm_cpu/logs/e1/3a50734b97d648c3/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-gemm_cpu_retry1-d02fc9631732486bb3394c1f89d10ba0/results-783048/reference-gemm_cpu/logs/e1/3a50734b97d648c3/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.002765130395984556, "reason": "", "score": 0.9995399305409427, "status": "valid", "times": [0.0027651275675675668, 0.0027689259729729737, 0.0027646183783783785, 0.002764256628571429, 0.0027627234324324335], "tree_hash": "86b2c773bf1af531fa80c774e1c50c9de761f882"}, "status": "confirmed"}`.

Commit retenu après confirmation : `fcecec9ec9afd614455a72a5fabe42ffa3fb0e58`.
Temps confirmé : 0.002759 s ; référence confirmée : 6.007480 s.
Réduction mesurée : 100.0%. Référence conservée : non.

Mother a choisi **2 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Unpacked cache-tiled loop ordering with OpenMP and compiler vectorization | In src/candidate.cpp, explore an unpacked GEMM route based on loop interchange (including i-k-j), cache tiling, and OpenMP ownership of disjoint output rows or tiles. Keep the output-column loop contiguous so the frozen GCC build can auto-vectorize it; do not pack matrices or use explicit x86 intrinsics, keeping this route distinct from the SIMD tree. Tune loop/tile order and scheduling using measured performance, including whether to avoid parallel overhead on small sizes. Respect threads (at most eight), read-only inputs, and complete output overwrite on every call. Preserve correctness for all supported sizes and signed, varying inputs within abs_error <= 0.002 + 5e-5*abs(reference). Change only src/candidate.cpp; record failed attempts and compare valid repeated native timings, prioritizing n=1024. |
| T2 | Register-tiled SIMD GEMM with measured packing ablation | Explore an explicit register-tiled FP32 FMA/SIMD microkernel with OpenMP ownership of disjoint output tiles. Measure direct-access and packed-panel variants using the same microkernel and comparable tiles where practical, so packing overhead and benefit are tested rather than assumed; consider packing B alone versus additional panels. Tune microkernel shape and panel layout, and include scratch allocation and packing in total runtime. Use AVX-512 or AVX2 only when compatible with the frozen GCC build and target, without changing compiler settings. Handle tails and small sizes generically, respect the threads budget (at most eight), fully overwrite output each invocation, and validate varying signed inputs against the fixed FP64 tolerance. Change only src/candidate.cpp; record failed attempts and report correctness and repeated native timings, prioritizing n=1024. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 20d5d3610fd14da9 | T1 | search | valid | 0.015874 | b41113f1f760 |
| 4184453b5e7a41a6 | T2 | search | valid | 0.003443 | 359c83cd5e09 |
| dc71b5b85c424453 | T1 | search | valid | 0.011405 | e4963ebe4ad9 |
| 132b8ca4ab774f70 | T2 | search | valid | 0.005633 | ff1e5099b79e |
| 39b4a9271f7f4f27 | T1 | search | valid | 0.020157 | 9d4c6b6235b0 |
| 5bf16cd2c3b8448f | T2 | search | valid | 0.003389 | 18b77394715a |
| 1ebc3c277286431d | T1 | search | valid | 0.016196 | e1ed1f1a7afa |
| 30462536c13c4e5d | Gm1 | search | valid | 0.003417 | 2556f8effe9d |
| 327ada26fd134727 | T2 | search | valid | 0.005219 | df79101a81eb |
| 14a797a5cb2d4db1 | T2 | search | valid | 0.003459 | 9e6310feeb3d |
| 52c15139e2464dfa | T2 | search | valid | 0.003460 | 1d52fdd1529d |
| fb2b011885c849d7 | Gm2 | search | valid | 0.002789 | fcecec9ec9af |
| 3a50734b97d648c3 | G | postprocess | valid | 0.002782 | bbab494ddfb3 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
