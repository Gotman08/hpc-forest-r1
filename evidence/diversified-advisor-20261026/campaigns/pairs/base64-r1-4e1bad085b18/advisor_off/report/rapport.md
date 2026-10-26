# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `cef59c871cae54570df451584a1414ddb8c47e064aa17fd65fcaafe5841f19a0`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 66, "tokens_used": 5245844, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 5245844}`.
Coûts par phase : `{"search": {"slots": 59, "tokens_used": 4662964, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 4662964}, "postprocess": {"slots": 4, "tokens_used": 582880, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 582880}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "88243824340141ec", "outcome": {"binary_sha256": "2fe3a506eb5fb002ba052a8e2709600ad8089801e02f00ff13280f231593274d", "cache_key": "6cbeb366ee46bc831510520902961633d167970d0b2bb5f3115f024ed1fa94e1", "commit": "9e48962229b7eab21fd9c6e94e80cf5cf894cd2c", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-base64-r1-4e1bad085b18/forest-app-dc2ddaa6ac4a41aa8864d09c9dc7d5f3/campaign/logs/e1/88243824340141ec/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-base64-r1-4e1bad085b18/forest-app-dc2ddaa6ac4a41aa8864d09c9dc7d5f3/campaign/logs/e1/88243824340141ec/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-base64-r1-4e1bad085b18/forest-app-dc2ddaa6ac4a41aa8864d09c9dc7d5f3/campaign/logs/e1/88243824340141ec/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-base64-r1-4e1bad085b18/forest-app-dc2ddaa6ac4a41aa8864d09c9dc7d5f3/campaign/logs/e1/88243824340141ec/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-base64-r1-4e1bad085b18/forest-app-dc2ddaa6ac4a41aa8864d09c9dc7d5f3/campaign/logs/e1/88243824340141ec/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-base64-r1-4e1bad085b18/forest-app-dc2ddaa6ac4a41aa8864d09c9dc7d5f3/campaign/logs/e1/88243824340141ec/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-base64-r1-4e1bad085b18/forest-app-dc2ddaa6ac4a41aa8864d09c9dc7d5f3/campaign/logs/e1/88243824340141ec/confirmation/attempt-001/sample-4.log"], "mean_seconds": 2.7853554672472006e-06, "reason": "", "score": 0.901456625076556, "status": "valid", "times": [2.783829703709849e-06, 2.7832370444834995e-06, 2.786334157012814e-06, 2.7845070296830734e-06, 2.7888694013467664e-06], "tree_hash": "0faced3a8a3f2a35931f1404835feb3c2f7f0215"}, "status": "confirmed"}`.

Commit retenu après confirmation : `9e48962229b7eab21fd9c6e94e80cf5cf894cd2c`.
Temps confirmé : 0.000003 s ; référence confirmée : 0.000025 s.
Réduction mesurée : 89.1%. Référence conservée : non.

Mother a choisi **2 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | AVX2 bulk Base64 decoding | Explore an explicit AVX2 bulk decoder for valid Base64 quartets: vectorize character-to-sextet mapping and packing into decoded bytes, while handling the final padded quartet and any remainder without out-of-bounds reads or writes. Keep a generic path for sizes too small for a vector block. Preserve the output layout and single-thread budget. Measure correctness and wall-clock time at both official sizes; retain the approach only if its measured gain justifies its overhead. |
| T2 | Direct scalar quartet decoder with exact stores | Test a deliberately distinct scalar alternative to the baseline’s 8-character lookup-and-pack fast loop: decode interior valid input in four-character quartets, use the valid-input contract to avoid redundant per-symbol validity branches, and write exactly three decoded bytes per complete quartet. Handle the final padded quartet and all generic remainders correctly, compute and write the count at offset 0, and write decoded bytes from offset 16. Do not assume output alignment or modify reserved bytes. Compare against the baseline at both official sizes; this is a hypothesis, and retain it only if correctness and measured wall-clock results justify it. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| b4e83a2682fb4b95 | T1 | search | valid | 0.000017 | ee870b64177a |
| f15f65c088df4681 | T2 | search | valid | 0.000020 | c5812f4aeea5 |
| dacd960d0c7849c0 | T2 | search | valid | 0.000026 | 1169de5200e5 |
| 6da857636d134f07 | T2 | search | valid | 0.000020 | 606b20e79bbb |
| 8110805c4ffa4761 | Gm1 | search | valid | 0.000017 | bbfebf7ae002 |
| f7b8fe4bb64246be | T1 | search | valid | 0.000008 | ab7a5198dbc9 |
| fb917eb2041d4901 | T2 | search | valid | 0.000021 | f594113d6aeb |
| fadf0b64ebc64af0 | T1 | search | incorrect | — | 97b80a8b08ab |
| 4f6f02d281c64435 | T1 | search | valid | 0.000008 | 79cd86e92995 |
| 6723f08171274757 | T1 | search | incorrect | — | 89bc73fc483c |
| 8570482e1f964c91 | T1 | search | valid | 0.000011 | 0037bd995f03 |
| 396149ad797a43a7 | T1 | search | valid | 0.000007 | 031ef0b5b644 |
| ccad60c9bd9a44d8 | T1 | search | valid | 0.000004 | addd8841229f |
| 4f656e86a64445df | T1 | search | incorrect | — | d56650bf1860 |
| f562b8609f834323 | T1 | search | valid | 0.000006 | 8f0e1e6b592d |
| 1a33eb9ab859452e | T1 | search | valid | 0.000003 | 93cffc0f976c |
| 80800882d0e24940 | T1 | search | valid | 0.000003 | 8878ef1e4371 |
| 88243824340141ec | G | postprocess | valid | 0.000003 | 9e48962229b7 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
