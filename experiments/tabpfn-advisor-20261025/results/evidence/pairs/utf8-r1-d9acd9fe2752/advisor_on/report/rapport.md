# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `95aadd03bdac6c39fa8c194b787a8908f4058669914dc7c098e7361abd8c68d1`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 63, "tokens_used": 4210238, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 4210238}`.
Coûts par phase : `{"search": {"slots": 55, "tokens_used": 3552736, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3552736}, "postprocess": {"slots": 4, "tokens_used": 657502, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 657502}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "5811917bddd348d1", "outcome": {"binary_sha256": "1d5fb1fdd750337a8afd8ca8afa03777bc2171d5f59ae1b022c9c0d8146956b8", "cache_key": "cc63fdb08eb475268be17967b32e2907993fcdd16851c6b3d67127a9aaa9844b", "commit": "e0051bb094ddd135b6636d20beb93d3e7a6abf88", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r1-d9acd9fe2752/forest-app-641533551394424bb28aab1ae51ac8d4/campaign/logs/e1/5811917bddd348d1/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r1-d9acd9fe2752/forest-app-641533551394424bb28aab1ae51ac8d4/campaign/logs/e1/5811917bddd348d1/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r1-d9acd9fe2752/forest-app-641533551394424bb28aab1ae51ac8d4/campaign/logs/e1/5811917bddd348d1/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r1-d9acd9fe2752/forest-app-641533551394424bb28aab1ae51ac8d4/campaign/logs/e1/5811917bddd348d1/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r1-d9acd9fe2752/forest-app-641533551394424bb28aab1ae51ac8d4/campaign/logs/e1/5811917bddd348d1/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r1-d9acd9fe2752/forest-app-641533551394424bb28aab1ae51ac8d4/campaign/logs/e1/5811917bddd348d1/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r1-d9acd9fe2752/forest-app-641533551394424bb28aab1ae51ac8d4/campaign/logs/e1/5811917bddd348d1/confirmation/attempt-001/sample-4.log"], "mean_seconds": 5.657970122841557e-05, "reason": "", "score": 0.4692422093326617, "status": "valid", "times": [5.679445853658538e-05, 5.674788006482986e-05, 5.744237741935486e-05, 5.599225463743678e-05, 5.592153548387098e-05], "tree_hash": "2a5442fc4253e282f16cf71a9e96298e51c63747"}, "status": "confirmed"}`.

Commit retenu après confirmation : `628f20f3b6d573ee52dba8bb812eb24df8e6ed1d`.
Temps confirmé : 0.000046 s ; référence confirmée : 0.000050 s.
Réduction mesurée : 8.6%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | SIMD ASCII-run skipping with scalar fallback | Explore a vectorized ASCII-block skipper with scalar UTF-8 validation as a fallback: quickly advance over full blocks proven ASCII, then validate non-ASCII sequences without skipping bytes or assuming data patterns. Keep tails and block boundaries safe. Measure the official mixed-width workload and check ASCII and malformed inputs for exact correctness. |
| T2 | Vectorized UTF-8 validity masks | Explore block-wise SIMD validation of UTF-8 byte classes and sequence constraints, including continuation-byte placement, overlong encodings, surrogates, values above U+10FFFF, and sequences crossing block boundaries. Compare against the scalar baseline on the official workload and correctness checks; do not depend on unverified ISA support. |
| T3 | Scalar SWAR ASCII skipping and decoder | Explore a scalar SWAR ASCII fast path: use ordinary word-sized loads and bitmasks to skip words proven ASCII, then validate non-ASCII bytes with a compact DFA or exact scalar decoder. Handle alignment, tails, and boundaries safely; use alias-safe loads and never read beyond the input. This is a no-SIMD contrast to T1's vectorized skipper. Measure on the official mixed-width workload and verify ASCII and malformed-input correctness. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 31198e2c5d834654 | T1 | search | valid | 0.000058 | b93ffc630703 |
| 0c01b38dfef84bf1 | T2 | search | valid | 0.000282 | fbe3d5c4be6c |
| 93f7f940e86744f2 | T3 | search | valid | 0.000069 | 7c22b9444284 |
| 537e4e1306884764 | T3 | search | valid | 0.000061 | b67472b663c4 |
| 2199c504f71f4e9a | T2 | search | valid | 0.000060 | a4924d7d6454 |
| 6505f8e1668a493b | T2 | search | valid | 0.000088 | fe1d6a6578e0 |
| 62a73915fc104da4 | T1 | search | valid | 0.000070 | cf3cf575ba2f |
| 346d272a7c444cab | T3 | search | valid | 0.000057 | 70b96cf72128 |
| 8f813002d57d4a55 | T1 | search | valid | 0.000056 | e2b58ceb09cb |
| acd74d3aec2b49f5 | T1 | search | valid | 0.000042 | 7d64a6ecc4c8 |
| 8b7606dd56824b2c | T4 | search | valid | 0.000083 | 73e2c67f8caa |
| af50050a3e41466a | T1 | search | valid | 0.000048 | c56fb8055f94 |
| e768c364b45f421e | T4 | search | valid | 0.000082 | 5b2b070a619a |
| 26905eaef726484a | T2 | search | valid | 0.000108 | 7ca6d37881b0 |
| a615eb82fd69490e | T1 | search | valid | 0.000042 | 628f20f3b6d5 |
| 4ccd277277ba4510 | T1 | search | valid | 0.000051 | bdb36d675416 |
| 66488a67920a49d6 | T1 | search | valid | 0.000070 | 5e688a7e16ad |
| 5811917bddd348d1 | G | postprocess | valid | 0.000057 | e0051bb094dd |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
