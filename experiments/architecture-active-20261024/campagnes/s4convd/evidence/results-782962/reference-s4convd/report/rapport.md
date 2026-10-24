# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `7af34e0eaefb7c68bd0bf0c071b2972e3188b50e8667616ff553de5a3205a8ac`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 40, "tokens_used": 1930904, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1930904}`.
Coûts par phase : `{"search": {"slots": 30, "tokens_used": 1027464, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1027464}, "postprocess": {"slots": 7, "tokens_used": 903440, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 903440}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "cadfaa07e8204c2b", "outcome": {"binary_sha256": "038c554f317e907b1cbe44f1bf55e71c15f077cc59362b06115eb88658b4d491", "cache_key": "dd2d4d4026306b2ff61b75d2ce761428f2881c51152cadefdc053cda71457b79", "commit": "37367a48bddba9dc93ffbdcc77687c0af32cdfef", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-s4convd-6b99437772564b7a82f2d12e9caabd14/results-782962/reference-s4convd/logs/e1/cadfaa07e8204c2b/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-s4convd-6b99437772564b7a82f2d12e9caabd14/results-782962/reference-s4convd/logs/e1/cadfaa07e8204c2b/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-s4convd-6b99437772564b7a82f2d12e9caabd14/results-782962/reference-s4convd/logs/e1/cadfaa07e8204c2b/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-s4convd-6b99437772564b7a82f2d12e9caabd14/results-782962/reference-s4convd/logs/e1/cadfaa07e8204c2b/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-s4convd-6b99437772564b7a82f2d12e9caabd14/results-782962/reference-s4convd/logs/e1/cadfaa07e8204c2b/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-s4convd-6b99437772564b7a82f2d12e9caabd14/results-782962/reference-s4convd/logs/e1/cadfaa07e8204c2b/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-s4convd-6b99437772564b7a82f2d12e9caabd14/results-782962/reference-s4convd/logs/e1/cadfaa07e8204c2b/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.00859961051940918, "reason": "", "score": 0.8048946583565576, "status": "valid", "times": [0.00859160041809082, 0.008611616134643554, 0.008574908256530761, 0.00859164810180664, 0.00862827968597412], "tree_hash": "64393f0ad92b0f599f63e1cbdf1fb090a8c6a39f"}, "status": "confirmed"}`.

Commit retenu après confirmation : `fa8d09505107630c8ac4fb516310e273ce56d66d`.
Temps confirmé : 0.008113 s ; référence confirmée : 0.035477 s.
Réduction mesurée : 77.1%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Improve forward and input-gradient CTA mapping without fusion | Own the separate forward and input-gradient kernels and their launch mapping in src/candidate.cu. Explore packing multiple short rows per CTA and other coalesced, well-utilized mappings to reduce inactive threads and CTA overhead; keep the two passes separate so this tree isolates mapping/kernel-efficiency gains from fusion. Preserve bounds-safe zero padding, full FP32, all-input correctness, complete output writes, and the fixed API. Judge candidates by correctness and full-call timing, not an assumed per-kernel benefit. |
| T2 | Measure a fused forward and input-gradient kernel | Own the forward/input-gradient execution path in src/candidate.cu. Test a fused kernel that computes y and gx together, sharing coordinate/filter handling where beneficial; measure whether fewer launches and shared work outweigh increased register use or reduced occupancy. Do not modify the weight-gradient path. Preserve full FP32, zero-padding semantics, all-input correctness and tolerances, complete fresh writes to both outputs, and the fixed API. Compare complete-call timing and report measured results rather than assuming fusion helps. |
| T3 | Compare one-stage and split weight-gradient reductions | Own the weight-gradient kernel and its use of scratch in src/candidate.cu. Compare reduction granularities rather than assuming multi-stage partial sums win: test a CTA-level reduction distributed across B*L for each (h,j), and, where useful, split B*L into tiles that write partial sums to scratch followed by a final reduction. You may also test tiling neighboring j outputs if it enables useful reuse. Use no extra allocations; every scratch read must follow a write in the current call, and all outputs must be freshly written. Preserve bounds, the contracted gradient, full FP32, and the required tolerances for all valid inputs. Judge variants by correctness and complete-call timing, since the supplied baseline timing does not attribute cost to this kernel. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| f014e1b6f1494b52 | T1 | search | valid | 0.034147 | ab9192a40897 |
| 376532aa1c0a4f8f | T2 | search | valid | 0.034929 | 2ca7ecdd848a |
| 9b2a7876f05a474b | T3 | search | valid | 0.014375 | 976f881a98d9 |
| 626a9fb119ef42b2 | T2 | search | valid | 0.036408 | 807fe5e22213 |
| cf4d414cae9d482e | T3 | search | valid | 0.019781 | 77c138b1d0bd |
| cc2c83db63bc4022 | T2 | search | valid | 0.034859 | d6c944c24a38 |
| 71b7793a2dab4e28 | T1 | search | valid | 0.034678 | 07f51070f964 |
| b95765cb6a144c79 | T3 | search | valid | 0.009406 | 746a3d0af789 |
| cd2e715d4dd34664 | Gm1 | search | valid | 0.013141 | 00ff1bab6b63 |
| ddb802d77f7f4fdf | T1 | search | valid | 0.034885 | 244e8d0a611f |
| 5711050b847f4e97 | Gm2 | search | valid | 0.008075 | fa8d09505107 |
| 38f593e95a0f410e | G | postprocess | valid | 0.008785 | 00d4d5f3a753 |
| cadfaa07e8204c2b | G | postprocess | valid | 0.008593 | 37367a48bddb |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
