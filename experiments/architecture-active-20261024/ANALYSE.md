# Diagnostic des recherches et des programmes livrés

Ce document distingue les faits mesurés, les décisions de la forêt et les hypothèses tirées des sources. Il est rédigé après les recherches concernées et n’est pas transmis aux modèles des campagnes en cours.

Le rapport actif / ancien est le temps ancien divisé par le temps nouveau, remesurés dans la même allocation. Une valeur supérieure à 1 favorise le nouveau. Une campagne réussie par programme ne suffit pas à attribuer un gain à l’architecture : le choix initial de Mother et les générations sont également variables.

Les analystes influencent certains essais par leurs avis, mais leurs opinions ne sont jamais des récompenses. Les liens avis → essai et décision → combinaison prouvent une utilisation du mécanisme ; ils ne prouvent pas que cet avis était nécessaire au gain. Une ablation avec plusieurs recherches indépendantes serait nécessaire pour établir cet effet.

## Bilan transversal

L’ancienne série archive 919 essais, dont 898 corrects ; la nouvelle en archive 372, dont 361 corrects. Le taux de correction décrit les essais admis et ne mesure pas à lui seul la qualité de l’exploration : un système peut produire moins d’erreurs en explorant moins de pistes.

Les tentatives retenues comptent 51,342,489 tokens vérifiables pour l’ancienne série et 61,779,565 pour l’active, dont 22,238,181 pour l’analyse et le pilotage. 0 invocations de ces deux séries retenues ont une consommation inconnue. Ces compteurs incluent le contexte traité et ne sont pas un prix facturé ; les appels et tokens en cache restent détaillés dans les reçus. Les coûts des échecs et des pilotes s’ajoutent séparément. Une allocation plus courte ne signifie donc pas nécessairement moins de travail modèle.

Sur les 21 campagnes terminées, 63 / 68 arbres de recherche ont effectivement reçu au moins un appel d’analyste. Les comptes ci-dessous concernent les tentatives retenues ; les échecs et leurs coûts restent séparément visibles.

Les 29 essais de combinaison intermédiaire comprennent 29 programmes corrects et 19 essais plus rapides que le meilleur candidat connu avant leur mesure exploratoire. Une combinaison qui améliore seulement ses propres sources peut encore rester derrière un autre arbre. Ces mesures exploratoires ne remplacent pas la confirmation finale.

Campagnes terminées avec tous les arbres suspendus et sans fermeture explicite : deferred, gemm_cpu, noise, reduction, s4convd, softmax, transpose. Le contrôleur termine alors les travaux admis puis passe à la livraison. Il faut distinguer ce comportement du simple épuisement du budget nominal.

| Programme | Temps utilisé / budget nominal | Essais corrects / total | Appels analyse et pilotage | Tokens de contrôle connus | Tokens totaux connus |
|---|---:|---:|---:|---:|---:|
| aobench | 68.7 % | 12 / 12 | 10 | 371672 | 1528459 |
| argmin | 57.3 % | 18 / 18 | 21 | 1124004 | 2465874 |
| base64 | 27.4 % | 12 / 15 | 22 | 1929341 | 4695689 |
| binomial | 76.0 % | 15 / 15 | 9 | 341636 | 2004476 |
| blackscholes | 16.0 % | 23 / 23 | 21 | 1138957 | 3380219 |
| deferred | 22.8 % | 17 / 18 | 13 | 930359 | 3320027 |
| gemm_cpu | 22.8 % | 13 / 13 | 14 | 776686 | 2211096 |
| mandelbrot | 26.0 % | 23 / 24 | 32 | 2151481 | 4234462 |
| noise | 68.2 % | 14 / 15 | 7 | 318306 | 2526778 |
| popcount | 39.0 % | 15 / 15 | 10 | 508351 | 1845961 |
| raytracer | 25.0 % | 31 / 33 | 26 | 2328845 | 6652546 |
| reduction | 21.2 % | 14 / 14 | 14 | 579833 | 2682509 |
| s4convd | 22.3 % | 13 / 13 | 16 | 607033 | 1930904 |
| sgemm | 83.6 % | 18 / 18 | 20 | 1193513 | 3262349 |
| softmax | 23.2 % | 17 / 17 | 22 | 1102415 | 2374253 |
| stencil3d | 20.9 % | 21 / 21 | 25 | 1474607 | 3764602 |
| stencil_y | 67.1 % | 16 / 17 | 19 | 1112484 | 2412847 |
| sumabs | 25.8 % | 22 / 22 | 21 | 1117909 | 2835500 |
| transpose | 64.1 % | 11 / 11 | 14 | 861170 | 2156999 |
| utf8 | 27.5 % | 19 / 21 | 24 | 1388553 | 3336199 |
| volume | 71.3 % | 17 / 17 | 16 | 881026 | 2157816 |

La fraction de temps peut dépasser 100 % lorsque la politique termine les travaux déjà admis et la confirmation. Les tokens connus n’incluent pas les consommations inconnues signalées dans les fiches ; les temps de phases se chevauchent et ne sont pas additionnables.

Les limites observées concernent donc aussi le pilotage : couvrir les arbres avant de les fermer, préserver des pistes de reformulation, et juger une combinaison contre le meilleur candidat disponible. Le fonctionnement des analystes et de Mother est établi ; leur bénéfice net varie selon le programme. Pour attribuer un gain à une composante, une étude suivante devrait répéter les recherches avec plusieurs initialisations, modes historique/observation/actif et budgets identiques, en comptant aussi le coût des analyses. Cette ablation n’a pas été exécutée dans cette campagne.

La fiabilité des sorties de Mother est une autre limite mesurée : 5 tentatives ont été relancées après une sortie native incomplète sans reçu de fin de tour. Ces appels ne sont pas rejoués dans la même conversation. Les réponses plus courtes et la gestion explicite de leur limite sont des pistes à tester séparément ; changer ce comportement au milieu de la présente série aurait rompu le gel du moteur. Les tentatives ratées restent incluses dans le bilan de ressources.

## aobench

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_ISPC_AO_1C | 512 | 1 | 883.63 | 764.05 | 1.1565 | 1.1552–1.1667 | Nouveau plus rapide dans chaque bloc |
| CPU_ISPC_AO_4C | 512 | 4 | 221.64 | 191.71 | 1.1561 | 1.1553–1.2644 | Nouveau plus rapide dans chaque bloc |
| CPU_ISPC_AO_40C | 2048 | 40 | 631.41 | 373.14 | 1.6922 | 1.1279–1.927 | Nouveau plus rapide dans chaque bloc |

Passage de 1 à plusieurs threads, sur les mêmes entrées et dans la même allocation :

| Entrée n | Threads | Ancien : temps 1 thread / temps parallèle | Actif : temps 1 thread / temps parallèle |
|---|---:|---:|---:|
| 512 | 4 | 3.9868 | 3.9854 |

Ces rapports décrivent la mise à l’échelle de chaque programme. Ils ne sont pas les speedups contre le naïf. Une augmentation du nombre de threads ne garantit pas un gain proportionnel ; ordonnancement, synchronisation, mémoire et partage du nœud peuvent intervenir. Cette campagne ne comporte pas le profilage nécessaire pour attribuer une mauvaise mise à l’échelle à une cause précise.

Les lignes CPU de ce programme emploient plusieurs tailles d’entrée, reprises du tableau historique. Leurs temps bruts ne constituent pas une mesure de mise à l’échelle à problème constant. Le tableau de mise à l’échelle ci-dessus ne rapproche que les lignes de même taille, même motif, même agrégat et même allocation.

Couverture des analystes pendant la recherche : 3 / 3 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 4 / 4 | 4 | 461.35 | 1512.4 | 1.2482 | 22.732 | 388.33 |
| T2 | 3 / 3 | 1 | 3493.6 | 884.9 | 0.91511 | 27.861 | 1127.7 |
| T3 | 3 / 3 | 1 | 2860.9 | 888.61 | 0.9385 | 26.835 | 1057.6 |
| Gm1 | 1 / 1 | 0 | 358.79 | 91.009 | 0.39473 | 5.3032 | 90.461 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Thread-safe OpenMP pixel parallelism and independent sampling
- **T2** : Isolated scalar primary-ray and pixel-output experiments
- **T3** : Ambient-ray generation and intersection throughput
- **Gm1** : Intégrer parallélisme T1 et chemin ambiant T3

Mother a lancé 3 arbres initiaux, puis créé 1 arbres ou combinaisons. 12 essais sur 12 sont corrects. 10 appels d’analyse/pilotage ont produit 7 actions appliquées ; 1 essais portent la provenance d’un avis et 1 celle d’un import explicite.

La durée réelle passe de 5815.9 à 4946.5 secondes, avec un budget nominal conservé de 7200 secondes. L’ancienne recherche comptait 13 essais corrects sur 13. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 30 invocations natives, 1,528,459 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 371,672 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.

Actions appliquées : close : 1, continue : 1, integrate : 1, suspend : 4.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 358.79 | 1.2858 | 1.2858 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : L’ancien utilise un générateur PCG32 par thread et teste les intersections rayon par rayon, avec arrêt dès qu’un obstacle est trouvé. Le nouveau initialise un état aléatoire par pixel à partir d’une graine de rendu, prépare des tableaux de directions puis teste les sphères et le plan par boucles séparées ; il distribue les pixels par paquets dynamiques de 64. Le générateur et les tirages internes diffèrent donc, même lorsque le pilote reçoit la même graine. Le contrat autorise une équivalence statistique du rendu, contrôlée par une erreur quadratique moyenne et un biais moyen bornés : ce cas ne prouve pas une identité pixel par pixel. Plusieurs changements sont mesurés ensemble, dont la préparation des rayons, le générateur et l’ordonnancement.

