# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `64d8eb7e906b3dc7ad32988399f30030cb833aed3a38ccb90691552f0d27e4d4`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 126, "tokens_used": 10490398, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 10490398}`.
Coûts par phase : `{"search": {"slots": 117, "tokens_used": 9662493, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 9662493}, "postprocess": {"slots": 5, "tokens_used": 827905, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 827905}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "ac4faa4ad195465e", "outcome": {"binary_sha256": "d411407d0681a6829e22d0a8d6f8cb6b95046f569852d8138470a3495717cb2c", "cache_key": "42086c127962e4b329c2b596fd72e742a94d4e0927e8022825e1864d6a0d2b47", "commit": "7cf2ba48cc9dc39c8b36d6c2a57f70948b529623", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r1-0af72bbb09b1/forest-app-1def47bda5d64b72899452db17ce1c04/campaign/logs/e1/ac4faa4ad195465e/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r1-0af72bbb09b1/forest-app-1def47bda5d64b72899452db17ce1c04/campaign/logs/e1/ac4faa4ad195465e/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r1-0af72bbb09b1/forest-app-1def47bda5d64b72899452db17ce1c04/campaign/logs/e1/ac4faa4ad195465e/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r1-0af72bbb09b1/forest-app-1def47bda5d64b72899452db17ce1c04/campaign/logs/e1/ac4faa4ad195465e/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r1-0af72bbb09b1/forest-app-1def47bda5d64b72899452db17ce1c04/campaign/logs/e1/ac4faa4ad195465e/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r1-0af72bbb09b1/forest-app-1def47bda5d64b72899452db17ce1c04/campaign/logs/e1/ac4faa4ad195465e/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r1-0af72bbb09b1/forest-app-1def47bda5d64b72899452db17ce1c04/campaign/logs/e1/ac4faa4ad195465e/confirmation/attempt-001/sample-4.log"], "mean_seconds": 8.141492137409654e-06, "reason": "", "score": 0.861687894946907, "status": "valid", "times": [8.135523909616402e-06, 8.155289805624476e-06, 8.140598732840542e-06, 8.144323731864878e-06, 8.13172450710197e-06], "tree_hash": "c05ab2306931777b474440a0e213f4495f0b6bfa"}, "status": "confirmed"}`.

Commit retenu après confirmation : `841d3a71cb76fe761f619764a4d54d95b6aa9c2f`.
Temps confirmé : 0.000007 s ; référence confirmée : 0.000051 s.
Réduction mesurée : 85.8%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Full-block SIMD UTF-8 validation | Explore a full structural SIMD validator that processes byte classes and continuation-position constraints in blocks, including correct cross-block state and tail handling. Check overlong encodings, surrogates, invalid leads, values above U+10FFFF, malformed continuations, and truncation. Build with the actual harness settings and use only instructions supported by that build and target. Compare correctness and measured n=65536 mixed-width latency with the supplied baseline; record failed approaches and measurements. |
| T2 | SIMD all-ASCII block skipping with scalar fallback | Test whether SIMD all-ASCII block detection can skip blocks while leaving every mixed block to a scalar UTF-8 validator, rather than implementing another full SIMD parser. Preserve correct handling when a multibyte sequence crosses a block boundary and for the final partial block. Measure the official valid mixed-width case and run the ASCII and malformed-input correctness checks. Support all permitted lengths, preserve the API and thread budget, and record failed approaches and measurements. |
| T3 | Scalar DFA UTF-8 validation | Explore a compact scalar DFA/state-transition-table validator as an alternative to the baseline's branch-heavy code-point cases; do not use SIMD. Enforce the complete UTF-8 scalar-value rules, including restricted second-byte ranges and incomplete final sequences, for all permitted lengths. Run the ASCII and malformed-input correctness checks and measure the official n=65536 valid mixed-width case against the baseline. Preserve the API, output behavior, and thread budget; record failed approaches and measurements. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 0215990ead76491b | T1 | search | valid | 0.000018 | ebead4c699b6 |
| 9c039461f97a49aa | T2 | search | valid | 0.000065 | b1966cf170b8 |
| ea0e04b46b4444d5 | T3 | search | valid | 0.000121 | 2b92f033879c |
| fecc62ad193a4abb | T3 | search | valid | 0.000081 | 3f6219ccdc3f |
| 2261629f7fd04245 | T1 | search | valid | 0.000010 | 042d37036f12 |
| 7035843afab94b95 | T4 | search | valid | 0.000011 | 301683700161 |
| 42f63128cfe84080 | T2 | search | valid | 0.000058 | b183dcb5b90a |
| ed6bb83819e44440 | T3 | search | valid | 0.000080 | 929525e0065c |
| ddf6e6de7e884598 | Gm1 | search | valid | 0.000013 | 413d09a73adb |
| dc845f323d024f5f | T4 | search | valid | 0.000016 | 73d3153816b6 |
| 868c48765e1a4055 | T1 | search | valid | 0.000015 | bf1802f715d5 |
| f71174cd1b9847ab | T2 | search | valid | 0.000056 | 6ae3f2e54700 |
| 477580f549fa4bf1 | T4 | search | valid | 0.000009 | 4c8934fbe5aa |
| 3a7b2bae2b694ee0 | T1 | search | valid | 0.000012 | a0b84a2d532b |
| d7c900beb93e43aa | T3 | search | valid | 0.000085 | 5ce18477a1b9 |
| 9db76a4bdcf74c37 | T2 | search | valid | 0.000051 | 797f0b964105 |
| 25d8b7fff4b94441 | T4 | search | valid | 0.000009 | 65f657d31bca |
| c664cb8ce72746dc | T1 | search | valid | 0.000009 | f0c93dba2fc3 |
| 99e881e9ec0d4c3a | T3 | search | valid | 0.000039 | ba721de255de |
| cf4f8c8179f84ed5 | T1 | search | valid | 0.000014 | c809cf80d2dc |
| 1c91574e69584876 | T1 | search | valid | 0.000011 | f25b79f824ba |
| 2d8e426db3974ab4 | T1 | search | valid | 0.000008 | e003842bb08f |
| 8d5abdb8224742c8 | T4 | search | valid | 0.000009 | 03d37ff5e1f6 |
| ee933394d253403d | T1 | search | valid | 0.000009 | 3a1ac3dc81f2 |
| bacb3627d7194386 | T1 | search | valid | 0.000011 | 7f3d0198eada |
| bc848e1e55364988 | T1 | search | valid | 0.000012 | cbf726310c4d |
| 48705ac3c51d40b3 | T1 | search | valid | 0.000009 | 12230c8dba36 |
| 7eb7a8f56ecc42bf | T1 | search | valid | 0.000013 | ec21e0427303 |
| 52a836f41afc41b7 | T1 | search | valid | 0.000010 | a4b869509577 |
| 0842c8732c54471f | T1 | search | valid | 0.000008 | bdda182cc18c |
| b83c62df8df34535 | T1 | search | valid | 0.000012 | c8129dfd6b43 |
| 825d6b6c6a2a46c7 | T1 | search | valid | 0.000007 | 841d3a71cb76 |
| 15f639693e254db6 | T1 | search | valid | 0.000011 | 23cd0dcc94e1 |
| b143ce49c4c14c09 | T1 | search | valid | 0.000007 | 28a022d14d92 |
| ac4faa4ad195465e | G | postprocess | valid | 0.000008 | 7cf2ba48cc9d |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
