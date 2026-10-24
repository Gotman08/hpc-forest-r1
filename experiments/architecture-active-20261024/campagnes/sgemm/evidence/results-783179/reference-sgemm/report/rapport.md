# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `ab97c278ffa21b38a47de52087922c4d428301a22bfb9cf55d3d9a2b494afdd8`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 51, "tokens_used": 3262349, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3262349}`.
Coûts par phase : `{"search": {"slots": 39, "tokens_used": 1941150, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1941150}, "postprocess": {"slots": 8, "tokens_used": 1321199, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1321199}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "6ed4037a0b654154", "outcome": {"binary_sha256": "9802bf05b8714522ff7950eb1127c8d4e536cb82d1784d34aecd9b53f08d0845", "cache_key": "3a236812c06bc6ae5623f549fce5f7056e562307413566d4235d737d2560fa0f", "commit": "1a201079e5254c44ba1a180990c51e304cb27cb5", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-sgemm_retry1-04fe70c6f9d349daa2a45f91eaa7d412/results-783179/reference-sgemm/logs/e1/6ed4037a0b654154/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-sgemm_retry1-04fe70c6f9d349daa2a45f91eaa7d412/results-783179/reference-sgemm/logs/e1/6ed4037a0b654154/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-sgemm_retry1-04fe70c6f9d349daa2a45f91eaa7d412/results-783179/reference-sgemm/logs/e1/6ed4037a0b654154/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-sgemm_retry1-04fe70c6f9d349daa2a45f91eaa7d412/results-783179/reference-sgemm/logs/e1/6ed4037a0b654154/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-sgemm_retry1-04fe70c6f9d349daa2a45f91eaa7d412/results-783179/reference-sgemm/logs/e1/6ed4037a0b654154/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-sgemm_retry1-04fe70c6f9d349daa2a45f91eaa7d412/results-783179/reference-sgemm/logs/e1/6ed4037a0b654154/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-sgemm_retry1-04fe70c6f9d349daa2a45f91eaa7d412/results-783179/reference-sgemm/logs/e1/6ed4037a0b654154/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.02069177398682, "reason": "", "score": 0.930156242006263, "status": "valid", "times": [0.0206889610291, 0.0206866703033, 0.0206907463074, 0.0206990909576, 0.020693401336699998], "tree_hash": "cee20b5ee07e1d9759e957eafeaa6e234734f6fd"}, "status": "confirmed"}`.

Commit retenu après confirmation : `1e3d9e2741b611d52df198d0c53c3dfd805e53d2`.
Temps confirmé : 0.011871 s ; référence confirmée : 0.275566 s.
Réduction mesurée : 95.7%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Coalescing control plus synchronous SIMT CTA tiling | First benchmark a minimal coalesced, row-major one-output-per-thread kernel with lanes varying over columns, to isolate the cost of the supplied baseline’s lane mapping. Then explore synchronous shared-memory CTA tiles using that coalesced orientation and one output per thread, varying tile dimensions and K depth. Support tails and all valid dimensions and values, compute every output with the requested alpha/beta semantics, and report correctness and repeated timing. Use full-FP32 CUDA-core arithmetic only; preserve the entry point and buffer/stream constraints, with no extra allocations or external math libraries. |
| T2 | Multi-accumulator register-blocked SIMT microtiles | Focus on register-blocked SIMT where each thread maintains multiple independent FP32 output accumulators, testing distinct row/column microtile mappings to reuse operands and improve arithmetic intensity. Compare against a one-output-per-thread control so the result is not merely a CTA tile-size comparison with T1; measure register/occupancy tradeoffs and correctness as well as repeated timing. Support tails and all valid dimensions and values, apply alpha/beta once per output, and preserve the entry point, buffers, stream, and full-FP32 requirement. Do not use tensor-core/reduced-precision math, extra allocations, or external math libraries. |
| T3 | Matched synchronous/asynchronous K-stage pipeline comparison | Explore whether asynchronous global-to-shared K-stage copies improve a tiled SIMT kernel. Establish a paired synchronous-staging control with the same CTA tile, lane mapping, and compute mapping as the asynchronous version, then compare timings and correctness to isolate the pipeline effect. Handle alignment, completion, synchronization, tails, and any needed fallback for all valid inputs; preserve full-FP32 arithmetic, alpha/beta semantics, entry point, stream, and buffer limits. Use only CUDA 12.6.3-supported mechanisms, no external math libraries, reduced precision, or extra allocations; treat gains as hypotheses to measure. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 336563f9016a4994 | T1 | search | valid | 0.023408 | aaeec1afaa9d |
| 0332e7182e574703 | T2 | search | valid | 0.014726 | 92d4f0a29311 |
| 3906be4089a1452f | T3 | search | valid | 0.017308 | b4babb086d60 |
| b1287bb5dab14c66 | T3 | search | valid | 0.021067 | 2bcf177418d9 |
| b970e40684494e99 | T1 | search | valid | 0.022899 | e0a3ca1e9af7 |
| 4ee90c8d348e4fd5 | T2 | search | valid | 0.037572 | 1057321e1378 |
| 7cda8bccaa0f438a | T2 | search | valid | 0.013830 | ed9b3d0bf361 |
| d86e6d6b71b5456b | T1 | search | valid | 0.019527 | 8d8b85eb53af |
| 757e76a20e0d4a2f | T3 | search | valid | 0.021284 | 777f878bb97f |
| 9577a3a19b3845f2 | T2 | search | valid | 0.011853 | 1e3d9e2741b6 |
| 4d56b643979d4e71 | Gm1 | search | valid | 0.021907 | 017b3068005b |
| d53728e433cf4c9a | T1 | search | valid | 0.040568 | 47b3529190bf |
| 3ec37cfeda7644a4 | T2 | search | valid | 0.016372 | 55774bcd151f |
| 0b41ade7af28400f | T2 | search | valid | 0.067510 | 285ffccd6ca5 |
| 480a32af0dc947e2 | T4 | search | valid | 0.011952 | fb481eed39ac |
| ba5ef08b89f64470 | T4 | search | valid | 0.011962 | 4c0991987403 |
| 4e54b76761a24b78 | G | postprocess | valid | 0.011980 | d8c6a52518fe |
| 6ed4037a0b654154 | G | postprocess | valid | 0.020694 | 1a201079e525 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
