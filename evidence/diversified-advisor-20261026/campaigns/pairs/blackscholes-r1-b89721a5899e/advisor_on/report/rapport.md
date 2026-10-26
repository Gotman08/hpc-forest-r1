# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `a4200bb8e7ef9a913f756bbad72f87849164a4112b4c13e4d39c19565e92c35e`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 170, "tokens_used": 12930360, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 12930360}`.
Coûts par phase : `{"search": {"slots": 164, "tokens_used": 12429468, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 12429468}, "postprocess": {"slots": 3, "tokens_used": 500892, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 500892}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "7069988362f1491d", "outcome": {"binary_sha256": "4f7eb0c233f759bf2cd81fd2101950d3dcfab396b0c206ad17e6722e4e07a62e", "cache_key": "7fd94f93b55601bfbe8879b7a733c7948f182b5f305337b6ef195c99c4a5acbd", "commit": "7035632c2f61d450e8f38d26f74a02d638bab543", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-blackscholes-r1-b89721a5899e/forest-app-039729ab62b440abb277705f4f46ba37/campaign/logs/e1/7069988362f1491d/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-blackscholes-r1-b89721a5899e/forest-app-039729ab62b440abb277705f4f46ba37/campaign/logs/e1/7069988362f1491d/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-blackscholes-r1-b89721a5899e/forest-app-039729ab62b440abb277705f4f46ba37/campaign/logs/e1/7069988362f1491d/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-blackscholes-r1-b89721a5899e/forest-app-039729ab62b440abb277705f4f46ba37/campaign/logs/e1/7069988362f1491d/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-blackscholes-r1-b89721a5899e/forest-app-039729ab62b440abb277705f4f46ba37/campaign/logs/e1/7069988362f1491d/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-blackscholes-r1-b89721a5899e/forest-app-039729ab62b440abb277705f4f46ba37/campaign/logs/e1/7069988362f1491d/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-blackscholes-r1-b89721a5899e/forest-app-039729ab62b440abb277705f4f46ba37/campaign/logs/e1/7069988362f1491d/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.0007579715005094685, "reason": "", "score": 0.7682979901287267, "status": "valid", "times": [0.000756778850481876, 0.0007563688613430171, 0.000754888722932703, 0.0007598999598022858, 0.0007619211079874606], "tree_hash": "8526ebd88b4776283b32832ddd1c508a4dab2367"}, "status": "confirmed"}`.