Sources auditées : [ancienne](mesures/paired-aobench/aobench/old_selected/candidate.cpp) et [nouvelle](mesures/paired-aobench/aobench/new_selected/candidate.cpp).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## argmin

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_ARGMIN_RANDOM | 8192 | 1 | 0.00046023 | 0.00030512 | 1.5083 | 1.1267–2.3872 | Nouveau plus rapide dans chaque bloc |
| CPU_ARGMIN_DECREASING | 8192 | 1 | 0.00048876 | 0.00050758 | 0.96293 | 0.95619–0.99529 | Ancien plus rapide dans chaque bloc |

Couverture des analystes pendant la recherche : 3 / 3 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 4 / 4 | 5 | 0.00054676 | 396.64 | 2.0168 | 2.6181 | 2.9375 |
| T2 | 6 / 6 | 3 | 0.00043046 | 429.02 | 3.1768 | 3.6282 | 3.7298 |
| T3 | 5 / 5 | 4 | 0.0022604 | 293.25 | 1.0081 | 3.0728 | 3.8172 |
| Gm1 | 1 / 1 | 0 | 0.00097912 | 66.115 | 0.49334 | 0.60575 | 0.72943 |
| Gm2 | 1 / 1 | 0 | 0.00052852 | 113.91 | 0.47518 | 0.58796 | 0.6158 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : One-pass AVX-512 lane minima with earliest-index state
- **T2** : Two-pass AVX-512 minimum reduction followed by earliest-match search
- **T3** : Unrolled scalar argmin with independent accumulators
- **Gm1** : Hybride T2 à deux passes et suivi d’indices par lane de T1
- **Gm2** : T2 avec états lane intercalés et réduction vectorielle finale de T1

Mother a lancé 3 arbres initiaux, puis créé 2 arbres ou combinaisons. 18 essais sur 18 sont corrects. 21 appels d’analyse/pilotage ont produit 12 actions appliquées ; 5 essais portent la provenance d’un avis et 5 celle d’un import explicite.

La durée réelle passe de 2016.2 à 1031.8 secondes, avec un budget nominal conservé de 1800 secondes. L’ancienne recherche comptait 8 essais corrects sur 8. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 48 invocations natives, 2,465,874 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 1,124,004 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.

Actions appliquées : close : 1, continue : 2, integrate : 2, share : 2, suspend : 5.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 0.00097912 | 0.43964 | 0.43964 |
| Gm2 | Oui | 0.00052852 | 0.81446 | 0.81446 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : Le nouveau code calcule d’abord le minimum avec AVX-512, puis recherche son premier indice dans un second parcours vectorisé. L’ancien procède par blocs et retrouve l’indice dans le bloc gagnant. La longueur du second parcours du nouveau dépend de la position du minimum : c’est une explication plausible du contraste entre les entrées aléatoires et décroissantes. Les mesures établissent le contraste ; elles n’isolent pas le coût de chaque instruction.

Sources auditées : [ancienne](mesures/paired-cpu-argmin/argmin/old_selected/candidate.cpp) et [nouvelle](mesures/paired-cpu-argmin/argmin/new_selected/candidate.cpp).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## base64

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_BASE64_SCALAR | 141020 | 1 | 0.0059675 | 0.0089716 | 0.66515 | 0.66084–0.66764 | Ancien plus rapide dans chaque bloc |
| CPU_BASE64_CHROMIUM | 141020 | 1 | 0.0059675 | 0.0089716 | 0.66515 | 0.66084–0.66764 | Ancien plus rapide dans chaque bloc |

Couverture des analystes pendant la recherche : 3 / 4 arbres de recherche ont eu au moins un appel. Arbres sans appel : T2. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 3 / 4 | 4 | 0.017935 | 1625.4 | 2.5252 | 3.7866 | 2.2728 |
| T2 | 2 / 2 | 0 | 0.082572 | 819.92 | 1.0889 | 2.2583 | 1.5255 |
| T3 | 4 / 6 | 5 | 0.063812 | 1429.7 | 1.5128 | 5.6577 | 3.0267 |
| T4 | 2 / 2 | 1 | 0.0090029 | 233.38 | 1.0409 | 2.2411 | 1.5161 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : AVX2 arithmetic-classification decoder
- **T2** : AVX-512VBMI permutation decoder
- **T3** : Scalar table-loop unrolling
- **T4** : Voie rapide AVX2 sans validation par bloc

Mother a lancé 3 arbres initiaux, puis créé 1 arbres ou combinaisons. 12 essais sur 15 sont corrects. 22 appels d’analyse/pilotage ont produit 12 actions appliquées ; 4 essais portent la provenance d’un avis et 2 celle d’un import explicite.

La durée réelle passe de 6930.5 à 1974.3 secondes, avec un budget nominal conservé de 7200 secondes. L’ancienne recherche comptait 60 essais corrects sur 61. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

3 réponses d’analyse/pilotage ont échoué à la validation ou au transport dans cette tentative. Motifs enregistrés : Observer read is outside its visible evidence (1); Mother action cites unavailable evidence (1); Observer claim has unsupported evidence IDs (1).

Coût connu de cette tentative : 57 invocations natives, 4,695,689 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 1,929,341 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.

Actions appliquées : branch : 1, close : 1, continue : 6, suspend : 4.

Lecture des sources : Les deux programmes décodent des blocs AVX2 de 32 caractères. L’ancien compacte les valeurs avec des instructions de multiplication-addition puis un mélange des octets. Le nouveau utilise des masques, décalages et opérations OU, et déroule jusqu’à quatre blocs avant de traiter la fin scalaire avec padding. Ce sont plusieurs compromis simultanés ; le déroulage ne garantit pas que le calcul par bloc soit moins coûteux. Le contrat porte sur des entrées Base64 standard valides : réussir ces contrôles ne prouve pas une détection complète des chaînes invalides.

Sources auditées : [ancienne](mesures/paired-base64/base64/old_selected/candidate.cpp) et [nouvelle](mesures/paired-base64/base64/new_selected/candidate.cpp).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## binomial

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_ISPC_BINOMIAL_1C | 131072 | 1 | 22.33 | 30.983 | 0.72071 | 0.71812–0.72378 | Ancien plus rapide dans chaque bloc |
| CPU_ISPC_BINOMIAL_4C | 131072 | 4 | 5.6045 | 7.7717 | 0.72114 | 0.72055–0.72239 | Ancien plus rapide dans chaque bloc |
| CPU_ISPC_BINOMIAL_40C | 2097152 | 40 | 53.807 | 33.613 | 1.6008 | 0.64218–2.4357 | Écart dans la variabilité observée |

Passage de 1 à plusieurs threads, sur les mêmes entrées et dans la même allocation :

| Entrée n | Threads | Ancien : temps 1 thread / temps parallèle | Actif : temps 1 thread / temps parallèle |
|---|---:|---:|---:|
| 131072 | 4 | 3.9843 | 3.9866 |

Ces rapports décrivent la mise à l’échelle de chaque programme. Ils ne sont pas les speedups contre le naïf. Une augmentation du nombre de threads ne garantit pas un gain proportionnel ; ordonnancement, synchronisation, mémoire et partage du nœud peuvent intervenir. Cette campagne ne comporte pas le profilage nécessaire pour attribuer une mauvaise mise à l’échelle à une cause précise.

Les lignes CPU de ce programme emploient plusieurs tailles d’entrée, reprises du tableau historique. Leurs temps bruts ne constituent pas une mesure de mise à l’échelle à problème constant. Le tableau de mise à l’échelle ci-dessus ne rapproche que les lignes de même taille, même motif, même agrégat et même allocation.

Couverture des analystes pendant la recherche : 3 / 4 arbres de recherche ont eu au moins un appel. Arbres sans appel : T3. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 3 / 3 | 2 | 71.596 | 306.89 | 0.86572 | 4.0069 | 44.675 |
| T2 | 3 / 3 | 1 | 296.87 | 325.27 | 0.81444 | 4.5188 | 149.5 |
| T3 | 3 / 3 | 0 | 294.28 | 224.89 | 0.80198 | 4.4878 | 144.4 |
| T4 | 2 / 2 | 2 | 175.01 | 310.5 | 0.56881 | 2.9536 | 92.724 |
| Gm1 | 1 / 1 | 0 | 37.432 | 84.336 | 0.2894 | 1.2996 | 13.04 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Outer-loop CPU parallelism and thread-budget-aware dispatch
- **T2** : Reduce terminal-state power-function cost without changing endpoint convention
- **T3** : Hoist invariant rollback coefficients and reduce per-state arithmetic
- **T4** : SIMD mapping across independent options
- **Gm1** : Mesurer l’intégration du parallélisme externe T1 et du SIMD T4

Mother a lancé 4 arbres initiaux, puis créé 1 arbres ou combinaisons. 15 essais sur 15 sont corrects. 9 appels d’analyse/pilotage ont produit 7 actions appliquées ; 1 essais portent la provenance d’un avis et 1 celle d’un import explicite.

La durée réelle passe de 1776.6 à 1368.9 secondes, avec un budget nominal conservé de 1800 secondes. L’ancienne recherche comptait 9 essais corrects sur 9. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 33 invocations natives, 2,004,476 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 341,636 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.

Actions appliquées : close : 1, integrate : 1, suspend : 5.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 37.432 | 1.9127 | 1.9127 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : L’ancien calcule une somme pondérée des valeurs terminales avec une récurrence des poids, linéaire dans le nombre de niveaux. Le nouveau conserve une récurrence triangulaire de remontée, quadratique dans ce nombre, mais vectorise huit options indépendantes et prépare les puissances et poids. Cette différence est algorithmique, pas seulement une taille de bloc. La vectorisation ne garantit donc pas une diminution du travail total. Le plan initial de Mother impose explicitement de conserver la formulation ou l’ordre de remontée dans plusieurs pistes ; aucune nouvelle branche de reformulation n’a été créée. La couverture des idées est donc une limite observable de cette recherche, même si les combinaisons intermédiaires fonctionnent.

