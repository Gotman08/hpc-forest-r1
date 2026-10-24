# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `0f9cae8f8cad288e078d5669814831a7cc90abe931053d5130d297f2b9fb3631`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 66, "tokens_used": 4234462, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 4234462}`.
Coûts par phase : `{"search": {"slots": 58, "tokens_used": 3182597, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3182597}, "postprocess": {"slots": 5, "tokens_used": 1051865, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1051865}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "0fa7e23293ca4afe", "outcome": {"binary_sha256": "54df57645b77a8615ac368dd55a4cc77bd792e58ce7df9bb9a8b7af1e0a72e6a", "cache_key": "e66cea70053449c30b5574032fa6776ce1e9a6f27ab4324a737620b0207c219a", "commit": "b774249738f077fb6bd631378aba0321491949e4", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-mandelbrot-c4413e222fca444dace8b950d1ef1be1/results-783044/reference-mandelbrot/logs/e1/0fa7e23293ca4afe/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-mandelbrot-c4413e222fca444dace8b950d1ef1be1/results-783044/reference-mandelbrot/logs/e1/0fa7e23293ca4afe/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-mandelbrot-c4413e222fca444dace8b950d1ef1be1/results-783044/reference-mandelbrot/logs/e1/0fa7e23293ca4afe/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-mandelbrot-c4413e222fca444dace8b950d1ef1be1/results-783044/reference-mandelbrot/logs/e1/0fa7e23293ca4afe/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-mandelbrot-c4413e222fca444dace8b950d1ef1be1/results-783044/reference-mandelbrot/logs/e1/0fa7e23293ca4afe/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-mandelbrot-c4413e222fca444dace8b950d1ef1be1/results-783044/reference-mandelbrot/logs/e1/0fa7e23293ca4afe/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-mandelbrot-c4413e222fca444dace8b950d1ef1be1/results-783044/reference-mandelbrot/logs/e1/0fa7e23293ca4afe/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.07521515280168412, "reason": "", "score": 0.8822555244197319, "status": "valid", "times": [0.07522163709818414, 0.07522556870850704, 0.07519152513086724, 0.07519733003597517, 0.07523970303488696], "tree_hash": "8921aa96eb542b867538da737f4182375685c2be"}, "status": "confirmed"}`.

Commit retenu après confirmation : `f7cd6a9edd4d81ec8b2c8591b46c20b188a08c0c`.
Temps confirmé : 0.075201 s ; référence confirmée : 0.563585 s.
Réduction mesurée : 86.7%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Thread-budgeted OpenMP work decomposition | Explore OpenMP work decomposition without changing the scalar pixel recurrence. Contrast static contiguous rows with dynamic/guided row scheduling and, if useful, a contiguous 2D tiled or collapsed-loop partition to test whether row granularity leaves imbalance within expensive rows. Vary chunk sizes only as measured experiments. Use a serial path when it avoids one-thread overhead; never exceed `threads` or change global OpenMP settings. Preserve the original float coordinate and recurrence behavior, write every output, and do not specialize to tested bounds or dimensions. Validate smaller and shifted-bound cases; measure native wall time at one and four cores, including scheduling overhead at n=1024. |
| T2 | Exact SIMD across independent pixels | Develop an exact SIMD kernel across adjacent x pixels, with correct active-lane handling and tails. Preserve not only the recurrence but also the original float coordinate calculation (`dx`, `dy`, `x0 + i*dx`, `y0 + j*dy`); do not replace it with an incrementally accumulated or otherwise differently rounded grid. Do not change compiler flags or assume an ISA feature merely from the architecture label: verify the candidate builds and runs under the frozen configuration, and report unavailable variants. Validate exact iteration counts for smaller and shifted bounds as well as the target case. Keep scheduling changes out of this experiment so its one-thread SIMD contribution remains identifiable; report the four-core-budget result without implying it uses four cores. |
| T3 | Scalar instruction-level parallelism via pixel interleaving | Explore scalar interleaving of small groups of independent pixel states to expose instruction-level parallelism, without explicit SIMD intrinsics or OpenMP scheduling changes. Compare the sequential baseline with a few group widths (for example, 2, 4, and 8), including a non-divisible tail and pixels with differing escape lengths. Preserve each pixel’s escape test, count, original float coordinate calculation, and recurrence operation order; do not change compiler flags, approximate membership, or specialize to tested inputs. Overwrite the full output and validate smaller and shifted-bound cases. Use one-thread throughput as the main kernel comparison and report the four-core-budget result transparently rather than claiming thread scaling. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 0933e856de4d4829 | T1 | search | valid | 0.282083 | 7a69dbbb2070 |
| 4bc6af7262ba4416 | T2 | search | valid | 0.303312 | 846e6d2e0189 |
| e2bb341cd8234f50 | T3 | search | valid | 0.191756 | 2e890654a006 |
| 001f76803f8b4980 | T1 | search | valid | 0.362791 | 0083d3e38047 |
| 6e7eb61792324bcf | T3 | search | valid | 0.150303 | 10c6b8be1958 |
| a4400fb4f3a9418a | T1 | search | valid | 0.283884 | 04cdca002b1d |
| 0703aae3887d4963 | T2 | search | valid | 0.178614 | d1b5b8008e25 |
| 5f6ae56f161a455a | T3 | search | valid | 0.290084 | 4fae9a49b736 |
| 917a8fe737a44549 | T1 | search | valid | 0.305478 | 974813afb32b |
| 90f41f3c458b41a4 | Gm1 | search | valid | 0.117140 | f44684fdafb6 |
| 026692d5a8b54621 | T3 | search | valid | 0.410460 | 4c85e33e1173 |
| 3036f461a82145f2 | T1 | search | valid | 0.283439 | b6b1186d7f57 |
| 50eaa0e5e84d498c | T1 | search | valid | 0.282221 | 4d3f1b7cf505 |
| be2f014d60e043e9 | Gm2 | search | valid | 0.075247 | f7cd6a9edd4d |
| e16d08eb891644e8 | T3 | search | valid | 0.150817 | 231bfd732bbb |
| 2f846fc3fb2c4e9d | T2 | search | incorrect | — | 4bb7179e7846 |
| 26d85137fac84e80 | T3 | search | valid | 0.154649 | 6c3b14a84ae3 |
| 9786c6a33e344bb9 | T3 | search | valid | 0.169668 | 9040126e3650 |
| 113dc9fdd2ab4049 | T4 | search | valid | 0.080355 | f0178b5cebd3 |
| 232933b7543f41fa | T4 | search | valid | 0.080299 | 9d24e6a00429 |
| 44e42a5d0ba146e5 | T4 | search | valid | 0.080237 | 51234adea34d |
| 42208c3ba12242bc | T5 | search | valid | 0.113553 | 34e704b25881 |
| 07648b0aa64342fe | T5 | search | valid | 0.112990 | a64fa121369c |
| 0fa7e23293ca4afe | G | postprocess | valid | 0.075228 | b774249738f0 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
