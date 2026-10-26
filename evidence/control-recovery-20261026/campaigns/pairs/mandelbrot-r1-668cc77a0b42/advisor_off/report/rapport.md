# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `ea2b10a6d1912fa4de4e9ecd951b8bfae5ffd7368bead0b8271d1059a6bace15`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 114, "tokens_used": 8588842, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 8588842}`.
Coûts par phase : `{"search": {"slots": 106, "tokens_used": 7742377, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 7742377}, "postprocess": {"slots": 5, "tokens_used": 846465, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 846465}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "72f779ce9af1464e", "outcome": {"binary_sha256": "31c4df09d31effd9de6228f0a0679b682fabc55880fe211fa2f0e42aa70d2c14", "cache_key": "0fe351702d3cb6cb00efa75b13ae200ab136f31724119147c2ab4782889e855c", "commit": "36064df89d7b14e49d54b8701e9e6c1daa2f1b42", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r1-668cc77a0b42/forest-app-a83db43b9056497ea5d5cb022d35a3a4/campaign/logs/e1/72f779ce9af1464e/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r1-668cc77a0b42/forest-app-a83db43b9056497ea5d5cb022d35a3a4/campaign/logs/e1/72f779ce9af1464e/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r1-668cc77a0b42/forest-app-a83db43b9056497ea5d5cb022d35a3a4/campaign/logs/e1/72f779ce9af1464e/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r1-668cc77a0b42/forest-app-a83db43b9056497ea5d5cb022d35a3a4/campaign/logs/e1/72f779ce9af1464e/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r1-668cc77a0b42/forest-app-a83db43b9056497ea5d5cb022d35a3a4/campaign/logs/e1/72f779ce9af1464e/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r1-668cc77a0b42/forest-app-a83db43b9056497ea5d5cb022d35a3a4/campaign/logs/e1/72f779ce9af1464e/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r1-668cc77a0b42/forest-app-a83db43b9056497ea5d5cb022d35a3a4/campaign/logs/e1/72f779ce9af1464e/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.1066633153291628, "reason": "", "score": 0.8407631502761209, "status": "valid", "times": [0.10663570435909472, 0.10666405987722036, 0.10663475304424741, 0.1067492442869001, 0.10663281507835143], "tree_hash": "50caf21779334686f62f6231b47ad779f3a1f3f9"}, "status": "confirmed"}`.