Sources auditées : [ancienne](mesures/paired-binomial/binomial/old_selected/candidate.cpp) et [nouvelle](mesures/paired-binomial/binomial/new_selected/candidate.cpp).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## blackscholes

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_ISPC_BLACKSCHOLES_1C | 131072 | 1 | 2.8692 | 2.8536 | 1.0055 | 1.0026–1.0418 | Nouveau plus rapide dans chaque bloc |
| CPU_ISPC_BLACKSCHOLES_4C | 131072 | 4 | 0.71921 | 0.25742 | 2.7939 | 2.7865–2.7984 | Nouveau plus rapide dans chaque bloc |
| CPU_ISPC_BLACKSCHOLES_40C | 2097152 | 40 | 13.966 | 12.568 | 1.1112 | 0.76739–1.8194 | Écart dans la variabilité observée |

Passage de 1 à plusieurs threads, sur les mêmes entrées et dans la même allocation :

| Entrée n | Threads | Ancien : temps 1 thread / temps parallèle | Actif : temps 1 thread / temps parallèle |
|---|---:|---:|---:|
| 131072 | 4 | 3.9894 | 11.086 |

Ces rapports décrivent la mise à l’échelle de chaque programme. Ils ne sont pas les speedups contre le naïf. Une augmentation du nombre de threads ne garantit pas un gain proportionnel ; ordonnancement, synchronisation, mémoire et partage du nœud peuvent intervenir. Cette campagne ne comporte pas le profilage nécessaire pour attribuer une mauvaise mise à l’échelle à une cause précise.

Les lignes CPU de ce programme emploient plusieurs tailles d’entrée, reprises du tableau historique. Leurs temps bruts ne constituent pas une mesure de mise à l’échelle à problème constant. Le tableau de mise à l’échelle ci-dessus ne rapproche que les lignes de même taille, même motif, même agrégat et même allocation.

Couverture des analystes pendant la recherche : 3 / 3 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 8 / 8 | 6 | 1.4007 | 634.4 | 2.257 | 7.652 | 21.624 |
| T2 | 6 / 6 | 3 | 2.6624 | 656.46 | 1.8422 | 5.7292 | 18.456 |
| T3 | 5 / 5 | 3 | 7.2541 | 317.19 | 1.3178 | 4.7873 | 17.591 |
| Gm1 | 1 / 1 | 0 | 1.0602 | 77.029 | 0.31819 | 0.95682 | 2.6778 |
| Gm2 | 1 / 1 | 0 | 0.7096 | 252.25 | 0.32708 | 0.95462 | 2.6015 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : OpenMP scaling and overhead within the threads budget
- **T2** : Compiler-vectorized versus explicit SIMD execution
- **T3** : Isolated scalar arithmetic rewrites and combination candidates
- **Gm1** : Combiner le parallélisme T1 et le noyau SIMD T2
- **Gm2** : Tester la variante T2 la plus rapide sur la base Gm1

Mother a lancé 3 arbres initiaux, puis créé 2 arbres ou combinaisons. 23 essais sur 23 sont corrects. 21 appels d’analyse/pilotage ont produit 16 actions appliquées ; 9 essais portent la provenance d’un avis et 3 celle d’un import explicite.

La durée réelle passe de 6927.3 à 1153.2 secondes, avec un budget nominal conservé de 7200 secondes. L’ancienne recherche comptait 77 essais corrects sur 79. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 54 invocations natives, 3,380,219 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 1,138,957 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.

Actions appliquées : close : 1, continue : 9, integrate : 2, share : 1, suspend : 3.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 1.0602 | 1.3278 | 1.3278 |
| Gm2 | Oui | 0.7096 | 1.4941 | 1.4941 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : Le nouveau chemin multithread emploie SSE2 pour calculer quatre options ensemble, avec des approximations polynomiales de log/exp et un retour scalaire hors de leur domaine. Le chemin à un thread reste scalaire. Cela concorde avec le gain marqué à quatre threads et le faible écart à un thread. À quarante threads, les blocs se recouvrent : le rapport central seul ne permet pas de conclure. La correction est celle des tolérances du contrat, pas une identité bit à bit pour toute entrée réelle possible.

Sources auditées : [ancienne](mesures/paired-blackscholes/blackscholes/old_selected/candidate.cpp) et [nouvelle](mesures/paired-blackscholes/blackscholes/new_selected/candidate.cpp).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## deferred

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_ISPC_DEFERRED_1C | 1280 | 1 | 114.97 | 98.047 | 1.1726 | 1.1684–1.1898 | Nouveau plus rapide dans chaque bloc |
| CPU_ISPC_DEFERRED_4C | 1280 | 4 | 34.815 | 28.517 | 1.2208 | 1.2081–1.4189 | Nouveau plus rapide dans chaque bloc |

Passage de 1 à plusieurs threads, sur les mêmes entrées et dans la même allocation :

| Entrée n | Threads | Ancien : temps 1 thread / temps parallèle | Actif : temps 1 thread / temps parallèle |
|---|---:|---:|---:|
| 1280 | 4 | 3.3023 | 3.4382 |

Ces rapports décrivent la mise à l’échelle de chaque programme. Ils ne sont pas les speedups contre le naïf. Une augmentation du nombre de threads ne garantit pas un gain proportionnel ; ordonnancement, synchronisation, mémoire et partage du nœud peuvent intervenir. Cette campagne ne comporte pas le profilage nécessaire pour attribuer une mauvaise mise à l’échelle à une cause précise.

Couverture des analystes pendant la recherche : 2 / 3 arbres de recherche ont eu au moins un appel. Arbres sans appel : T2. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 3 / 4 | 2 | 62.029 | 722.58 | 1.5708 | 1.4618 | 9.8002 |
| T2 | 2 / 2 | 0 | 115.08 | 250.15 | 0.83459 | 1.1855 | 7.7034 |
| T3 | 7 / 7 | 3 | 104.14 | 1042.5 | 2.9089 | 4.0823 | 26.064 |
| Gm1 | 1 / 1 | 0 | 60.567 | 116.15 | 0.4266 | 0.4307 | 2.9153 |
| Gm2 | 1 / 1 | 0 | 57.065 | 106.93 | 0.43003 | 0.42683 | 2.8161 |
| Gm3 | 1 / 1 | 0 | 54.035 | 103.91 | 0.42833 | 0.42426 | 2.731 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Parallelize independent coarse tiles within the requested thread budget
- **T2** : Reduce recursive hierarchy and conservative light-culling overhead
- **T3** : Optimize per-pixel shading math and row-wise vectorization
- **Gm1** : Combiner le parallélisme des tuiles T1 et l’optimisation du shading T3
- **Gm2** : Tester le meilleur candidat T3 au sein de l’intégration Gm1
- **Gm3** : Tester le dernier changement de shading T3 sur le meilleur candidat Gm2

Mother a lancé 3 arbres initiaux, puis créé 3 arbres ou combinaisons. 17 essais sur 18 sont corrects. 13 appels d’analyse/pilotage ont produit 11 actions appliquées ; 7 essais portent la provenance d’un avis et 3 celle d’un import explicite.

La durée réelle passe de 7062.5 à 1644.4 secondes, avec un budget nominal conservé de 7200 secondes. L’ancienne recherche comptait 73 essais corrects sur 80. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 44 invocations natives, 3,320,027 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 930,359 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a suspendu tous les arbres de recherche. Après la fin des travaux déjà admis, le moteur a poursuivi l’assemblage et la confirmation. Ce fait explique une fin anticipée possible ; le statut brut `budget_exhausted` ne doit pas être interprété seul comme un épuisement du temps.

Actions appliquées : continue : 5, integrate : 3, suspend : 3.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 60.567 | 1.0332 | 1.0332 |
| Gm2 | Oui | 57.065 | 1.0614 | 1.0614 |
| Gm3 | Oui | 54.035 | 1.0561 | 1.0561 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : Le nouveau programme prépare les propriétés des lumières dans un cache local à la tuile, parallélise les lignes du premier niveau de bornes Z et passe à un ordonnancement dynamique des tuiles de rendu. L’ancien utilisait un ordonnancement statique pour ces tuiles. Le gain à un thread indique que le seul parallélisme ne suffit pas à expliquer toute la différence ; aucune ablation ne sépare ici les effets du cache de lumières et de l’ordonnancement.

Sources auditées : [ancienne](mesures/paired-deferred/deferred/old_selected/candidate.cpp) et [nouvelle](mesures/paired-deferred/deferred/new_selected/candidate.cpp).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## gemm_cpu

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_BOEHM_DEFAULT_FINAL | 1024 | 8 | 2.7127 | 3.1654 | 0.857 | 0.83476–0.86183 | Ancien plus rapide dans chaque bloc |
| CPU_BOEHM_O3_FINAL | 1024 | 8 | 2.7127 | 3.1654 | 0.857 | 0.83476–0.86183 | Ancien plus rapide dans chaque bloc |
| CPU_BOEHM_O3_REORDER | 1024 | 8 | 2.7127 | 3.1654 | 0.857 | 0.83476–0.86183 | Ancien plus rapide dans chaque bloc |
| CPU_BOEHM_O3_TILING | 1024 | 8 | 2.7127 | 3.1654 | 0.857 | 0.83476–0.86183 | Ancien plus rapide dans chaque bloc |

