# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `6fb663e8c8e2cdca38921304b4fae8331cd7da0e40c170d4757ca72c7504dc31`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 44, "tokens_used": 2412847, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2412847}`.
Coûts par phase : `{"search": {"slots": 38, "tokens_used": 1945708, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1945708}, "postprocess": {"slots": 3, "tokens_used": 467139, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 467139}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "f42f92e86c6e4a1a", "outcome": {"binary_sha256": "f6ffaa16cb2a667a7665f1ecc518bfcd331ef5baa95417826d01fa5e5d086ee5", "cache_key": "ca6e4ec950161c2f84da90d15ad0787f7546563701e5c324ccdbba3cbe807239", "commit": "ea29ccfe59b8900a57f0c17fc7523488b3348a40", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-stencil_y_retry2-0b45598ce8e942e2a362cfad35ab3f2f/results-783205/reference-stencil_y/logs/e1/f42f92e86c6e4a1a/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-stencil_y_retry2-0b45598ce8e942e2a362cfad35ab3f2f/results-783205/reference-stencil_y/logs/e1/f42f92e86c6e4a1a/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-stencil_y_retry2-0b45598ce8e942e2a362cfad35ab3f2f/results-783205/reference-stencil_y/logs/e1/f42f92e86c6e4a1a/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-stencil_y_retry2-0b45598ce8e942e2a362cfad35ab3f2f/results-783205/reference-stencil_y/logs/e1/f42f92e86c6e4a1a/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-stencil_y_retry2-0b45598ce8e942e2a362cfad35ab3f2f/results-783205/reference-stencil_y/logs/e1/f42f92e86c6e4a1a/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-stencil_y_retry2-0b45598ce8e942e2a362cfad35ab3f2f/results-783205/reference-stencil_y/logs/e1/f42f92e86c6e4a1a/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-stencil_y_retry2-0b45598ce8e942e2a362cfad35ab3f2f/results-783205/reference-stencil_y/logs/e1/f42f92e86c6e4a1a/confirmation/attempt-001/sample-4.log"], "mean_seconds": 2.95756799169e-06, "reason": "", "score": 0.5388530158525162, "status": "valid", "times": [2.88767996244e-06, 3.00960009918e-06, 2.84095993266e-06, 3.09120002203e-06, 2.95839994214e-06], "tree_hash": "fc0e62e87745415ab0db0bffb60f658214831e1a"}, "status": "confirmed"}`.

Commit retenu après confirmation : `ea29ccfe59b8900a57f0c17fc7523488b3348a40`.
Temps confirmé : 0.000003 s ; référence confirmée : 0.000003 s.
Réduction mesurée : 14.4%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Coalesced direct-global stencil without shared memory | Implement and measure a single-pass direct-global stencil with one output per thread and no shared memory or block-wide barriers. Map warp lanes to contiguous x elements; compare practical launch mappings and unroll the eight neighbor terms. Reproduce the baseline y-halo mapping for every offset, produce all 64³ outputs from current A on every call, and use no extra launch or allocation. Validate against the independent oracle and compare full-run event latency with the baseline. |
| T2 | Shared-memory pencil geometry: full-height versus y-subtile tiling | Explore shared-memory pencil geometry as a contrast to the supplied 4-by-64 block. Compare wider x pencils while retaining the full 64-row y slab (for example, 8- or 16-wide x pencils) against x-wide blocks producing smaller y subtiles with radius-4 halos. Measure the tradeoff between improved x coalescing, block count, halo duplication, synchronization, and occupancy; do not assume either shape wins. Preserve the exact stencil coefficients and baseline y-halo/period-63 endpoint mapping, cover every output, validate against the independent oracle for varying signed inputs, and compare full-run event latency. Use only the existing buffers and allowed launch model. |
| T3 | Register reuse across multiple y outputs | Implement and measure register-blocked y outputs: assign contiguous x elements across warp lanes and have each thread compute multiple nearby y outputs, reusing their overlapping input neighborhood in registers rather than shared memory. Explore a small number of outputs per thread and suitable launch geometry; preserve exact coefficients and baseline halo mapping, compute every output from current A, and use no additional allocation or launch. Compare oracle correctness and full-run latency. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 4d42e32818ef4cbd | T1 | search | valid | 0.000003 | d15d29ba1156 |
| 002fbb87c9d94101 | T2 | search | valid | 0.000003 | c11a06c6a6eb |
| d9de9e6475e9480a | T3 | search | valid | 0.000003 | fd05e962b1eb |
| 188db7c4c14746ee | T2 | search | valid | 0.000004 | c7044762314f |
| 94ee21b6e9dd4f08 | T3 | search | valid | 0.000003 | cd268011b7a5 |
| 4ed11623d73f46b4 | T1 | search | valid | 0.000003 | fecae1e2fa30 |
| b8038404f884418a | T2 | search | valid | 0.000003 | 7e9fc5e3aeba |
| 7ca2f77e0d4148ac | T1 | search | valid | 0.000003 | 2a0831885d20 |
| 3c3afe85465e4d5d | T2 | search | valid | 0.000003 | 2d22277a1ce1 |
| a6e80b3d95af4edf | T2 | search | valid | 0.000003 | d8d9fd951bfb |
| dc76ae46db21414e | T1 | search | valid | 0.000003 | 4353dd077f17 |
| 86851286e2ec45b0 | T3 | search | valid | 0.000003 | 5581bf96bcc5 |
| 264197d63c124b41 | T2 | search | valid | 0.000003 | 1882ec1ddb60 |
| cb0db758c3bc46a8 | T1 | search | valid | 0.000004 | f0555eaaf8ce |
| 3124b8354d9f416e | T3 | search | incorrect | — | 5c617116e795 |
| 4bf3de724d1e4f6f | T2 | search | valid | 0.000003 | 425a77f0f253 |
| f42f92e86c6e4a1a | G | postprocess | valid | 0.000003 | ea29ccfe59b8 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
