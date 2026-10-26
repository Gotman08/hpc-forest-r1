# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `a04908b459f8dcb1b66d967f98975244bd7184f93873a240c87f20bce6ad4266`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 185, "tokens_used": 11992566, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 11992566}`.
Coûts par phase : `{"search": {"slots": 177, "tokens_used": 11177819, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 11177819}, "postprocess": {"slots": 5, "tokens_used": 814747, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 814747}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "04bfcb98f9414183", "outcome": {"binary_sha256": "96be737278a0a32684561228b7d74148ca47a13c65d56a939be565f390b2e65b", "cache_key": "f1036eee6243ae6f6589d897120d1c2c1b1d9386fae0bcee453d8157a7fcf7d3", "commit": "db2334ad6f18617332ccfd0949a6bdf69c4acbfc", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-popcount-r1-0917efac19f7/forest-app-b024fe211da24e2396c88ad1602a4246/campaign/logs/e1/04bfcb98f9414183/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-popcount-r1-0917efac19f7/forest-app-b024fe211da24e2396c88ad1602a4246/campaign/logs/e1/04bfcb98f9414183/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-popcount-r1-0917efac19f7/forest-app-b024fe211da24e2396c88ad1602a4246/campaign/logs/e1/04bfcb98f9414183/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-popcount-r1-0917efac19f7/forest-app-b024fe211da24e2396c88ad1602a4246/campaign/logs/e1/04bfcb98f9414183/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-popcount-r1-0917efac19f7/forest-app-b024fe211da24e2396c88ad1602a4246/campaign/logs/e1/04bfcb98f9414183/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-popcount-r1-0917efac19f7/forest-app-b024fe211da24e2396c88ad1602a4246/campaign/logs/e1/04bfcb98f9414183/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-popcount-r1-0917efac19f7/forest-app-b024fe211da24e2396c88ad1602a4246/campaign/logs/e1/04bfcb98f9414183/confirmation/attempt-001/sample-4.log"], "mean_seconds": 5.918064397289165e-05, "reason": "", "score": 0.9282065490597375, "status": "valid", "times": [5.921101237842546e-05, 5.919018148999829e-05, 5.917147997653228e-05, 5.917831505936567e-05, 5.915223096013657e-05], "tree_hash": "00a593d5754fb056656ed08e4db1fa387ddea647"}, "status": "confirmed"}`.

