# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `2bf2420a09f5d5011256b557405dbfd62834a9d1c7afb8db03288c5355866440`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 45, "tokens_used": 10056277, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 10056277}`.
Coûts par phase : `{"search": {"slots": 33, "tokens_used": 1965473, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1965473}, "postprocess": {"slots": 9, "tokens_used": 8090804, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 8090804}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "f1843fc5ccdb4b63", "outcome": {"binary_sha256": "094a0bf369221a92a3efbe5ed7908ce324d7b27b7bdbc1f9fdee8dd283efcd7c", "cache_key": "a0dd963f5d602b33dc35b5665ca99dc94192a84488ac97e9f3b25ae8ef5deb52", "commit": "fb0d9a4822413f62bf242c0a021d910821a9ac2a", "correct": true, "logs": ["/gpfs/scratch/nimarano/hpc-forest-cuda-memory-9c311c3ac9e8480b919384621c7e4f7e/results-776048/cuda-nbody/logs/e1/f1843fc5ccdb4b63/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-9c311c3ac9e8480b919384621c7e4f7e/results-776048/cuda-nbody/logs/e1/f1843fc5ccdb4b63/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-9c311c3ac9e8480b919384621c7e4f7e/results-776048/cuda-nbody/logs/e1/f1843fc5ccdb4b63/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-9c311c3ac9e8480b919384621c7e4f7e/results-776048/cuda-nbody/logs/e1/f1843fc5ccdb4b63/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-9c311c3ac9e8480b919384621c7e4f7e/results-776048/cuda-nbody/logs/e1/f1843fc5ccdb4b63/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-9c311c3ac9e8480b919384621c7e4f7e/results-776048/cuda-nbody/logs/e1/f1843fc5ccdb4b63/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-9c311c3ac9e8480b919384621c7e4f7e/results-776048/cuda-nbody/logs/e1/f1843fc5ccdb4b63/confirmation/attempt-001/sample-4.log"], "mean_seconds": 9.987650291964732e-05, "reason": "", "score": 0.9489303860787198, "status": "valid", "times": [0.00010014911992810768, 9.976289430066636e-05, 0.0001000045717944687, 9.956789052194024e-05, 9.989803805305365e-05], "tree_hash": "88e06dd102a33573ae70c5120cb56ae57d56fdc3"}, "status": "confirmed"}`.

Commit retenu après confirmation : `fb0d9a4822413f62bf242c0a021d910821a9ac2a`.
Temps confirmé : 0.000100 s ; référence confirmée : 0.001856 s.
Réduction mesurée : 94.6%. Référence conservée : non.

