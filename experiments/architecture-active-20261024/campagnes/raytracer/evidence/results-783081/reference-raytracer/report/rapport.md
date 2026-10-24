# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `a3d438667c8924e2817aa7d4125ce9ba4d8a72b0fde9577159c099d3d40524ec`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 74, "tokens_used": 6652546, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 6652546}`.
Coûts par phase : `{"search": {"slots": 58, "tokens_used": 3522915, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3522915}, "postprocess": {"slots": 13, "tokens_used": 3129631, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3129631}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "c126a573dd7b4a03", "outcome": {"binary_sha256": "43bced14b4dfc1d21abce8d1d30f904261d48d614191aca2ba119060bf06ea67", "cache_key": "cad7da4bab1b88e6e580dae8d39b968e40056e103bd8eab5d3815b0ddc69cda7", "commit": "08002a7820592440f243d2ae540e4560a3e3c1b0", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-raytracer-364c7e9906bf4f8481f5afcdbdc7e340/results-783081/reference-raytracer/logs/e1/c126a573dd7b4a03/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-raytracer-364c7e9906bf4f8481f5afcdbdc7e340/results-783081/reference-raytracer/logs/e1/c126a573dd7b4a03/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-raytracer-364c7e9906bf4f8481f5afcdbdc7e340/results-783081/reference-raytracer/logs/e1/c126a573dd7b4a03/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-raytracer-364c7e9906bf4f8481f5afcdbdc7e340/results-783081/reference-raytracer/logs/e1/c126a573dd7b4a03/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-raytracer-364c7e9906bf4f8481f5afcdbdc7e340/results-783081/reference-raytracer/logs/e1/c126a573dd7b4a03/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-raytracer-364c7e9906bf4f8481f5afcdbdc7e340/results-783081/reference-raytracer/logs/e1/c126a573dd7b4a03/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-raytracer-364c7e9906bf4f8481f5afcdbdc7e340/results-783081/reference-raytracer/logs/e1/c126a573dd7b4a03/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.039033337489698464, "reason": "", "score": 0.856969918578375, "status": "valid", "times": [0.03906432333608343, 0.0390017520419626, 0.03907031176718405, 0.03898904718039709, 0.03904125312286516], "tree_hash": "0bf574717b08212e8deb81c085162b56c22bdd2b"}, "status": "confirmed"}`.

Commit retenu après confirmation : `08002a7820592440f243d2ae540e4560a3e3c1b0`.
Temps confirmé : 0.039033 s ; référence confirmée : 0.233870 s.
Réduction mesurée : 83.3%. Référence conservée : non.

