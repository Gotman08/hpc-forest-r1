# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `9f14dfff765dfd8356a4f9f0829b89405e8a34df8a77ae8ab9bfbf8e2eb0545c`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 74, "tokens_used": 6116255, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 6116255}`.
Coûts par phase : `{"search": {"slots": 63, "tokens_used": 4543888, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 4543888}, "postprocess": {"slots": 8, "tokens_used": 1572367, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1572367}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "066481b2a9884989", "outcome": {"binary_sha256": "f5043629a691f84812536445c7309f4fda62f92a50ef3a6d803909eee2558fc9", "cache_key": "d88110dfc50417f5070699484ab92997969bfceb083756a1d732accfefebecdb", "commit": "553544ecbee84ea9e69a5fce19e656ee6ed2c67b", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-7e6f5cddcd5b42a2a5f3cc063861110b/campaign/logs/e1/066481b2a9884989/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-7e6f5cddcd5b42a2a5f3cc063861110b/campaign/logs/e1/066481b2a9884989/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-7e6f5cddcd5b42a2a5f3cc063861110b/campaign/logs/e1/066481b2a9884989/confirmation/attempt-001/warmup-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-7e6f5cddcd5b42a2a5f3cc063861110b/campaign/logs/e1/066481b2a9884989/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-7e6f5cddcd5b42a2a5f3cc063861110b/campaign/logs/e1/066481b2a9884989/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-7e6f5cddcd5b42a2a5f3cc063861110b/campaign/logs/e1/066481b2a9884989/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-7e6f5cddcd5b42a2a5f3cc063861110b/campaign/logs/e1/066481b2a9884989/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/forest-app-7e6f5cddcd5b42a2a5f3cc063861110b/campaign/logs/e1/066481b2a9884989/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.003995901998132467, "reason": "", "score": 0.9067669116565603, "status": "valid", "times": [0.004007742274552584, 0.003991342149674892, 0.0040501621551811695, 0.003911731764674187, 0.004018531646579504], "tree_hash": "185cf45afb03c092c5c592c6ea793c5790c62cc0"}, "status": "confirmed"}`.

Commit retenu après confirmation : `553544ecbee84ea9e69a5fce19e656ee6ed2c67b`.
Temps confirmé : 0.003996 s ; référence confirmée : 0.038863 s.
Réduction mesurée : 89.7%. Référence conservée : non.

Mother a choisi **2 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Odd-only Eratosthenes sieve | Replace repeated per-number divisor scans with an odd-only Eratosthenes sieve sized from the runtime input. Mark composites from p*p with odd strides, sum exactly the primes through the inclusive limit, preserve argument validation and output, and measure the full implementation against the fixed benchmark while passing every supplied test. |
| T2 | Wheel-based incremental trial division | Develop and measure a distinct low-memory prime-generation alternative: enumerate candidates using a wheel that skips multiples of 2, 3, and 5, test each candidate only with previously found primes up to its square root, and accumulate the exact inclusive sum. Preserve the complete input/output contract and pass every supplied test; compare measured performance with the baseline without hard-coded answers or test-specific behavior. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 736599f93a5c4d64 | T1 | search | valid | 0.004020 | cf7af70004e9 |
| 8dddfc6b73a5417e | T2 | search | valid | 0.004200 | f678f88af145 |
| 5887b1416f08433c | T1 | search | valid | 0.003980 | 649b2783f0f7 |
| acf58c10700f4c86 | T2 | search | valid | 0.004131 | e3f192b42a52 |
| 55a8a3f965074d15 | T1 | search | valid | 0.004064 | 260a46ec11a9 |
| 9c11a7d183eb4d25 | T1 | search | valid | 0.004011 | 753de940911e |
| 5fe21186f8954287 | T1 | search | valid | 0.003991 | 9202c948dbf1 |
| 405b006b39e54c1c | T2 | search | valid | 0.004208 | 3af560e53e53 |
| acfe5f46250e4299 | T1 | search | valid | 0.004889 | 7025fff25c5a |
| 8bee816055e44dbb | T1 | search | valid | 0.004011 | ba20ff562540 |
| 04866b8ae0d0406f | T2 | search | valid | 0.004184 | 95f490387907 |
| c46c488136ab431a | T2 | search | valid | 0.004195 | b61260e992f2 |
| cba6a7a3e818414a | T1 | search | valid | 0.003952 | 63acbe0563bf |
| c8331847cef9407a | T2 | search | valid | 0.004098 | 783c8b0e4036 |
| ae458ecb97ed4b71 | T1 | search | valid | 0.003985 | 4671171de1d2 |
| 754594b594ee4b6e | T1 | search | valid | 0.004137 | 04a03b9dbb00 |
| 1da5bb23da984306 | T1 | search | valid | 0.003975 | c0366ded4f0e |
| f0443255ebfd499d | T1 | search | valid | 0.003951 | 40be6298fcd3 |
| 403481ea4a4f4b26 | T2 | search | valid | 0.004102 | deeca43a02c5 |
| 177d29c05fde48e0 | T1 | search | valid | 0.003974 | 2d243ae385b6 |
| 68ad7ac464c04e9a | T2 | search | valid | 0.004147 | d6af35f2d3b4 |
| f48dc80dc178423e | T2 | search | valid | 0.004091 | 9156f78c5951 |
| 796a2bcd2fd646db | T2 | search | valid | 0.004134 | b282ceb7dc60 |
| 2d5e7b838c5c461d | G | postprocess | valid | 0.003935 | aac7c5c84fde |
| 066481b2a9884989 | G | postprocess | valid | 0.003935 | 553544ecbee8 |

Les confirmations réexécutent la commande de test fournie, avec FOREST_PHASE=confirmation. L'application ne crée pas de cas de correction supplémentaires. Les tours de mesure sont entrelacés ; le temps porte sur la commande complète, lancement du programme compris. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
