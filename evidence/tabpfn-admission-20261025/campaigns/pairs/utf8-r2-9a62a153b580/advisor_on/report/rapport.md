# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `941ecc05255d0bd1ccc531ca7dd2a71cd304146ab2041111752e97db1219ef25`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 43, "tokens_used": 3479329, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3479329}`.
Coûts par phase : `{"search": {"slots": 29, "tokens_used": 1700055, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1700055}, "postprocess": {"slots": 11, "tokens_used": 1779274, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1779274}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "a465ee1189e240da", "outcome": {"binary_sha256": "de56d3af5c4ec7b4410a1da9e272c3eb7b822bdd1fa2490f89220a18b1906835", "cache_key": "5c79ada903f9ca61387ecd48ed91ac134b8d02314cf302f9291aa4aef64d511c", "commit": "bdd2024ebd34dc7bbefe39c282c4e566796e0f90", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r2-9a62a153b580/forest-app-758c596058854480a44af79b178504f7/campaign/logs/e1/a465ee1189e240da/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r2-9a62a153b580/forest-app-758c596058854480a44af79b178504f7/campaign/logs/e1/a465ee1189e240da/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r2-9a62a153b580/forest-app-758c596058854480a44af79b178504f7/campaign/logs/e1/a465ee1189e240da/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r2-9a62a153b580/forest-app-758c596058854480a44af79b178504f7/campaign/logs/e1/a465ee1189e240da/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r2-9a62a153b580/forest-app-758c596058854480a44af79b178504f7/campaign/logs/e1/a465ee1189e240da/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r2-9a62a153b580/forest-app-758c596058854480a44af79b178504f7/campaign/logs/e1/a465ee1189e240da/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r2-9a62a153b580/forest-app-758c596058854480a44af79b178504f7/campaign/logs/e1/a465ee1189e240da/confirmation/attempt-001/sample-4.log"], "mean_seconds": 1.604298839602464e-05, "reason": "", "score": 0.7551870041796689, "status": "valid", "times": [1.604904791970212e-05, 1.605978776104905e-05, 1.603915638659542e-05, 1.6038329941860476e-05, 1.602861997091614e-05], "tree_hash": "ade1fa638048463782e28855bb9c5f823edf029c"}, "status": "confirmed"}`.

Commit retenu après confirmation : `11672c5516af73daf4192b626293a69a21d38a30`.
Temps confirmé : 0.000016 s ; référence confirmée : 0.000049 s.
Réduction mesurée : 67.6%. Référence conservée : non.

Mother a choisi **2 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Compare full SIMD and hybrid ASCII-block UTF-8 validation | Compare two single-threaded SIMD strategies on the official valid mixed-width performance case: full byte-class/neighbor-mask validation, and bounded SIMD ASCII-block skipping with scalar UTF-8 parsing for non-ASCII regions. Handle vector boundaries and tails safely, and enforce all UTF-8 scalar-value rules, including special second-byte limits. Preserve the ABI, overwrite the full output on every call, respect the thread budget, and never overread. Check which instructions are supported by the actual build target rather than assuming a specific ISA. Report timings and correctness for the required valid, ASCII, malformed, and truncated cases for each strategy. |
| T2 | Scalar parser and control-flow optimization | Explore a scalar-only alternative to the baseline’s code-point loop, focusing on streamlined pointer/bounds handling and lower-overhead scalar classification or state transitions. Do not use SIMD or parallelism, so this remains distinct from the vectorized search. Modify only src/candidate.cpp; preserve the ABI, full output write, and correctness for all valid and malformed inputs. Measure against the supplied baseline and report failed attempts as well as the strongest validated candidate. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 8f367281d6b846ad | T1 | search | valid | 0.000016 | 11672c5516af |
| bb7a3e51e18d4e45 | T2 | search | valid | 0.000052 | fd3944600802 |
| 2c3e813ad5ce49a2 | T2 | search | valid | 0.000047 | 1664cf3b6aff |
| bfa5f3ad8bde4976 | Gm1 | search | valid | 0.000046 | 1196c8c76129 |
| 104ba72df0ba4882 | T1 | search | valid | 0.000057 | 8089ee46cf15 |
| d1e3b3339a114e4c | G | postprocess | valid | 0.000019 | 7903729c3683 |
| abacfc3ffb1644c9 | G | postprocess | valid | 0.000016 | fe088c77a854 |
| a465ee1189e240da | G | postprocess | valid | 0.000016 | bdd2024ebd34 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