Couverture des analystes pendant la recherche : 2 / 2 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 4 / 4 | 4 | 11.405 | 398.45 | 0.78878 | 3.5131 | 4.9749 |
| T2 | 6 / 6 | 4 | 3.3892 | 777.43 | 3.7157 | 5.1238 | 6.3115 |
| Gm1 | 1 / 1 | 0 | 3.4172 | 71.767 | 0.65402 | 0.85429 | 1.0413 |
| Gm2 | 1 / 1 | 0 | 2.7889 | 148.63 | 0.62998 | 0.85235 | 1.0278 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Unpacked cache-tiled loop ordering with OpenMP and compiler vectorization
- **T2** : Register-tiled SIMD GEMM with measured packing ablation
- **Gm1** : Intégration mesurée du tuilage T1 autour du noyau SIMD T2
- **Gm2** : Intégration mesurée de T2 rapide avec le candidat combiné Gm1

Mother a lancé 2 arbres initiaux, puis créé 2 arbres ou combinaisons. 13 essais sur 13 sont corrects. 14 appels d’analyse/pilotage ont produit 11 actions appliquées ; 6 essais portent la provenance d’un avis et 6 celle d’un import explicite.

La durée réelle passe de 6810.1 à 1639.1 secondes, avec un budget nominal conservé de 7200 secondes. L’ancienne recherche comptait 85 essais corrects sur 85. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

1 réponses d’analyse/pilotage ont échoué à la validation ou au transport dans cette tentative. Motifs enregistrés : Observer read is outside its visible evidence (1).

Coût connu de cette tentative : 34 invocations natives, 2,211,096 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 776,686 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a suspendu tous les arbres de recherche. Après la fin des travaux déjà admis, le moteur a poursuivi l’assemblage et la confirmation. Ce fait explique une fin anticipée possible ; le statut brut `budget_exhausted` ne doit pas être interprété seul comme un épuisement du temps.

Actions appliquées : continue : 4, integrate : 2, share : 2, suspend : 3.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 3.4172 | 1.0076 | 1.0076 |
| Gm2 | Oui | 2.7889 | 1.2152 | 1.2152 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : L’ancien utilise un micro-noyau AVX-512 8×32 directement sur les matrices. Le nouveau emploie un noyau 8×16 et, à partir de n=256, copie A et B en panneaux avec des blocs de 128 sur les dimensions k et n. Il ajoute donc une organisation des accès mémoire, mais aussi des copies et des synchronisations OpenMP. Les mesures par taille et par nombre de threads sont nécessaires pour juger le compromis ; le seul ajout de packing ne garantit pas un gain.

Sources auditées : [ancienne](mesures/paired-gemm-cpu/gemm_cpu/old_selected/candidate.cpp) et [nouvelle](mesures/paired-gemm-cpu/gemm_cpu/new_selected/candidate.cpp).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## mandelbrot

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_ISPC_MANDELBROT_1C | 1024 | 1 | 49.039 | 150.2 | 0.32648 | 0.32598–0.32867 | Ancien plus rapide dans chaque bloc |
| CPU_ISPC_MANDELBROT_4C | 1024 | 4 | 12.509 | 37.829 | 0.33068 | 0.33034–0.33161 | Ancien plus rapide dans chaque bloc |

Passage de 1 à plusieurs threads, sur les mêmes entrées et dans la même allocation :

| Entrée n | Threads | Ancien : temps 1 thread / temps parallèle | Actif : temps 1 thread / temps parallèle |
|---|---:|---:|---:|
| 1024 | 4 | 3.9201 | 3.9706 |

Ces rapports décrivent la mise à l’échelle de chaque programme. Ils ne sont pas les speedups contre le naïf. Une augmentation du nombre de threads ne garantit pas un gain proportionnel ; ordonnancement, synchronisation, mémoire et partage du nœud peuvent intervenir. Cette campagne ne comporte pas le profilage nécessaire pour attribuer une mauvaise mise à l’échelle à une cause précise.

Couverture des analystes pendant la recherche : 5 / 5 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 6 / 6 | 5 | 282.08 | 361.96 | 1.3935 | 14.496 | 103.82 |
| T2 | 2 / 3 | 5 | 178.61 | 858.8 | 0.47214 | 5.3145 | 25.814 |
| T3 | 7 / 7 | 5 | 150.3 | 597.34 | 1.9632 | 17.671 | 84.325 |
| Gm1 | 1 / 1 | 0 | 117.14 | 56.481 | 0.26868 | 2.2068 | 9.6859 |
| Gm2 | 1 / 1 | 0 | 75.247 | 85.754 | 0.32864 | 2.1586 | 7.8565 |
| T4 | 3 / 3 | 2 | 80.237 | 195.48 | 0.98498 | 6.5314 | 23.937 |
| T5 | 2 / 2 | 2 | 112.99 | 142.79 | 0.30808 | 4.477 | 17.941 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Thread-budgeted OpenMP work decomposition
- **T2** : Exact SIMD across independent pixels
- **T3** : Scalar instruction-level parallelism via pixel interleaving
- **Gm1** : Mesurer l’intégration du kernel scalaire intercalé avec OpenMP
- **Gm2** : Mesurer OpenMP avec l’interleaving scalaire par huit
- **T4** : Ordonnancement OpenMP du kernel huit états
- **T5** : Partager par lignes le kernel SIMD exact

Mother a lancé 3 arbres initiaux, puis créé 4 arbres ou combinaisons. 23 essais sur 24 sont corrects. 32 appels d’analyse/pilotage ont produit 21 actions appliquées ; 8 essais portent la provenance d’un avis et 7 celle d’un import explicite.

La durée réelle passe de 6862.8 à 1873 secondes, avec un budget nominal conservé de 7200 secondes. L’ancienne recherche comptait 58 essais corrects sur 59. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

1 réponses d’analyse/pilotage ont échoué à la validation ou au transport dans cette tentative. Motifs enregistrés : Observer claim has unsupported evidence IDs (1).

Coût connu de cette tentative : 68 invocations natives, 4,234,462 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 2,151,481 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.

Actions appliquées : branch : 2, close : 1, continue : 9, integrate : 2, suspend : 7.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 117.14 | 1.637 | 1.2831 |
| Gm2 | Oui | 75.247 | 1.9975 | 1.5567 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : L’ancien traite des blocs de 128 pixels avec des boucles marquées omp simd. Le nouveau déroule explicitement huit orbites avec un indicateur actif pour chacune. Les deux répartissent les lignes avec OpenMP en ordonnancement dynamique. Ce changement échange une structure propice à la vectorisation contre un déroulage scalaire explicite ; la source seule ne permet pas de déduire les instructions effectivement émises ni leur coût.

Sources auditées : [ancienne](mesures/paired-mandelbrot/mandelbrot/old_selected/candidate.cpp) et [nouvelle](mesures/paired-mandelbrot/mandelbrot/new_selected/candidate.cpp).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## noise

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_ISPC_PERLIN_1C | 768 | 1 | 262.32 | 146.89 | 1.7859 | 1.773–1.8199 | Nouveau plus rapide dans chaque bloc |

Couverture des analystes pendant la recherche : 2 / 3 arbres de recherche ont eu au moins un appel. Arbres sans appel : T3. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 5 / 5 | 3 | 179.01 | 588.8 | 2.0774 | 10.844 | 32.301 |
| T2 | 5 / 5 | 1 | 278.32 | 406.22 | 1.49 | 11.046 | 34.299 |
| T3 | 1 / 2 | 0 | 312.33 | 625.14 | 0.59191 | 2.3891 | 7.0468 |
| Gm1 | 1 / 1 | 0 | 146.71 | 78.108 | 0.48142 | 1.8857 | 4.0535 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Per-axis, per-octave coordinate-state reuse
- **T2** : Scalar Perlin hash, gradient, and interpolation kernel
- **T3** : SIMD across independent image pixels
- **Gm1** : Intégrer états d’axes et optimisation scalaire

Mother a lancé 3 arbres initiaux, puis créé 1 arbres ou combinaisons. 14 essais sur 15 sont corrects. 7 appels d’analyse/pilotage ont produit 6 actions appliquées ; 2 essais portent la provenance d’un avis et 1 celle d’un import explicite.

La durée réelle passe de 1733.2 à 1228.4 secondes, avec un budget nominal conservé de 1800 secondes. L’ancienne recherche comptait 11 essais corrects sur 11. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 39 invocations natives, 2,526,778 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 318,306 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a suspendu tous les arbres de recherche. Après la fin des travaux déjà admis, le moteur a poursuivi l’assemblage et la confirmation. Ce fait explique une fin anticipée possible ; le statut brut `budget_exhausted` ne doit pas être interprété seul comme un épuisement du temps.

Actions appliquées : continue : 2, integrate : 1, suspend : 3.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 146.71 | 1.2202 | 1.2202 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : L’ancien partage les premiers niveaux de la table de permutation entre les huit coins, mais recalcule les coordonnées de cellule et les poids à chaque pixel et octave. Le nouveau prépare séparément ces états pour les axes x, y et z, puis les réutilise dans la boucle des pixels. Les vecteurs de préparation sont alloués et remplis à chaque appel, donc leur coût fait partie du chronométrage ; il ne s’agit pas d’un cache conservé entre deux tests. L’écriture de l’interpolation diffère également, ce qui reste soumis à la tolérance du contrôle protégé. Sans ablation, le gain éventuel ne peut pas être attribué à une seule de ces modifications.

Sources auditées : [ancienne](mesures/paired-noise/noise/old_selected/candidate.cpp) et [nouvelle](mesures/paired-noise/noise/new_selected/candidate.cpp).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## popcount

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_POPCOUNT_CLANG | 1000 | 1 | 0.081532 | 0.081506 | 1.0003 | 0.99981–1.0009 | Code ou binaire identique : variation de mesure |
| CPU_POPCOUNT_GCC | 1000 | 1 | 0.081494 | 0.0815 | 0.99993 | 0.99923–1.0005 | Code ou binaire identique : variation de mesure |

