# Six familles supplémentaires — comparaison Forest avec et sans TabPFN

**Le lot est terminé : 11 livraisons sur 12, toutes correctes sur les contrôles réservés.** La condition avec conseiller ne montre pas d'avantage sur ce lot diversifié. Elle livre des programmes nettement moins rapides sur Base64, GEMM CPU et Black–Scholes. Argmin est aussi moins rapide sur les nouvelles tailles ; Stencil est trop bruité pour départager les stratégies. Popcount avec conseiller échoue au plan initial de Mother, avant tout appel TabPFN.

Ces observations ne permettent pas d'attribuer chaque différence au seul classement TabPFN : il n'y a qu'une recherche par condition et famille, et les plans de Mother peuvent différer avant l'intervention du conseiller. Elles montrent en revanche pourquoi les bons résultats UTF-8/Mandelbrot ne suffisaient pas à conclure.

## Comparaison finale sur ROMEO

Même code livré pour les colonnes « recherche » et « réservées », sans nouvelle sélection ni retour vers les agents. Les entrées de recherche ci-dessous sont remesurées avec la graine de confirmation distincte. Speedup = temps du naïf / temps du code livré ; plus grand est meilleur.

| Problème | Recherche : sans | Recherche : avec | Réservées : sans | Réservées : avec |
| --- | ---: | ---: | ---: | ---: |
| Base64 | 9,054× | 5,659× | 9,032× | 5,695× |
| Argmin | 6,621× | 6,461× | 7,471× | 6,489× |
| Popcount récurrent | 12,935× | Échec de Mother | 13,315× | Aucune livraison |
| GEMM **CPU** | 83,824× | 45,804× | 92,674× | 29,593× |
| Stencil 3D | 5,196× | 5,994× | 5,645× | 5,541× |
| Black–Scholes | 10,805× | 3,360× | 11,967× | 3,478× |

Sur les entrées réservées, le rapport des speedups avec/sans vaut 0,631 pour Base64, 0,869 pour Argmin, 0,319 pour GEMM, 0,981 pour Stencil et 0,291 pour Black–Scholes. Ce sont des rapports entre les livraisons observées, pas des probabilités de succès du conseiller. L'échec Popcount n'est ni retiré du taux de livraison ni transformé en speedup zéro.

[CSV de synthèse complet](results/comparison-summary.csv) · [remesure des entrées de recherche](results/registered/common-comparison.csv) · [entrées réservées](results/reserved/common-comparison.csv) · [mêmes commits et transferts](results/generalization-comparison.csv).

### Dispersion des temps

Les cinq rondes sont toutes conservées. La dispersion reste faible pour Base64, Argmin et Popcount, mais atteint, au pire régime, un coefficient de variation de 23,2 % pour Black–Scholes sur les tailles de recherche, de 18,4 % pour GEMM sur les tailles réservées, et **42,9 % pour Stencil sur les tailles réservées**. Le coefficient est l'écart-type des cinq rondes divisé par leur moyenne, calculé séparément par code, taille et nombre de threads.

Le petit avantage apparent de Stencil sur la distribution de recherche ne se maintient pas sur les tailles réservées, et ce bruit interdit d'en tirer un classement fiable. Les grands écarts de Base64, GEMM et Black–Scholes sont observés sur les deux ensembles ; leur amplitude précise reste propre à cette exécution. Aucune conclusion statistique sur la variabilité des recherches LLM n'est calculée à partir des cinq rondes de chronométrage.

[Dispersion par régime](results/timing-dispersion.csv) · [échantillons recherche](results/registered/common-raw-samples.csv) · [échantillons réservés](results/reserved/common-raw-samples.csv).

## Protocole et prévention des biais

Le choix des six familles, entrées, graines, ordres et plafonds a été enregistré avant leur recherche. Les familles existaient dans la suite de référence du dépôt ; elles sont supplémentaires pour l'évaluation TabPFN, pas présentées comme totalement inconnues de Forest ou des modèles préentraînés.

| Famille | Tailles de recherche | Tailles réservées | Threads chronométrés | Graine de recherche | Ordre |
| --- | --- | --- | --- | ---: | --- |
| Base64 | 16 384 ; 262 144 | 32 768 ; 524 288 | 1 | 137 | sans → avec |
| Argmin | 4 093 ; 65 536 | 8 191 ; 131 072 | 1 | 149 | avec → sans |
| Popcount | 257 ; 2 048 | 509 ; 4 096 | 1 | 163 | sans → avec |
| GEMM CPU | 384 ; 768 | 513 ; 1 025 | 1 et 4 | 179 | avec → sans |
| Stencil 3D | 96 ; 160 | 121 ; 192 | 1 et 4 | 191 | sans → avec |
| Black–Scholes | 32 768 ; 262 144 | 65 537 ; 524 288 | 1 et 4 | 211 | avec → sans |

