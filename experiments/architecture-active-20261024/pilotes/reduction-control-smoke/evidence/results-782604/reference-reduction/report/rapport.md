# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `9132ecbf4b0d97ef58f368047a3f086893fb510e6c292ce4e9289760390004b2`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 35, "tokens_used": 4607361, "tokens_reserved": 0, "unknown_usage_calls": 1, "bounded_usage_calls": 0, "exact_tokens_used": 4607361}`.
Coûts par phase : `{"search": {"slots": 30, "tokens_used": 3779372, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3779372}, "postprocess": {"slots": 2, "tokens_used": 827989, "tokens_reserved": 0, "unknown_usage_calls": 1, "bounded_usage_calls": 0, "exact_tokens_used": 827989}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"experiment_id": null, "reason": "Final G produced no committed program to confirm", "status": "unavailable"}`.

Commit retenu après confirmation : `deb46f3e5ac79724b28cb8f8cc429824dc1567bf`.
Temps confirmé : 0.000007 s ; référence confirmée : 0.000047 s.
Réduction mesurée : 84.7%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Isolate and improve the CTA-local reduction | In src/candidate.cu, isolate the CTA-local reduction: replace reduce0's modulo-based shared-memory tree with a warp-centric or permitted CUB block reduction, while keeping the 128-thread launch geometry, one input per lane, multi-stage scratch schedule, and final copy fixed. The existing warpReduceSum helper is not currently used by reduce0, so it is a natural comparison point, not a measured improvement. Handle tails safely and preserve exact signed sums. Validate all checks and compare complete-run timings; report whether the local change helps independently of launch topology. |
| T2 | Reduce large-n global stages and partial-sum traffic | In src/candidate.cu, focus the experiment on the large-n global schedule: the supplied n=4194304 path currently launches reduction stages producing 32768, 256, 2, then 1 partials, followed by a copy. Explore work partitioning and partial counts that reduce stages and/or write the final result directly to out, retaining enough first-stage parallelism. Keep the small-n path to T3's scope. Alternative CTA implementations are allowed, but where practical compare against the existing CTA reduction so stage-count gains are distinguishable from T1's block-reduction gains. Never rely on uninitialized scratch or implicit inter-block ordering. Validate the complete supported domain and compare total-run timings. |
| T3 | Measure a direct small-n path and crossover | In src/candidate.cu, focus on supported small n: compare a one-CTA reduction that writes directly to out against the existing staged reduction plus copy, and choose any crossover from generic measured sizes rather than exact test values. The n=1 baseline already performs only a device copy, so use it as a control instead of assuming a kernel launch is faster. Keep the large-n path to T2's scope; validate all checks and compare complete-run timings. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 6216fdffdae04837 | T1 | search | valid | 0.000030 | eb58ca1f8f68 |
| 9133f760bf7740d8 | T2 | search | valid | 0.000017 | 19c2213468f2 |
| 9398cac053fc446f | T3 | search | valid | 0.000047 | 19ce188706b2 |
| 8b671423be1b4baf | T1 | search | valid | 0.000029 | 8f23b533fdfc |
| 5c526c5e47cb4297 | T3 | search | valid | 0.000047 | e3c0ab10642c |
| 1416447281d7464a | T2 | search | valid | 0.000012 | e6d01a6da383 |
| e3339368d3544fda | T1 | search | valid | 0.000030 | a08067dc48b4 |
| 5e5d84d7830b44aa | T2 | search | valid | 0.000010 | 5a87e633f018 |
| 236aa7426cba4c07 | T3 | search | valid | 0.000047 | 4aa348cf2396 |
| 43a677dc48024052 | T1 | search | valid | 0.000029 | 914b19cd468e |
| 853009491fe04ef0 | T2 | search | valid | 0.000009 | e77dbebddda1 |
| f3aad00acd6e40b4 | T3 | search | valid | 0.000047 | a8100d1f1169 |
| cba5d013bacb44d8 | T1 | search | valid | 0.000030 | a83f3b2645f2 |
| 14359d8de9e642e7 | T2 | search | valid | 0.000007 | deb46f3e5ac7 |
| 33c6f228517f4427 | T1 | search | valid | 0.000030 | 7ba876fae31f |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
