# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `1c0a54b6b4cba0132b3338d62d8be30cde6f11905589ce1a9da6b3ae56339e04`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 128, "tokens_used": 11910093, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 11910093}`.
Coûts par phase : `{"search": {"slots": 121, "tokens_used": 11201429, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 11201429}, "postprocess": {"slots": 3, "tokens_used": 708664, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 708664}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "e1b9e5eb08384e5a", "outcome": {"binary_sha256": "60876698953bb6c2a930f20ae505ba01d3aa38a511929e3486cd77ffa33728e6", "cache_key": "f1434c4e0fe0fd07551951f559bef8650c486a5fb649e23a25bd2b3210723113", "commit": "e7baab0d1e688b2682fe08799f74bab508e80b6b", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r2-9a62a153b580/forest-app-7dcaf3b27d454e7aa3f38795efe3050f/campaign/logs/e1/e1b9e5eb08384e5a/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r2-9a62a153b580/forest-app-7dcaf3b27d454e7aa3f38795efe3050f/campaign/logs/e1/e1b9e5eb08384e5a/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r2-9a62a153b580/forest-app-7dcaf3b27d454e7aa3f38795efe3050f/campaign/logs/e1/e1b9e5eb08384e5a/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r2-9a62a153b580/forest-app-7dcaf3b27d454e7aa3f38795efe3050f/campaign/logs/e1/e1b9e5eb08384e5a/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r2-9a62a153b580/forest-app-7dcaf3b27d454e7aa3f38795efe3050f/campaign/logs/e1/e1b9e5eb08384e5a/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r2-9a62a153b580/forest-app-7dcaf3b27d454e7aa3f38795efe3050f/campaign/logs/e1/e1b9e5eb08384e5a/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r2-9a62a153b580/forest-app-7dcaf3b27d454e7aa3f38795efe3050f/campaign/logs/e1/e1b9e5eb08384e5a/confirmation/attempt-001/sample-4.log"], "mean_seconds": 1.4485153404348668e-05, "reason": "", "score": 0.7731782073833421, "status": "valid", "times": [1.4488100510576232e-05, 1.448332736013985e-05, 1.4478644963503638e-05, 1.449216309263312e-05, 1.44835310948905e-05], "tree_hash": "96c5452b81f02499e38d8c6fdcaeb15315197f0f"}, "status": "confirmed"}`.