Les graines de données de recherche et de confirmation sont 1103 et 3209 ; les entrées réservées utilisent 7867. Le chronométrage emploie la graine de sa phase +101. Les tailles et graines chronométrées réservées sont disjointes ; quelques petits contrôles de correction restent communs. Les générateurs et leurs familles de distribution restent les mêmes : ce lot ne teste pas tous les changements possibles de distribution. L'Argmin chronométré est décroissant, donc la nouvelle taille, et non sa graine, change effectivement cet échantillon.

Un seul Forest ; **GPT-6 Luna, effort max, pour tous les rôles LLM**, aucun mélange de modèles. Même moteur de 90 fichiers Python, validé par 1 095 tests réussis et 2 ignorés ; aucune retouche de ce moteur, de ses prompts ou des programmes livrés à partir des résultats en cours.

Chaque condition démarre au naïf avec conversations, base, mémoire documentaire et exemples du conseiller neufs. Les configurations d'une paire ne diffèrent que par l'activation TabPFN et les identifiants de sessions isolées. Aucune trajectoire d'une autre campagne n'est importée. Les audits le vérifient dans les preuves conservées.

Chaque condition dispose de **5 400 s de recherche et 7 200 s de bout en bout**, attente de Luna, analystes, conseiller, compilation, mesures et confirmation comprises. Les plafonds sont égaux ; le nombre d'arbres, d'essais, de tokens et la durée consommée restent des résultats de la recherche autonome. TabPFN reçoit au moins 8 et au plus 128 observations, avec au plus 20 s par appel et 5 % du budget cible ; une opportunité sur quatre conserve l'exploration native.

Tout s'exécute sur ROMEO : recherches, appels directs à Luna, TabPFN et programmes. Pas de relais PC. AMD EPYC 9654, GCC 14.2, aucun GPU dans ce lot CPU. Les paires emploient des ensembles de CPU disjoints sur le même nœud partagé. La remesure commune **784761** intervient après la fin des dix jobs de recherche, puis après la remesure UTF-8/Mandelbrot. Aucun de nos jobs de recherche ne lui fait concurrence ; le nœud n'est pas déclaré exclusif.

Le job 784761 évalue successivement les distributions enregistrée et réservée, avec le même ensemble autorisé de CPU et les mêmes codes. Il conserve **520 lignes détaillées de chronométrage**. Les empreintes d'entrées et affinités déclarées concordent entre candidats ; l'affinité déclarée du thread principal ne prétend pas tracer chaque worker OpenMP. À chaque ronde, le protocole combine géométriquement les temps par taille/thread, puis moyenne les cinq rondes. Les détails par régime restent exportés.

## Durées, exploration et arrêts

Chaque cellule « sans / avec » respecte cet ordre. Les essais sont ceux de recherche ; les intégrations et confirmations sont comptées séparément dans les journaux.

| Famille | Durée totale (min), sans / avec | Essais, sans / avec | Arbres initiaux → finaux, sans / avec | Profondeur max., sans / avec | Arrêt, sans / avec |
| --- | ---: | ---: | --- | ---: | --- |
| Base64 | 85,0 / 86,3 | 16 / 27 | 2→2 / 2→3 | 2 / 2 | réserve / réserve |
| Argmin | 39,1 / 85,5 | 21 / 36 | 2→2 / 2→4 | 3 / 3 | revue / réserve |
| Popcount | 84,2 / 1,2 | 84 / 0 | 3→3 / aucun | 4 / — | réserve / plan invalide |
| GEMM CPU | 84,4 / 84,1 | 54 / 51 | 3→4 / 3→3 | 2 / 3 | réserve / réserve |
| Stencil 3D | 49,8 / 32,3 | 22 / 17 | 3→3 / 3→3 | 3 / 3 | revue / revue |
| Black–Scholes | 65,8 / 84,9 | 33 / 62 | 2→5 / 3→6 | 3 / 3 | revue / réserve |

« Réserve » désigne la réserve finale ou l'échéance ; « revue » une clôture explicitement examinée. Cette dernière peut survenir avant 90 minutes et ne certifie pas que l'optimum a été atteint.

**423 essais de recherche**, 204 analyses de code complètes et 9 jobs d'analyse indisponibles. Les 330 reçus natifs de pilotage sont vérifiés sans rupture de chaîne. Cinq réouvertures ont eu lieu : deux Base64 avec, une Argmin avec, une GEMM avec et une GEMM sans. Argmin avec exerce une continuation après limite de sortie ; Black–Scholes avec un événement natif d'attente vide. Deux jobs de pilotage restent indisponibles après leurs tentatives bornées, sans empêcher la livraison.

Les courbes à 10/30/60/90 minutes montrent notamment que Base64 sans progresse encore après 60 minutes, tandis que la condition avec plafonne dans cette trajectoire. Black–Scholes avec produit davantage d'essais que sans, mais un code final plus lent. Plus de temps et de données ne suffisent donc pas à expliquer ou à résoudre tous les écarts.

[Essais et consommation](results/arms.csv) · [courbes observées](results/learning-curves.csv) · [audit Mother](results/control-recovery.csv) · [réouvertures](results/idle-recovery-effects.csv).

## Deux faiblesses qui restent visibles