Mother a choisi **4 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Parallélisation OpenMP du rendu | Paralléliser les pixels ou les lignes avec OpenMP, en respectant threads comme plafond et en attribuant chaque pixel à un seul travailleur. Comparer le chemin série ou équipe réduite à threads=1 à l’exécution OpenMP, afin de mesurer son surcoût, puis évaluer des politiques de répartition adaptées à 4 et 40 threads sans dépasser le budget. Préserver le calcul par rayon et l’écriture complète des deux sorties. Valider tous les cas officiels, notamment les changements de caméra et de résolution, et rapporter les mesures ainsi que leur dispersion. |
| T2 | Parcours BVH et tests AABB | Optimiser le test de boîte et le parcours BVH scalaire dans src/candidate.cpp. Réduire le travail temporaire ou les branches inutiles sans changer les intervalles inclusifs, l’ordre de visite déterminé par dirIsNeg, le bornage par maxt, ni la sémantique du dépilement. Garder les triangles et leur ordre de parcours inchangés; valider exactement les IDs et la tolérance de profondeur sur tous les cas officiels. |
| T3 | Noyau d’intersection triangle | Optimiser le noyau scalaire TriIntersect et ses accès aux sommets, sans modifier l’ordre de parcours des triangles ni les règles de comparaison. Préserver notamment divisor == 0, les bornes barycentriques et t, ainsi que le remplacement du hit lors d’une égalité avec maxt. Mesurer le résultat à 1, 4 et 40 threads avec validation exacte des IDs et de la tolérance de profondeur. |
| T4 | Vectorisation SIMD de rayons voisins | Étudier le traitement SIMD de pixels voisins comme approche distincte des optimisations scalaires T2/T3 : évaluer la vectorisation des parties régulières et, si utile, un parcours multi-rayons avec masques et état de parcours indépendant par voie. Mesurer le bénéfice réel face au chemin scalaire, en tenant compte de la divergence BVH; ne pas supposer une largeur SIMD ou une extension ISA non établie, ni modifier les options de compilation ou la cible. Chaque voie doit respecter les règles d’intersection et l’ordre de remplacement des hits à égalité. Écrire toutes les sorties et valider exactement les IDs ainsi que la tolérance de profondeur sur les budgets 1, 4 et 40, et sur les changements de caméra et de résolution. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| e3511f70efc242a6 | T1 | search | valid | 0.047292 | 939ad196acb7 |
| 527b4a53220f4786 | T2 | search | valid | 0.234709 | 4609459cbcfc |
| 33ba3888c7d4419c | T3 | search | valid | 0.233635 | ccaec34246aa |
| 31b7cc3876874a9d | T4 | search | incorrect | — | b106f72bd571 |
| a0bac7283c364e1e | T2 | search | valid | 0.217994 | c702fb68cb4b |
| 091f27d7c3174248 | T1 | search | valid | 0.049811 | 4f09a0403054 |
| 572500d0befb49c0 | T3 | search | valid | 0.242395 | 4f2bc010ca80 |
| 29071471e7524445 | T2 | search | valid | 0.205301 | 9f689121c7b9 |
| 89691b59746e41fd | T1 | search | valid | 0.047517 | f4636c30b8de |
| d41c0b560aa048ab | T4 | search | incorrect | — | f111297a509c |
| 1702c0afb1a047f9 | Gm1 | search | valid | 0.047176 | 89a8175ee0bd |
| 9c680e441c954dab | T3 | search | valid | 0.233934 | cf90b6608e66 |
| cf02499191ba4562 | T1 | search | valid | 0.046600 | b535c6bdd6ed |
| 2b4d875f40a24114 | T2 | search | valid | 0.217657 | 001034661790 |
| d4351d54e8484718 | T3 | search | valid | 0.233981 | fca42b126076 |
| 2065d246932e4e97 | T1 | search | valid | 0.049528 | ad5bc43b17c3 |
| 977d335543cc41f8 | T2 | search | valid | 0.202322 | ff61b9bd2c15 |
| 7796f3bcd8b2413f | T3 | search | valid | 0.230901 | ecf8fb1e05b6 |
| 43fb340553b54ba3 | Gm2 | search | valid | 0.041702 | 3686f6f3c9e0 |
| 7ff9b3ecb84347a4 | T4 | search | valid | 0.234549 | c49637a32960 |
| aa71f7ed9db94d4a | T1 | search | valid | 0.045388 | a3874475939f |
| 942e8afc26574c64 | T2 | search | valid | 0.244706 | 1d9de3e8b938 |
| 93a89c41db9e40e1 | T3 | search | valid | 0.233827 | dd8b3f94bdb5 |
| efd0f3cc5e464fdf | T2 | search | valid | 0.198273 | b1e4d6c5ba70 |
| fc449948e3754eaa | T1 | search | valid | 0.049729 | c80c1d44063d |
| 53e85dfe33224102 | T2 | search | valid | 0.197660 | b007147ae159 |
| 6695704590374e49 | T1 | search | valid | 0.047082 | 7138cf08b0e1 |
| 3898c7a628194d6b | Gm3 | search | valid | 0.040644 | 16a787ecb33f |
| 7074f32abaf746a2 | T1 | search | valid | 0.047276 | 3e20db1e7c1d |
| e8fb144443b44508 | G | postprocess | valid | 0.040161 | 4c51256b3795 |
| d5f8e4f94a89449f | G | postprocess | valid | 0.039449 | 88b4bd4126fb |
| 3718aa4c356142df | G | postprocess | valid | 0.040643 | fae2cff63263 |
| c126a573dd7b4a03 | G | postprocess | valid | 0.038919 | 08002a782059 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
