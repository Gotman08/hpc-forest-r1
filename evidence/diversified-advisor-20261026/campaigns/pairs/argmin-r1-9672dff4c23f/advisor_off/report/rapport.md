# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `7f3e75db8591a4422e3bb3b057806bf887c5ca526fe0f46381ff26dc0761fb8c`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 89, "tokens_used": 5819836, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 5819836}`.
Coûts par phase : `{"search": {"slots": 75, "tokens_used": 4227105, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 4227105}, "postprocess": {"slots": 10, "tokens_used": 1592731, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1592731}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "8151232fc5874839", "outcome": {"binary_sha256": "165a572fb12c5c269630a9e252da33b83ecdbdc21e9ec4d143d350e05e4cfd30", "cache_key": "68a395d1c86479001ce5fd9bd3442d81d18bfc8ef077a2be571eeaa40c11b235", "commit": "6e0152ce48128c1c47600e6160785bbeca198695", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-argmin-r1-9672dff4c23f/forest-app-2f6609520bf946f69156e80b98eddad4/campaign/logs/e1/8151232fc5874839/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-argmin-r1-9672dff4c23f/forest-app-2f6609520bf946f69156e80b98eddad4/campaign/logs/e1/8151232fc5874839/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-argmin-r1-9672dff4c23f/forest-app-2f6609520bf946f69156e80b98eddad4/campaign/logs/e1/8151232fc5874839/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-argmin-r1-9672dff4c23f/forest-app-2f6609520bf946f69156e80b98eddad4/campaign/logs/e1/8151232fc5874839/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-argmin-r1-9672dff4c23f/forest-app-2f6609520bf946f69156e80b98eddad4/campaign/logs/e1/8151232fc5874839/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-argmin-r1-9672dff4c23f/forest-app-2f6609520bf946f69156e80b98eddad4/campaign/logs/e1/8151232fc5874839/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-argmin-r1-9672dff4c23f/forest-app-2f6609520bf946f69156e80b98eddad4/campaign/logs/e1/8151232fc5874839/confirmation/attempt-001/sample-4.log"], "mean_seconds": 1.0548177814691521e-06, "reason": "", "score": 0.8941348399403454, "status": "valid", "times": [1.0567696430331468e-06, 1.0553078281660306e-06, 1.0536267978526709e-06, 1.0544760346407558e-06, 1.0539086036531562e-06], "tree_hash": "7b16c27af7d7b134a218944dd13bed0bbc9ddb4c"}, "status": "confirmed"}`.

Commit retenu après confirmation : `cfe81a736846a5b94cc88dc3ea33e6c04a90552a`.
Temps confirmé : 0.000001 s ; référence confirmée : 0.000009 s.
Réduction mesurée : 88.3%. Référence conservée : non.

Mother a choisi **2 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Explicit SIMD argmin reduction | Explore an explicitly vectorized argmin scan using x86 SIMD intrinsics where supported by the build target. Reduce values and recover the smallest matching index correctly; handle tails and all valid n. Compare viable vector widths or reduction strategies using the official correctness and timing protocol. Do not rely on test-value assumptions or exceed the one-thread budget. |
| T2 | Scalar best-value and dependency-chain reduction | First test a scalar rewrite that keeps the best value in a register alongside its index, rather than comparing through the baseline's changing a[j] expression; preserve strict-less-than updates so ties select the earliest index. Then explore loop forms and modest independent partial accumulators/unrolling, merging partial results by value and then smallest index. Use no explicit x86 intrinsics or parallel execution. Validate all valid sizes and input patterns, and compare official timings at both timed sizes; compiler transformation of the baseline is unknown, so judge by measured results. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| d30a0d594fe842b4 | T1 | search | valid | 0.000003 | 676d57e97626 |
| 2ed6dafb7938445b | T2 | search | valid | 0.000009 | bf835c427e8e |
| 9b4b376bab34407e | T2 | search | valid | 0.000004 | e80b52973336 |
| b129b7284d664c4a | T1 | search | valid | 0.000001 | d62b0fadc276 |
| 42d1fb1e2202461f | T2 | search | valid | 0.000005 | 49ee829eb744 |
| 07d45883e07a46ed | T1 | search | valid | 0.000001 | d32a928c3dc5 |
| bd9889d906584c66 | T2 | search | valid | 0.000004 | 35cdd4e1cabb |
| 993466a0d0814605 | T2 | search | valid | 0.000004 | 4d0175cf6412 |
| 8219ccba103147ce | T1 | search | valid | 0.000001 | 576dd35e4354 |
| 1d2a975e97d34452 | Gm1 | search | valid | 0.000001 | cfe81a736846 |
| 427d526ccf2d4601 | T2 | search | valid | 0.000004 | f4f23768e37e |
| 423673b4cff24d44 | T1 | search | valid | 0.000007 | e37b52be8c97 |
| f95ec23bb9b4467e | T2 | search | valid | 0.000010 | 9d1969796d7e |
| 6bb6ab305e2c46ac | T2 | search | valid | 0.000005 | 641d042cdb3e |
| bff8d398b14d464c | T1 | search | valid | 0.000002 | 51c0c1e87229 |
| 8f10dd90aca748c8 | T2 | search | valid | 0.000009 | 53ab84e202b1 |
| de7d5ff03cf741e9 | T1 | search | valid | 0.000001 | d03c189b7320 |
| 099c54def073419d | T2 | search | valid | 0.000004 | 00704d328db6 |
| c7f759fda100457b | T1 | search | valid | 0.000003 | d20c0dd6b4da |
| 33bf4a41a21e411b | T2 | search | valid | 0.000005 | 5e3280332490 |
| fb79237784f34898 | T2 | search | valid | 0.000004 | f5b663e56594 |
| 8094511fbeb44c1a | T2 | search | valid | 0.000004 | 8ac7561ff30b |
| f534dd17936d4ed9 | G | postprocess | valid | 0.000002 | d1d99e5f47a7 |
| 8151232fc5874839 | G | postprocess | valid | 0.000001 | 6e0152ce4812 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
