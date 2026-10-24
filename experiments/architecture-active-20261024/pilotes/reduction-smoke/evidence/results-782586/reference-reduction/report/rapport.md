# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `9c336387f756c7552ee3b3c34a5b92ffdc7a2ac87a0279d3807ed3054a7997d6`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 12, "tokens_used": 560706, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 560706}`.
Coûts par phase : `{"search": {"slots": 5, "tokens_used": 91558, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 91558}, "postprocess": {"slots": 4, "tokens_used": 469148, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 469148}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "a1b82fa3b0684425", "outcome": {"binary_sha256": "a2ccbfa99d13489d9e89357394403676d0da53edeaa5d9b35378be6386268258", "cache_key": "c8e932fb3686c427f7d3a153426ce4388246d110fd890d458cee1a226088050b", "commit": "86b6b16faa4005fa237f2d8be15f8574d2b02a73", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-reduction-smoke-adb1dce7b06c423fa8b79861a0a2269a/results-782586/reference-reduction/logs/e1/a1b82fa3b0684425/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-reduction-smoke-adb1dce7b06c423fa8b79861a0a2269a/results-782586/reference-reduction/logs/e1/a1b82fa3b0684425/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-reduction-smoke-adb1dce7b06c423fa8b79861a0a2269a/results-782586/reference-reduction/logs/e1/a1b82fa3b0684425/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-reduction-smoke-adb1dce7b06c423fa8b79861a0a2269a/results-782586/reference-reduction/logs/e1/a1b82fa3b0684425/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-reduction-smoke-adb1dce7b06c423fa8b79861a0a2269a/results-782586/reference-reduction/logs/e1/a1b82fa3b0684425/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-reduction-smoke-adb1dce7b06c423fa8b79861a0a2269a/results-782586/reference-reduction/logs/e1/a1b82fa3b0684425/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-reduction-smoke-adb1dce7b06c423fa8b79861a0a2269a/results-782586/reference-reduction/logs/e1/a1b82fa3b0684425/confirmation/attempt-001/sample-4.log"], "mean_seconds": 6.630399942398072e-06, "reason": "", "score": 0.8750837993363771, "status": "valid", "times": [6.714239716529846e-06, 6.521599888801574e-06, 6.572160124778748e-06, 6.659839749336243e-06, 6.684160232543946e-06], "tree_hash": "10c4917a56c8e5bf204fda0984a2a724c66461d3"}, "status": "confirmed"}`.

Commit retenu après confirmation : `92871e7750fc7078e98d6923ab3310a8534cbb4b`.
Temps confirmé : 0.000007 s ; référence confirmée : 0.000046 s.
Réduction mesurée : 85.8%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Custom warp-level hierarchical reduction for large inputs | Explore a hand-written high-throughput multi-CTA reduction for large n. Replace the repeated 128-thread reduction passes with coalesced loads, per-thread accumulation over multiple elements, and an efficient warp-level/block reduction. Search tile size and launch geometry to reduce partial count and total work; have a final device pass write the result directly to out. Do not rely on output initialization or atomics. Preserve exact int32 reduction semantics and validate all required sizes, including n=2^22. |
| T2 | CUB BlockReduce-based large-input reduction | Independently explore a hierarchical reduction using allowed CUB BlockReduce primitives (not a device-wide CUB API). Tune how input elements are assigned to threads and blocks to produce compact first-pass partials, then reduce the partials and write directly to out. Keep this mechanism distinct from hand-written warp/block collectives; use only provided scratch, and verify correctness for all valid sizes before measuring. |
| T3 | Single-launch path for small and moderate inputs | Investigate launch-latency reduction with a generic size-aware path: for a measured beneficial range, let one CTA process the full input and write out directly, avoiding intermediate passes and the final copy; retain a correct scalable fallback for larger inputs. Determine the crossover from measurements rather than specializing to listed test values. Preserve the ABI, exactness, scratch bounds, and correctness across required and other valid sizes. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| cf99fcfb82c44b80 | T1 | search | valid | 0.000007 | b5248080ec38 |
| 02575f7272c54adb | T2 | search | valid | 0.000006 | 92871e7750fc |
| 020bcd1bc8c44e5f | T3 | search | valid | 0.000047 | aa133394d118 |
| a1b82fa3b0684425 | G | postprocess | valid | 0.000006 | 86b6b16faa40 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
