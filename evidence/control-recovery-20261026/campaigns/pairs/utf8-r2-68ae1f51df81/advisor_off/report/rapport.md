# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `29deeb40d030da4ee24c4c323c8f4c21234e051938821c47eb46cb35c08d7be7`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 153, "tokens_used": 11284834, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 11284834}`.
Coûts par phase : `{"search": {"slots": 144, "tokens_used": 10413453, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 10413453}, "postprocess": {"slots": 5, "tokens_used": 871381, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 871381}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "5ea74e4d9a194f70", "outcome": {"binary_sha256": "66355163c7f413a32d5b82625fb7406653b7676edb61e3200950bc9ec059c63d", "cache_key": "5edf4f411404f7c67edb5dcac1c1d016f202c277713400fca61b059b4df8ee55", "commit": "e6360fbdf37dc2b3911b417ad9f42877df613427", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r2-68ae1f51df81/forest-app-16871baed54247d59639e2a4e0913f31/campaign/logs/e1/5ea74e4d9a194f70/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r2-68ae1f51df81/forest-app-16871baed54247d59639e2a4e0913f31/campaign/logs/e1/5ea74e4d9a194f70/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r2-68ae1f51df81/forest-app-16871baed54247d59639e2a4e0913f31/campaign/logs/e1/5ea74e4d9a194f70/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r2-68ae1f51df81/forest-app-16871baed54247d59639e2a4e0913f31/campaign/logs/e1/5ea74e4d9a194f70/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r2-68ae1f51df81/forest-app-16871baed54247d59639e2a4e0913f31/campaign/logs/e1/5ea74e4d9a194f70/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r2-68ae1f51df81/forest-app-16871baed54247d59639e2a4e0913f31/campaign/logs/e1/5ea74e4d9a194f70/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r2-68ae1f51df81/forest-app-16871baed54247d59639e2a4e0913f31/campaign/logs/e1/5ea74e4d9a194f70/confirmation/attempt-001/sample-4.log"], "mean_seconds": 7.429151888123305e-06, "reason": "", "score": 0.8790048051382479, "status": "valid", "times": [7.427264404104176e-06, 7.425450770847931e-06, 7.428418928508073e-06, 7.427480438318639e-06, 7.4371448988377075e-06], "tree_hash": "c5d70dd4656ed9a45f96c8b3b38a224683c59c35"}, "status": "confirmed"}`.

