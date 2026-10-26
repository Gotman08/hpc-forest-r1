# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `d51afaf8cf13e06f9e849964d804596a2d4bf56ca0ca2d7e6564a94ddd9ab9b9`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 108, "tokens_used": 8704238, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 8704238}`.
Coûts par phase : `{"search": {"slots": 98, "tokens_used": 7622830, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 7622830}, "postprocess": {"slots": 6, "tokens_used": 1081408, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1081408}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "f842bfbaa9804a6d", "outcome": {"binary_sha256": "f23ec8579915ff8887244334b7a3d8944528df9282b5a7decdb11c99f277aa67", "cache_key": "3556f4c30d6f18d4c3fa9d58aeb13054a21cdeead1fb642b977265146c1c3b43", "commit": "826a97bf2940f2406bf3b31c8ff6a42539d97542", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-base64-r1-4e1bad085b18/forest-app-a97c186a987d4947b5779ac5c9d4678e/campaign/logs/e1/f842bfbaa9804a6d/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-base64-r1-4e1bad085b18/forest-app-a97c186a987d4947b5779ac5c9d4678e/campaign/logs/e1/f842bfbaa9804a6d/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-base64-r1-4e1bad085b18/forest-app-a97c186a987d4947b5779ac5c9d4678e/campaign/logs/e1/f842bfbaa9804a6d/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-base64-r1-4e1bad085b18/forest-app-a97c186a987d4947b5779ac5c9d4678e/campaign/logs/e1/f842bfbaa9804a6d/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-base64-r1-4e1bad085b18/forest-app-a97c186a987d4947b5779ac5c9d4678e/campaign/logs/e1/f842bfbaa9804a6d/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-base64-r1-4e1bad085b18/forest-app-a97c186a987d4947b5779ac5c9d4678e/campaign/logs/e1/f842bfbaa9804a6d/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-base64-r1-4e1bad085b18/forest-app-a97c186a987d4947b5779ac5c9d4678e/campaign/logs/e1/f842bfbaa9804a6d/confirmation/attempt-001/sample-4.log"], "mean_seconds": 4.713151807146105e-06, "reason": "", "score": 0.8439455271593548, "status": "valid", "times": [4.673364573288845e-06, 4.868230395718773e-06, 4.665632267150426e-06, 4.687691971369225e-06, 4.6708398282032535e-06], "tree_hash": "5a6505bddfeb95f8634ffb6e55896617e6201fc9"}, "status": "confirmed"}`.

Commit retenu après confirmation : `9fbd20aed617276084e1e6906ae4a67719a16ebf`.
Temps confirmé : 0.000005 s ; référence confirmée : 0.000025 s.
Réduction mesurée : 81.8%. Référence conservée : non.

Mother a choisi **2 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | SIMD bulk Base64 decoding and width comparison | Explore safe single-thread SIMD bulk decoding in src/candidate.cpp. Benchmark an AVX2 path and, if it compiles under the supplied GCC/target without changing build settings, a wider AVX-512 path; do not presume wider vectors win. Process complete non-padding blocks and use bounded handling for tails. Never overread input or write beyond the exact payload; write the decoded uint64 count at offset 0 and payload at offset 16 while preserving bytes 8..15. Preserve the ABI and correctness for every valid input size, including short inputs and padding. Record compile viability, correctness, and official wall-clock results; retain useful variants for possible later integration even if a standalone variant is slower. |
| T2 | Grouped scalar decoder and reusable tail kernel | Explore a non-SIMD grouped scalar decoder in src/candidate.cpp, comparing direct quartet decoding, lookup or arithmetic mapping, and modest unrolling without the stream state machine. Handle empty/short inputs and the final padded quartet with bounded writes; derive the exact count only under the valid standard-padded input contract. Preserve the ABI, exact output layout, reserved bytes, and single-thread budget. Measure standalone correctness and official wall-clock performance at the timed sizes, and report whether the implementation is also a useful safe tail kernel for a later SIMD combination—even if it is slower standalone. Record failed variants rather than treating a speedup as guaranteed. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| deaac3afde244bee | T1 | search | valid | 0.000020 | 467dd00e4358 |
| 9ec181d206ef4aec | T2 | search | valid | 0.000198 | 0a0536b0a51a |
| 09da697d5f674c2b | T2 | search | valid | 0.000029 | 219be3f93ba9 |
| 37928ae207bc473d | Gm1 | search | valid | 0.000020 | 263f249a03f1 |
| ca40bd0390d44560 | T1 | search | valid | 0.000037 | 3d92bec86998 |
| 0cc6978991f04218 | T3 | search | valid | 0.000006 | 30633cdb4890 |
| 1a895ec8d1474676 | T2 | search | valid | 0.000204 | f4f95b8319b2 |
| e9792192dbd94478 | T1 | search | valid | 0.000028 | d106363ac256 |
| 6f7b30e977c74bf0 | T1 | search | valid | 0.000005 | 562d19641ab6 |
| 98bcbe42b8b94aa5 | T3 | search | valid | 0.000006 | 9dabb87ec35b |
| 3d6402d6248b4ee1 | Gm2 | search | valid | 0.000006 | 26be952a65de |
| bf8128c45d894960 | T3 | search | valid | 0.000009 | 1e86c005993e |
| 348da9ec80f14965 | T2 | search | build_failed | — | b7ab5e3870b3 |
| fe226b3810824337 | T3 | search | valid | 0.000005 | e61a41665fa2 |
| 1325ce2d7a014235 | T1 | search | valid | 0.000008 | f37bb493c196 |
| a74e59151d674c8b | T2 | search | valid | 0.000028 | b8e2fcd434b8 |
| 34f26e9496844290 | T3 | search | valid | 0.000026 | 3c1983bc64a0 |
| 9a737dfffdb74630 | T1 | search | valid | 0.000005 | 6e5684e40af0 |
| ea23c71b8feb43e7 | T2 | search | incorrect | — | 6424b4bfbf0c |
| 1c19cc2962604f43 | T3 | search | valid | 0.000045 | 9ea4c10add74 |
| cd24eeb4f7464ac9 | T1 | search | incorrect | — | 4cbcd0a10d98 |
| 8831fb7502934731 | T2 | search | incorrect | — | 5fa642a48e8e |
| 8891aacbe51b43f7 | Gm3 | search | valid | 0.000005 | c7940a8b63ce |
| ee08e2fc6f2d41f1 | T1 | search | valid | 0.000005 | a30d33403e95 |
| 427c10cc5fff449e | T1 | search | valid | 0.000005 | 2c4950de8edc |
| d12b421153be4e0c | T1 | search | valid | 0.000005 | e733aaa218da |
| b32fe2543d7949e9 | T1 | search | valid | 0.000007 | 41ec8a5a8c39 |
| 2abc700df71849bd | T3 | search | valid | 0.000006 | b4b065c2e30c |
| 3cab3a43918449b7 | T2 | search | incorrect | — | fb2bffe81d05 |
| 45e36a449d2b4e52 | T1 | search | valid | 0.000007 | 56140467d20f |
| 96f4115d991f45f4 | G | postprocess | valid | 0.000004 | 9fbd20aed617 |
| f842bfbaa9804a6d | G | postprocess | valid | 0.000005 | 826a97bf2940 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
