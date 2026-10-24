# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `a1ef51a848fa6d317e2f8e784f3120aab226567e556433f8d42a38eb9d343297`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 54, "tokens_used": 2835500, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2835500}`.
Coûts par phase : `{"search": {"slots": 43, "tokens_used": 1695437, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1695437}, "postprocess": {"slots": 8, "tokens_used": 1140063, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1140063}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "1864127ae70f4754", "outcome": {"binary_sha256": "358f6ef9a6108961698524f5adfe3e64082c3595ad361157b96b56ff623c09aa", "cache_key": "6a16e2c201971bb81f1d1168d601036d9d295197632bfafea0d4500a99a3927a", "commit": "f4672fb4288b5f6ddb6174143d976ef0a3702d8d", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-sumabs-9b36f1da2fcd4bf3b7a71e91231ca668/results-783132/reference-sumabs/logs/e1/1864127ae70f4754/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-sumabs-9b36f1da2fcd4bf3b7a71e91231ca668/results-783132/reference-sumabs/logs/e1/1864127ae70f4754/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-sumabs-9b36f1da2fcd4bf3b7a71e91231ca668/results-783132/reference-sumabs/logs/e1/1864127ae70f4754/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-sumabs-9b36f1da2fcd4bf3b7a71e91231ca668/results-783132/reference-sumabs/logs/e1/1864127ae70f4754/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-sumabs-9b36f1da2fcd4bf3b7a71e91231ca668/results-783132/reference-sumabs/logs/e1/1864127ae70f4754/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-sumabs-9b36f1da2fcd4bf3b7a71e91231ca668/results-783132/reference-sumabs/logs/e1/1864127ae70f4754/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-sumabs-9b36f1da2fcd4bf3b7a71e91231ca668/results-783132/reference-sumabs/logs/e1/1864127ae70f4754/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.0002881328058242798, "reason": "", "score": 0.8098849676207472, "status": "valid", "times": [0.00028803200721740725, 0.00028835361003875734, 0.0002883968114852905, 0.0002881200075149536, 0.00028776159286499027], "tree_hash": "15f85cf866377de1f1e5097f88285fffa3ce030f"}, "status": "confirmed"}`.

Commit retenu après confirmation : `f4672fb4288b5f6ddb6174143d976ef0a3702d8d`.
Temps confirmé : 0.000288 s ; référence confirmée : 0.001227 s.
Réduction mesurée : 76.5%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Hierarchical fusion: partial granularity and finalization | Build a two-stage fused sum(abs(x)) with simple contiguous scalar loads and a conventional per-CTA reduction. Explore global work partitioning: vary first-stage partial count/granularity and the finalizer’s fan-in so the large input is sufficiently parallel while finalization stays cheap. Leave vectorized loads and thread/block mapping to T3. Every consumed partial must be written in the current call, and the finalizer must overwrite output. Validate all required sizes and the stated FP64 error bound; compare full-call time. |
| T2 | Single-kernel CTA aggregation with output atomics | Evaluate a distinct single-kernel alternative: reset output in the default stream, stream input once, reduce locally per CTA, then atomicAdd one CTA result to output. Explore keeping CTA atomic count modest; do not rely on scratch initialization or omit the per-call reset. Compare total time including reset and launch overhead against hierarchical candidates, and validate every required size and the FP64 tolerance. |
| T3 | Within-CTA streaming and reduction mapping | Use the two-stage fused topology as a controlled starting point. Hold global input tile boundaries, partial count, and finalizer organization fixed for each comparison; explore within-CTA streaming and reduction mapping, including multiple accumulators, suitable contiguous/vector loads, and CTA dimensions or work per thread. Handle alignment and tails for every valid input. Do not retune global partitioning or finalizer fan-in, which T1 owns. Validate all required sizes and the stated FP64 error bound, and measure full-call time. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| de3c9c834e5e486b | T1 | search | valid | 0.000459 | b30319ad8269 |
| f44a435ddec44211 | T2 | search | valid | 0.000447 | 491cc58c7849 |
| 2f1c4897b2e14825 | T3 | search | valid | 0.000295 | 89e9028ac5aa |
| 8247268c232e48cc | T2 | search | valid | 0.001554 | c8e02e650448 |
| ae1d98143ce04df2 | T1 | search | valid | 0.000473 | cae3944bd9d8 |
| 3a356f6c536e4d76 | T3 | search | valid | 0.000294 | 3e3f461ffe6f |
| 8d8b8137ccb947d5 | T2 | search | valid | 0.000344 | f7108ef097bc |
| 8546f4f034a64302 | T1 | search | valid | 0.000290 | 3040f1d26c46 |
| 8307eb041be4421a | T3 | search | valid | 0.000339 | 319b11767638 |
| 6198a8f322d8497c | Gm1 | search | valid | 0.000300 | 29697990d072 |
| f505affbf906415b | T1 | search | valid | 0.000295 | d1ae4c6a3736 |
| 1bf20829cfe547c0 | T2 | search | valid | 0.000401 | bac329e8f228 |
| a0f10ae14e88474e | T3 | search | valid | 0.000288 | 93fc08780e17 |
| 6d96df35e28240e2 | T1 | search | valid | 0.000306 | 1be021969984 |
| 63185eb286ee4951 | T3 | search | valid | 0.000482 | 34c3baad5464 |
| 367bc0a0880546cb | T1 | search | valid | 0.000461 | d32bb05ca1ca |
| 95421f9471844e38 | Gm2 | search | valid | 0.000291 | 1d853308dfc2 |
| 380f84670c614b7e | T1 | search | valid | 0.000291 | 6cbfc7c29762 |
| 09625b21746b434b | T3 | search | valid | 0.000387 | 49a69d21dbfc |
| e71a05dd193442d2 | G | postprocess | valid | 0.000305 | e4b77ff65e4a |
| 185071fd6df74577 | G | postprocess | valid | 0.000450 | 447af8ed0839 |
| 1864127ae70f4754 | G | postprocess | valid | 0.000288 | f4672fb4288b |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
