# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `5be6679d34e629a8f731453a2dfa8318b083af39613d0edd43ce0da0815ffb85`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 49, "tokens_used": 2465874, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2465874}`.
Coûts par phase : `{"search": {"slots": 41, "tokens_used": 1814831, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1814831}, "postprocess": {"slots": 5, "tokens_used": 651043, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 651043}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "772715a3c9644c4f", "outcome": {"binary_sha256": "bfe46612f33e46d5d674c08b3805717b69fe3db0e7857da49a56c503c6cf162b", "cache_key": "f185969dc934d5b573c60118112177940812c1b46360dd9f34a9695051ef381e", "commit": "4dbd9c1c1a5779d27b4df47680f9cc5307a6bc64", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-argmin-571ae8eb9fca4076a77bea27e266397c/results-782994/reference-argmin/logs/e1/772715a3c9644c4f/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-argmin-571ae8eb9fca4076a77bea27e266397c/results-782994/reference-argmin/logs/e1/772715a3c9644c4f/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-argmin-571ae8eb9fca4076a77bea27e266397c/results-782994/reference-argmin/logs/e1/772715a3c9644c4f/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-argmin-571ae8eb9fca4076a77bea27e266397c/results-782994/reference-argmin/logs/e1/772715a3c9644c4f/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-argmin-571ae8eb9fca4076a77bea27e266397c/results-782994/reference-argmin/logs/e1/772715a3c9644c4f/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-argmin-571ae8eb9fca4076a77bea27e266397c/results-782994/reference-argmin/logs/e1/772715a3c9644c4f/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-argmin-571ae8eb9fca4076a77bea27e266397c/results-782994/reference-argmin/logs/e1/772715a3c9644c4f/confirmation/attempt-001/sample-4.log"], "mean_seconds": 1.5702143800000004e-07, "reason": "", "score": 0.9659978454693063, "status": "valid", "times": [1.5590255000000003e-07, 1.5683166000000013e-07, 1.5620435000000012e-07, 1.578868599999999e-07, 1.5828177000000003e-07], "tree_hash": "07e324b6fb6123154d3cf691f07174bde0539738"}, "status": "confirmed"}`.

Commit retenu après confirmation : `4dbd9c1c1a5779d27b4df47680f9cc5307a6bc64`.
Temps confirmé : 0.000000 s ; référence confirmée : 0.000004 s.
Réduction mesurée : 96.5%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | One-pass AVX-512 lane minima with earliest-index state | Explore a one-pass AVX-512 lane-state argmin: keep each lane's signed minimum and earliest absolute index across successive 16-element vectors, then combine lane results using value-first and index-second ordering. Handle the initial block and scalar tail correctly, including INT32_MAX, INT32_MIN and ties. Stay within the supplied thread budget; compare correctness and repeated timings against the baseline. |
| T2 | Two-pass AVX-512 minimum reduction followed by earliest-match search | Explore a two-pass AVX-512 argmin: first compute the global signed int32 minimum; then scan from index zero with vector equality comparisons to find the earliest matching element, extracting the lowest matching lane and handling a scalar tail. Preserve first-index ties and INT32 extrema. Do not change the frozen compiler, target, or protocol; verify this code builds and is valid on the supplied target. Check correctness before comparing repeated timings, particularly on random and decreasing inputs where the second-pass search length may differ. |
| T3 | Unrolled scalar argmin with independent accumulators | Explore a compiler-friendly scalar scan with a small fixed unroll factor and several independent (minimum value, earliest index) accumulators. Fold the accumulators with signed-value then lowest-index ordering; handle any remainder scalarly. Do not use explicit SIMD or parallel workers in this branch. Measure whether reduced loop-carried dependence helps on both random and decreasing inputs, after correctness checks. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| e4f15a349e7d4b6b | T1 | search | valid | 0.000001 | 1cea4a8f361d |
| b3f11615836f4fda | T2 | search | valid | 0.000001 | 6a4ed52207a9 |
| 75b9b413be8447c2 | T3 | search | valid | 0.000003 | 1ef90e9d0545 |
| 6e7fbe8507524825 | T3 | search | valid | 0.000002 | 289b3a61e3b2 |
| 0801caa5ba464e9d | T2 | search | valid | 0.000001 | 4e05bef2020e |
| f3a2c4655db84bc9 | T1 | search | valid | 0.000002 | b1f5fc499e4f |
| 9c7f95fc870d402a | T3 | search | valid | 0.000003 | 71ff673ca583 |
| 8d1cb2ab28e04b5a | T2 | search | valid | 0.000000 | dc6078d0ffb2 |
| ace51fcaffd047f0 | T3 | search | valid | 0.000002 | 3a003dd04c92 |
| 1395d856b89b4d08 | T1 | search | valid | 0.000001 | 57a154894cdf |
| ff76215ff1a74133 | T2 | search | valid | 0.000000 | 758b4c60804c |
| 01d820c0a1d144a8 | T3 | search | valid | 0.000003 | e8aa54e16af7 |
| 46925fdbf0494a52 | T2 | search | valid | 0.000000 | 738f1415880b |
| 9ac096ace3c441ba | T1 | search | valid | 0.000001 | b83addf604cf |
| 301734c6ea5e4c4d | T2 | search | valid | 0.000000 | 47a7c4fb593a |
| cf527205c2664ce4 | Gm1 | search | valid | 0.000001 | 42d9c6966f95 |
| bd422d2c28e944fb | Gm2 | search | valid | 0.000001 | 6ff9d2837771 |
| 772715a3c9644c4f | G | postprocess | valid | 0.000000 | 4dbd9c1c1a57 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
