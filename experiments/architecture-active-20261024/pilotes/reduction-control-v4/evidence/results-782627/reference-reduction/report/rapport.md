# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `521cc621e46c9e04500551e056aece96796862cffb7fc301f3b8010a474b51ec`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 44, "tokens_used": 2054646, "tokens_reserved": 0, "unknown_usage_calls": 1, "bounded_usage_calls": 0, "exact_tokens_used": 2054646}`.
Coûts par phase : `{"search": {"slots": 37, "tokens_used": 1696452, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1696452}, "postprocess": {"slots": 4, "tokens_used": 358194, "tokens_reserved": 0, "unknown_usage_calls": 1, "bounded_usage_calls": 0, "exact_tokens_used": 358194}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"experiment_id": null, "reason": "Final G produced no committed program to confirm", "status": "unavailable"}`.

Commit retenu après confirmation : `3f111dd6c8edc0dbe84ebde8699bd1718b64dfb5`.
Temps confirmé : 0.000007 s ; référence confirmée : 0.000047 s.
Réduction mesurée : 84.1%. Référence conservée : non.

Mother a choisi **2 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Global reduction hierarchy and launch-count alternatives | Explore global reduction hierarchy and launch count, treating fewer launches as a hypothesis rather than a requirement. For the primary comparisons, keep the baseline intra-block reduction fixed so this tree isolates global topology. Compare a two-kernel design (input partials, then finalization writing directly to out) with a design that adds a parallel partial-reduction stage or retains a recursive hierarchy when a single-CTA finalizer has too much work. Tune tile size and partial count, and compare full-call performance rather than attributing gains from launch count alone. Handle all valid n generically; do not scan the entire large input in one CTA or specialize to listed test sizes. Use only the supplied scratch and default stream, without relying on scratch initialization. Ensure intermediate sums are exact under cancellation using int64 intermediates or proven-safe bounds, and narrow only after the true total is established. Validate all required inputs, report failed variants, and provide repeated measurements. |
| T2 | Intra-block reduction primitive and synchronization | Explore replacing reduce0's intra-block modulo/shared-memory reduction tree with a lower-synchronization block reduction, such as warp shuffles plus a small shared warp-partial exchange or an allowed CUB block primitive. To isolate this axis, retain the baseline's recursive global pass structure, 128-thread mapping, and one input element per lane; do not change the global tile geometry. Preserve correct synchronization and exact summation for every valid input, including safe handling of intermediate sums, and obey the scratch, stream, allocation, and bounds constraints. Validate all required inputs and compare repeated full-call measurements against the baseline; report failures and do not assume a local-kernel improvement guarantees a whole-call improvement. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| d35c915c07694ddb | T1 | search | valid | 0.000044 | 88a67ef64531 |
| da71647248f546cb | T2 | search | valid | 0.000031 | e31365d1fd3f |
| 3eec74c802984c84 | T1 | search | valid | 0.000044 | 4114223efcbd |
| 3665f246711f422c | T2 | search | valid | 0.000031 | 46e53c516164 |
| 6e0f71dc5f294618 | T1 | search | valid | 0.000008 | 6b076a4ba27c |
| 9ce980521a4545d5 | T2 | search | valid | 0.000030 | f53159ab6978 |
| 31f72f89e26046a8 | Gm1 | search | valid | 0.000027 | 516095daa5c3 |
| 0054e839b5aa4352 | T1 | search | valid | 0.000017 | 8d54be94ea5d |
| 960180ab73914e01 | T2 | search | valid | 0.000030 | e9bee255b785 |
| ddad4571f70148db | T1 | search | valid | 0.000013 | 4228083a790d |
| 5da48cd7af1d48fe | T2 | search | valid | 0.000030 | 7dd22975e1af |
| 8261f2ce0a66458d | T1 | search | valid | 0.000014 | 3679e708f335 |
| 6d2125faa19745c9 | Gm2 | search | valid | 0.000007 | 3f111dd6c8ed |
| f805677fab9149ce | G | postprocess | infrastructure_error | — |  |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
