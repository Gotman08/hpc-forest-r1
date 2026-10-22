# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `479e4e7d906c6ae22b71757818736fb1f781e2a226741a7b11edda437d7bb952`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 18, "tokens_used": 8536702, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 8536702}`.
Coûts par phase : `{"search": {"slots": 5, "tokens_used": 217127, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 217127}, "postprocess": {"slots": 10, "tokens_used": 8319575, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 8319575}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "fe8207f9ecac4c0b", "outcome": {"binary_sha256": "6d56e1ccb60f58430d0a801aafab3328f81fc01fe86ec931e2a6d29454206b53", "cache_key": "2ea5b80447b4b4439f8b60dddc8596936da04a8c2db8e5236f3c9c9512855cb9", "commit": "d8052b227330b6fce97abdfad06e9a90a21d6be5", "correct": true, "logs": ["/gpfs/scratch/nimarano/hpc-forest-cuda-memory-21c416d16d78440a83e722965be34e7c/results-775521/cuda-nbody/logs/e1/fe8207f9ecac4c0b/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-21c416d16d78440a83e722965be34e7c/results-775521/cuda-nbody/logs/e1/fe8207f9ecac4c0b/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-21c416d16d78440a83e722965be34e7c/results-775521/cuda-nbody/logs/e1/fe8207f9ecac4c0b/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-21c416d16d78440a83e722965be34e7c/results-775521/cuda-nbody/logs/e1/fe8207f9ecac4c0b/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-21c416d16d78440a83e722965be34e7c/results-775521/cuda-nbody/logs/e1/fe8207f9ecac4c0b/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-21c416d16d78440a83e722965be34e7c/results-775521/cuda-nbody/logs/e1/fe8207f9ecac4c0b/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-21c416d16d78440a83e722965be34e7c/results-775521/cuda-nbody/logs/e1/fe8207f9ecac4c0b/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.000698771369939367, "reason": "", "score": 0.7254431181243203, "status": "valid", "times": [0.0006987139930235196, 0.0006990704844612785, 0.0006990149110387554, 0.0006985479117298238, 0.0006985095494434574], "tree_hash": "26ee1583ce33bf9e58227d4c1dd1657a68c49de4"}, "status": "confirmed"}`.

Commit retenu après confirmation : `d8052b227330b6fce97abdfad06e9a90a21d6be5`.
Temps confirmé : 0.000699 s ; référence confirmée : 0.001846 s.
Réduction mesurée : 62.2%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Explore staging source positions and mass in shared memory in source chunks so multiple target threads reuse each staged source. Keep the output mapping at one target per thread to distinguish this from register-blocked output work. Tune a valid block/items_per_block/shared_memory_bytes configuration and the shared tile layout; handle partial source and target tiles without letting inactive threads skip required barriers. Preserve i==j exclusion, the exact interface and all correctness requirements. Compare using the prescribed three-size geometric-mean kernel-time objective, and retain only candidates that pass the full correctness checks. | Shared-memory source tiling, one target per thread |
| T2 | Explore assigning a small batch of target particles to each thread, with separate accumulators, so a source particle's loaded position and mass can be reused across those targets. This is an output-axis/register-reuse investigation, not merely another one-target-per-thread shared-memory tile. Tune the batch size and allowed launch configuration while monitoring register pressure and available parallelism. Cover all target tails and preserve the full state, self exclusion, numerical requirements, and exact masses. Measure against the prescribed objective and validate every candidate with the complete oracle/check suite. | Register-blocked target outputs |
| T3 | Explore lowering the cost of pair evaluation while retaining the one-target-per-thread mapping as a clear comparison: for example, algebraically cancel target mass in the acceleration expression and evaluate inverse distance with rsqrtf to form an inverse-cube factor. Test arithmetic ordering and only consider FMA or loop unrolling when measurements justify them. These transformations change floating-point rounding: preserve softening and self exclusion, use no global fast-math option, and reject any candidate that fails tolerances, oracle checks, or the nonfinite-output constraint, including extreme-mass and coincident-position cases. Compare on the official geometric-mean metric. | Per-interaction arithmetic efficiency |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 85c1ff0376cc4045 | T1 | search | valid | 0.001008 | f72219ea2565 |
| 16bd9f82c0e34e9f | T2 | search | valid | 0.002605 | 5726c42e8265 |
| 2a7cd6b7c3af45e9 | T3 | search | incorrect | — | 03cef4df6207 |
| 79c03ae33d024935 | G | postprocess | valid | 0.001647 | 561cf3ca4d53 |
| fe8207f9ecac4c0b | G | postprocess | valid | 0.000699 | d8052b227330 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
