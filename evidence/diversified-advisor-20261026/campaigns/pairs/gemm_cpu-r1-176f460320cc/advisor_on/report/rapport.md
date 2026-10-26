# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `365775744eadcc49ab5fd733e11af341320effc3a2fcefde9e4d530ce15cdab9`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 141, "tokens_used": 10186624, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 10186624}`.
Coûts par phase : `{"search": {"slots": 135, "tokens_used": 9662021, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 9662021}, "postprocess": {"slots": 3, "tokens_used": 524603, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 524603}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "b0283c51ba944cfd", "outcome": {"binary_sha256": "b55454e8914ecd6414522954219cda2ed7d748570c55eaf8ec32cb7d092161a8", "cache_key": "89338be2250e611e05aa0b40178761804d8def0cf94f2d238d855d33e04d43ac", "commit": "6a92d618c3da825f0d78839f9f48511c992ed6f4", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-gemm_cpu-r1-176f460320cc/forest-app-dc48864d7acf4d988f9b69d68bc80549/campaign/logs/e1/b0283c51ba944cfd/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-gemm_cpu-r1-176f460320cc/forest-app-dc48864d7acf4d988f9b69d68bc80549/campaign/logs/e1/b0283c51ba944cfd/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-gemm_cpu-r1-176f460320cc/forest-app-dc48864d7acf4d988f9b69d68bc80549/campaign/logs/e1/b0283c51ba944cfd/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-gemm_cpu-r1-176f460320cc/forest-app-dc48864d7acf4d988f9b69d68bc80549/campaign/logs/e1/b0283c51ba944cfd/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-gemm_cpu-r1-176f460320cc/forest-app-dc48864d7acf4d988f9b69d68bc80549/campaign/logs/e1/b0283c51ba944cfd/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-gemm_cpu-r1-176f460320cc/forest-app-dc48864d7acf4d988f9b69d68bc80549/campaign/logs/e1/b0283c51ba944cfd/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-gemm_cpu-r1-176f460320cc/forest-app-dc48864d7acf4d988f9b69d68bc80549/campaign/logs/e1/b0283c51ba944cfd/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.0030260493860343796, "reason": "", "score": 0.9778047754947564, "status": "valid", "times": [0.0030177464273110637, 0.00301440704545906, 0.0030168695156836747, 0.0030548381900894063, 0.003026385751628693], "tree_hash": "2fddf121ed4cb0be8fa41122a3957126f9b7378e"}, "status": "confirmed"}`.