**Plan initial de Mother, Popcount avec.** La réponse contient deux pistes mais le champ G est vide. Le contrat la refuse avec « The mother must provide nonempty research guidance ». Il n'y a qu'un appel initial, aucune génération de recherche et aucun appel TabPFN. La reprise de Mother pendant la recherche ne répare pas cette première réponse de préparation. L'échec est conservé ; aucune relance de remplacement ne lui attribue artificiellement un résultat.

**Clôture avec analyste indisponible, Stencil avec.** La clôture est confirmée après 32,3 minutes, avec quatre hypothèses examinées et T3 encore déclaré indisponible. Ses tentatives d'analyse ont échoué sur des exigences de mécanisme/citations de code. Les règles de clôture autorisent ici la fin, mais l'absence de cette analyse réduit la solidité du bilan. Une clôture « valide » au sens du contrôleur n'est pas forcément la meilleure décision d'exploration.

[Qualité des analystes](results/analyst-quality.csv) · [revues et motifs de clôture](results/closure-quality.csv). Les plans initiaux, dont celui de Popcount, figurent dans les preuves sélectionnées.

## TabPFN a-t-il réellement servi ?

| Famille | Appels | Avis acceptés | Parents changés | Exemples à la fin | Temps du conseiller |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base64 | 14 | 6 | 5 | 27 | 87,7 s |
| Argmin | 17 | 13 | 11 | 36 | 110,5 s |
| Popcount | 0 | 0 | 0 | 0 | 0 s |
| GEMM CPU | 28 | 24 | 16 | 51 | 195,5 s |
| Stencil 3D | 5 | 3 | 2 | 17 | 28,3 s |
| Black–Scholes | 34 | 22 | 10 | 62 | 236,4 s |
| Total | 98 | 68 | 44 | — | 658,4 s |

Le rôle est donc bien exercé sur cinq familles. Les 44 changements de parent ne sont pas 44 améliorations prouvées. Les poids de TabPFN restent fixes ; le contexte de transitions mesurées se remplit pendant la campagne, puis est remis à zéro à la suivante. Les caractéristiques lexicales/statiques et un petit nombre d'observations ne suffisent pas nécessairement à prédire les bonnes transformations de code.

Sur Black–Scholes, la décomposition initiale diffère avant le premier conseil : une piste SIMD exclut initialement CND dans la condition avec, alors que le plan sans couvre le noyau complet. Les livraisons finissent avec des voies mathématiques différentes. Cela empêche d'attribuer tout l'écart au conseiller seul.

L'[interprétation détaillée](INTERPRETATION.md) relie les différences des sources livrées aux mesures, précise le domaine Base64 valide et la portée matérielle des variantes GEMM. Ce sont des observations après recherche, sans conseils renvoyés au système et sans ablation prétendant isoler chaque mécanisme.

## Intervention de préparation et preuves

Le premier prétest GEMM a échoué avant toute optimisation : l'adaptateur naïf historique ne calcule que pour n=32,128,1024. L'[amendement](protocol-amendment-gemm.json) ajoute la même boucle naïve r,c,k pour les autres tailles, sans modifier l'oracle, les tolérances, le moteur, l'ordre ou les budgets. L'ancien prétest 784719 et ses fichiers restent conservés ; ce n'est pas une recherche supplémentaire remplacée après examen d'un speedup. Le naïf élargi n'est pas directement comparable à un speedup historique publié.

Les jobs de paire sont 784716, 784717, 784718, 784722, 784720 et 784721. Les archives brutes ont été rapatriées avec vérification SHA-256. Les preuves publiables contiennent les codes confirmés, configurations, plans initiaux, contrôles, avis et mesures ; les identifiants, poids, transcriptions natives et bases brutes restent hors publication.

[Protocole figé](protocol.json) · [entrées réservées figées](heldout-protocol.json) · [audit des sources réservées](results/reserved-source-audit.json) · [guide des CSV](results/README.md) · [preuves sélectionnées](../../evidence/diversified-advisor-20261026/campaigns/) · [archives GitHub](https://github.com/Gotman08/hpc-forest-r1/releases/tag/archives-forest-20261026).

## Ce que l'on peut conclure

La diversification change l'appréciation : les résultats favorables du conseiller sur les deux cas de régression ne se reproduisent pas sur ces six familles. Ce lot ne justifie pas une activation automatique de TabPFN. Il ne démontre pas non plus qu'aucun conseiller ne peut aider Forest.

Les prochaines évaluations doivent conserver des familles et entrées réservées, plusieurs graines indépendantes et les échecs dans le bilan. Pour isoler le choix de parent, une étude distincte pourrait fixer un plan initial commun aux deux conditions. Réparer le plan initial incomplet et mieux traiter une clôture avec analyse indisponible relève de la robustesse de Forest ; toute modification demandera une nouvelle version et ne sera pas mélangée aux données présentes.

Les [huit essais de régression](../control-recovery-20261026/RAPPORT.md) restent un bilan séparé : huit livraisons sur huit après correction du contrôle, mais le meilleur ancien Mandelbrot reste plus rapide.