Commit retenu après confirmation : `db2334ad6f18617332ccfd0949a6bdf69c4acbfc`.
Temps confirmé : 0.000059 s ; référence confirmée : 0.000765 s.
Réduction mesurée : 92.3%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Scalar hardware POPCNT path | Replace only the bit-at-a-time popcount helper with a scalar hardware POPCNT/compiler-builtin implementation suitable for the supplied EPYC 9654 and existing GCC 14.2 build. Verify that the official build actually emits and can execute the intended instruction rather than assuming compiler flags; do not change compiler settings. Keep the recurrence loops and update order unchanged, preserve exact uint32 behavior for all valid inputs, and report correctness, timing against the supplied baseline, and failed approaches. |
| T2 | Portable SWAR population count | Explore a fixed-operation, branchless 32-bit SWAR population-count helper without relying on target-specific popcount instructions. Limit changes to the count implementation, preserve exact uint32 recurrence semantics for all valid inputs, and compare official-harness correctness and timing against the supplied baseline. Record failed variants and compiler behavior. |
| T3 | Sequential loop structure and unrolling | Investigate inner-loop control overhead and small-factor unrolling or loop-layout changes while keeping one scalar compiler-builtin population-count implementation fixed. First measure a simple, non-unrolled kernel using that helper as a control; then compare loop variants using the same helper to isolate the loop change. Also measure the best loop variant combined with the helper, without assuming gains add. Do not parallelize the loop-carried recurrence. Preserve exact update order and uint32 behavior for all valid inputs, handle tails and all valid sizes, respect the threads budget, and report correctness, official-harness timings, actual code-generation observations, and failed variants. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 82c831f2ceee472e | T1 | search | valid | 0.000059 | 318b5211f514 |
| c6655cecb2524ab2 | T2 | search | valid | 0.000059 | 9f1fc6cd049a |
| 88c453081ba042fa | T3 | search | valid | 0.000060 | f411991e3dfa |
| ebfefca386f34a72 | T2 | search | valid | 0.000336 | f1e298fd29ec |
| 63a5c162b08a4298 | T1 | search | valid | 0.000059 | 1d133464688c |
| 3360ed47a0ba423d | T3 | search | valid | 0.000059 | b3e6a8924f37 |
| 79ebcc5df00c4dfd | T1 | search | valid | 0.000059 | c4696afc9b88 |
| 2cbcbd3e54c24850 | T2 | search | valid | 0.000296 | c2be722f9d1e |
| 9f4184316f104bb2 | T1 | search | valid | 0.000059 | 1541ed3da2d5 |
| c7b094b04a6442f4 | T2 | search | valid | 0.000316 | 20ed1aaeccdf |
| 8261923b7dbf426e | T2 | search | valid | 0.000315 | bc53c0e99884 |
| da2868b2cc5d4004 | T3 | search | valid | 0.000059 | 8ec1b546b0d2 |
| 1951d9a0825341e7 | T1 | search | valid | 0.000059 | aebea78ad5ac |
| bb6e983bd9434781 | Gm1 | search | valid | 0.000059 | 634a3611541c |
| 8a866a5e82e84b36 | T3 | search | valid | 0.000059 | 2ad9a2c41fd9 |
| b6da4277fc924eab | T2 | search | valid | 0.000335 | 8cf6d7e0b8c8 |
| 591a17ebe2834740 | T1 | search | valid | 0.000059 | 7be43183e023 |
| 0dbb2c3af800452b | T3 | search | valid | 0.000060 | ba2640d6e733 |
| af3a43b6e1fd4f23 | T1 | search | valid | 0.000059 | 1d9916a1a548 |
| 34d96b9aef4645de | T2 | search | valid | 0.000318 | dcd82664cbb9 |
| ed705039517c494a | T3 | search | valid | 0.000060 | 3540b16e9bb6 |
| 82e7a80e60e443dc | T1 | search | valid | 0.000119 | 42039878d93e |
| ba04b4b680c445ff | T3 | search | valid | 0.000059 | 0f3308c1cc78 |
| 1be0be944bcb420b | T2 | search | valid | 0.000296 | 33844b3f95ab |
| 014031cd6a264e88 | T3 | search | valid | 0.000059 | 9dfd3549ca34 |
| cfb6c01eeadd4f7a | T1 | search | valid | 0.000099 | 668debff772f |
| 89a1df0a9a494ff9 | T2 | search | valid | 0.000059 | 39d112a17334 |
| cab2fdd2425b42fc | T3 | search | valid | 0.000060 | 8bdf221997dd |
| 6afd95c50c9f4fe1 | T3 | search | valid | 0.000059 | e0d0fcae7976 |
| ba3ba3e43980496a | T1 | search | valid | 0.000059 | c2aa9b60d151 |
| dedc120711bb4c2e | T2 | search | valid | 0.000297 | d924ab7f9d3a |
| 19c0442c92664f4c | T3 | search | valid | 0.000060 | a18e9a7b016a |
| 3fa7d7d903a04896 | T2 | search | valid | 0.000316 | dfa8e6b6e707 |
| 57108e6455844e76 | T1 | search | valid | 0.000059 | b38364910136 |
| 1f44b380d0b74bbe | T2 | search | valid | 0.000284 | 0f25e06e3262 |
| 1033997b2a1647d0 | T3 | search | valid | 0.000059 | 3d2c2d6980ca |
| ee58f392bde64a69 | T1 | search | valid | 0.000059 | 1c287b1332f0 |
| 217c8da0cd2643b7 | T2 | search | valid | 0.000297 | e6f5183891a6 |
| 54b3ef94115a41e2 | T3 | search | valid | 0.000059 | ee7d1678ccc0 |
| 44211f8fe0994eb2 | Gm2 | search | valid | 0.000059 | 7bc2ef492fc0 |
| 31e44a0f6e6f4d2f | T1 | search | valid | 0.000059 | 59e47ff2d0d3 |
| 04a63a0c897d4fd7 | T3 | search | valid | 0.000059 | 5a2eeabdd7d2 |
| 8f763a285a92441c | T2 | search | valid | 0.000317 | 59bab27aba36 |
| 3dafe4b7af5c488c | T3 | search | valid | 0.000060 | 18497e1abbd1 |
| 96653e1ac2514f67 | T1 | search | valid | 0.000059 | 8de66f1612b9 |
| 5b5f3de67c1043f9 | T2 | search | valid | 0.000356 | ae1fea56b375 |
| d586b631e7914abb | T3 | search | valid | 0.000068 | eff421868dd3 |
| 1088f1dd90824439 | Gm3 | search | valid | 0.000059 | f29d7ebf3ba5 |
| 02e911fce7864a09 | T1 | search | valid | 0.000059 | 0293e20e51a8 |
| 49d3770f49c944ce | T2 | search | valid | 0.000317 | a9acdf46d0da |
| 2ff1781ca6d6486f | T3 | search | valid | 0.000059 | 0264bcb60825 |
| a24147e020044e9a | T1 | search | valid | 0.000059 | fd236892fa28 |
| 806889e84e4849dd | T3 | search | valid | 0.000059 | 4fe7611c2ee6 |
| b960b0ce0483415f | T2 | search | valid | 0.000298 | 7d735af764f7 |
| 7ebc78c3ef1144f7 | T1 | search | valid | 0.000099 | b9152837ac03 |
| 55109f76582b4cdb | T3 | search | valid | 0.000059 | 932243fe9e4b |
| bf129e0c05a84e68 | T1 | search | valid | 0.000059 | 0ffb17122512 |
| 5830d1661b7a4ab0 | T2 | search | valid | 0.000337 | 2edb9765a375 |
| bda23f502a66452d | T3 | search | valid | 0.000059 | 4cf6233348dd |
| 7f82486bf62a449f | T1 | search | valid | 0.000060 | b2e8df9a2800 |
| 0a29321085ee4de4 | T3 | search | valid | 0.000059 | 03f3bdce6bef |
| 9fc1dbadbcd74a75 | T2 | search | valid | 0.000277 | 731e23515a0c |
| 9ae86d9634d7444f | T1 | search | valid | 0.000059 | 3bea77d48073 |
| 2e39fffb8af74257 | T2 | search | valid | 0.000330 | 106347208a82 |
| de31e45c5b1d4353 | T3 | search | valid | 0.000060 | fea361dcab85 |
| ff66fcb0f9584d02 | T2 | search | valid | 0.000298 | f264e9d69687 |
| c52a5ffcb66448dc | T3 | search | valid | 0.000060 | 9d1420f73700 |
| 5f33f77ddb044b14 | T1 | search | valid | 0.000066 | d526357b3a44 |
| 5d08072caf124b48 | T2 | search | valid | 0.000277 | fef150e77d55 |
| 5122e046870c4de6 | T3 | search | valid | 0.000059 | b82f0d46e887 |
| 8a605d605f6a4ea9 | T2 | search | valid | 0.000059 | 38c4b8f0288f |
| 121abfebe7874561 | T1 | search | valid | 0.000059 | b2b1aea0c63f |
| f00a1c6eaf244cc3 | T3 | search | valid | 0.000059 | c51aacbd9b23 |
| 0e9894f10dcb4d87 | T2 | search | valid | 0.000317 | f179faa9514c |
| 8cb6c2f4f6364b64 | T1 | search | valid | 0.000059 | c85b01e9d6de |
| 47f64a2709454e32 | T3 | search | valid | 0.000059 | a5b4a652696b |
| c2b075ad8e4249f2 | T2 | search | valid | 0.000318 | 256ad0aae516 |
| 91712ca374dd4ca4 | T1 | search | valid | 0.000059 | 978187e75502 |
| 8974d0b6794e4ef5 | T3 | search | valid | 0.000059 | bbd1fda5e797 |
| 495ae18971db45be | T2 | search | valid | 0.000284 | ab992994a12d |
| 68216445648340ce | T3 | search | valid | 0.000059 | f3942f879e9f |
| 1c707be288a749ef | T3 | search | valid | 0.000059 | 4c3d16459732 |
| d9c391c8b6a2441d | T2 | search | valid | 0.000298 | 2e3f3bb1a186 |
| f91ec1f6e5434ecd | T1 | search | valid | 0.000059 | 1992de9eec2a |
| 7432d1cd0cf74632 | T3 | search | valid | 0.000059 | dd8410b3cc7f |
| 9336db6bd46d4b90 | T2 | search | valid | 0.000329 | 76fd1f2945c0 |
| 43d31629c37e400d | T3 | search | valid | 0.000059 | 78774793952a |
| 04bfcb98f9414183 | G | postprocess | valid | 0.000059 | db2334ad6f18 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
