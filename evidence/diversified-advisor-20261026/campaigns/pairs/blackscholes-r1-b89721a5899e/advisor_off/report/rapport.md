# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `941a1ab838a55896c90ea54a3c3bc8a17bc65ce9bf31d24652cf496afd31aec6`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 130, "tokens_used": 10315738, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 10315738}`.
Coûts par phase : `{"search": {"slots": 117, "tokens_used": 8542009, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 8542009}, "postprocess": {"slots": 10, "tokens_used": 1773729, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1773729}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "980afef902e14990", "outcome": {"binary_sha256": "3c349da95ec47354d6ef81080edce32624a538339678376099fec5b266e5dc6c", "cache_key": "0bbe5a4d39c3a84d131741e3bbd833f70342bbcb1ad4223e1a47b4fa79c75d0c", "commit": "229120c801527671ce3df6a1d3786eab9d0a310c", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-blackscholes-r1-b89721a5899e/forest-app-0fd8ba16ae7941f89ed80f64b9e9a7f4/campaign/logs/e1/980afef902e14990/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-blackscholes-r1-b89721a5899e/forest-app-0fd8ba16ae7941f89ed80f64b9e9a7f4/campaign/logs/e1/980afef902e14990/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-blackscholes-r1-b89721a5899e/forest-app-0fd8ba16ae7941f89ed80f64b9e9a7f4/campaign/logs/e1/980afef902e14990/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-blackscholes-r1-b89721a5899e/forest-app-0fd8ba16ae7941f89ed80f64b9e9a7f4/campaign/logs/e1/980afef902e14990/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-blackscholes-r1-b89721a5899e/forest-app-0fd8ba16ae7941f89ed80f64b9e9a7f4/campaign/logs/e1/980afef902e14990/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-blackscholes-r1-b89721a5899e/forest-app-0fd8ba16ae7941f89ed80f64b9e9a7f4/campaign/logs/e1/980afef902e14990/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-blackscholes-r1-b89721a5899e/forest-app-0fd8ba16ae7941f89ed80f64b9e9a7f4/campaign/logs/e1/980afef902e14990/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.0002354577171700595, "reason": "", "score": 0.9141632491667537, "status": "valid", "times": [0.0002357181333067805, 0.0002356307863627529, 0.0002352612961751899, 0.0002354132581698645, 0.0002352651118357097], "tree_hash": "68d55f023e5701e96d322aa54d054462559af55d"}, "status": "confirmed"}`.

Commit retenu après confirmation : `229120c801527671ce3df6a1d3786eab9d0a310c`.
Temps confirmé : 0.000235 s ; référence confirmée : 0.002508 s.
Réduction mesurée : 90.6%. Référence conservée : non.

