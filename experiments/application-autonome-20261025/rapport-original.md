# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `4cd35aff37d062615a27230b6712e709ad01324262bb65b1832ec96941379ee0`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 13, "tokens_used": 251677, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 251677}`.
Coûts par phase : `{"search": {"slots": 5, "tokens_used": 49262, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 49262}, "postprocess": {"slots": 5, "tokens_used": 202415, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 202415}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "28ac987f0b834a01", "outcome": {"binary_sha256": "5070c0b21006aa320378cf85f07118231d25653db74bbedfed4fd4594c1daec6", "cache_key": "659250b3f5ce84bda13f07ce37868c71f72d1cca681b1a441adc86d5a0d7d1fa", "commit": "febb91f3c4a952bdc4df1a6ee6edf507a76f3cc9", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-ef67876d343b44979c70a5ece22f593c/campaign/logs/e1/28ac987f0b834a01/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-ef67876d343b44979c70a5ece22f593c/campaign/logs/e1/28ac987f0b834a01/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-ef67876d343b44979c70a5ece22f593c/campaign/logs/e1/28ac987f0b834a01/confirmation/attempt-001/warmup-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-ef67876d343b44979c70a5ece22f593c/campaign/logs/e1/28ac987f0b834a01/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-ef67876d343b44979c70a5ece22f593c/campaign/logs/e1/28ac987f0b834a01/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-ef67876d343b44979c70a5ece22f593c/campaign/logs/e1/28ac987f0b834a01/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-ef67876d343b44979c70a5ece22f593c/campaign/logs/e1/28ac987f0b834a01/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-ef67876d343b44979c70a5ece22f593c/campaign/logs/e1/28ac987f0b834a01/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.004022610560059548, "reason": "", "score": 0.9061303900740245, "status": "valid", "times": [0.004101608879864216, 0.003877929411828518, 0.00394141860306263, 0.004035277757793665, 0.004156818147748709], "tree_hash": "54a97cb01ff50273fc70493ad48b15f6dc652948"}, "status": "confirmed"}`.

Commit retenu après confirmation : `febb91f3c4a952bdc4df1a6ee6edf507a76f3cc9`.
Temps confirmé : 0.004023 s ; référence confirmée : 0.038831 s.
Réduction mesurée : 89.6%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Odd-only sieve representation and loop optimization | Starting from the odd-only Eratosthenes seed, investigate sieve storage and marking-loop variants (such as byte versus packed flags and efficient summation). Preserve the complete input/output contract and the 0–200000 range. Run the supplied correctness tests and fixed benchmark; report measured comparisons and keep only validated improvements. |
| T2 | Linear-sieve algorithm comparison | Implement and measure an independent Euler/linear sieve that accumulates the exact prime sum for every valid bound. Compare it with the current seed on the supplied tests and fixed benchmark; retain it only if evidence shows a valid speed improvement, without specializing to benchmark values. |
| T3 | Small-bound primality path and general crossover | Explore a separate square-root-bounded primality/divisor-enumeration path, optionally paired with the sieve only at a principled measured crossover for small limits. Preserve correctness for every valid input; do not choose a threshold solely to fit the fixed 20000 benchmark. Run supplied tests and report benchmark evidence before retaining any change. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| e465dafb1ade4e02 | T1 | search | valid | 0.004020 | 238eeb734973 |
| 6dc6cc188dd3479c | T2 | search | valid | 0.004059 | e35ec84f85c3 |
| 71f2dff327be43c6 | T3 | search | valid | 0.004528 | 736ebee26d73 |
| 28ac987f0b834a01 | G | postprocess | valid | 0.003976 | febb91f3c4a9 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
