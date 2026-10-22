# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `89ee241e031f49a38b15a095630525a23792610a4638ff3c9c1493d66e418a0f`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 41, "tokens_used": 10141771, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 10141771}`.
Coûts par phase : `{"search": {"slots": 29, "tokens_used": 1891353, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1891353}, "postprocess": {"slots": 9, "tokens_used": 8250418, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 8250418}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "5db7ae8c14c24b28", "outcome": {"binary_sha256": "4a215b50ec6620caaa036d8a71a1bf10cc7091286d34daafe0b255790e35ae2e", "cache_key": "2879560e2bfced414888b16e2d30dd58d020d77df5d1a47ba46b23bf46d34fd7", "commit": "a8d4c48b71cf9c9acd03ea9a96063112bffa1030", "correct": true, "logs": ["/gpfs/scratch/nimarano/hpc-forest-cuda-memory-7bf195685d4a4ea690a28ef41cac7743/results-776290/cuda-nbody/logs/e1/5db7ae8c14c24b28/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-7bf195685d4a4ea690a28ef41cac7743/results-776290/cuda-nbody/logs/e1/5db7ae8c14c24b28/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-7bf195685d4a4ea690a28ef41cac7743/results-776290/cuda-nbody/logs/e1/5db7ae8c14c24b28/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-7bf195685d4a4ea690a28ef41cac7743/results-776290/cuda-nbody/logs/e1/5db7ae8c14c24b28/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-7bf195685d4a4ea690a28ef41cac7743/results-776290/cuda-nbody/logs/e1/5db7ae8c14c24b28/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-7bf195685d4a4ea690a28ef41cac7743/results-776290/cuda-nbody/logs/e1/5db7ae8c14c24b28/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/hpc-forest-cuda-memory-7bf195685d4a4ea690a28ef41cac7743/results-776290/cuda-nbody/logs/e1/5db7ae8c14c24b28/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.0008538705592490145, "reason": "", "score": 0.6823728603239669, "status": "valid", "times": [0.0008539955896845762, 0.0008540050178726589, 0.0008537034848574773, 0.0008538960519484462, 0.0008537526518819134], "tree_hash": "0eade56e2a395418614b920b2ee5168efb7ef4cf"}, "status": "confirmed"}`.

Commit retenu après confirmation : `6dc99abed60b4a25c79a582edf996c33bf83d242`.
Temps confirmé : 0.000854 s ; référence confirmée : 0.001834 s.
Réduction mesurée : 53.5%. Référence conservée : non.

Mother a choisi **4 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Tuilage des sources en mémoire partagée | Explorer le chargement par tuiles des Particle sources en mémoire partagée, avec réutilisation par les threads cibles d’un bloc. Étudier les tailles et dispositions de tuile, le chargement des queues et la synchronisation; ajuster block et items_per_block si utile. Conserver une sortie complète par particule, les entrées en lecture seule et toutes les contraintes numériques. Mesurer les candidats validés sur les trois tailles officielles et rapporter la configuration ainsi que les résultats. |
| T2 | Diffusion warp des sources par registres et shuffles | Explorer une voie alternative de réutilisation des sources par warp : chargement par lanes puis diffusion des champs nécessaires aux lanes qui accumulent les cibles, en évitant la mémoire partagée lorsque cela est pertinent. Traiter correctement les masques, les queues et l’exclusion i==j pour toute taille. Ne modifier que src/nbody_kernel.cu et src/launch.json; valider toutes les contraintes d’entrée et mesurer les trois tailles officielles. |
| T3 | Blocage de plusieurs cibles par thread | Étudier le traitement de plusieurs particules cibles par thread : conserver leurs états et accumulateurs en registres, puis réutiliser localement chaque source entre ces cibles. Explorer les compromis entre nombre de cibles, pression de registres et block/items_per_block. Garantir que chaque sortie est écrite exactement une fois, notamment pour les tailles non multiples, et mesurer uniquement les variantes validées sur les trois tailles officielles. |
| T4 | Réduction arithmétique et calcul de l’inverse de la distance | Explorer des réductions du travail arithmétique, notamment la simplification masse-cible de l’accélération et les variantes sqrtf/rsqrtf ou réciproque, sans activer de fast-math global. Préserver G=1, l’adoucissement 0.001, la mise à jour vitesse-avant-position et les masses exactes. Comparer précision et temps; rejeter toute variante qui échoue aux cas limites, à l’oracle FP64 ou aux tolérances officielles. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 35c7d193c8a34331 | T1 | search | valid | 0.001005 | 6a789960722c |
| a47dcaea04a9475f | T2 | search | valid | 0.000977 | 0b6bfd71d9af |
| 377b57d9fd5245fb | T3 | search | valid | 0.002591 | ff17dac2bf39 |
| da61858a6bc84794 | T4 | search | incorrect | — | 04e37bb7d534 |
| 52d4281997e54319 | T1 | search | valid | 0.001017 | c365e65de97c |
| a47bc86ffef142bf | T3 | search | valid | 0.002609 | 0fb0746e5639 |
| d826ec029be64b8b | T2 | search | valid | 0.001738 | 9a9386a713c6 |
| ea1e8dbc578e4807 | T1 | search | valid | 0.001614 | 953662d8557c |
| f4a29d1b77484ed3 | T4 | search | valid | 0.001815 | bbed8119a05b |
| ec3c2b107121491a | T2 | search | valid | 0.000904 | 5d4c54791204 |
| 6ae20d0a866240de | T3 | search | valid | 0.004203 | d742cbb1c86b |
| 34a8792fc6fe41b4 | T1 | search | valid | 0.001696 | a7506b0fa4b7 |
| 99c33593615e4830 | T2 | search | valid | 0.001741 | c0e91b66f379 |
| 9fc61170db0a481f | T1 | search | valid | 0.001698 | 59552ca14b21 |
| df91a829afbd4cb1 | T4 | search | generation_failed | — |  |
| f264cb6f7b244f1e | T3 | search | valid | 0.002748 | bc9278bf047a |
| 505a0137c1e74ebf | T2 | search | valid | 0.000936 | 0a9e380aba53 |
| f704764fdf4646db | T3 | search | valid | 0.003420 | 60a6fc9cd8b9 |
| 36621123dde34055 | T4 | search | valid | 0.001021 | 6e67d230b71c |
| 8d1b57c6a222477c | T2 | search | valid | 0.000977 | dcf91b8deedf |
| f4d8f90ea00e469f | T1 | search | valid | 0.001124 | 755b9047a4b1 |
| 2d8a76b886264ac3 | T4 | search | valid | 0.000985 | d130006a8b75 |
| 2b123bd88aec470e | T2 | search | valid | 0.000890 | 4485f2ff248d |
| 4750d0315ca24212 | T4 | search | incorrect | — | 4a118ddd3d30 |
| 5d697700e03a461a | T3 | search | valid | 0.002714 | 4695a0662a89 |
| 5ebf2310933040f2 | T2 | search | valid | 0.000942 | 9c836ce16271 |
| 2109090d5aa349b0 | T1 | search | valid | 0.003317 | cd88d9213b9f |
| 1650707a621649ef | G | postprocess | valid | 0.000854 | 6dc99abed60b |
| 5db7ae8c14c24b28 | G | postprocess | valid | 0.000854 | a8d4c48b71cf |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