Commit retenu après confirmation : `6a92d618c3da825f0d78839f9f48511c992ed6f4`.
Temps confirmé : 0.003026 s ; référence confirmée : 0.133312 s.
Réduction mesurée : 97.7%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Direct output-stationary SIMD kernel, isolated from thread scaling | Prioritize a single-thread, output-stationary blocked GEMM as a kernel experiment: retain small C tiles in registers, vectorize across contiguous output columns, and tune register/cache blocking and unrolling without first adding parallel complexity. Keep dynamic n handling, including fringes. Measure this kernel at both thread budgets (it may use one worker at either) so its benefit can be distinguished from threading and considered for later combination. Use explicit intrinsics only when supported by the actual build, or retain a safe general path. Validate correctness and wall-clock time across the timed cases and preserve correctness for every valid size; other correctness-preserving experiments remain possible. |
| T2 | Per-call B transpose/packing with k-wise SIMD reductions | Explore the alternative of transposing or packing B into per-call scratch so each output dot product can use contiguous k-wise loads and SIMD reductions. Measure whether the transform cost pays off at the tested sizes and thread budgets; parallelize independent output rows or row groups within the threads limit. Do not reuse cached data or specialize to n=384/768. Check signed-input correctness against the FP64 tolerance, including the changed reduction order, and preserve a correct general-n path. |
| T3 | Row-owned i-k-j loop and OpenMP decomposition | Prioritize OpenMP decomposition and thread scaling around a cache-aware, compiler-vectorizable i-k-j row-major loop: initialize C, then update contiguous C row segments from contiguous B rows, assigning independent row slabs or 2D output tiles to workers. Compare these decompositions, static scheduling, and parallel-region overhead, with a serial path when the budget is one. This contrasts with T1's output-stationary kernel and T2's transformed-B reduction approach. Respect the thread budget, keep n dynamic, measure all timed cases, and validate the full-output overwrite and numerical tolerance. Treat the loop form as the main hypothesis, not a restriction on correctness-preserving experiments. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 295d32ca804e4c14 | T1 | search | valid | 0.010720 | 0fa09c68d9a7 |
| ce67e774841d446c | T2 | search | valid | 0.011954 | 35100057821b |
| 2fd56690b16f4484 | T3 | search | valid | 0.004284 | 8bdfd3b2ca34 |
| 9cf73a00e8c447e5 | T3 | search | valid | 0.004264 | 7f3dde18b381 |
| 62b17d400b1d416e | Gm1 | search | valid | 0.005492 | 8df0785e7fe4 |
| 2bea127a2fd9410c | T1 | search | valid | 0.030642 | 6bc76a831ddf |
| 15cce5c70de74363 | T2 | search | valid | 0.062490 | df8affce3846 |
| c3edc974a30148ba | T1 | search | valid | 0.005512 | a0d2fc6a3264 |
| 06893564164f446b | T3 | search | valid | 0.004335 | 60d8e59abb57 |
| daa5f2ed9cf14ee9 | T3 | search | valid | 0.004401 | 37814847e5f4 |
| 798e5c3828c146c9 | T3 | search | valid | 0.004293 | d8c96d83c721 |
| e8fb4c355bab4f26 | T3 | search | valid | 0.004184 | fe378c1cc4b5 |
| 7fcbb30269d643de | T2 | search | valid | 0.064556 | e4765d08a28f |
| e100dd61e14b4768 | T1 | search | valid | 0.033435 | 041035330fcb |
| fd3210a930594a87 | T2 | search | valid | 0.012064 | 7916b3c5a989 |
| 60b1d3ea0d8d4172 | T3 | search | valid | 0.004112 | e56a06e22785 |
| 5cece87d477843b2 | T1 | search | valid | 0.005489 | a8fdb72511f3 |
| c7c7c9b71c724954 | T3 | search | valid | 0.004157 | 3130b3a83739 |
| 1d24ff42665b46ce | T3 | search | valid | 0.004004 | f075c9382195 |
| c7314fd86a4e449e | T3 | search | valid | 0.004205 | a80221a500da |
| 21ae4389c6f74796 | T3 | search | valid | 0.004077 | c942ebab0dd9 |
| 8a3ecc6d86844c4d | T3 | search | valid | 0.004148 | 27ed49b97f2b |
| 0737854c94114e5c | T3 | search | valid | 0.004011 | 7fae19415610 |
| d858535e8c0847a2 | T2 | search | valid | 0.062873 | 1e797a17d6dd |
| 3b84a5cedbab4c74 | T1 | search | valid | 0.010805 | 1ec24a72a962 |
| db615f7e6711456a | T3 | search | valid | 0.004386 | d26b5003b394 |
| 2352f1dfdf1448c4 | T3 | search | valid | 0.004352 | 0215885b2792 |
| f44022c3687a4d0e | T1 | search | valid | 0.005525 | ad43dab56309 |
| 4705ab204c434b3b | T1 | search | valid | 0.005556 | b5381871eaef |
| 8f1849d57c334f97 | T1 | search | valid | 0.022182 | 92d4cd7a6c5c |
| d205b6347b5144dd | T3 | search | valid | 0.004222 | 252cc1afd177 |
| 4c6e1ce48cd8408e | T3 | search | valid | 0.004302 | f4b05f158307 |
| abc77e21c0b34f2a | T3 | search | valid | 0.004267 | c6ef20429170 |
| c86f0679be4f407e | T3 | search | valid | 0.004018 | 8d7a95f22f96 |
| 64c6f14985404bb1 | T3 | search | valid | 0.004285 | 9d0cbbb1997e |
| 138b6dc59d354031 | T3 | search | valid | 0.004199 | 696f2ebf7f7d |
| 087badc33fc24ab2 | T3 | search | valid | 0.004315 | 9fe147993fc6 |
| eae2f66c602c4259 | T3 | search | valid | 0.003272 | 5e1e238b4937 |
| 49ac961ee58e4285 | T3 | search | valid | 0.004031 | 7af141958f18 |
| 1d8b2b040c6d4117 | T3 | search | valid | 0.004311 | 07855938e9f7 |
| ee2d0d4691e1430b | T3 | search | valid | 0.004427 | aa15f31eafaa |
| 427e3c7b84254cb9 | T3 | search | valid | 0.004122 | 955e5c5552eb |
| 8b06c0ee3c5d410c | T3 | search | valid | 0.004250 | d234f7a92e5a |
| 857d936880044cfd | T3 | search | valid | 0.004272 | ed9704871e4e |
| c9d235e89c6c4c5f | T3 | search | valid | 0.005094 | 6c9ac7db870a |
| 89584946ecc54282 | T3 | search | valid | 0.004317 | e70ee77954e3 |
| 3da880400c664101 | T3 | search | valid | 0.004322 | 0c11ba0aa9e6 |
| 75fc5b2dd6d94298 | T3 | search | valid | 0.004058 | 69cc2a7a7409 |
| 4b70d38d411449db | T3 | search | valid | 0.003677 | d1cc5e6e90b7 |
| 1764f4e00e6f4c38 | T3 | search | valid | 0.003673 | 9925083f65fe |
| d2fd446f570a4d36 | T3 | search | valid | 0.004339 | 1771a4752248 |
| b2d8f72b896b490f | T3 | search | valid | 0.004404 | b7d6daff4476 |
| b0283c51ba944cfd | G | postprocess | valid | 0.003009 | 6a92d618c3da |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