Couverture des analystes pendant la recherche : 2 / 3 arbres de recherche ont eu au moins un appel. Arbres sans appel : T3. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 4 / 4 | 2 | 0.081694 | 294.07 | 0.95086 | 2.8813 | 3.1857 |
| T2 | 5 / 5 | 3 | 0.081733 | 291.35 | 1.1828 | 3.6363 | 4.0131 |
| T3 | 4 / 4 | 0 | 0.081696 | 240.81 | 0.96704 | 2.8896 | 3.2747 |
| Gm1 | 1 / 1 | 0 | 0.081767 | 33.907 | 0.23641 | 0.71744 | 0.79075 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : GCC builtin versus target-local POPCNT
- **T2** : Portable SWAR population count
- **T3** : Sequential loop control and measured combinations
- **Gm1** : Mesurer le compte rapide T2 combiné au déroulage T3

Mother a lancé 3 arbres initiaux, puis créé 1 arbres ou combinaisons. 15 essais sur 15 sont corrects. 10 appels d’analyse/pilotage ont produit 5 actions appliquées ; 2 essais portent la provenance d’un avis et 1 celle d’un import explicite.

La durée réelle passe de 1937.2 à 702.58 secondes, avec un budget nominal conservé de 1800 secondes. L’ancienne recherche comptait 12 essais corrects sur 12. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 32 invocations natives, 1,845,961 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 508,351 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.

Actions appliquées : close : 1, integrate : 1, suspend : 3.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 0.081767 | 0.99958 | 0.9991 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : Les deux versions conservent le même déroulage de quatre éléments, la même dépendance au résultat précédent et un builtin de comptage de bits. La nouvelle nettoie les includes et enveloppe le builtin dans une fonction inline. Les fichiers sources diffèrent, mais les binaires comparés sont identiques, séparément avec GCC et Clang. Les rapports très proches de 1 sont donc des variations de mesure, pas un progrès algorithmique.

Sources auditées : [ancienne](mesures/paired-popcount-gcc/popcount/old_selected/candidate.cpp) et [nouvelle](mesures/paired-popcount-gcc/popcount/new_selected/candidate.cpp).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## raytracer

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_ISPC_RAYTRACER_1C | 900 | 1 | 233.64 | 195.96 | 1.1923 | 1.192–1.1962 | Nouveau plus rapide dans chaque bloc |
| CPU_ISPC_RAYTRACER_4C | 900 | 4 | 60.904 | 51.892 | 1.1737 | 1.17–1.1749 | Nouveau plus rapide dans chaque bloc |
| CPU_ISPC_RAYTRACER_40C | 900 | 40 | 19.908 | 18.416 | 1.081 | 0.81243–3.1282 | Écart dans la variabilité observée |

Passage de 1 à plusieurs threads, sur les mêmes entrées et dans la même allocation :

| Entrée n | Threads | Ancien : temps 1 thread / temps parallèle | Actif : temps 1 thread / temps parallèle |
|---|---:|---:|---:|
| 900 | 4 | 3.8362 | 3.7763 |
| 900 | 40 | 11.736 | 10.641 |

Ces rapports décrivent la mise à l’échelle de chaque programme. Ils ne sont pas les speedups contre le naïf. Une augmentation du nombre de threads ne garantit pas un gain proportionnel ; ordonnancement, synchronisation, mémoire et partage du nœud peuvent intervenir. Cette campagne ne comporte pas le profilage nécessaire pour attribuer une mauvaise mise à l’échelle à une cause précise.

Couverture des analystes pendant la recherche : 4 / 4 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 9 / 9 | 4 | 45.388 | 826.59 | 2.2317 | 8.6337 | 58.567 |
| T2 | 8 / 8 | 5 | 197.66 | 767.22 | 2.1665 | 10.206 | 83.115 |
| T3 | 6 / 6 | 2 | 230.9 | 692.64 | 1.2907 | 7.9138 | 66.644 |
| T4 | 1 / 3 | 2 | 234.55 | 676.19 | 1.0008 | 3.9197 | 11.098 |
| Gm1 | 1 / 1 | 0 | 47.176 | 82.816 | 0.32019 | 0.95579 | 6.5525 |
| Gm2 | 1 / 1 | 0 | 41.702 | 58.992 | 0.32612 | 0.94612 | 6.0728 |
| Gm3 | 1 / 1 | 0 | 40.644 | 115.1 | 0.26791 | 0.933 | 6.0036 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Parallélisation OpenMP du rendu
- **T2** : Parcours BVH et tests AABB
- **T3** : Noyau d’intersection triangle
- **T4** : Vectorisation SIMD de rayons voisins
- **Gm1** : Intégration mesurée du parallélisme OpenMP et de l’optimisation BVH
- **Gm2** : OpenMP et chemin AABB accéléré
- **Gm3** : Intégration des variantes récentes OpenMP et AABB

Mother a lancé 4 arbres initiaux, puis créé 3 arbres ou combinaisons. 31 essais sur 33 sont corrects. 26 appels d’analyse/pilotage ont produit 11 actions appliquées ; 13 essais portent la provenance d’un avis et 3 celle d’un import explicite.

La durée réelle passe de 6960.6 à 1803.4 secondes, avec un budget nominal conservé de 7200 secondes. L’ancienne recherche comptait 69 essais corrects sur 74. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 77 invocations natives, 6,652,546 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 2,328,845 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.

Actions appliquées : close : 1, continue : 2, integrate : 3, suspend : 5.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 47.176 | 1.0025 | 1.0025 |
| Gm2 | Oui | 41.702 | 1.1175 | 1.1175 |
| Gm3 | Oui | 40.644 | 1.1167 | 1.026 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : Le nouveau distingue les rayons dont toutes les directions inverses sont finies, utilise pour eux un test de boîte spécialisé avec sorties anticipées, ajoute des indications de branchement et précharge le triangle suivant. Il conserve un chemin générique pour les directions inverses non finies. L’ancien et le nouveau distribuent le rendu par paquets de deux lignes avec OpenMP. Les différences mesurées agrègent donc surtout plusieurs modifications du parcours BVH et des intersections ; aucun profil matériel ne les départage ici.

Sources auditées : [ancienne](mesures/paired-raytracer/raytracer/old_selected/candidate.cpp) et [nouvelle](mesures/paired-raytracer/raytracer/new_selected/candidate.cpp).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## reduction

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| gpu_reduce_02 | 4194304 | GPU | 0.027884 | 0.0079706 | 3.4984 | 2.9266–4.305 | Nouveau plus rapide dans chaque bloc |
| gpu_reduce_03 | 4194304 | GPU | 0.027884 | 0.0079706 | 3.4984 | 2.9266–4.305 | Nouveau plus rapide dans chaque bloc |
| gpu_reduce_04 | 4194304 | GPU | 0.027884 | 0.0079706 | 3.4984 | 2.9266–4.305 | Nouveau plus rapide dans chaque bloc |
| gpu_reduce_05 | 4194304 | GPU | 0.027884 | 0.0079706 | 3.4984 | 2.9266–4.305 | Nouveau plus rapide dans chaque bloc |
| gpu_reduce_06 | 4194304 | GPU | 0.027884 | 0.0079706 | 3.4984 | 2.9266–4.305 | Nouveau plus rapide dans chaque bloc |
| gpu_reduce_07 | 4194304 | GPU | 0.027884 | 0.0079706 | 3.4984 | 2.9266–4.305 | Nouveau plus rapide dans chaque bloc |

Couverture des analystes pendant la recherche : 3 / 3 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 3 / 3 | 3 | 0.0069436 | 567.35 | 1.7799 | 68.834 | 17.579 |
| T2 | 3 / 3 | 3 | 0.046483 | 326.55 | 7.6224 | 73.05 | 24.697 |
| T3 | 6 / 6 | 5 | 0.0063413 | 746.99 | 15.279 | 130.95 | 41.184 |
| Gm1 | 1 / 1 | 0 | 0.0073346 | 98.417 | 2.5308 | 19.377 | 5.9491 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Large-input hierarchical reduction and warp/block reduction costs
- **T2** : Small-input direct-output reduction and launch crossover
- **T3** : Large-input atomic final aggregation
- **Gm1** : Combinaison mesurée des voies grande et petite tailles

Mother a lancé 3 arbres initiaux, puis créé 1 arbres ou combinaisons. 14 essais sur 14 sont corrects. 14 appels d’analyse/pilotage ont produit 9 actions appliquées ; 4 essais portent la provenance d’un avis et 1 celle d’un import explicite.

La durée réelle passe de 7022.8 à 1526.6 secondes, avec un budget nominal conservé de 7200 secondes. L’ancienne recherche comptait 64 essais corrects sur 64. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

2 réponses d’analyse/pilotage ont échoué à la validation ou au transport dans cette tentative. Motifs enregistrés : Observer claim has unsupported evidence IDs (2).

Coût connu de cette tentative : 35 invocations natives, 2,682,509 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 579,833 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a suspendu tous les arbres de recherche. Après la fin des travaux déjà admis, le moteur a poursuivi l’assemblage et la confirmation. Ce fait explique une fin anticipée possible ; le statut brut `budget_exhausted` ne doit pas être interprété seul comme un épuisement du temps.

Actions appliquées : continue : 4, integrate : 1, suspend : 4.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 0.0073346 | 1.053 | 0.86458 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : Pour la taille chronométrée de 2^22 entiers, le nouveau programme remet la sortie à zéro puis lance 512 blocs au plus, avec accumulation par thread, réduction de warp et addition atomique par bloc. L’ancien réalise plusieurs étages de réduction par tuiles de 128 éléments. Le nombre de lancements et la répartition du travail changent donc réellement. Le gain mesuré est cohérent avec ce changement ; aucun profil matériel ne permet ici d’attribuer une fraction précise du gain à chaque mécanisme. Le vainqueur vient d’un arbre de recherche, pas de Gm1.

