# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `a80607d34218f867696be5f91bf8bd1fb359f874b0cf2ca248cf82e5875225f0`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 153, "tokens_used": 18480709, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 18480709}`.
Coûts par phase : `{"search": {"slots": 136, "tokens_used": 15868642, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 15868642}, "postprocess": {"slots": 14, "tokens_used": 2612067, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2612067}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "ddb280da78a841d6", "outcome": {"binary_sha256": "1f6a947fdf9de3996c0bd28f3af7d33d389e542626b2a279f8c0cfc3f0f9002d", "cache_key": "3daf36d3d7703d9150e4bcf6ed2979899d9af5edeaaeb59b7910ba0261fdfe9b", "commit": "f325db92a9af57a6e80888793a6ad5a36088c777", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-mandelbrot-r2-c8b10d1cf551/forest-app-1d3d1a2ee6d7441ba6dc6e36e4def62a/campaign/logs/e1/ddb280da78a841d6/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-mandelbrot-r2-c8b10d1cf551/forest-app-1d3d1a2ee6d7441ba6dc6e36e4def62a/campaign/logs/e1/ddb280da78a841d6/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-mandelbrot-r2-c8b10d1cf551/forest-app-1d3d1a2ee6d7441ba6dc6e36e4def62a/campaign/logs/e1/ddb280da78a841d6/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-mandelbrot-r2-c8b10d1cf551/forest-app-1d3d1a2ee6d7441ba6dc6e36e4def62a/campaign/logs/e1/ddb280da78a841d6/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-mandelbrot-r2-c8b10d1cf551/forest-app-1d3d1a2ee6d7441ba6dc6e36e4def62a/campaign/logs/e1/ddb280da78a841d6/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-mandelbrot-r2-c8b10d1cf551/forest-app-1d3d1a2ee6d7441ba6dc6e36e4def62a/campaign/logs/e1/ddb280da78a841d6/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-mandelbrot-r2-c8b10d1cf551/forest-app-1d3d1a2ee6d7441ba6dc6e36e4def62a/campaign/logs/e1/ddb280da78a841d6/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.05777496682981375, "reason": "", "score": 0.9069819383950295, "status": "valid", "times": [0.057773343190016674, 0.05777628367740191, 0.057787228214656705, 0.05776336719995894, 0.0577746118670345], "tree_hash": "a70d66513721f9d9d10b24ce68c0e7ff37999e86"}, "status": "confirmed"}`.

