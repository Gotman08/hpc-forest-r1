# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `8cf1c6734ca7159519aec408487af30dfc49dd2c1ce2e9a34d17f67a17d2609f`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 133, "tokens_used": 9881848, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 9881848}`.
Coûts par phase : `{"search": {"slots": 121, "tokens_used": 8366318, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 8366318}, "postprocess": {"slots": 9, "tokens_used": 1515530, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1515530}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "b9733e67cc19485e", "outcome": {"binary_sha256": "a925d29b9d19c19a55a847a478d837cf837bcfdd28eda51618836153523c4502", "cache_key": "c5f67385e06b89e167de4807113beb03b4fd1030d9613387a8d10a7a387dff43", "commit": "f43285dcf336395e679adb382506f7dd93c07453", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r1-668cc77a0b42/forest-app-bbabec9b336847d39cb3ffa7f945ba71/campaign/logs/e1/b9733e67cc19485e/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r1-668cc77a0b42/forest-app-bbabec9b336847d39cb3ffa7f945ba71/campaign/logs/e1/b9733e67cc19485e/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r1-668cc77a0b42/forest-app-bbabec9b336847d39cb3ffa7f945ba71/campaign/logs/e1/b9733e67cc19485e/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r1-668cc77a0b42/forest-app-bbabec9b336847d39cb3ffa7f945ba71/campaign/logs/e1/b9733e67cc19485e/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r1-668cc77a0b42/forest-app-bbabec9b336847d39cb3ffa7f945ba71/campaign/logs/e1/b9733e67cc19485e/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r1-668cc77a0b42/forest-app-bbabec9b336847d39cb3ffa7f945ba71/campaign/logs/e1/b9733e67cc19485e/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r1-668cc77a0b42/forest-app-bbabec9b336847d39cb3ffa7f945ba71/campaign/logs/e1/b9733e67cc19485e/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.1053785676106722, "reason": "", "score": 0.8423761031681581, "status": "valid", "times": [0.10536236819323826, 0.10535078301930376, 0.10535186940321455, 0.10538884940597527, 0.10543896803162915], "tree_hash": "2180b29d7d65ced0834b9893a87861d8feb11879"}, "status": "confirmed"}`.

