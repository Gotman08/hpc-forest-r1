# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `0e9bfe480502fba63cad990979c1fc1333a754c38464e763ad14227301e66505`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 149, "tokens_used": 11002496, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 11002496}`.
Coûts par phase : `{"search": {"slots": 141, "tokens_used": 10042673, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 10042673}, "postprocess": {"slots": 5, "tokens_used": 959823, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 959823}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "b0854f206d74484d", "outcome": {"binary_sha256": "2e70a09344c41cae7750949023c2f483ea0a777ac75a682c2f67d305f1df2bad", "cache_key": "4d083daed3808a2542cbb5583dbc8afe9f5167538a186d3ed7ea92d88b5becfb", "commit": "05b0cbdc349031fa7d60296ca4505c6cc852ad83", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-gemm_cpu-r1-176f460320cc/forest-app-6e7c2bfbd1464e33bddadc296a8bc190/campaign/logs/e1/b0854f206d74484d/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-gemm_cpu-r1-176f460320cc/forest-app-6e7c2bfbd1464e33bddadc296a8bc190/campaign/logs/e1/b0854f206d74484d/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-gemm_cpu-r1-176f460320cc/forest-app-6e7c2bfbd1464e33bddadc296a8bc190/campaign/logs/e1/b0854f206d74484d/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-gemm_cpu-r1-176f460320cc/forest-app-6e7c2bfbd1464e33bddadc296a8bc190/campaign/logs/e1/b0854f206d74484d/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-gemm_cpu-r1-176f460320cc/forest-app-6e7c2bfbd1464e33bddadc296a8bc190/campaign/logs/e1/b0854f206d74484d/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-gemm_cpu-r1-176f460320cc/forest-app-6e7c2bfbd1464e33bddadc296a8bc190/campaign/logs/e1/b0854f206d74484d/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-gemm_cpu-r1-176f460320cc/forest-app-6e7c2bfbd1464e33bddadc296a8bc190/campaign/logs/e1/b0854f206d74484d/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.0016956501794194423, "reason": "", "score": 0.9877826750368701, "status": "valid", "times": [0.0016782179942533319, 0.0016503753822868675, 0.0016791017577905834, 0.0017008333848974844, 0.001769722377868945], "tree_hash": "f97d114fcc00a250667ffee60b0753cff690767f"}, "status": "confirmed"}`.