Sources auditées : [ancienne](mesures/paired-extra-reduction-s4convd/reduction/old_selected/candidate.cu) et [nouvelle](mesures/paired-extra-reduction-s4convd/reduction/new_selected/candidate.cu).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## s4convd

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| gpu_s4convd_kernels | 16384 | GPU | 4.659 | 8.1086 | 0.57458 | 0.56772–0.57784 | Ancien plus rapide dans chaque bloc |

Couverture des analystes pendant la recherche : 3 / 3 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 3 / 3 | 2 | 34.147 | 547.84 | 1.8538 | 66.441 | 29.177 |
| T2 | 3 / 3 | 3 | 34.859 | 295.05 | 1.7925 | 58.779 | 27.537 |
| T3 | 3 / 3 | 4 | 9.4061 | 468.2 | 1.8891 | 65.439 | 26.939 |
| Gm1 | 1 / 1 | 0 | 13.141 | 97.474 | 0.61322 | 22.622 | 8.6061 |
| Gm2 | 1 / 1 | 0 | 8.075 | 70.623 | 0.60916 | 18.992 | 7.9507 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Improve forward and input-gradient CTA mapping without fusion
- **T2** : Measure a fused forward and input-gradient kernel
- **T3** : Compare one-stage and split weight-gradient reductions
- **Gm1** : Combiner le mapping T1 et la réduction gk T3
- **Gm2** : Intégrer le mapping T1 au kernel gk b957

Mother a lancé 3 arbres initiaux, puis créé 2 arbres ou combinaisons. 13 essais sur 13 sont corrects. 16 appels d’analyse/pilotage ont produit 9 actions appliquées ; 2 essais portent la provenance d’un avis et 2 celle d’un import explicite.

La durée réelle passe de 6980.4 à 1609.1 secondes, avec un budget nominal conservé de 7200 secondes. L’ancienne recherche comptait 57 essais corrects sur 58. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 36 invocations natives, 1,930,904 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 607,033 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a suspendu tous les arbres de recherche. Après la fin des travaux déjà admis, le moteur a poursuivi l’assemblage et la confirmation. Ce fait explique une fin anticipée possible ; le statut brut `budget_exhausted` ne doit pas être interprété seul comme un épuisement du temps.

Actions appliquées : continue : 3, integrate : 2, suspend : 4.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 13.141 | 1.0939 | 1.0939 |
| Gm2 | Oui | 8.075 | 1.1649 | 1.1649 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : Le programme ancien conserve quatre accumulateurs pour les calculs forward et gradient d’entrée, et découpe le gradient du noyau en tuiles avec une réduction finale. Le nouveau conserve des boucles plus simples pour les deux premiers calculs et regroupe quatre coefficients par bloc pour le troisième. Les deux programmes passent les contrôles, mais le nouveau est moins rapide dans cette comparaison. Le parallélisme et les chaînes de dépendances constituent des pistes d’explication, pas une attribution démontrée sans profilage.

Sources auditées : [ancienne](mesures/paired-extra-reduction-s4convd/s4convd/old_selected/candidate.cu) et [nouvelle](mesures/paired-extra-reduction-s4convd/s4convd/new_selected/candidate.cu).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## sgemm

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| gpu_sgemm_02 | 4096 | GPU | 5.7394 | 11.881 | 0.48308 | 0.47756–0.48743 | Ancien plus rapide dans chaque bloc |
| gpu_sgemm_03 | 4096 | GPU | 5.7394 | 11.881 | 0.48308 | 0.47756–0.48743 | Ancien plus rapide dans chaque bloc |
| gpu_sgemm_04 | 4096 | GPU | 5.7394 | 11.881 | 0.48308 | 0.47756–0.48743 | Ancien plus rapide dans chaque bloc |
| gpu_sgemm_05 | 4096 | GPU | 5.7394 | 11.881 | 0.48308 | 0.47756–0.48743 | Ancien plus rapide dans chaque bloc |
| gpu_sgemm_07 | 4096 | GPU | 5.7394 | 11.881 | 0.48308 | 0.47756–0.48743 | Ancien plus rapide dans chaque bloc |
| gpu_sgemm_08 | 4096 | GPU | 5.7394 | 11.881 | 0.48308 | 0.47756–0.48743 | Ancien plus rapide dans chaque bloc |
| gpu_sgemm_11 | 4096 | GPU | 5.7394 | 11.881 | 0.48308 | 0.47756–0.48743 | Ancien plus rapide dans chaque bloc |
| gpu_sgemm_06 | 4096 | GPU | 5.7394 | 11.881 | 0.48308 | 0.47756–0.48743 | Ancien plus rapide dans chaque bloc |
| gpu_sgemm_09 | 4096 | GPU | 5.7394 | 11.881 | 0.48308 | 0.47756–0.48743 | Ancien plus rapide dans chaque bloc |
| gpu_sgemm_10 | 4096 | GPU | 5.7394 | 11.881 | 0.48308 | 0.47756–0.48743 | Ancien plus rapide dans chaque bloc |
| gpu_sgemm_cublas | 4096 | GPU | 5.7394 | 11.881 | 0.48308 | 0.47756–0.48743 | Ancien plus rapide dans chaque bloc |

Couverture des analystes pendant la recherche : 4 / 4 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 4 / 4 | 5 | 19.527 | 455.18 | 2.2652 | 24.779 | 21.569 |
| T2 | 6 / 6 | 3 | 11.853 | 511.16 | 3.4072 | 33.027 | 29.619 |
| T3 | 3 / 3 | 2 | 17.308 | 458.98 | 1.7025 | 18.491 | 13.443 |
| Gm1 | 1 / 1 | 0 | 21.907 | 125.59 | 0.59557 | 6.4592 | 4.896 |
| T4 | 2 / 2 | 1 | 11.952 | 179.97 | 1.1621 | 9.879 | 6.6688 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Coalescing control plus synchronous SIMT CTA tiling
- **T2** : Multi-accumulator register-blocked SIMT microtiles
- **T3** : Matched synchronous/asynchronous K-stage pipeline comparison
- **Gm1** : Tuilage partagé synchrone avec microtuiles registre
- **T4** : Ordre de parcours CTA et localité cache

Mother a lancé 3 arbres initiaux, puis créé 2 arbres ou combinaisons. 18 essais sur 18 sont corrects. 20 appels d’analyse/pilotage ont produit 15 actions appliquées ; 7 essais portent la provenance d’un avis et 3 celle d’un import explicite.

La durée réelle passe de — à 1504.6 secondes, avec un budget nominal conservé de 1800 secondes. L’ancienne recherche comptait 14 essais corrects sur 15. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 48 invocations natives, 3,262,349 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 1,193,513 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.

Actions appliquées : branch : 1, close : 1, continue : 6, integrate : 1, share : 1, suspend : 5.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 21.907 | 0.67219 | 0.54107 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : L’ancien charge des tuiles A et B de 64×64 en mémoire partagée, synchronise les threads et calcule seize accumulateurs par thread. Le nouveau calcule huit sorties par thread, réparties sur deux lignes et quatre bandes de colonnes, en lisant directement A et B à chaque pas de réduction, sans tuile partagée. Il dépend donc davantage des caches et de la réutilisation locale aux threads. Le gain éventuel ne peut pas être déduit du seul nombre d’accumulateurs ; les mesures portent sur les matrices carrées du contrat, en FP32 et sans appel à une bibliothèque de multiplication optimisée.

Sources auditées : [ancienne](mesures/paired-sgemm/sgemm/old_selected/candidate.cu) et [nouvelle](mesures/paired-sgemm/sgemm/new_selected/candidate.cu).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## softmax

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| gpu_softmax_triton | 4096 | GPU | 0.041504 | 0.041248 | 1.0062 | 0.9977–1.0209 | Écart dans la variabilité observée |

Couverture des analystes pendant la recherche : 3 / 3 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 5 / 5 | 6 | 0.041243 | 709.46 | 0.2113 | 105.52 | 40.819 |
| T2 | 4 / 4 | 3 | 0.042549 | 446.04 | 0.16974 | 95.426 | 34.893 |
| T3 | 6 / 6 | 3 | 0.048661 | 664.24 | 0.25616 | 121.06 | 50.995 |
| Gm1 | 1 / 1 | 0 | 0.041712 | 79.25 | 0.041824 | 19.687 | 6.9303 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Direct fused one-row-per-CTA kernel
- **T2** : Grouped multi-row-per-CTA kernel
- **T3** : Streaming online reduction to reduce live row state
- **Gm1** : Intégration mesurée des mappings direct et groupé

Mother a lancé 3 arbres initiaux, puis créé 1 arbres ou combinaisons. 17 essais sur 17 sont corrects. 22 appels d’analyse/pilotage ont produit 10 actions appliquées ; 8 essais portent la provenance d’un avis et 1 celle d’un import explicite.

La durée réelle passe de 6830.4 à 1668.2 secondes, avec un budget nominal conservé de 7200 secondes. L’ancienne recherche comptait 51 essais corrects sur 51. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 51 invocations natives, 2,374,253 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 1,102,415 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a suspendu tous les arbres de recherche. Après la fin des travaux déjà admis, le moteur a poursuivi l’assemblage et la confirmation. Ce fait explique une fin anticipée possible ; le statut brut `budget_exhausted` ne doit pas être interprété seul comme un épuisement du temps.