Commit retenu après confirmation : `f43285dcf336395e679adb382506f7dd93c07453`.
Temps confirmé : 0.105379 s ; référence confirmée : 0.563166 s.
Réduction mesurée : 81.3%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Thread-budget-aware OpenMP parallelization | Compare a serial path for a one-thread budget and OpenMP distribution using static contiguous rows/coarse tiles versus dynamic or guided smaller tiles. Never exceed the threads budget and leave each pixel's arithmetic unchanged. Measure one- and four-core performance to distinguish parallel benefit from scheduling overhead and imbalance; validate exact output for every check, including shifted bounds, and record losing schedules. |
| T2 | Exact SIMD for divergent pixel iterations | Compare scalar and SIMD variants under the same simple outer row partition and thread count, so the vectorization effect is isolated from scheduling. Explore lanes across adjacent x coordinates with per-lane escape state and correct tail handling. Verify which ISA the actual build enables; preserve baseline coordinate generation, float operation order, and escape-test timing, without reassociation or approximate math that changes counts. Validate all checks and measure at one and four cores. |
| T3 | Exact nonescaping-point fast paths | Compare conservative analytic certificates for nonescaping interior points (including float-safety margins) with exact orbit-cycle detection, which may return the maximum count only after proving a repeated floating-point state. Fall back to the baseline recurrence whenever safety is uncertain; preserve behavior for nonpositive parameters and all valid bounds, without approximate membership or assumptions about standard bounds. Compare shortcut-on/off under the same simple row partition, never exceeding the threads budget. Validate exact output on every check, including shifted bounds, and measure at one and four cores; record overhead or failed approaches. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| a4f5f574db0a4856 | T1 | search | valid | 0.282244 | 490fd5b09f49 |
| 05d3e9e7b0dc4071 | T2 | search | valid | 0.471915 | 8b160853f23d |
| 6a157ff097f34ddf | T3 | search | valid | 0.127391 | dd5483b38945 |
| d88d18941a814fbf | T1 | search | valid | 0.361688 | dac6190fbc96 |
| b50c255e736447dd | Gm1 | search | valid | 0.319722 | 6ec19f8310f8 |
| f41feec4985a4394 | T2 | search | valid | 0.361627 | 16a2c21128bc |
| 951296cd40384f85 | Gm2 | search | valid | 0.109594 | c298e321165d |
| 6b656a19df634706 | T3 | search | valid | 0.362794 | a7d8098da0b5 |
| cb0c6ac083a14d9c | T4 | search | valid | 0.109321 | ce0607bf2ca9 |
| 12a37eacf9464fc0 | T1 | search | valid | 0.305558 | b1a6eefc701f |
| 2b1ed9ec19404c82 | T1 | search | valid | 0.282036 | 14064a795399 |
| ec5a30cc69ef4b19 | T3 | search | valid | 0.127146 | bbe7931458e2 |
| 97bc6dc346554a1f | T4 | search | valid | 0.109384 | 3045242ea167 |
| 162ebb269427412a | T1 | search | valid | 0.283113 | f94764cd3329 |
| e8ed722c7e8b4d11 | T1 | search | valid | 0.283261 | 3cdaed33e0d1 |
| 09af3143cc764655 | T3 | search | valid | 0.126969 | 222034c3e73b |
| 84c5808632f042c5 | T1 | search | valid | 0.282434 | 8cb67235ed4f |
| 5cafb0f3d51c4705 | T4 | search | valid | 0.110159 | 9b74a258be36 |
| af08fa75e5f54228 | T1 | search | valid | 0.282147 | a48f92174e62 |
| b8f3802f6fc644c9 | T3 | search | valid | 0.124842 | b1b353c60a52 |
| a43d5b82eba94a65 | T1 | search | valid | 0.362742 | fe58a33c491b |
| 25163271f7d2432e | T1 | search | valid | 0.282546 | 33d3955a2dd2 |
| d82392fe580c4e9e | T4 | search | valid | 0.109433 | 637f3dd2f20d |
| af2b4627abf04dde | T3 | search | valid | 0.126265 | 6b52d2038c0f |
| 435ad4dd43754992 | T1 | search | valid | 0.283265 | ad70d0e80972 |
| 525cc788302d47f6 | T4 | search | valid | 0.109345 | e1d25fbc0fd9 |
| 35ede335d12341f0 | T3 | search | valid | 0.318894 | ba8f69c1dbfd |
| d64a64993de1491d | T1 | search | valid | 0.305004 | e78f497cad0f |
| b4d7fe37ea024270 | T3 | search | valid | 0.136156 | 147d2514602d |
| 08d87e5b12674a26 | T1 | search | valid | 0.305170 | ca5fefc5a204 |
| 078e48e61d5c43a6 | T4 | search | valid | 0.109336 | 93fe7aec42b2 |
| 335f47ccaf644de6 | T1 | search | valid | 0.282038 | e6b10385006b |
| 27852fe83c5f4e20 | T3 | search | valid | 0.122700 | bbc67f2b3b19 |
| 2bc7e0a5066a4cfc | T4 | search | valid | 0.109616 | ffe0d7c89caa |
| bfa350b65e0c4dc5 | T1 | search | valid | 0.282100 | 9a51d9ed2a0f |
| 99ea5c081e7042b1 | T3 | search | valid | 0.345965 | 4a5cb32bd1d1 |
| db7b480b2e1349fd | T1 | search | valid | 0.362558 | 71a3f264e4d6 |
| 32187f9961fe4a76 | T3 | search | valid | 0.124884 | 269cbd5d2d8b |
| bd9f708aff4f458c | T1 | search | valid | 0.283772 | 0fe7e488a45e |
| bd163e75f8fa4403 | T4 | search | valid | 0.109352 | eed2e9dbcb0e |
| ec1eea2b819e46b0 | T4 | search | valid | 0.109264 | 6a15237902d7 |
| 24c4f5f8d4934de4 | T4 | search | valid | 0.109365 | b259d8ff6650 |
| b81e038366274456 | T4 | search | valid | 0.109366 | 18070ad6e7e1 |
| cc8a8e5c5d6546c6 | T4 | search | valid | 0.109310 | d7e0b7927009 |
| 80ef9d9368934386 | T4 | search | valid | 0.109374 | b39d84dd7dfe |
| f6c6d2da349b4f0c | T4 | search | valid | 0.109389 | 2b39ea3e59d0 |
| 626b2cd5f4724f28 | T4 | search | valid | 0.109482 | 3902c22e2d0f |
| 27e3919ea89b4c86 | T4 | search | valid | 0.109824 | 83374375fbcc |
| 948c2a71163b447c | T4 | search | valid | 0.109306 | 5d0ed0fcdf65 |
| 58bdd58e8a154d03 | G | postprocess | valid | 0.105466 | fa9aa2a8212e |
| a73b13b32d534633 | G | postprocess | valid | 0.105589 | ee768d7bd4ba |
| b9733e67cc19485e | G | postprocess | valid | 0.105433 | f43285dcf336 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