Commit retenu après confirmation : `adf65d0bc500785421a821908699686fc5b9396d`.
Temps confirmé : 0.106625 s ; référence confirmée : 0.563177 s.
Réduction mesurée : 81.1%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | OpenMP decomposition and irregular-work scheduling | Within the scalar-per-pixel path, compare contiguous static rows, interleaved rows, and bounded tiles with static versus dynamic or guided scheduling. Measure load imbalance against scheduling overhead, including uneven escape counts; make the one-thread path avoid unnecessary parallel overhead and respect threads as the CPU budget. Preserve baseline coordinates and per-pixel float recurrence, overwrite all output, and validate correctness across small and shifted-bound cases as well as n=1024 at one and four threads. |
| T2 | Exact SIMD with divergence-aware pixel grouping | Compare compiler-vectorized and explicit SIMD approaches using only ISA features compatible with the official build. Test adjacent-x packets against a two-dimensional tile or row-interleaved lane mapping to assess divergence. Match each lane's baseline coordinate arithmetic, recurrence order, escape test, and count exactly; do not introduce approximate membership, reassociation, or FMA unless equivalence is proven. Primarily measure one thread to isolate SIMD, then report correctness and performance at the official sizes and thread counts. |
| T3 | Exact floating-point orbit-cycle detection | Explore exact periodic-orbit acceleration for long-lived pixels. Contrast low-cost fixed-point detection with bounded recent-state or other exact cycle-detection approaches; only skip remaining iterations after a repeated finite floating-point state establishes a cycle whose checked states have not escaped. Preserve baseline counts and fall back otherwise. Measure detection overhead and saved work on canonical and shifted bounds at one and four threads; report unsuccessful approaches and validate all outputs. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| f9550da5d9bc4e59 | T1 | search | valid | 0.283527 | 640c606c9a9a |
| f9a9a1a0733548ef | T2 | search | incorrect | — | 2014afb2c07e |
| 48c223ac50d64f9e | T3 | search | valid | 0.479870 | 1dc8531d04d0 |
| 07aa2e8c993a49ee | T1 | search | valid | 0.362418 | 1b26062f44bf |
| e2c13688873b49df | T2 | search | incorrect | — | b2210255d8b2 |
| fdcf63350df84c09 | T3 | search | valid | 0.203893 | d57d83dce99a |
| 2c1dab3a16f64135 | T1 | search | valid | 0.283999 | e96868f04ba0 |
| 9978db8cdc0f4e1d | T3 | search | valid | 0.241661 | b2ab9e71b681 |
| 85b74821d3dc4ce5 | Gm1 | search | valid | 0.110977 | 6d7942082b94 |
| be5acce43bb64783 | T1 | search | valid | 0.304972 | 0e435ab7b02c |
| c472965d20e44c74 | T2 | search | valid | 0.563774 | 2933d7b4cba0 |
| 41a480f7555e439d | T3 | search | valid | 0.125017 | 4f4df1fd60b4 |
| 322d5986637544a6 | T1 | search | valid | 0.295671 | ee1276d30e7c |
| 84c4532c35d84099 | T1 | search | valid | 0.304700 | 45267468ec20 |
| fb88db9dfd554de8 | T3 | search | valid | 0.168841 | e80032a13b55 |
| ef2737b29f8b4b21 | T1 | search | valid | 0.282153 | 5107d3f8deea |
| 50ef9aae38234b6f | T2 | search | incorrect | — | 8edd42ec5235 |
| 53af1a91aefc4ee6 | T1 | search | valid | 0.288352 | b50dc3abf15d |
| 571ba51a73024aea | T1 | search | valid | 0.282413 | b6dcd2e87208 |
| 8d139110ae3c4d42 | Gm2 | search | valid | 0.107968 | a637752c402a |
| fb02fd16d9e34228 | T4 | search | valid | 0.108093 | ce6a1bf0e566 |
| 43c615c03dc349ba | T4 | search | valid | 0.106942 | 627b7cc50b47 |
| 661a40d422bf4587 | T4 | search | valid | 0.107208 | b8e93b46bb63 |
| b74972de9f9f476f | T4 | search | valid | 0.108019 | e08e081310b2 |
| 12f071b30dc74e71 | T4 | search | valid | 0.108042 | d69057bbc3c7 |
| b143ee04517148a8 | T4 | search | valid | 0.106616 | adf65d0bc500 |
| 6556f93073534486 | T2 | search | valid | 0.562778 | 54ea23b24ab7 |
| 0d4e29d991934ed9 | T3 | search | valid | 0.247418 | 79ca8b558518 |
| 5a82e95e993f406d | T4 | search | valid | 0.108417 | 7440ec6b2f24 |
| 3ce89b17bbfb4536 | T3 | search | valid | 0.120550 | b9622a036745 |
| eb936ee5f0ad4370 | T2 | search | valid | 0.565095 | 0bf2d26961a6 |
| 2cfd886cc88f4b1e | T1 | search | valid | 0.288675 | a4dd72e2131f |
| a2e50733f662495b | T2 | search | valid | 0.362011 | 53d6adec014a |
| fbe1a159b264445c | T3 | search | valid | 0.123402 | eff0698de0ae |
| 911ac6e9fb2c43b9 | T1 | search | valid | 0.307137 | 8e1193a0a411 |
| ec13215ff3af45b7 | T3 | search | valid | 0.131806 | eb674d023b0a |
| 625a7f07f2f1415c | T2 | search | valid | 0.565705 | a7fa9a149edb |
| 8ac20515369045fb | T4 | search | valid | 0.107702 | 65bcde302b6d |
| 0d0a2433f8314b83 | T4 | search | valid | 0.108057 | c2ac7c92b4fa |
| 61aaad3f874a4916 | G | postprocess | valid | 0.112033 | 29ee5decdd5d |
| 72f779ce9af1464e | G | postprocess | valid | 0.106618 | 36064df89d7b |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
