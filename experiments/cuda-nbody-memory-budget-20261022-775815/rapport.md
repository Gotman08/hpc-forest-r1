# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `2c98693b91a5cf51ccba8706926f0973c5d3e652a985fcf341fbeb0c41c62de7`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 37, "tokens_used": 4617636, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 4617636}`.
Coûts par phase : `{"search": {"slots": 26, "tokens_used": 1242381, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1242381}, "postprocess": {"slots": 8, "tokens_used": 3375255, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3375255}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "1a380d99a03b42a0", "outcome": {"binary_sha256": "1b5ece84c991e63e6d274c62b7475658891f184550f924b9d0ee0e915e5a2cd8", "cache_key": "0f769f3039f2739f9bfaba71e6ecb1d8f126aacf427751d5f674c677d50dfc5c", "commit": "305465a7337dac4c448e95ab69846f4837523436", "correct": true, "logs": ["/gpfs/scratch/nimarano/hpc-forest-cuda-memory-00674889b3a54de1b9bb850eed2279e6/results-775815/cuda-nbody/logs/e1/1a380d99a03b42a0/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-00674889b3a54de1b9bb850eed2279e6/results-775815/cuda-nbody/logs/e1/1a380d99a03b42a0/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-00674889b3a54de1b9bb850eed2279e6/results-775815/cuda-nbody/logs/e1/1a380d99a03b42a0/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-00674889b3a54de1b9bb850eed2279e6/results-775815/cuda-nbody/logs/e1/1a380d99a03b42a0/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-00674889b3a54de1b9bb850eed2279e6/results-775815/cuda-nbody/logs/e1/1a380d99a03b42a0/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-00674889b3a54de1b9bb850eed2279e6/results-775815/cuda-nbody/logs/e1/1a380d99a03b42a0/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-00674889b3a54de1b9bb850eed2279e6/results-775815/cuda-nbody/logs/e1/1a380d99a03b42a0/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.0005237849692291979, "reason": "", "score": 0.7790399716582347, "status": "valid", "times": [0.0005239514069947524, 0.000523452651684931, 0.0005238091299210192, 0.0005237377838673014, 0.0005239738736779853], "tree_hash": "3fbc93faa6a5717f293fb95e99598e65e474cf6c"}, "status": "confirmed"}`.

Commit retenu après confirmation : `305465a7337dac4c448e95ab69846f4837523436`.
Temps confirmé : 0.000524 s ; référence confirmée : 0.001847 s.
Réduction mesurée : 71.6%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Shared-memory tiling of source particles | In src/nbody_kernel.cu and src/launch.json, develop and measure shared-memory source tiling: cooperatively stage source Particle records and reuse each tile across target threads, with correct synchronization and tail handling. Explore tile geometry and legal shared-memory/block settings within the 49,152-byte limit. Preserve the 28-byte Particle layout, entry point, and full input-size correctness; pass all stated edge cases and oracle/tolerance checks. Judge by the official geometric-mean CUDA-event time for N=4096,8192,16384, not by an assumed bandwidth gain. |
| T2 | Pairwise force arithmetic and numerical accuracy | In src/nbody_kernel.cu, explore an equivalent direct-acceleration formulation that cancels the target mass from the force sum, and selectively evaluate reciprocal-square-root/cube arithmetic or other narrowly scoped math changes. Do not enable global fast math. Preserve softening, update order, exact mass output, and valid behavior for coincident positions, extreme positive masses, and zero or negative dt. Validate all required sizes and oracle tolerances before comparing official benchmark timings; retain slower or inaccurate variants as evidence, not candidates. |
| T3 | Register-blocked output mapping and launch geometry | In src/nbody_kernel.cu and src/launch.json, explore register-blocked output batching: make the kernel honor the configured items_per_block/grid relationship and evaluate a small number of outputs per thread, reusing each loaded source particle across those outputs where beneficial. Tune legal block and items_per_block settings for the three scored sizes. Keep this tree focused on output mapping/register reuse rather than shared-memory staging or a changed force formula, so its results are complementary to the other missions. Preserve complete output and correctness for all required sizes and edge cases; rank by measured geometric-mean kernel time. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| de30553b88e54531 | T1 | search | valid | 0.000996 | df4438e6f415 |
| 5398a8f78ec94cc1 | T2 | search | incorrect | — | f411f556be87 |
| 15e748c538d3437c | T3 | search | valid | 0.002587 | fe8f77b0e875 |
| d92cf45cd6814646 | T1 | search | valid | 0.000965 | c18c1fd373b3 |
| 16acacf704444b7c | T3 | search | valid | 0.002674 | 72ec21144816 |
| 8dc9c16f618345ed | T1 | search | valid | 0.001197 | 62d3ae81147a |
| 4b1937b9658c4b1f | T2 | search | valid | 0.001850 | 755c7740d624 |
| ddc14e877adb45d7 | T3 | search | valid | 0.004258 | 52dba08ff5e2 |
| 0fa3c15e02bc4240 | T1 | search | valid | 0.000965 | 48202aae3818 |
| 2b0d41e0d521450c | T3 | search | valid | 0.002597 | 016730e28971 |
| 634bff6fffc04501 | T1 | search | valid | 0.000963 | cce3543891ba |
| f5b5515eac7f42bc | T2 | search | valid | 0.001016 | 75404c04e63a |
| 357bbe6e115540df | T1 | search | valid | 0.000967 | 6d6471a4897e |
| 6aabcd3c82f94ae7 | T2 | search | valid | 0.001033 | addd8f8a564a |
| 6254e9c4756443e9 | T1 | search | valid | 0.000969 | dbfee3df9142 |
| c7a378a9af3d4d0d | T3 | search | valid | 0.002593 | f61eee9efe95 |
| c4dd3a2f62154641 | T1 | search | valid | 0.000971 | 85510988d229 |
| bfcb46dd975e49d9 | T3 | search | valid | 0.002570 | 5d4b4014ee06 |
| b3e3951ce1ec4c59 | T2 | search | generation_failed | — |  |
| 18c0e5f33d554ea1 | T1 | search | valid | 0.000969 | 462c77efd2d2 |
| d9eff8edb675451d | T1 | search | valid | 0.000964 | 7a198dfe81c7 |
| 92d277cd78574f87 | T3 | search | valid | 0.002691 | 6792ea295ff4 |
| b952bd34ae97444d | T1 | search | valid | 0.000968 | e051c3b6bf99 |
| ab6e69917d074845 | T1 | search | valid | 0.000968 | b9ec24c7d89b |
| b9c8264315b147ca | G | postprocess | valid | 0.000592 | 62f7c3006d55 |
| 1a380d99a03b42a0 | G | postprocess | valid | 0.000524 | 305465a7337d |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