Commit retenu après confirmation : `b3cfb7899c673584dc984d8bb9307c6f97f0691b`.
Temps confirmé : 0.000012 s ; référence confirmée : 0.000049 s.
Réduction mesurée : 76.6%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Full-block SIMD UTF-8 validation | Explore full-block SIMD UTF-8 validation by checking lead/continuation structure and special lead-byte constraints across vector blocks, carrying sequence context exactly across block boundaries and handling incomplete tails without overreading. Keep the main experiment distinct from T2: vectorize validation of multibyte bytes rather than merely skipping ASCII blocks and parsing non-ASCII scalarly. Use only ISA features supported by the actual build target; exploit the guaranteed 64-byte input alignment only if beneficial. Use one thread, preserve the full run contract, and measure the complete call on the mixed-width workload while checking ASCII and malformed inputs. |
| T2 | Bulk ASCII skipping with scalar fallback | Explore bulk detection and skipping of pure-ASCII words or blocks, then use a correct scalar parser for regions containing non-ASCII bytes; do not make full SIMD multibyte validation the main mechanism, which is T1's contrast. Compare sensible word/vector check widths or fallback thresholds if useful, accounting for the cost of rescanning blocks that contain non-ASCII. The input base is guaranteed 64-byte aligned, but handle arbitrary valid lengths and never overread the final partial block. Use one thread, preserve the full run contract, and measure the complete call on the mixed-width workload while checking ASCII and malformed inputs. |
| T3 | Branch-reduced scalar DFA | Explore a single-threaded, table-driven scalar UTF-8 DFA to reduce the baseline's per-codepoint branching and dependency cost. Ensure the accept/reject state distinguishes incomplete trailing sequences and rejects overlong encodings, surrogates, illegal leads, and out-of-range values. Measure the mixed-width workload and verify ASCII and malformed inputs; use no input-specific assumptions or extra threads. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 8ba10ee624d74edc | T1 | search | valid | 0.000040 | 755c115e4137 |
| c00a05f1e33c4d70 | T2 | search | valid | 0.000056 | b01fc917b96b |
| 1950fabff7ce4ec1 | T3 | search | valid | 0.000107 | f87b17083aa1 |
| 1a8f396e515f4882 | T2 | search | valid | 0.000053 | 7fc1eef523ba |
| c5462a32b0d24718 | T3 | search | valid | 0.000111 | d84b2ab8a13a |
| 25b6f0c4d383444c | T1 | search | valid | 0.000026 | b3459d482700 |
| 42f40d7da44d44f5 | T2 | search | valid | 0.000053 | 0d7260b516f0 |
| 51cf02143f1d4953 | T3 | search | valid | 0.000077 | 072030be79a6 |
| 5b8d659e7a4d4bf9 | T1 | search | valid | 0.000018 | 26d353a71e66 |
| 9ebdaf79bfa643b7 | T2 | search | valid | 0.000068 | d0b1fcad5ab6 |
| fc57469d109844eb | T1 | search | valid | 0.000014 | 38b39080a0e8 |
| ad8e067112c64958 | T2 | search | valid | 0.000049 | ec6f8be6bdb0 |
| 59a70426f7f842ac | T3 | search | valid | 0.000076 | eb4f673866bc |
| 833d20bef71a467d | T1 | search | valid | 0.000019 | dcd1580965b6 |
| 4ab6375a8aee4123 | T2 | search | valid | 0.000049 | 0184843ce232 |
| 634db1cef7d04c7f | T3 | search | valid | 0.000114 | 6a5e5c624d1d |
| 83443b32e24d4e0d | T2 | search | valid | 0.000051 | bf26a1cb4175 |
| 8468274f5ead43c4 | T1 | search | valid | 0.000026 | 491c426593d6 |
| b978d8f816374d19 | T3 | search | valid | 0.000083 | 2a8f31681b82 |
| 09e8084cf30d4700 | T2 | search | valid | 0.000052 | af5382169118 |
| 6f4fac5a35b74e8c | T3 | search | valid | 0.000113 | 8825a1161c58 |
| 4153d688179a40eb | T1 | search | valid | 0.000022 | 1bad9c894704 |
| c03699d3ae5f49da | T2 | search | valid | 0.000049 | 8b588cd0fa14 |
| 50eefa01e27d4519 | T1 | search | valid | 0.000028 | ff3b821e891c |
| 19791bee318e46b9 | T1 | search | valid | 0.000012 | e356d872e17e |
| a840ab0b875146a5 | T1 | search | valid | 0.000014 | 05dc5e9a3c8d |
| e72d801b05214995 | T1 | search | valid | 0.000041 | 2444ff780887 |
| cd933fce59f64c30 | T1 | search | valid | 0.000015 | e1f6c4d66b92 |
| 3c03799a044d4ff2 | T1 | search | valid | 0.000012 | 0ede474035e6 |
| 9cae6e66c2ab4c12 | T1 | search | valid | 0.000014 | d93bd4846c4a |
| bce26b4eeef74040 | Gm1 | search | valid | 0.000014 | 117eaea58699 |
| 2bb72290e8ba4edb | T1 | search | valid | 0.000013 | 7ede50f4c7d8 |
| 8a44c84b32a84d31 | T1 | search | valid | 0.000021 | e8e401cc8b98 |
| 7d71785121184e77 | T1 | search | valid | 0.000026 | 448c0f594880 |
| 20b576b296934a57 | T1 | search | valid | 0.000025 | e07093e29da6 |
| df461f4e901c491b | T1 | search | valid | 0.000012 | b3cfb7899c67 |
| dc5d519a8d79403a | T1 | search | valid | 0.000023 | 23f132603420 |
| e1b9e5eb08384e5a | G | postprocess | valid | 0.000014 | e7baab0d1e68 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
