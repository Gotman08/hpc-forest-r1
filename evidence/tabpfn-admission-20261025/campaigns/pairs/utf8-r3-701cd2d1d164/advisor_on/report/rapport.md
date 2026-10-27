# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `c4a1a5b43d364d43c3cab996d4decf23f9406d32cbdbbc749a8fd913662af5ff`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 91, "tokens_used": 7833397, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 7833397}`.
Coûts par phase : `{"search": {"slots": 80, "tokens_used": 6718635, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 6718635}, "postprocess": {"slots": 7, "tokens_used": 1114762, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1114762}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "d55dc74ffb2640b0", "outcome": {"binary_sha256": "8e357a97fccbab8d656081696d924418a9ef70a99f6fb08ca9b8d8802ace2a04", "cache_key": "be2271cc5a6a8577dd8cc890d523aa214b776119fc3eaa1150a6607336da2b51", "commit": "a15d3cb0b3a2518dbb771541a32ee3e2554a1756", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r3-701cd2d1d164/forest-app-5b8ac6f7980a40379319b138d98aa9bb/campaign/logs/e1/d55dc74ffb2640b0/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r3-701cd2d1d164/forest-app-5b8ac6f7980a40379319b138d98aa9bb/campaign/logs/e1/d55dc74ffb2640b0/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r3-701cd2d1d164/forest-app-5b8ac6f7980a40379319b138d98aa9bb/campaign/logs/e1/d55dc74ffb2640b0/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r3-701cd2d1d164/forest-app-5b8ac6f7980a40379319b138d98aa9bb/campaign/logs/e1/d55dc74ffb2640b0/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r3-701cd2d1d164/forest-app-5b8ac6f7980a40379319b138d98aa9bb/campaign/logs/e1/d55dc74ffb2640b0/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r3-701cd2d1d164/forest-app-5b8ac6f7980a40379319b138d98aa9bb/campaign/logs/e1/d55dc74ffb2640b0/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r3-701cd2d1d164/forest-app-5b8ac6f7980a40379319b138d98aa9bb/campaign/logs/e1/d55dc74ffb2640b0/confirmation/attempt-001/sample-4.log"], "mean_seconds": 8.110904792023683e-06, "reason": "", "score": 0.8588761267788897, "status": "valid", "times": [8.110856170636566e-06, 8.114262780418643e-06, 8.112639098374387e-06, 8.108530281394368e-06, 8.108235629294452e-06], "tree_hash": "61782188ff37077349f484c82211fabcf0a74544"}, "status": "confirmed"}`.

Commit retenu après confirmation : `a7a572ac05b8679e88fdc987de9f3e8a386be589`.
Temps confirmé : 0.000007 s ; référence confirmée : 0.000049 s.
Réduction mesurée : 85.9%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Full-block SIMD validation of mixed-width UTF-8 | Focus on full-block SIMD validation of mixed-width UTF-8: classify bytes and check continuation requirements and special lead-byte constraints across blocks. Do not treat an all-ASCII block check with scalar fallback as the main experiment; that overlaps T2. Handle cross-block sequences and tails explicitly, with no out-of-bounds reads. Use only ISA features supported by the actual build and target. Preserve rejection of malformed continuations, overlong forms, surrogates, values above U+10FFFF, and truncation. Keep the required run signature, overwrite the complete uint32 output on every call, and respect the thread budget. Check correctness on ASCII and malformed inputs, then measure the specified valid mixed-width workload against the baseline. |
| T2 | Word-at-a-time ASCII scanning with scalar multibyte decoding | The baseline already scans ASCII one byte at a time before scalar multibyte decoding. Test whether bounded word-at-a-time high-bit detection can reduce that scanning cost, retaining strict scalar decoding from the first non-ASCII byte. Do not turn this into full vector UTF-8 validation or a bytewise DFA, which are T1 and T3. Handle tails safely without overreads. Preserve all Unicode scalar-value checks, the required run signature, complete output overwrite, and the thread budget. Measure the specified valid mixed-width workload against baseline; report ASCII performance separately rather than assuming an ASCII-only gain helps the primary workload. |
| T3 | Table-driven scalar DFA | Explore a compact table-driven or branch-reduced scalar DFA that validates byte classes and sequence state without word-at-a-time scanning or SIMD. Ensure transitions reject overlong encodings, surrogates, values above U+10FFFF, malformed continuations, and truncated sequences. Keep the required run signature, write the complete uint32 output each call, and respect the thread budget. Measure against the baseline on mixed-width and ASCII workloads and verify malformed cases before comparing timings. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 43e49a848f564c62 | T1 | search | valid | 0.000019 | 840fd026f80b |
| 397d41f7598c4b7b | T2 | search | valid | 0.000046 | b4261a18108c |
| b1050a3a970c49ac | T3 | search | valid | 0.000108 | b9876c42795f |
| 370e41d399354680 | T2 | search | valid | 0.000052 | 0484bf92e7e2 |
| c44c427f3f694a2c | T1 | search | valid | 0.000018 | 6a79d69b676c |
| a8516afcc8c94955 | Gm1 | search | valid | 0.000022 | a790b2688984 |
| fd86635b1b2b4271 | T3 | search | valid | 0.000125 | 0510c23ffe05 |
| d752849eabd54ffd | T2 | search | valid | 0.000048 | d3cf7feca09f |
| 1660a53101f04c0a | T1 | search | valid | 0.000012 | b2cefbe0bf35 |
| 7a58186aaa024533 | T3 | search | valid | 0.000079 | 4303f24ce36b |
| 5e0f1f2e19bd427f | T3 | search | valid | 0.000079 | 88d21a1cd885 |
| 913e0856cf4a4bb4 | T1 | search | valid | 0.000010 | 078b49031e8c |
| ff34d69c7c414782 | T1 | search | valid | 0.000008 | 477d1da9e1a8 |
| b1f738f60fa74b90 | T3 | search | valid | 0.000107 | 2ed3998cfeb6 |
| b8b433e0d071465f | T1 | search | valid | 0.000011 | b98214e12b1d |
| daa138c663334f91 | T1 | search | valid | 0.000013 | a30313acbe08 |
| 7024fe5cca594d4b | T1 | search | valid | 0.000008 | 451bbc898a00 |
| 5ffcbc8762854895 | T1 | search | valid | 0.000007 | a7a572ac05b8 |
| adfc4b3e0e504441 | T1 | search | valid | 0.000008 | 37e2f5979da4 |
| 89de0c1f3ab54753 | T1 | search | valid | 0.000009 | cd4d7f994398 |
| 4a1b8e4b653a4562 | T1 | search | valid | 0.000009 | a3bb55d7bc09 |
| 232e666c0a094a47 | T1 | search | valid | 0.000009 | db4e57fb3805 |
| d610a2f0921149ec | T1 | search | valid | 0.000012 | a830b16fdb6b |
| d77c9f90ed0741c6 | Gm2 | search | valid | 0.000008 | cb7f8dd1dcaa |
| d55ea453fad643eb | G | postprocess | valid | 0.000007 | fb6959169da9 |
| d55dc74ffb2640b0 | G | postprocess | valid | 0.000008 | a15d3cb0b3a2 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