Mother a choisi **2 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | OpenMP parallelization of the scalar Black-Scholes loop | Isolate thread-level throughput: compare the unchanged scalar Black-Scholes body with a static OpenMP loop, using no more workers than the positive threads budget. Use the serial path for a one-thread budget; if considering a parallelization threshold, base it generically on n rather than timed values. Do not add hand-written SIMD or alter the math. Write every output element and preserve correctness for all valid inputs and sizes. Measure correctness and wall time at both timed sizes and thread budgets, including the serial-versus-parallel crossover. |
| T2 | SIMD vectorization of the Black-Scholes math kernel | Isolate within-core SIMD by keeping execution single-threaded (within the threads budget) and outer-loop scheduling unchanged. Contrast compiler-supported vectorization/vector-math of the existing FP32 formula with an explicit SIMD kernel where supported by the official build and target; do not assume particular compiler flags or vector-library availability. Preserve the supplied CND approximation and validate any changed operation order or math approximation against the fixed tolerance across valid inputs, using scalar handling where necessary. Do not specialize to timed values. Measure correctness and wall time at both timed sizes and thread budgets; report any compile/build constraints and keep these results distinct from threaded speedups. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| de42fb9e1fd74115 | T1 | search | valid | 0.001277 | 2313d75ad312 |
| 6959a9c7bf0a4bec | T2 | search | valid | 0.002566 | 9d96cfb5850c |
| 9b59ae2e427d4f88 | T1 | search | valid | 0.001766 | de4033a973c6 |
| da5e8f83e5f74d03 | T2 | search | valid | 0.001869 | 53222895a6aa |
| 2f50f7a208bf4b41 | T3 | search | valid | 0.001221 | 9f9eb8476283 |
| e7145681779341ed | T1 | search | valid | 0.001489 | bc80126ef58c |
| 156b2c79c0b54a37 | Gm1 | search | valid | 0.001069 | 18c6cb04d2f4 |
| fb00906464234c1a | T3 | search | valid | 0.001224 | 1b7ed16f5b67 |
| c5073d95eb214cf1 | Gm2 | search | valid | 0.001045 | ac749c2a01cd |
| 1cfa900a14454aea | T2 | search | valid | 0.001232 | e2772436107a |
| b79ece7b96a24b40 | T4 | search | valid | 0.001284 | 608f7a227b1b |
| bbf494179ab041d8 | T3 | search | valid | 0.001222 | 1301365152a0 |
| 4a0cbbc4cf944060 | T2 | search | valid | 0.000482 | 901e213c78ec |
| 9c9b920123034f07 | T4 | search | valid | 0.001330 | 5d19a27a307e |
| 1322f02c92904489 | T4 | search | valid | 0.000905 | f3eedefec008 |
| 225fa691c1704ab8 | T3 | search | valid | 0.001218 | 63789b37be6d |
| dec788f2eb3e4f8b | T4 | search | valid | 0.001301 | 31ac4df59e6e |
| 3983958fcc7247b1 | T2 | search | valid | 0.002486 | 725591795b3d |
| f1647cb71fee44ad | Gm3 | search | valid | 0.000245 | 45677c959960 |
| 35178f347865402b | T3 | search | valid | 0.001221 | a108287815bf |
| 9a9a8a9c82bf41d1 | T4 | search | valid | 0.001314 | 784990e4b461 |
| b37353dcca8943b3 | T2 | search | valid | 0.000680 | 5f4a0ac7e7a4 |
| 8c477cce45b34f73 | T3 | search | valid | 0.001233 | 298a6fa9a0bf |
| 1e2be8f59c314398 | T4 | search | valid | 0.001076 | 8b3e370adc49 |
| ace9b8e395f442d4 | T5 | search | valid | 0.000341 | 6bbd4f980928 |
| cc51b6dd13884929 | T2 | search | valid | 0.001011 | d4b483eecc13 |
| 7d263e1abab746b9 | T5 | search | valid | 0.000342 | 8af04942602a |
| 56ab8eeccf164d27 | T5 | search | valid | 0.000291 | a192717405a2 |
| fe50d9f0089b416e | T3 | search | valid | 0.001221 | ca71536e24d3 |
| 2d1b1f5c69c84e74 | T4 | search | valid | 0.000899 | 7aebdb42a99c |
| e916991ce3ce416c | T5 | search | valid | 0.000343 | c9fbc7f65f88 |
| 0d71ae623b4a45c1 | T2 | search | valid | 0.001731 | 5bb88563fd4c |
| dbb2adea27e241da | T2 | search | valid | 0.001890 | 975af3ec3e6b |
| c44a0903278a4920 | T5 | search | valid | 0.000276 | 0c12b599bd86 |
| bf1ce8ef35dd4a7f | T5 | search | valid | 0.000342 | dea3ed1d5bb5 |
| a4b251c848554f25 | T5 | search | valid | 0.000384 | 5b8e8357d0de |
| e5c0e484d0de451e | G | postprocess | valid | 0.000238 | fe8806efa521 |
| 980afef902e14990 | G | postprocess | valid | 0.000235 | 229120c80152 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
