# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `f859ed57d3b7360c0950ba347177b8153a39e8291d7510b062ff04f2c0f2941f`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 45, "tokens_used": 4695689, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 4695689}`.
Coûts par phase : `{"search": {"slots": 39, "tokens_used": 4336925, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 4336925}, "postprocess": {"slots": 3, "tokens_used": 358764, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 358764}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "4af57510d2614968", "outcome": {"binary_sha256": "99420f82b95f00bc6374fe46f82ae8376ffb0a7e56289f1177210506fe7d9e24", "cache_key": "b25172a3a4a0fb9f640b3b8c46a0224eef4b86eefea80d12f2da2303d6802718", "commit": "9104d45d919f8c2e425188ab3562a18abc62e2ff", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-base64_retry1-70fba928cdcc4bcda5dd73d5bfd23a9e/results-783163/reference-base64/logs/e1/4af57510d2614968/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-base64_retry1-70fba928cdcc4bcda5dd73d5bfd23a9e/results-783163/reference-base64/logs/e1/4af57510d2614968/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-base64_retry1-70fba928cdcc4bcda5dd73d5bfd23a9e/results-783163/reference-base64/logs/e1/4af57510d2614968/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-base64_retry1-70fba928cdcc4bcda5dd73d5bfd23a9e/results-783163/reference-base64/logs/e1/4af57510d2614968/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-base64_retry1-70fba928cdcc4bcda5dd73d5bfd23a9e/results-783163/reference-base64/logs/e1/4af57510d2614968/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-base64_retry1-70fba928cdcc4bcda5dd73d5bfd23a9e/results-783163/reference-base64/logs/e1/4af57510d2614968/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-base64_retry1-70fba928cdcc4bcda5dd73d5bfd23a9e/results-783163/reference-base64/logs/e1/4af57510d2614968/confirmation/attempt-001/sample-4.log"], "mean_seconds": 9.046970592250845e-06, "reason": "", "score": 0.8592311066865028, "status": "valid", "times": [9.112802887234436e-06, 9.02817382580939e-06, 9.024913658625076e-06, 9.029599233856264e-06, 9.039363355729065e-06], "tree_hash": "eb797e0674fad6c1d9695908b8269c27eda1b5d0"}, "status": "confirmed"}`.

Commit retenu après confirmation : `0e4cdb24a73d73e29684c0e77e6b41ec15c08029`.
Temps confirmé : 0.000009 s ; référence confirmée : 0.000055 s.
Réduction mesurée : 83.7%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | AVX2 arithmetic-classification decoder | In its own research branch, modify only src/candidate.cpp to evaluate an AVX2 decoder whose primary mapping method is vector range classification and arithmetic offsets, followed by vector bit packing—not a wide table-permute lookup. Use safe block loads/stores and a correct tail/padding path; verify ISA support under the frozen build without changing flags. Preserve exact output semantics and stay within the threads budget. Validate empty and short strings plus lengths around vector-block boundaries, all padding cases, random valid inputs, and the official Lena input before repeated native timing. Do not specialize to its length; record failures and results. |
| T2 | AVX-512VBMI permutation decoder | In its own research branch, modify only src/candidate.cpp to evaluate a distinct AVX-512VBMI table-permutation approach for mapping Base64 input bytes to six-bit values, then pack decoded bytes. Do not merely widen T1’s loop: contrast its mapping strategy explicitly. Verify the required instructions are enabled by the frozen build and supported by the target; do not change compiler flags or assume 512-bit execution is faster. Use safe loads/stores and correct tails/padding, preserve exact output semantics, and respect the threads budget. Validate empty and short strings, lengths around vector-block boundaries, every padding case, random valid inputs, and the official Lena input before repeated native timing; record unsupported-ISA and performance failures. |
| T3 | Scalar table-loop unrolling | In its own research branch, modify only src/candidate.cpp to test scalar scheduling improvements to the existing table-driven eight-character/six-byte decode loop: unroll multiple independent groups so table lookups can overlap and loop overhead is amortized. Keep this a scalar-focused contrast to the SIMD trees; do not add explicit SIMD or parallel execution. Preserve exact output semantics, safe tails/padding, and the threads budget. Validate empty and short strings, lengths around the unrolled-group boundary, every padding case, random valid inputs, and the official Lena input before repeated native timing. Do not specialize to the benchmark length; record unsuccessful unroll/group-size choices and results. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| fce2189a219043de | T1 | search | valid | 0.000022 | f3876d2a3bbc |
| 49c9a44541894d26 | T2 | search | valid | 0.000083 | 3825a445a774 |
| c06b3e4810164fa0 | T3 | search | valid | 0.000082 | 45e35945f5a8 |
| d3c9857d0af34a15 | T2 | search | valid | 0.000589 | a2d9b9a02722 |
| 624f7b074b9c4fc6 | T3 | search | valid | 0.000064 | e4952bb61617 |
| 3bf34d0190944fef | T1 | search | valid | 0.000018 | 4875cffce149 |
| 791f1e0e1cf44692 | T3 | search | valid | 0.000148 | 302234baba87 |
| 5b164d060a4d4cb3 | T3 | search | valid | 0.000081 | 4c8349b6edee |
| 97ae5147d9be401e | T3 | search | incorrect | — | 8520bce90c61 |
| d7105bd720094b50 | T1 | search | incorrect | — | 0ef01a0a01e9 |
| 722a395607c74fc1 | T3 | search | incorrect | — | e6883c3d353a |
| 744cf508453f4ba6 | T4 | search | valid | 0.000015 | 2dd02fcdb0ff |
| f42c40ea87974114 | T4 | search | valid | 0.000009 | 0e4cdb24a73d |
| 9fa13cab1cf14b4c | T1 | search | valid | 0.000020 | 1f58b1edfec8 |
| 4af57510d2614968 | G | postprocess | valid | 0.000009 | 9104d45d919f |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
