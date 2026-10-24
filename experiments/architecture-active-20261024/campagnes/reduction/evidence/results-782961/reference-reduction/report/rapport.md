# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `867a3d0b118f14e9f1a238105361b4618c1df0c80a82551602702f1ff71d5d0b`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 38, "tokens_used": 2682509, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2682509}`.
Coûts par phase : `{"search": {"slots": 30, "tokens_used": 1715116, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1715116}, "postprocess": {"slots": 5, "tokens_used": 967393, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 967393}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "fce07c6261534d76", "outcome": {"binary_sha256": "12d85209ea1c494931f0b8c733759d65459b64f3309809854a947ef3219498f1", "cache_key": "939c394ff3ede1193c69b0a01b5a166271f16d120f631cf33bbc864b3b801a47", "commit": "f7403d982f28d389808e5b89f5394ab2584ae6a5", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-reduction-b7e5d3b25b6d454a991f93e394a5282c/results-782961/reference-reduction/logs/e1/fce07c6261534d76/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-reduction-b7e5d3b25b6d454a991f93e394a5282c/results-782961/reference-reduction/logs/e1/fce07c6261534d76/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-reduction-b7e5d3b25b6d454a991f93e394a5282c/results-782961/reference-reduction/logs/e1/fce07c6261534d76/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-reduction-b7e5d3b25b6d454a991f93e394a5282c/results-782961/reference-reduction/logs/e1/fce07c6261534d76/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-reduction-b7e5d3b25b6d454a991f93e394a5282c/results-782961/reference-reduction/logs/e1/fce07c6261534d76/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-reduction-b7e5d3b25b6d454a991f93e394a5282c/results-782961/reference-reduction/logs/e1/fce07c6261534d76/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-reduction-b7e5d3b25b6d454a991f93e394a5282c/results-782961/reference-reduction/logs/e1/fce07c6261534d76/confirmation/attempt-001/sample-4.log"], "mean_seconds": 6.415616035461426e-06, "reason": "", "score": 0.8788524772698734, "status": "valid", "times": [6.339200139045715e-06, 6.510720252990722e-06, 6.228479743003845e-06, 6.4134401082992556e-06, 6.586239933967591e-06], "tree_hash": "c97260f2cf171e17c3eda16108f293405d90d723"}, "status": "confirmed"}`.

Commit retenu après confirmation : `23e3eb7519c42bddfd6183824ad2b92653200597`.
Temps confirmé : 0.000006 s ; référence confirmée : 0.000047 s.
Réduction mesurée : 86.4%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Large-input hierarchical reduction and warp/block reduction costs | In src/candidate.cu, explore large-input hierarchical reduction for n=4194304. Replace the current modulo-based interleaved reduction and repeated block-wide synchronization with an efficient warp/block reduction approach, while having CTAs accumulate multiple values per thread from coalesced, disjoint input tiles. Write partials to bounded scratch and reduce them directly to out. Tune tile and block configuration; compare a two-stage path with an additional final reduction stage if the partial count makes a single final CTA inefficient. Cover all legal sizes with bounded reads, exact int32 output, unchanged ABI/default stream, and a correct fallback. Compare all checks and repeated timings against the baseline. |
| T2 | Small-input direct-output reduction and launch crossover | In src/candidate.cu, explore a generic size-based single-CTA reduction that writes directly to out for small inputs, eliminating intermediate partials and the final device copy where beneficial. Measure crossover thresholds rather than hardcoding test sizes. Explicitly compare against the baseline n=1 device-to-device copy path, which launches no kernel, and retain whichever path measures better. Keep a correct fallback for larger inputs and preserve correctness, bounded reads, exact int32 results, ABI, and default-stream behavior for every legal size. Compare all checks and repeated timings. |
| T3 | Large-input atomic final aggregation | In src/candidate.cu, evaluate a large-input alternative with an ordered output-zeroing kernel followed by a multi-CTA grid-stride reduction; each CTA reduces its own values and performs one int32 atomicAdd to out. Tune CTA count/work per CTA to balance input throughput against contention. Do not rely on initialized scratch or unsafe inter-block initialization. Preserve exact results, bounds, ABI, default-stream ordering, and a correct fallback for other legal sizes; compare all checks and repeated timings against the baseline and hierarchical approach. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| c799f88db22c44fc | T1 | search | valid | 0.000009 | e254035503f4 |
| 761d3dc0cfe94314 | T2 | search | valid | 0.000046 | 936437275f3a |
| f9b237d912eb46da | T3 | search | valid | 0.000008 | ac74f2ea846f |
| e5f62ce3f3b9407c | T2 | search | valid | 0.000047 | da39b622e717 |
| 6ce6317ff2354659 | T1 | search | valid | 0.000007 | 87385cb6224a |
| f24ffbf8905c4409 | T3 | search | valid | 0.000006 | 23e3eb7519c4 |
| 26e0ee59d90e4de3 | T2 | search | valid | 0.000047 | f378153f7f23 |
| c7c6213440cf4ef2 | T3 | search | valid | 0.000015 | b9d74682cdaf |
| ea1b3e5f969947dc | Gm1 | search | valid | 0.000007 | 9583b9f51ee3 |
| 247b9e5d67554ac4 | T1 | search | valid | 0.000009 | 2f637d7955a3 |
| 0baaf9e2f2294351 | T3 | search | valid | 0.000008 | 058fd2ea710b |
| 85625693994647e1 | T3 | search | valid | 0.000008 | 88d1901c47c2 |
| cd22f6eecbcf4be0 | T3 | search | valid | 0.000011 | 8b3d83588c6c |
| fce07c6261534d76 | G | postprocess | valid | 0.000006 | f7403d982f28 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