Commit retenu après confirmation : `225b800f0389ca2817feea47fe3bf168a2901468`.
Temps confirmé : 0.000006 s ; référence confirmée : 0.000054 s.
Réduction mesurée : 89.2%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Non-SIMD word-at-a-time ASCII scanning | Explore a non-SIMD, word-at-a-time ASCII detector to skip ASCII runs, then use the supplied scalar UTF-8 decoder for non-ASCII bytes. Only read complete words within the remaining input (or use an equivalent safe load); handle the tail and every input length correctly. Keep this focused on ASCII-run skipping rather than vectorized general UTF-8 validation, and compare against the bytewise path without assuming the ASCII fraction. Preserve correctness for all valid and malformed inputs. |
| T2 | Full SIMD UTF-8 validation | Explore a one-pass SIMD validator that checks byte classes and neighboring-byte continuation relationships across blocks, including overlong encodings, surrogates, values above U+10FFFF, and truncated sequences. Handle block boundaries and tails safely for arbitrary n; do not rely on benchmark contents. Measure valid mixed-width performance and verify all correctness cases. |
| T3 | Scalar table-driven DFA | Explore a scalar table-driven finite-state validator or equivalent branch-reduced scalar state machine, without SIMD. Encode all UTF-8 lead, continuation, and special-range constraints and handle end-of-input in every state. Keep the work distinct from ASCII block scanning and vectorized validation; measure valid mixed-width performance and verify all correctness cases. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| a042f2c5cd994379 | T1 | search | valid | 0.000128 | d9053304a49e |
| 560d132f251e4235 | T2 | search | valid | 0.000014 | 1c1c9c762163 |
| eeccb83e37d64258 | T3 | search | valid | 0.000107 | 81961812487f |
| 982e2d7aaee446e4 | T1 | search | valid | 0.000062 | 38caa0fe5aa6 |
| 72751b3f468e448b | T4 | search | valid | 0.000007 | 3153a3ec7823 |
| 2002689499e24aaa | T3 | search | valid | 0.000107 | b3c45d0e800e |
| 1ae24457ff8945e8 | T2 | search | valid | 0.000017 | 7ba75f8d968e |
| c841908372154da0 | T4 | search | valid | 0.000007 | 37893e3c5d75 |
| ffade2f47ac746fc | T1 | search | valid | 0.000067 | 1565f7781b23 |
| 06f39022fd154d6a | T5 | search | valid | 0.000006 | 2938ed5b9237 |
| 002f8efe300c43e6 | T3 | search | valid | 0.000087 | 124d193aa7c2 |
| 8cc3f9753cee4924 | T5 | search | valid | 0.000006 | c8ab0d7916b2 |
| db35f7b99ee443cf | T2 | search | valid | 0.000007 | 2eb7dd76bfc2 |
| 12c26ba8a78e49b4 | T4 | search | valid | 0.000007 | b58dd8924e0a |
| 65156f9c8b2c41ae | Gm1 | search | valid | 0.000008 | 8187227f483d |
| 43bde6268ee74bdf | T5 | search | valid | 0.000006 | da36e0441b95 |
| 8fd1a9d847884f7d | T2 | search | valid | 0.000008 | f3acb9d6f064 |
| 75b95f8ca8c14863 | T4 | search | valid | 0.000007 | c9a2d1b96ad1 |
| 98cb042ccd6b49d9 | T5 | search | valid | 0.000007 | ecc16f7611da |
| de23b5f7aeba44e6 | T5 | search | valid | 0.000006 | 821f933ebe04 |
| 46d40f961d154188 | T2 | search | valid | 0.000008 | d73e90a8ddd9 |
| 63bec7d488454191 | T4 | search | valid | 0.000007 | 8970befbada5 |
| b16336e70a764dd9 | T5 | search | valid | 0.000006 | e39b2e357386 |
| d536eefd9d934f90 | T1 | search | valid | 0.000045 | 617dde467c5f |
| e95d2e137db74e3c | T3 | search | valid | 0.000069 | 9e224e5a52a3 |
| 7b72663b870e4b52 | T2 | search | valid | 0.000007 | 4dccdecdd920 |
| b904348d030a4aee | T1 | search | valid | 0.000056 | b81faae6a98e |
| b12cda02fda6426a | T3 | search | valid | 0.000066 | 5b732b8314e2 |
| 3cefa469474d48b1 | T2 | search | valid | 0.000009 | d6d1ccd21376 |
| 2f091f28dfb24183 | T1 | search | valid | 0.000042 | 77af0feb95dd |
| e306636751ca4bbe | T3 | search | valid | 0.000088 | 60a1ecad11b1 |
| 8fc8f24e9c674e71 | T1 | search | valid | 0.000048 | cb3161f9b0cb |
| 2984f3be988545bb | T5 | search | valid | 0.000006 | 8dad00e002ef |
| 6583a8717c62484c | T1 | search | valid | 0.000101 | d3033abb4690 |
| 8817287667c5465a | T5 | search | valid | 0.000006 | 894f4c146b64 |
| b9614009de674a6a | T1 | search | valid | 0.000124 | c3bbc80906ee |
| a366abb6970b4e7a | T5 | search | valid | 0.000006 | 06bd0b9ee76f |
| 4a039e00eab04d11 | T5 | search | valid | 0.000008 | 31aef5dfd387 |
| 5f66307c01b24729 | T5 | search | valid | 0.000006 | 79ac67e862d4 |
| a51bca0a41b540b1 | T5 | search | valid | 0.000006 | d8be19b5d27f |
| ee010f576c79416f | T5 | search | valid | 0.000007 | a4a8254d8576 |
| 20501e4cefe040bd | T5 | search | valid | 0.000008 | 4c3c2c728786 |
| e02d59d153184d2b | T5 | search | valid | 0.000008 | b22f7e58855a |
| 83d269e699a14262 | T5 | search | valid | 0.000006 | f34e7ffc4105 |
| ccb349b43d524bbb | T5 | search | valid | 0.000006 | e6029f34da66 |
| 3e278fe2d5bf4d30 | T5 | search | valid | 0.000006 | b38b5bfb0fa4 |
| 96bc29faacdf4b5b | T5 | search | valid | 0.000006 | 225b800f0389 |
| 5736d2bedfb042d8 | T5 | search | valid | 0.000006 | fd500e76e60a |
| f1b569cbc28c456a | T5 | search | valid | 0.000007 | 7420a5fdbbf8 |
| df3d9baef9ce44ee | T5 | search | valid | 0.000006 | 2500c29b92aa |
| 715612575374404b | T5 | search | valid | 0.000007 | f63424f8838b |
| 391fc9a5c82f48f2 | T5 | search | valid | 0.000006 | 6496e64e03b0 |
| c8f527d9102a44d7 | T5 | search | valid | 0.000007 | aa61ad8a5552 |
| 5ea74e4d9a194f70 | G | postprocess | valid | 0.000008 | e6360fbdf37d |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
