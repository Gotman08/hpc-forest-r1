# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `c2902d383c65e79f3a94f1724324dd4bfd52c4e727a59f0c27b8ee557bda7528`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 103, "tokens_used": 9364442, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 9364442}`.
Coûts par phase : `{"search": {"slots": 85, "tokens_used": 6852090, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 6852090}, "postprocess": {"slots": 15, "tokens_used": 2512352, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2512352}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "44bcee95cd284e27", "outcome": {"binary_sha256": "0d4ba11cec855622506a4856a987a638edd1d7569081cd5c8435412eb3622dce", "cache_key": "f7cc3b398e4a2b846ad2d546f75b50472df4aa80e206cf7bfaa6eecf1723c629", "commit": "8d6fe0cf91b08e0c4546aa72a8a887d7979dd2b0", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r1-21612544cf49/forest-app-a3a4c23609b340ddb2928568143a9cad/campaign/logs/e1/44bcee95cd284e27/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r1-21612544cf49/forest-app-a3a4c23609b340ddb2928568143a9cad/campaign/logs/e1/44bcee95cd284e27/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r1-21612544cf49/forest-app-a3a4c23609b340ddb2928568143a9cad/campaign/logs/e1/44bcee95cd284e27/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r1-21612544cf49/forest-app-a3a4c23609b340ddb2928568143a9cad/campaign/logs/e1/44bcee95cd284e27/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r1-21612544cf49/forest-app-a3a4c23609b340ddb2928568143a9cad/campaign/logs/e1/44bcee95cd284e27/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r1-21612544cf49/forest-app-a3a4c23609b340ddb2928568143a9cad/campaign/logs/e1/44bcee95cd284e27/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r1-21612544cf49/forest-app-a3a4c23609b340ddb2928568143a9cad/campaign/logs/e1/44bcee95cd284e27/confirmation/attempt-001/sample-4.log"], "mean_seconds": 6.9251478361564515e-06, "reason": "", "score": 0.8768222448065973, "status": "valid", "times": [6.9226428396572845e-06, 6.91904669647292e-06, 6.9312994016952e-06, 6.929469100197762e-06, 6.923281142759093e-06], "tree_hash": "a45f5f4db5e3c08c26615e4003546a0ffdd3514e"}, "status": "confirmed"}`.

Commit retenu après confirmation : `8d6fe0cf91b08e0c4546aa72a8a887d7979dd2b0`.
Temps confirmé : 0.000007 s ; référence confirmée : 0.000049 s.
Réduction mesurée : 86.0%. Référence conservée : non.

Mother a choisi **2 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | SIMD validation of UTF-8 structure across blocks | Explore exact blockwise SIMD UTF-8 validation, checking lead/continuation relationships and special second-byte bounds for overlong encodings, surrogates, and values above U+10FFFF. This must go beyond SIMD-only ASCII scanning. Handle sequences crossing block boundaries and any scalar edges or tail without overreads. Compile with the unchanged build and ensure any ISA-specific path is safe for the actual target. Preserve exact validation for every input, write uint32_t 1 or 0 every call, respect the threads budget, measure on the official mixed-width workload, and record failed approaches and correctness results. |
| T2 | Scalar word-at-a-time ASCII skipping and sequence decoding | Explore a scalar-only alternative to the baseline bytewise ASCII loop: detect all-ASCII machine words using safe loads such as memcpy, then validate non-ASCII sequences with a compact, potentially branch-reduced scalar decoder. Do not use SIMD or assume ASCII runs are long; measure whether chunk skipping helps on the official mixed-width workload. Avoid aliasing violations and out-of-bounds reads, preserve every UTF-8 validity rule and full output overwrite, respect the threads budget, and record failed approaches and correctness results. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 163f3f7a29ec422b | T1 | search | valid | 0.000022 | 3609a382a0f6 |
| fc03e51496b1450a | T2 | search | valid | 0.000101 | 11eb9835c9ef |
| f7c5a2eb0ac14b7c | T2 | search | valid | 0.000043 | 9fe16413036b |
| eec750b6443a4775 | T1 | search | valid | 0.000166 | 1982e5ee019f |
| 1df016036f814951 | T2 | search | valid | 0.000056 | 4c39a71b7b04 |
| 2688d70282ef49f6 | T2 | search | valid | 0.000057 | 6a7f3b56e37a |
| a6d0c9d8674b4651 | T1 | search | valid | 0.000061 | 2e53895510a9 |
| af3509f3897a4a93 | T1 | search | valid | 0.000022 | 7ad6bff8ed7f |
| e452a14152f74ca9 | T1 | search | valid | 0.000009 | 89d45a31c20d |
| 51f2c940e4584b6d | T1 | search | valid | 0.000009 | ceaba141a78e |
| 805e456fd1d14a74 | T1 | search | valid | 0.000012 | 8f26d096f6e4 |
| 97fa212d00ff4335 | T1 | search | valid | 0.000011 | 83fb57e61cb6 |
| c4fb66ffc6344cf7 | T1 | search | valid | 0.000008 | 7e9920ef096f |
| 344208d19711433c | T1 | search | valid | 0.000008 | 47d422310458 |
| 2b403f3d7c77453c | Gm1 | search | valid | 0.000011 | 582223d23805 |
| 384a53dc0f194cfa | T1 | search | valid | 0.000007 | 929f14733038 |
| 081399ac5b9f40d1 | T1 | search | valid | 0.000007 | f283b2c9110b |
| 15d5c03716b34c32 | T1 | search | valid | 0.000021 | 0caeb1d0bffd |
| bc731269e4ce40db | T1 | search | valid | 0.000008 | afb334a0e6ed |
| 167d4a7089444b7c | T1 | search | valid | 0.000009 | b59adf043cf5 |
| e636b1e72e84472c | T1 | search | valid | 0.000017 | 4d250cfc0e65 |
| c07710de38ef46fb | T1 | search | valid | 0.000009 | c32c4c6f36bd |
| dba42c82f9af425a | T1 | search | valid | 0.000009 | af3e59921a11 |
| 5ba432d7d0d94686 | T1 | search | valid | 0.000011 | 995fa3af8fe4 |
| a8827e2e03e94865 | T1 | search | valid | 0.000008 | 1b2fee2d603b |
| 55cb1737ae9c4025 | T1 | search | valid | 0.000009 | 1c389104b619 |
| bf7dba82cf2240ff | T1 | search | valid | 0.000008 | 4c776102b035 |
| a01332aae2ae4bea | G | postprocess | valid | 0.000007 | c9efe5d720e2 |
| 62a5446de2304104 | G | postprocess | valid | 0.000007 | 636c3142592a |
| 4f47ddfbf1f449a0 | G | postprocess | valid | 0.000007 | eb3b0afca250 |
| 44bcee95cd284e27 | G | postprocess | valid | 0.000007 | 8d6fe0cf91b0 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
