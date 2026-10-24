# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `dca0ca5e4166f9f1dda8a92ae7f09d2b110c7bb3822e214283fe32c8009f68d7`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 42, "tokens_used": 2157816, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2157816}`.
Coûts par phase : `{"search": {"slots": 35, "tokens_used": 1504452, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1504452}, "postprocess": {"slots": 4, "tokens_used": 653364, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 653364}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "8fdbf80fa1554618", "outcome": {"binary_sha256": "6a91308289450d6c5b3a965821df50c903710db82b97ad656e0de7f88d7a8dcf", "cache_key": "f4cab8bcc522769191748cda232ac51badfd16ab931d94c394290d4fa106c83c", "commit": "ab87e45bebae1ebbc8ff1ce1b008fe0280b5d710", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-volume-5b6d54e4f6a4436b9592fc33a25a1cf3/results-783165/reference-volume/logs/e1/8fdbf80fa1554618/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-volume-5b6d54e4f6a4436b9592fc33a25a1cf3/results-783165/reference-volume/logs/e1/8fdbf80fa1554618/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-volume-5b6d54e4f6a4436b9592fc33a25a1cf3/results-783165/reference-volume/logs/e1/8fdbf80fa1554618/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-volume-5b6d54e4f6a4436b9592fc33a25a1cf3/results-783165/reference-volume/logs/e1/8fdbf80fa1554618/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-volume-5b6d54e4f6a4436b9592fc33a25a1cf3/results-783165/reference-volume/logs/e1/8fdbf80fa1554618/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-volume-5b6d54e4f6a4436b9592fc33a25a1cf3/results-783165/reference-volume/logs/e1/8fdbf80fa1554618/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-volume-5b6d54e4f6a4436b9592fc33a25a1cf3/results-783165/reference-volume/logs/e1/8fdbf80fa1554618/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.22597287811463918, "reason": "", "score": 0.958804607618548, "status": "valid", "times": [0.2260363892505277, 0.22587930181415616, 0.22583517498180514, 0.22577874130335254, 0.22633478322335432], "tree_hash": "0be2f667438182eba8293b2e60e4e43a53012b13"}, "status": "confirmed"}`.

Commit retenu après confirmation : `ab87e45bebae1ebbc8ff1ce1b008fe0280b5d710`.
Temps confirmé : 0.225973 s ; référence confirmée : 5.259419 s.
Réduction mesurée : 95.7%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Parallélisation OpenMP du rendu par pixel | Explorer le partage parallèle des pixels dans volume_serial, en utilisant threads comme maximum d’équipe et en comparant une distribution de lignes ou d’itérations adaptée au coût variable des rayons. Garder les écritures sans course, couvrir chaque pixel exactement une fois et préserver le chemin à un thread. Valider la correction et comparer les mesures à 1, 4 et 40 cœurs. |
| T2 | Arithmétique et organisation des accès du sampler Density | Explorer le calcul de Density en comparant une voie sans copie — facteurs de coordonnées, indices et accès plats — à une éventuelle préparation par appel d’un volume à halo/clamp, en comptant intégralement allocation et préparation dans le temps mesuré. Préserver les dimensions arbitraires, les bornes inclusives, la conversion des coordonnées en indices, le clamp et l’ordre d’interpolation; ne retenir une préparation que si son coût total est compensé. Vérifier la tolérance sur les densités et résolutions requises et mesurer chaque variante isolément. |
| T3 | Surcoût de traversée et de contrôle des rayons | Cibler la traversée des rayons, en particulier la préparation/intersection des rayons d’ombre et les mises à jour de position, paramètre et contrôle dans transmittance et raymarch. Chercher à réduire le surcoût de contrôle et de calcul scalaire sans réécrire l’interpolation de Density, afin de distinguer cette piste de T2. Conserver la séquence des échantillons, les pas, l’accumulation, l’atténuation et l’arrêt anticipé; évaluer correction et temps séparément puis dans une combinaison mesurée. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 731dd58654d4436e | T1 | search | valid | 0.942796 | 7fe70ed49205 |
| 4e1bd1001df247d6 | T2 | search | valid | 5.188690 | 97e63eaa70de |
| 52aa15116b2c4d93 | T3 | search | valid | 5.253313 | cb2d43a91d99 |
| 0c7a8938ba394bdf | T2 | search | valid | 5.062816 | 0f5007b2ee75 |
| 842bb9b00e474d39 | T1 | search | valid | 0.961114 | 10782d523098 |
| bad8d2d552dc44f5 | T3 | search | valid | 5.252772 | 9bce3bc60454 |
| 28cfe80ea031466e | T2 | search | valid | 4.713549 | 3f4ebb5773be |
| 7ae8475c543d42e4 | T1 | search | valid | 0.953141 | 1993c0c3a176 |
| 3c38f4160b22499a | T3 | search | valid | 5.241878 | 412452565284 |
| 63d486b49fdf4062 | T2 | search | valid | 5.316476 | 41bbeff83a52 |
| 382b2ac15e8648af | T1 | search | valid | 0.946774 | bbaa5f20f562 |
| ea64c9423f774121 | T3 | search | valid | 1.393683 | 742c99251d9e |
| 6ee6084606d44971 | T2 | search | valid | 5.543188 | 060c99224125 |
| a2e0eefcabe94221 | T1 | search | valid | 0.942291 | 596195635aeb |
| af82b0510bfa4f40 | T1 | search | valid | 0.942755 | cfc4a951108f |
| 91429a7d2ad74de9 | Gm1 | search | valid | 0.235233 | ced00c478a5b |
| 8fdbf80fa1554618 | G | postprocess | valid | 0.225677 | ab87e45bebae |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