Actions appliquées : continue : 6, integrate : 1, suspend : 3.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 0.041712 | 0.98875 | 0.98875 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : L’ancien utilise systématiquement une réduction en ligne par morceaux, puis relit les valeurs pour produire la sortie. Le nouveau calcule directement les lignes de largeur modérée et conserve un noyau par morceaux pour les lignes très larges ; il ajoute aussi des chemins de repli et la gestion du calcul en double précision. La remesure de la forme chronométrée ne départage pas nettement les deux versions : la plage des rapports entre blocs traverse 1. Davantage de chemins pris en charge ne constitue pas à lui seul un gain de vitesse sur cette entrée.

Sources auditées : [ancienne](mesures/paired-extra-softmax/softmax/old_selected/candidate.py) et [nouvelle](mesures/paired-extra-softmax/softmax/new_selected/candidate.py).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## stencil3d

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_ISPC_STENCIL_1C | 256 | 1 | 87.767 | 80.254 | 1.0936 | 0.93968–1.6843 | Écart dans la variabilité observée |
| CPU_ISPC_STENCIL_4C | 256 | 4 | 50.186 | 37.066 | 1.354 | 0.68867–2.4148 | Écart dans la variabilité observée |

Passage de 1 à plusieurs threads, sur les mêmes entrées et dans la même allocation :

| Entrée n | Threads | Ancien : temps 1 thread / temps parallèle | Actif : temps 1 thread / temps parallèle |
|---|---:|---:|---:|
| 256 | 4 | 1.7488 | 2.1652 |

Ces rapports décrivent la mise à l’échelle de chaque programme. Ils ne sont pas les speedups contre le naïf. Une augmentation du nombre de threads ne garantit pas un gain proportionnel ; ordonnancement, synchronisation, mémoire et partage du nœud peuvent intervenir. Cette campagne ne comporte pas le profilage nécessaire pour attribuer une mauvaise mise à l’échelle à une cause précise.

Couverture des analystes pendant la recherche : 4 / 4 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 4 / 4 | 5 | 219.89 | 339.82 | 0.86143 | 12.404 | 67.619 |
| T2 | 7 / 7 | 5 | 79.497 | 644.04 | 2.1049 | 22.684 | 95.771 |
| T3 | 3 / 3 | 2 | 296.35 | 452.51 | 1.0551 | 9.6876 | 60.049 |
| Gm1 | 1 / 1 | 0 | 54.595 | 89.925 | 0.23139 | 2.9116 | 9.149 |
| T4 | 3 / 3 | 2 | 58.612 | 292.6 | 0.75102 | 8.9493 | 37.196 |
| Gm2 | 1 / 1 | 0 | 55.09 | 90.215 | 0.27457 | 2.9136 | 9.1533 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Compare per-step and persistent OpenMP teams
- **T2** : Contrast compiler auto-vectorization and target-supported SIMD
- **T3** : Isolate temporal blocking from spatial-only cache blocking
- **Gm1** : Combiner SIMD sur x et parallélisme OpenMP par lignes
- **T4** : Réduire les chargements redondants en x dans le noyau fusionné
- **Gm2** : Combiner l’auto-vectorisation avec le parallélisme persistant

Mother a lancé 3 arbres initiaux, puis créé 3 arbres ou combinaisons. 21 essais sur 21 sont corrects. 25 appels d’analyse/pilotage ont produit 16 actions appliquées ; 8 essais portent la provenance d’un avis et 5 celle d’un import explicite.

La durée réelle passe de 6901.4 à 1501.9 secondes, avec un budget nominal conservé de 7200 secondes. L’ancienne recherche comptait 58 essais corrects sur 59. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 56 invocations natives, 3,764,602 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 1,474,607 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.

Actions appliquées : branch : 1, close : 1, continue : 8, integrate : 2, suspend : 4.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 54.595 | 1.4889 | 1.4889 |
| Gm2 | Oui | 55.09 | 1.453 | 0.99101 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : Les deux versions conservent une équipe OpenMP pendant les pas de temps. L’ancien distribue les couples (z, y) par omp for collapse(2), avec des noyaux AVX/SSE écrits en intrinsics. Le nouveau affecte à chaque thread une tranche contiguë de z et utilise des pointeurs restrict ainsi qu’une boucle omp simd, dont le compilateur choisit les instructions. Il ne faut donc pas attribuer un éventuel gain au seul maintien d’une équipe persistante, déjà présent avant : la répartition du domaine et le code vectoriel ont aussi changé.

Sources auditées : [ancienne](mesures/paired-stencil3d/stencil3d/old_selected/candidate.cpp) et [nouvelle](mesures/paired-stencil3d/stencil3d/new_selected/candidate.cpp).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## stencil_y

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| gpu_stencil_y | 64 | GPU | 0.0033446 | 0.0029936 | 1.1173 | 1.082–1.2246 | Nouveau plus rapide dans chaque bloc |

Couverture des analystes pendant la recherche : 3 / 3 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 5 / 5 | 2 | 0.0030045 | 523.81 | 2.8471 | 10.364 | 8.1622 |
| T2 | 7 / 7 | 4 | 0.0029006 | 622.52 | 4.0108 | 14.495 | 11.507 |
| T3 | 3 / 4 | 5 | 0.0029763 | 735.76 | 2.3311 | 6.7592 | 4.907 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Coalesced direct-global stencil without shared memory
- **T2** : Shared-memory pencil geometry: full-height versus y-subtile tiling
- **T3** : Register reuse across multiple y outputs

Mother a lancé 3 arbres initiaux, puis créé 0 arbres ou combinaisons. 16 essais sur 17 sont corrects. 19 appels d’analyse/pilotage ont produit 9 actions appliquées ; 4 essais portent la provenance d’un avis et 0 celle d’un import explicite.

La durée réelle passe de — à 1207 secondes, avec un budget nominal conservé de 1800 secondes. L’ancienne recherche comptait 21 essais corrects sur 23. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 44 invocations natives, 2,412,847 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 1,112,484 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.

Actions appliquées : close : 1, continue : 3, resume : 1, suspend : 4.

Lecture des sources : Les deux programmes utilisent une tuile partagée de 32×40 valeurs et un bloc de threads 32×16, avec deux sorties par thread. L’ancien traite deux lignes espacées de 16, accepte des dimensions passées en paramètres et calcule les coefficients à partir de la hauteur. Le nouveau traite deux lignes adjacentes, spécialise les dimensions à 64³ et initialise une fois les coefficients en mémoire constante ; les halos utilisent la même convention périodique de période 63. Cette spécialisation correspond au cas fixe testé, mais elle ne valide pas le nouveau programme pour d’autres dimensions. Le chargement des halos, l’adressage et l’écriture de la combinaison arithmétique changent aussi ; la mesure ne sépare pas leurs contributions.

Sources auditées : [ancienne](mesures/paired-stencil-y/stencil_y/old_selected/candidate.cu) et [nouvelle](mesures/paired-stencil-y/stencil_y/new_selected/candidate.cu).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## sumabs

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| gpu_sum_abs_fusion | 268435456 | GPU | 0.28208 | 0.28806 | 0.97923 | 0.97779–0.98201 | Ancien plus rapide dans chaque bloc |

Couverture des analystes pendant la recherche : 3 / 3 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 7 / 7 | 4 | 0.28978 | 687.07 | 11.512 | 133.35 | 40.74 |
| T2 | 4 / 4 | 3 | 0.34358 | 399.59 | 6.5528 | 76.593 | 23.691 |
| T3 | 6 / 6 | 3 | 0.28823 | 737.08 | 9.9719 | 112.77 | 35.129 |
| Gm1 | 1 / 1 | 0 | 0.29978 | 98.739 | 1.6064 | 18.728 | 5.9581 |
| Gm2 | 1 / 1 | 0 | 0.29099 | 79.508 | 1.6679 | 19.567 | 5.9818 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Hierarchical fusion: partial granularity and finalization
- **T2** : Single-kernel CTA aggregation with output atomics
- **T3** : Within-CTA streaming and reduction mapping
- **Gm1** : Combinaison du mapping T3 et du partitionnement T1
- **Gm2** : Mapping T3 avec le partitionnement à 4096 partiels de T1

Mother a lancé 3 arbres initiaux, puis créé 2 arbres ou combinaisons. 22 essais sur 22 sont corrects. 21 appels d’analyse/pilotage ont produit 12 actions appliquées ; 9 essais portent la provenance d’un avis et 7 celle d’un import explicite.

La durée réelle passe de 6899.9 à 1858.6 secondes, avec un budget nominal conservé de 7200 secondes. L’ancienne recherche comptait 54 essais corrects sur 54. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 54 invocations natives, 2,835,500 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 1,117,909 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.

Actions appliquées : close : 1, continue : 3, integrate : 2, share : 1, suspend : 5.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 0.29978 | 0.98434 | 0.96664 |
| Gm2 | Oui | 0.29099 | 0.99584 | 0.9905 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : L’ancien remet la sortie à zéro puis accumule atomiquement les sommes de blocs, avec des lectures float4, huit accumulateurs par thread et 512 threads par bloc. Le nouveau écrit des sommes partielles avec des lectures float2 et 128 threads par bloc, puis lance une réduction finale distincte ; il borne le nombre de sommes partielles à 1 024 et spécialise ce cas. Cela remplace les additions atomiques sur la sortie par un second noyau et un tampon de travail. La comparaison mesure cet ensemble de choix ; elle ne permet pas d’isoler le coût des atomiques, de la vectorisation et des lancements.

Sources auditées : [ancienne](mesures/paired-sumabs/sumabs/old_selected/candidate.cu) et [nouvelle](mesures/paired-sumabs/sumabs/new_selected/candidate.cu).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## transpose

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| gpu_transpose_m2050 | 1024 | GPU | 0.0033344 | 0.0032243 | 1.0341 | 1.016–1.0854 | Nouveau plus rapide dans chaque bloc |
| gpu_transpose_k20c | 1024 | GPU | 0.0033344 | 0.0032243 | 1.0341 | 1.016–1.0854 | Nouveau plus rapide dans chaque bloc |