Commit retenu après confirmation : `42aa467d66cb0cd819625d58c11046cab8e2b035`.
Temps confirmé : 0.001552 s ; référence confirmée : 0.137095 s.
Réduction mesurée : 98.9%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Single-thread cache locality and loop blocking | Explore a single-thread, cache-friendly row-major GEMM using loop interchange and cache blocking, with tile sizes that work across arbitrary n and correct handling of edge tiles. Keep this branch free of explicit SIMD intrinsics, panel packing, and OpenMP so it isolates locality and compiler auto-vectorization. Ensure every output element is assigned on every call, validate against the FP64 oracle for all supported sizes, and compare official timings at both timed sizes with one thread. |
| T2 | Explicit SIMD microkernel and panel packing | Explore an explicit register-tiled FP32 SIMD microkernel, using the ISA enabled for the supplied target; assess whether packing panels is worthwhile with its allocation and copy costs included. Keep this branch single-threaded to isolate kernel throughput. Handle arbitrary dimensions and edge tiles, overwrite all output elements, preserve the required FP32 tolerance for signed inputs, and measure both timed sizes with one thread. |
| T3 | OpenMP scaling and output ownership | Focus on OpenMP scaling and output ownership. With one fixed correct compute kernel per comparison, compare static row-stripe partitioning with static 2D output-tile ownership; avoid K-splitting reductions and global OpenMP state changes, and never exceed the caller's thread budget. Measure one and four threads at both timed sizes, including overhead. Keep kernel design fixed while comparing partition policies so this does not become a second broad single-thread kernel-tuning effort. Validate all supported sizes, preserve the FP32 tolerance, and overwrite the full output on every call. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 8a8cc1333f3c43f3 | T1 | search | valid | 0.012104 | c091c7e0b2ea |
| 70973fc15fdf43c7 | T2 | search | valid | 0.003556 | 7f60893e3279 |
| c2510c35213742a3 | T3 | search | valid | 0.067221 | bcaa27a9c2a9 |
| 55a536d8d1114644 | T1 | search | valid | 0.012171 | fb137f8ac936 |
| 332c73df3e7540b0 | T4 | search | valid | 0.001924 | f47f95577108 |
| c5e82dae69814bd5 | T2 | search | valid | 0.003410 | 6b3343aecd02 |
| 5ebc67539cff47ab | T3 | search | valid | 0.066104 | 21240cbf5632 |
| 4f16622ceb194d97 | Gm1 | search | valid | 0.002277 | b5e94f7c4230 |
| accaab7bc2bd4ddd | T4 | search | valid | 0.001939 | 6d82256d2464 |
| a63ed812cd4743bd | T1 | search | valid | 0.012090 | dcf9347fed42 |
| 494891fa0d1c4dd5 | T2 | search | valid | 0.003568 | 6ef0227b9e5b |
| 9295a6e815e04b08 | T3 | search | valid | 0.067321 | 6543698004a2 |
| f21ea94e426740f8 | T4 | search | valid | 0.001812 | f8f275aab7b7 |
| 9316d7cf5a374c7c | T1 | search | valid | 0.012112 | 72caf6ea9630 |
| 507a000ead5f441a | T2 | search | valid | 0.006583 | b886cbe2b389 |
| 652d2f35265c449b | T3 | search | valid | 0.064869 | f5fdcc854f7a |
| 7dd5858e0bd84820 | T4 | search | valid | 0.001788 | 8697306a8b3e |
| df14e812f3dd4565 | T1 | search | valid | 0.012176 | ef4c302dbed2 |
| 56c36e46d3b44ce2 | T2 | search | valid | 0.003050 | ec12dc93a87d |
| c38e960d31024e08 | T4 | search | valid | 0.001926 | 315cce17c2ac |
| b3ff02a6160540cd | T3 | search | valid | 0.065279 | 112b92954bbe |
| e22732ac0d8a4b34 | T1 | search | valid | 0.012178 | 2072b56fae3b |
| b1ce642e3e7d48c6 | T2 | search | valid | 0.002783 | e0245ffc39c5 |
| 5c1adad076dc496a | T4 | search | valid | 0.001936 | a35fae916fda |
| 08d4f644334e4c80 | T3 | search | valid | 0.067289 | 907738f2f0ce |
| cf158a19843c43bc | T1 | search | valid | 0.009028 | af4c16343bf7 |
| b06027acacc642e4 | T2 | search | valid | 0.002793 | 0d20a2414d38 |
| fb9586c2746844e9 | T3 | search | valid | 0.069388 | a8431acd21ec |
| 130bb3bdf15f40f9 | T4 | search | valid | 0.001531 | 42aa467d66cb |
| 16c12001d8a345cd | T1 | search | valid | 0.009978 | e1b0ce68046d |
| 5e7dcebbb68146d1 | T4 | search | valid | 0.001890 | d00e3765e28c |
| ac7f8947e57d4b05 | T4 | search | valid | 0.002067 | ed8a124be6ad |
| 5afb9ad923a94c74 | T4 | search | valid | 0.001904 | 4dc4043fbf15 |
| c0eedef61c984461 | T4 | search | valid | 0.002025 | 973c2c786a40 |
| b71e6b01378640a1 | T4 | search | valid | 0.001896 | 4b476df6d796 |
| 5e2e706bcdbb426f | T4 | search | valid | 0.001922 | cd4ebc4d5b73 |
| 10849fd6425c4290 | T4 | search | valid | 0.002251 | 7a05167e03a9 |
| 62ecff6ecff347b6 | T4 | search | valid | 0.001952 | f145248d9140 |
| 1cc2d792a7d348c1 | T4 | search | valid | 0.002064 | 047f552b4efa |
| e38d74b4b51c48c0 | T4 | search | valid | 0.001955 | ce0594d64047 |
| b5c05ebc2c694a4b | T4 | search | valid | 0.003201 | 4421918b7c6b |
| 774343788b0e43f1 | T4 | search | valid | 0.002068 | cc500144aa29 |
| 4ff490535fd94e43 | T4 | search | valid | 0.001831 | ea533d0a107d |
| 180c55ad23554988 | T2 | search | valid | 0.002888 | 24456cfcec99 |
| 6792ee09789544ea | T3 | search | valid | 0.067177 | 4c342bee0e24 |
| 7d55de3bbf574013 | T1 | search | valid | 0.013600 | 3599d05be353 |
| 9035608906054e86 | T1 | search | valid | 0.009764 | 753fb97e6b40 |
| 1debcabd2957425c | T3 | search | valid | 0.066332 | 7c52eb65dadf |
| 5f16ffb7eea840aa | T4 | search | valid | 0.002074 | 28a118614864 |
| c4a5509569ff42ae | T2 | search | valid | 0.002789 | 65ec50af49d6 |
| 9016fe091c2d4b32 | T3 | search | valid | 0.065589 | e27d5335d95b |
| 591206c4bc284509 | T4 | search | valid | 0.003581 | c31ddf8204f4 |
| 931ba28dbd5248d7 | T2 | search | valid | 0.004848 | adbf8c172f8a |
| 2f3083b6516d4e96 | T3 | search | valid | 0.068626 | 2be6f3b6d11a |
| daf969b5bf9542d5 | T4 | search | valid | 0.002015 | b0f2ff25376e |
| b0854f206d74484d | G | postprocess | valid | 0.001651 | 05b0cbdc3490 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