Commit retenu après confirmation : `f325db92a9af57a6e80888793a6ad5a36088c777`.
Temps confirmé : 0.057775 s ; référence confirmée : 0.563341 s.
Réduction mesurée : 89.7%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | OpenMP parallelism and load balancing | Isolate thread scaling and load balance using the unchanged scalar mandel recurrence; do not add SIMD or interior-point shortcuts. Compare a one-thread path and four-thread worksharing, including contiguous static rows versus tiled or flattened dynamic/guided work assignment for uneven escape costs. Use no more than the supplied threads budget, preserve full output writes and scalar float behavior, and measure one- and four-thread cases on standard and shifted bounds. Report scheduling overhead and retain only correct measured gains. |
| T2 | Exact SIMD escape-time kernel | Focus on SIMD across adjacent pixels while preserving the scalar float recurrence, operation order, and exact counts. First measure a single-worker vector kernel against the scalar baseline to isolate SIMD; for the four-thread check, use only a simple fixed contiguous-row work partition, without tuning scheduling (that is T1's scope). Select only an ISA/compiler path actually supported by the build target; handle divergent lanes and tails exactly, and do not use fast-math or approximate counts. Report the isolated one-thread result separately from the SIMD-plus-basic-worksharing four-thread result, including shifted bounds. |
| T3 | Certified interior-point fast paths | Investigate exact fast paths for points whose orbit is guaranteed to remain bounded, such as rigorously certified interior regions. Any predicate must be conservative and proven to return the same maximum iteration count as the supplied finite-float reference; otherwise fall back to the unchanged recurrence. Do not assume default or symmetric bounds. Validate boundary and shifted-bound cases, record rejected or failed shortcuts, and keep only a universally correct measured gain. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 4c261e7a0ba84064 | T1 | search | valid | 0.282362 | 6cbf4c6b0f70 |
| 6cb08e7721d14352 | T2 | search | valid | 0.371108 | 6ae7140acf63 |
| 96f4ba317bf149b6 | T3 | search | valid | 0.560463 | b82bc0697985 |
| 13440a1457fc4c6a | T1 | search | valid | 0.363045 | 03d415a04a03 |
| 6a7918d7221f4b4a | Gm1 | search | valid | 0.091076 | 55a5ff48b7ed |
| 583c51fabd6746ce | T2 | search | valid | 0.361207 | 4c350a83ffe5 |
| 44a0dc1cb44a4e64 | T4 | search | valid | 0.070408 | 35798fee2e52 |
| 6f58214a65f94909 | T3 | search | valid | 0.552461 | bf8c1a385bfd |
| a0fe6102fb324e44 | T4 | search | valid | 0.080879 | aa97752de0cc |
| c81cda44be05490f | T1 | search | valid | 0.304520 | 188a6798738b |
| 490fe251d7d641b2 | T3 | search | valid | 0.495783 | 1d91e1d52737 |
| 3bb5705939b54c74 | T1 | search | valid | 0.282004 | 22ebb5f67c3e |
| aa9de521bb264df2 | Gm2 | search | valid | 0.073034 | 1f6161029db0 |
| 8b5909a975b34d9d | T4 | search | incorrect | — | 1b80f21de14e |
| 0aeeb4919b5548ba | T3 | search | valid | 0.529697 | 593dc71457c9 |
| e42b77706efb4671 | T1 | search | valid | 0.284010 | d97872f589f0 |
| 53fcd429063b4146 | T1 | search | valid | 0.282134 | 29b422d068a9 |
| 8943889d256145d0 | T3 | search | valid | 0.493546 | 250f2ee4a14b |
| 0d984f3f7b204a00 | T1 | search | valid | 0.282086 | 7816575e3216 |
| 5eaebd7c965f42b1 | T1 | search | valid | 0.305036 | f39b3af4dfd7 |
| 56ffb9fd3a4d4d95 | T3 | search | valid | 0.491559 | a51d03a48be6 |
| 9a9f74135a324b50 | T4 | search | valid | 0.066067 | b463cb010383 |
| f6bc4959bab74b68 | T1 | search | valid | 0.282367 | b385d12c7a87 |
| 41a1ee4530994ae1 | T2 | search | valid | 0.370901 | 17c8eed7bc83 |
| 0c0a248354034e85 | T4 | search | incorrect | — | 0f824d721548 |
| a8ca6cab502c4091 | T3 | search | valid | 0.495025 | fe9cfe1a7cf9 |
| 66dae75d5ac448d2 | T2 | search | valid | 0.362632 | d5f89365d379 |
| 346815efbfec4536 | T3 | search | valid | 0.489834 | 834284b0011a |
| ae12112f82634df2 | T2 | search | valid | 0.362608 | 0cae0732c919 |
| b73881fc652e44a9 | T4 | search | valid | 0.066121 | 99745c8a20e6 |
| 89cad303bde2473b | T2 | search | valid | 0.192181 | c95febb2170b |
| 7a1d132b2f694d42 | T4 | search | valid | 0.070500 | ca0ff52ae849 |
| 4397fc751e56410a | T3 | search | valid | 0.564405 | 22ea2537caf4 |
| 14097895f9494882 | T1 | search | valid | 0.283216 | 3ea7e6e6c37e |
| ff4507d500254c1a | T2 | search | valid | 0.362541 | 8cec38110bf7 |
| cfbafde2e3a1414e | T1 | search | valid | 0.282243 | 6324004584d1 |
| b50fbd2deaef41c8 | T1 | search | valid | 0.282095 | 11be4a41cc20 |
| 50ee59e7e73b4326 | T2 | search | valid | 0.703825 | e3ea723cc1d3 |
| 7832fbad855a4018 | T3 | search | valid | 0.519675 | 3e2b3bbc99c3 |
| 5d5d062de4f1407f | T1 | search | valid | 0.288967 | 45985fd90d93 |
| f882e7ae5d9d4f6b | T2 | search | valid | 0.362818 | 621e7244fa95 |
| 4e52544c99934939 | T1 | search | valid | 0.305070 | f99ff5fc8183 |
| f491f8e0b9494138 | T3 | search | valid | 0.489839 | dbc2d3b1856c |
| a8aa5a1847d445c8 | T1 | search | valid | 0.282903 | ef1b1cce8de7 |
| 07c8fa5527c6443f | T1 | search | valid | 0.282226 | 378281d42249 |
| c4a8cd2fea784e92 | T1 | search | valid | 0.282307 | bae149501c71 |
| 1522032ffb9d490b | T1 | search | valid | 0.282270 | 10ab481c394a |
| 7be20315db0f496b | T4 | search | valid | 0.065974 | b398ee9ed5fe |
| e525c3b24a3646f2 | T4 | search | valid | 0.072877 | 22e44201aa89 |
| 6b30340e5fe24df3 | T4 | search | valid | 0.073435 | d88e0a2203f7 |
| d571aee28017417e | T4 | search | valid | 0.066018 | 6061569616ce |
| 302d205ff23e48c2 | T4 | search | incorrect | — | db2e5cd956e7 |
| 94d6482d9e304930 | T4 | search | valid | 0.080881 | 8c732183bfda |
| e353640d8fb748fc | T4 | search | valid | 0.071353 | 679cabc80e96 |
| 3f38d22d2dbe4ce4 | T4 | search | valid | 0.071738 | 181bf586d9cc |
| 5e50575fd1cb40e7 | T4 | search | valid | 0.073014 | d0caa8a6b3ba |
| 64dc9355ae2d4b74 | T4 | search | valid | 0.081194 | 393079f6f273 |
| 72b300cc59364dbf | G | postprocess | valid | 0.064671 | ca59cb5db16a |
| 0444a0ecab3e4106 | G | postprocess | valid | 0.071275 | d0490aed1e54 |
| eccc34791ac742b2 | G | postprocess | valid | 0.064573 | f527d84f862b |
| f50dd28bc7a34651 | G | postprocess | valid | 0.064609 | df279e99f087 |
| ddb280da78a841d6 | G | postprocess | valid | 0.057789 | f325db92a9af |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