Commit retenu après confirmation : `28089481de3d647dec1df3586ccc60b4187c3538`.
Temps confirmé : 0.000756 s ; référence confirmée : 0.002513 s.
Réduction mesurée : 69.9%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Thread-budgeted parallel loop | Explore OpenMP data-parallel execution over disjoint output indices, using the caller's threads value as an upper bound and avoiding parallel-region overhead for a one-thread call. Keep the supplied per-element arithmetic and CND unchanged. Write every output on every call, preserve correctness for all valid sizes and inputs, and compare timings at both official thread budgets; record any case where parallel overhead outweighs the benefit. |
| T2 | SIMD for full Black-Scholes kernel | Explore SIMD execution across the full per-element Black-Scholes calculation, including vector arithmetic for the supplied CND polynomial and vectorized or otherwise SIMD-compatible log, sqrt, and exp operations. Retain the supplied CND coefficients/formula as the algorithmic reference so this tests a vectorized-kernel approach distinct from T3's scalar lower-work CND approach. Do not change compiler flags or assume an ISA beyond what the build supports. For arbitrary valid n, use alignment-safe accesses and handle tails; the 64-byte input base does not guarantee aligned array sections, and output alignment is unspecified. Any approximations must satisfy the fixed tolerance over the valid input domain; use a safe fallback where needed. Respect the caller's thread budget, overwrite all outputs, and validate and measure both official sizes and thread budgets on varied and constant inputs. |
| T3 | Lower-cost CND evaluation | Explore reducing the work in the scalar CND evaluator alone, for example through Horner evaluation or a lower-cost piecewise/rational approximation with robust symmetry and tail behavior. Keep the outer Black-Scholes calculation and loop organization unchanged to isolate this opportunity. Preserve the required tolerance for all valid inputs, including varied and constant inputs, and measure at both sizes and thread budgets. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 3b1acaa2eb07421c | T1 | search | valid | 0.001269 | ad3d5cea6fd7 |
| 5f2553b9e3d34a7c | T2 | search | valid | 0.001339 | c7f18dc1db8b |
| 411cbeb0bcb44ce4 | T3 | search | valid | 0.002420 | daaa8f990d86 |
| fa531fd0c8a84bfa | T3 | search | valid | 0.003453 | ba11a65d2745 |
| 4a4ba69784d44492 | Gm1 | search | valid | 0.001301 | 11eccc362ddd |
| 606282317c8944ee | T1 | search | valid | 0.001269 | f332edf08a42 |
| 5b258baa4a034591 | T2 | search | valid | 0.001266 | 00ee9028c34d |
| 51754629684b4956 | T1 | search | valid | 0.001277 | b0e94999edd7 |
| 94e6cdff41d34edb | T3 | search | valid | 0.002413 | b6f5228251d8 |
| d412321e31c34f95 | T1 | search | valid | 0.001232 | 98c92a262a94 |
| 0f367351c0bc4b2e | T3 | search | valid | 0.002412 | c0539fa09d6f |
| 6b6c750ee6b44f7d | Gm2 | search | valid | 0.001242 | d373c98b437a |
| 0a5e4845df5f4dd0 | T2 | search | valid | 0.001662 | 5f069d0b492f |
| e94b916702ec42c1 | T3 | search | valid | 0.003020 | 0376e26250a1 |
| a72c4f8237354635 | T3 | search | valid | 0.002471 | c5cef0cca3bf |
| 7c368fc685cd4138 | T3 | search | valid | 0.003036 | e0663994531e |
| 39cee734155e4520 | T1 | search | valid | 0.001263 | 77de734417ea |
| b0bc955d77f8484f | T2 | search | valid | 0.003367 | 9cc51c3184ce |
| 0d69507722fc4221 | T3 | search | valid | 0.002442 | 08360b71bafc |
| 6cdc5338e51e422f | T3 | search | valid | 0.002378 | 3213505d51c1 |
| 036f9bce796c4eeb | T3 | search | valid | 0.003397 | ced1f663b5b5 |
| 16cac73551dd46bc | T1 | search | valid | 0.001511 | 0175e1cb8a85 |
| 51c88fb91a214fd3 | T1 | search | valid | 0.001500 | 7c8ec1907fcf |
| c24371873c65463c | T3 | search | valid | 0.001776 | 47bfbcf4434d |
| 1d52e3ff0a3347ed | T1 | search | valid | 0.001830 | c492bd70a15a |
| 32aaa413743341bc | T1 | search | valid | 0.001290 | 7ab8148c91f6 |
| 883afb5d8dc340bc | T3 | search | valid | 0.001757 | 7a3bc0ecf1bc |
| 326279a45b9a41cb | T1 | search | valid | 0.001370 | bcab34efa45d |
| f51be95f20bb475a | T3 | search | valid | 0.002471 | 4c4248bd0c77 |
| d24def5910e74122 | Gm3 | search | valid | 0.000892 | f0e58015b9f0 |
| 9502f7d5ffb94484 | T1 | search | valid | 0.001325 | 8c7a103e0832 |
| 17c0fea753164e7f | T3 | search | valid | 0.002153 | 7db0e0ee3cb4 |
| 1b0aa07ba5584853 | T3 | search | valid | 0.003174 | 482a07257900 |
| e572976909874d69 | T1 | search | valid | 0.001486 | 0a97092b39f3 |
| 0d4919ccf99e4129 | T3 | search | valid | 0.001779 | 6b5c14ec9e6c |
| 53b3006fc1dd41cd | T1 | search | valid | 0.001490 | c2020dad3ff6 |
| ddc569a518014ecd | T3 | search | valid | 0.002421 | 01ad94cfc0fe |
| b13123370ead48c3 | T1 | search | valid | 0.001251 | 5d353279cf35 |
| adb3b2af91ed4b9c | T1 | search | valid | 0.001791 | 8d38d07d9b70 |
| 8799a2f531a049e9 | T3 | search | valid | 0.001631 | b3417a31f956 |
| 16bcc6e019594717 | T1 | search | valid | 0.001786 | 3090465261bf |
| b449da6b50364d12 | T3 | search | valid | 0.001557 | fa5122cc27b8 |
| 28ec349857b2424b | T1 | search | valid | 0.001774 | 4f61c2cbdbed |
| c467d6ff20f24a58 | Gm4 | search | valid | 0.000799 | 335bbebf6291 |
| 34439b9692aa4bc5 | T1 | search | valid | 0.001232 | 6b9d732df8a6 |
| c5e70b79f5654bcc | T3 | search | valid | 0.001758 | 34f12998f664 |
| 76e83399098d4c3c | T1 | search | valid | 0.001243 | 057a4f94586f |
| f64957d0687b4278 | T1 | search | valid | 0.001296 | 1873c14fea9a |
| 7c02bec72ea945c1 | Gm5 | search | valid | 0.000759 | 28089481de3d |
| 052ce6b8ee1543e2 | T1 | search | valid | 0.002145 | 194b2c42b182 |
| 5bdf8c727bf5411e | T4 | search | incorrect | — | 3f52aee0513b |
| 36facd611d464710 | T5 | search | valid | 0.001071 | 2e59052ac8ba |
| 6fa6e05d9ef449a0 | T3 | search | valid | 0.001555 | ad686b4fbea8 |
| 07b3538e7aba406a | T5 | search | valid | 0.001075 | 9d3846c4b727 |
| 7c7bd12434094a77 | T5 | search | valid | 0.001065 | bccc61af567f |
| 79675c11e2384ac5 | T3 | search | valid | 0.002596 | 58639d7d1947 |
| 8acb9a10a0174a46 | T5 | search | valid | 0.001074 | 51269f0d8fa5 |
| 87e96d58b4734aac | T5 | search | valid | 0.001066 | a7f75a3d829b |
| 03dc29547a394a0b | T3 | search | valid | 0.003170 | 92a2985e3a10 |
| 8f80a92d555f4617 | T5 | search | valid | 0.001066 | f64bf8672028 |
| cc01f7bf12074755 | T3 | search | valid | 0.002166 | f09a06fda60a |
| 7e892e2da35646be | T5 | search | valid | 0.001084 | 47c1ed8c553a |
| a0e759e576544b51 | T3 | search | valid | 0.002043 | 62064ef809a0 |
| 32c8452e259543c3 | T6 | search | incorrect | — | f866805fad7f |
| be60f80d6c7447ba | T5 | search | valid | 0.001081 | 8b13a3b97a6e |
| 54f87367b671413d | T3 | search | incorrect | — | 272fbb30bb06 |
| fedbcae785b848e1 | T5 | search | valid | 0.001064 | 0e808d15e023 |
| 7069988362f1491d | G | postprocess | valid | 0.000762 | 7035632c2f61 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