Mother a choisi **4 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Shared-memory source tiling | Explore conventional block-local source tiling while keeping one target particle per thread and serial traversal of the source dimension, so the main change is reusing staged source particles across output threads. Tune the tile layout and size, block configuration, and dynamic shared-memory setting within the stated launch limits. Handle arbitrary n and tail tiles without extra kernels, buffers, or host preprocessing. Preserve the entry point, Particle layout, complete outputs and masses; pass every supplied correctness case. Evaluate complete source-and-launch candidates using the official search measurements. |
| T2 | Per-thread multi-target coarsening | Explore register-level output coarsening: have each thread maintain multiple target particles and reuse each loaded source particle across those targets, without shared-memory source staging as the principal mechanism. Tune coarsening and launch parameters while handling all n and tails safely. Preserve the entry point, Particle layout, update order, complete output and exact masses; pass every supplied correctness case. Compare measured source-and-launch candidates under the official protocol. |
| T3 | Source-parallel force reduction | Explore a distinct mapping that assigns lanes within a warp (or block) to portions of the source-particle reduction for a target, then combines partial force sums. Focus on parallelizing the reduction dimension rather than output coarsening or block-wide source tiling. Handle arbitrary n, self-interaction exclusion, tail sources and reduction synchronization without races or extra launches/buffers. Preserve the entry point, Particle layout, integration order, and exact masses; validate all supplied cases and compare official measurements. |
| T4 | Force arithmetic simplification | Explore per-interaction arithmetic reductions such as safe factoring of the target-mass term, reciprocal-square-root use, or other instruction simplifications compatible with NVRTC CUDA 12.6.3 and no global fast-math option. Keep self-interaction exclusion unless an alternative is proven safe, preserve float32 state and exact masses, and reject transformations that fail the FP64-oracle tolerances or produce nonfinite output—including on the isolated extreme-mass case. Keep the entry point and single-kernel interface; measure complete source-and-launch candidates using the official protocol. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| aae515bf57f94665 | T1 | search | valid | 0.000969 | d28aed5445e6 |
| e099ff53da844775 | T2 | search | valid | 0.002615 | cdd3e221b598 |
| 072b1a80b8fa466d | T3 | search | valid | 0.000152 | e568be9d2b0a |
| 7a33f8f04fdf415f | T4 | search | valid | 0.001015 | ce2d18e6b1bf |
| 2edf23e904aa477b | T1 | search | valid | 0.000993 | 9caf39a75943 |
| 335e165bec36493e | T2 | search | valid | 0.004168 | c71f1693d69a |
| 36b0e8c95e694a2e | T4 | search | incorrect | — | 3121437eed1f |
| 54965513c23b4631 | T3 | search | valid | 0.000144 | 1174186ce4c7 |
| 5e30f66d28c84e34 | T1 | search | valid | 0.000959 | 2ab238d9ae80 |
| 3aec87f1ed714bf4 | T2 | search | valid | 0.002582 | b370a56ebb02 |
| 8052fe0a6b7b4d62 | T3 | search | valid | 0.000133 | 3c16471bb695 |
| b067236e66fc41e3 | T1 | search | valid | 0.000961 | 0bc4fed352dc |
| 986ed4e1c49d44e1 | T3 | search | valid | 0.000144 | fff81576991c |
| 917b639f9f734e82 | T4 | search | valid | 0.001849 | f3bfaae6e930 |
| d4299d0b4ca44112 | T1 | search | valid | 0.000967 | 43a59806dd5e |
| 08eb76bfcf6f4c3b | T2 | search | valid | 0.002765 | 2fe73e60b35e |
| 6c7b9306ff1c45c4 | T3 | search | valid | 0.000197 | 5365e150fcab |
| 4cac546b57bc4d08 | T1 | search | valid | 0.000968 | a643c0538bcf |
| 929d39cd705e4487 | T2 | search | valid | 0.002585 | 0eaf17a3443e |
| 7d651842ff4e48f5 | T3 | search | valid | 0.000298 | 92047ac5dde8 |
| cc1fd62237d84c67 | T1 | search | valid | 0.000890 | adf6c55fc118 |
| 206c8a2af7294599 | T4 | search | valid | 0.001180 | fa94899b99fa |
| b306ffa7eebb4043 | T2 | search | valid | 0.003425 | 415fe5459819 |
| 0c5c6d925f44466a | T3 | search | valid | 0.000141 | 253496638f8e |
| adcb4f6a36b74958 | T4 | search | valid | 0.001180 | e424f134d842 |
| 7bedf3b808574349 | T1 | search | incorrect | — | 96aa0ba05b33 |
| 82706559abee4549 | T2 | search | valid | 0.004251 | d96ceb0a16ad |
| f914248a67cb48e9 | T4 | search | valid | 0.001090 | dee732bf8034 |
| 9bcc1b2d95ca4e8b | T3 | search | valid | 0.000133 | d6e7f0135a89 |
| 6aa6069b720f4954 | T2 | search | incorrect | — | e0c0832e67a3 |
| 2505e16e21d24a25 | T1 | search | valid | 0.000921 | 70859ca128a3 |
| bd224cee51694d00 | G | postprocess | valid | 0.000101 | 5a33efdbbf12 |
| f1843fc5ccdb4b63 | G | postprocess | valid | 0.000100 | fb0d9a482241 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