Couverture des analystes pendant la recherche : 2 / 2 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 6 / 6 | 3 | 0.0031422 | 599.27 | 3.4087 | 24.085 | 8.4836 |
| T2 | 4 / 4 | 5 | 0.0033821 | 556.8 | 2.3507 | 15.367 | 6.4379 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Shared-memory transpose layouts and ownership
- **T2** : Warp-local register/shuffle transpose

Mother a lancé 2 arbres initiaux, puis créé 0 arbres ou combinaisons. 11 essais sur 11 sont corrects. 14 appels d’analyse/pilotage ont produit 7 actions appliquées ; 6 essais portent la provenance d’un avis et 0 celle d’un import explicite.

La durée réelle passe de — à 1154.4 secondes, avec un budget nominal conservé de 1800 secondes. L’ancienne recherche comptait 22 essais corrects sur 22. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Coût connu de cette tentative : 30 invocations natives, 2,156,999 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 861,170 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a suspendu tous les arbres de recherche. Après la fin des travaux déjà admis, le moteur a poursuivi l’assemblage et la confirmation. Ce fait explique une fin anticipée possible ; le statut brut `budget_exhausted` ne doit pas être interprété seul comme un épuisement du temps.

Actions appliquées : continue : 3, resume : 1, suspend : 3.

Lecture des sources : Les deux versions passent par une tuile partagée de 32×33 mots. L’ancien charge des scalaires avec des blocs de threads 32×8 et permute l’ordre des tuiles. Le nouveau charge et écrit quatre mots à la fois avec uint4, utilise des blocs 8×32 et revient à un ordre de tuiles direct. La comparaison agrège donc la vectorisation des accès et la distribution du travail. Le nouveau exploite le contrat de dimensions positives multiples de 32 ; il n’est pas validé ici pour des dimensions arbitraires hors de ce contrat.

Sources auditées : [ancienne](mesures/paired-transpose/transpose/old_selected/candidate.cu) et [nouvelle](mesures/paired-transpose/transpose/new_selected/candidate.cu).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## utf8

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_UTF8_BEST | 65536 | 1 | 0.013363 | 0.029064 | 0.45978 | 0.45188–0.45997 | Ancien plus rapide dans chaque bloc |
| CPU_UTF8_MEAN | 65536 | 1 | 0.013375 | 0.029368 | 0.45542 | 0.45188–0.45997 | Ancien plus rapide dans chaque bloc |

Couverture des analystes pendant la recherche : 3 / 3 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 2 / 4 | 4 | 0.02962 | 1389.3 | 1.1111 | 8.8836 | 2.2124 |
| T2 | 10 / 10 | 7 | 0.039978 | 795.19 | 2.4533 | 22.532 | 8.414 |
| T3 | 5 / 5 | 3 | 0.049545 | 538.64 | 1.0075 | 11.174 | 4.2415 |
| Gm1 | 1 / 1 | 0 | 0.056234 | 68.576 | 0.27994 | 2.2335 | 0.83409 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Whole-stream SIMD UTF-8 validation with cross-block state
- **T2** : SIMD-assisted ASCII-run skipping with a scalar slow path
- **T3** : Branch-reduced scalar UTF-8 decoding
- **Gm1** : Test a faster ASCII-prefix scan with a word-scanned scalar suffix

Mother a lancé 3 arbres initiaux, puis créé 1 arbres ou combinaisons. 19 essais sur 21 sont corrects. 24 appels d’analyse/pilotage ont produit 14 actions appliquées ; 11 essais portent la provenance d’un avis et 3 celle d’un import explicite.

La durée réelle passe de 7046 à 1979.7 secondes, avec un budget nominal conservé de 7200 secondes. L’ancienne recherche comptait 63 essais corrects sur 63. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

1 réponses d’analyse/pilotage ont échoué à la validation ou au transport dans cette tentative. Motifs enregistrés : Observer claim has unsupported evidence IDs (1).

Coût connu de cette tentative : 61 invocations natives, 3,336,199 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 1,388,553 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.

Actions appliquées : close : 1, continue : 6, integrate : 1, resume : 1, share : 1, suspend : 4.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 0.056234 | 0.71093 | 0.71093 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : Les deux versions utilisent SSE2. L’ancien déroule deux blocs de 16 octets et vérifie les restrictions de second octet par opérations vectorielles. Le nouveau traite un bloc à la fois et inspecte certaines restrictions par une boucle sur les positions concernées. Les deux passent 79 729 chaînes de contrôle. La boucle supplémentaire est une hypothèse pour la régression sur le mélange UTF-8 chronométré ; elle n’est pas un défaut de correction.

Sources auditées : [ancienne](mesures/paired-utf8/utf8/old_selected/candidate.cpp) et [nouvelle](mesures/paired-utf8/utf8/new_selected/candidate.cpp).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).

## volume

| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| CPU_ISPC_VOLUME_1C | 896 | 1 | 3898.5 | 1224.4 | 3.184 | 3.1761–3.1873 | Nouveau plus rapide dans chaque bloc |
| CPU_ISPC_VOLUME_4C | 896 | 4 | 990.33 | 307 | 3.2258 | 3.2241–3.23 | Nouveau plus rapide dans chaque bloc |
| CPU_ISPC_VOLUME_40C | 896 | 40 | 101.66 | 45.09 | 2.2545 | 1.9469–3.4578 | Nouveau plus rapide dans chaque bloc |

Passage de 1 à plusieurs threads, sur les mêmes entrées et dans la même allocation :

| Entrée n | Threads | Ancien : temps 1 thread / temps parallèle | Actif : temps 1 thread / temps parallèle |
|---|---:|---:|---:|
| 896 | 4 | 3.9366 | 3.9882 |
| 896 | 40 | 38.35 | 27.154 |

Ces rapports décrivent la mise à l’échelle de chaque programme. Ils ne sont pas les speedups contre le naïf. Une augmentation du nombre de threads ne garantit pas un gain proportionnel ; ordonnancement, synchronisation, mémoire et partage du nœud peuvent intervenir. Cette campagne ne comporte pas le profilage nécessaire pour attribuer une mauvaise mise à l’échelle à une cause précise.

Couverture des analystes pendant la recherche : 3 / 3 arbres de recherche ont eu au moins un appel. Arbres sans appel : aucun. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.

| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 6 / 6 | 5 | 942.29 | 1270.2 | 1.8683 | 85.6 | 757.39 |
| T2 | 5 / 5 | 3 | 4713.5 | 838.85 | 1.5473 | 112.94 | 1167.8 |
| T3 | 4 / 4 | 1 | 1393.7 | 1253.1 | 1.2006 | 82.89 | 807.53 |
| Gm1 | 1 / 1 | 0 | 235.23 | 173.91 | 0.3164 | 12.177 | 67.179 |

Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.

- **T1** : Parallélisation OpenMP du rendu par pixel
- **T2** : Arithmétique et organisation des accès du sampler Density
- **T3** : Surcoût de traversée et de contrôle des rayons
- **Gm1** : Intégration mesurée des pistes parallélisme, Density et traversée

Mother a lancé 3 arbres initiaux, puis créé 1 arbres ou combinaisons. 17 essais sur 17 sont corrects. 16 appels d’analyse/pilotage ont produit 7 actions appliquées ; 3 essais portent la provenance d’un avis et 1 celle d’un import explicite.

La durée réelle passe de 6356.3 à 5133.7 secondes, avec un budget nominal conservé de 7200 secondes. L’ancienne recherche comptait 19 essais corrects sur 19. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.

Un exemple concret de réutilisation d’une idée issue d’un programme plus lent apparaît ici. Le candidat T2 `6ee6084606d44971`, correct et mesuré à 5,54319 s, proposait de réduire les clamps dans Density. Mother l’a combiné avec Gm1 `91429a7d2ad74de9`, mesuré à 0,23523 s. Le programme G `8fdbf80fa1554618` a obtenu 0,22568 s en recherche, puis 0,22597 s lors de sa confirmation indépendante. Le diff entre les commits `ced00c4` et `ab87e45` ne change que le chargement des voisins dans Density et supprime son ancien helper D. Les identifiants et mesures sont dans ESSAIS.csv. Cette filiation atteste la réutilisation de l’idée ; elle n’isole pas l’effet causal d’un avis d’analyste ni celui de toute l’architecture.

Coût connu de cette tentative : 39 invocations natives, 2,157,816 tokens vérifiables, 0 invocations à consommation inconnue. L’analyse et le pilotage représentent 881,026 tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.

Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.

Actions appliquées : close : 1, continue : 2, integrate : 1, suspend : 3.

| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |
|---|---|---:|---:|---:|
| Gm1 | Oui | 235.23 | 4.0058 | 4.0058 |

Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.

Lecture des sources : Les deux versions préparent les facteurs de passage vers les coordonnées de voxels avant le rendu et utilisent un ordonnancement dynamique OpenMP. L’ancien distingue un chemin intérieur sans clamp et un chemin de bord, et distribue les pixels par blocs de 64. Le nouveau utilise trois clamps puis dérive les indices voisins, passe à des blocs de 256 et évite le calcul d’éclairage et de transmittance lorsque la densité locale est nulle. Le gain éventuel ne vient donc pas du seul ajout de parallélisme, déjà présent avant. Le protocole conserve le volume et les transformations de caméra déclarés ; l’audit séparé vérifie aussi les dimensions d’image prises en charge par la référence ISPC.

Sources auditées : [ancienne](mesures/paired-volume/volume/old_selected/candidate.cpp) et [nouvelle](mesures/paired-volume/volume/new_selected/candidate.cpp).

Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).
