# Reprises Forest : comparaison sur ROMEO

Rapport produit le 2026-10-24T00:20:10+00:00.

Les 14 programmes peu explorés ont été relancés avec une mémoire neuve et une cible de deux heures, contre trente minutes auparavant. 14/14 pipelines ont terminé et 14/14 intégrations G ont été confirmées. Le comparatif porte sur 35 lignes du tableau documentaire : **21 favorisent le nouveau code dans chaque bloc de mesure, 10 favorisent l’ancien, 4 présentent des écarts qui changent de sens selon le bloc, et 0 correspondent à un code ou binaire identique**.

Ces 35 lignes ne sont pas 35 expériences indépendantes : certaines partagent le même programme et le même gagnant. Les étendues observées ne sont pas des intervalles de confiance. Une première tentative de 14 campagnes a été interrompue après environ 44 minutes pour corriger la capacité du contexte. Base64 a ensuite nécessité une relance supplémentaire après correction du classement des réponses tronquées. La comparaison finale retient une campagne par programme, toutes avec un contexte de 64 000 caractères ; les variations entre recherches restent possibles.

## Les speedups côte à côte

Chaque speedup ROMEO est le temps du naïf divisé par celui de la variante. « Ancien historique » vient de la première étude ; « ancien remesuré » et « nouveau » proviennent de la nouvelle allocation commune. Le ratio nouveau/ancien est le temps de l’ancien divisé par celui du nouveau : au-dessus de 1, le nouveau code est plus rapide. Les références publiées conservent leur matériel et leur protocole propres.

| Programme / entrée | Publié | Réf. ROMEO actuelle | Forest ancien historique | Forest ancien remesuré | Forest nouveau | Nouveau / ancien | Étendue par blocs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AOBench — ISPC 1 cœur(s) | 6,19× | 7,26× | 1,07× | 1,07× | 1,57× | 1,4679× | 1,4663× – 1,4698× |
| AOBench — ISPC 4 cœur(s) | 28,06× | 14,25× | 1,07× | 1,07× | 6,24× | 5,8525× | 5,8456× – 5,8667× |
| Black–Scholes options — ISPC 1 cœur(s) | 8,45× | 9,71× | 1,00× | 1,00× | 1,05× | 1,0470× | 1,0264× – 1,0498× |
| Black–Scholes options — ISPC 4 cœur(s) | 32,48× | 33,33× | 3,90× | 3,98× | 4,18× | 1,0490× | 1,0082× – 1,0519× |
| Deferred shading — ISPC 1 cœur(s) | 5,02× | 7,20× | 1,00× | 1,00× | 1,00× | 0,9996× | 0,9974× – 1,0007× |
| Deferred shading — ISPC 4 cœur(s) | 23,06× | 26,68× | 3,45× | 3,45× | 3,34× | 0,9674× | 0,9667× – 0,9737× |
| Mandelbrot — ISPC 1 cœur(s) | 6,21× | 9,26× | 1,00× | 1,00× | 11,47× | 11,4805× | 11,3786× – 11,5132× |
| Mandelbrot — ISPC 4 cœur(s) | 20,28× | 36,90× | 3,99× | 3,99× | 45,53× | 11,4208× | 11,4097× – 11,4366× |
| Ray tracer — ISPC 1 cœur(s) | 4,31× | 6,07× | 1,03× | 1,03× | 1,00× | 0,9737× | 0,9731× – 0,9738× |
| Ray tracer — ISPC 4 cœur(s) | 20,29× | 23,06× | 3,96× | 3,96× | 3,84× | 0,9692× | 0,9673× – 0,9704× |
| 3D stencil — ISPC 1 cœur(s) | 4,05× | 4,81× | 5,85× | 5,85× | 5,42× | 0,9266× | 0,8771× – 0,9748× |
| 3D stencil — ISPC 4 cœur(s) | 15,53× | 12,77× | 13,39× | 12,58× | 12,58× | 1,0000× | 0,9908× – 1,0071× |
| Volume rendering — ISPC 1 cœur(s) | 3,60× | 2,87× | 1,14× | 1,14× | 1,35× | 1,1827× | 1,1812× – 1,1829× |
| Volume rendering — ISPC 4 cœur(s) | 17,53× | 11,47× | 3,54× | 3,54× | 5,31× | 1,4983× | 1,4980× – 1,4994× |
| AOBench — ISPC 40 cœurs | 182,36× | 121,70× | 1,07× | 1,07× | 40,23× | 37,7093× | 34,1544× – 38,0900× |
| Black–Scholes options — ISPC 40 cœurs | 83,97× | 31,87× | 3,55× | 3,28× | 1,86× | 0,5658× | 0,0963× – 1,7388× |
| Ray tracer — ISPC 40 cœurs | 195,67× | 40,95× | 13,38× | 12,71× | 12,31× | 0,9684× | 0,7867× – 1,1245× |
| Volume rendering — ISPC 40 cœurs | 243,18× | 100,82× | 32,92× | 26,57× | 44,43× | 1,6725× | 1,3839× – 1,9664× |
| Base64 lena — baseline scalar_base64_decode | 9,86× | 9,53× | 1,00× | 1,00× | 9,19× | 9,1849× | 9,1458× – 9,2082× |
| Base64 lena — baseline chromium_base64_decode | 8,76× | 6,94× | 0,73× | 0,73× | 6,69× | 9,1849× | 9,1458× – 9,2082× |
| Validation UTF-8 aléatoire — minimum | 24,48× | 4,87× | 2,16× | 2,17× | 3,41× | 1,5717× | 1,5707× – 1,5795× |
| Validation UTF-8 aléatoire — moyenne | 22,69× | 4,87× | 2,17× | 2,17× | 3,42× | 1,5743× | 1,5707× – 1,5795× |
| Boehm GEMM — DEFAULT_FINAL | 280,06× | 25,40× | 475,24× | 496,99× | 1350,00× | 2,7164× | 2,7061× – 2,7217× |
| Boehm GEMM — O3_FINAL | 101,31× | 40,45× | 744,15× | 791,57× | 2150,20× | 2,7164× | 2,7061× – 2,7217× |
| Boehm GEMM — O3_REORDER | 18,21× | 77,19× | 744,15× | 791,57× | 2150,20× | 2,7164× | 2,7061× – 2,7217× |
| Boehm GEMM — O3_TILING | 23,16× | 76,07× | 744,15× | 791,57× | 2150,20× | 2,7164× | 2,7061× – 2,7217× |
| Réduction : suppression des branchements divergents | 2,33× | 1,41× | 6,58× | 6,70× | 1,71× | 0,2550× | 0,2495× – 0,2651× |
| Réduction : adressage séquentiel | 4,68× | 1,52× | 6,58× | 6,70× | 1,71× | 0,2550× | 0,2495× – 0,2651× |
| Réduction : premier ajout pendant le chargement global | 8,34× | 2,46× | 6,58× | 6,70× | 1,71× | 0,2550× | 0,2495× – 0,2651× |
| Réduction : déroulage du dernier warp | 15,01× | 2,54× | 6,58× | 6,70× | 1,71× | 0,2550× | 0,2495× – 0,2651× |
| Réduction : déroulage complet | 21,16× | 2,53× | 6,58× | 6,70× | 1,71× | 0,2550× | 0,2495× – 0,2651× |
| Réduction naïve → plusieurs éléments par thread | 30,04× | 3,26× | 6,58× | 6,70× | 1,71× | 0,2550× | 0,2495× – 0,2651× |
| Softmax naïf PyTorch → Triton fusionné | 4,15× | 4,77× | 5,07× | 5,06× | 5,12× | 1,0115× | 1,0008× – 1,0212× |
| sum(abs(x)) : deux kernels → un kernel fusionné | 3,00× | 2,75× | 4,19× | 4,19× | 4,35× | 1,0393× | 1,0378× – 1,0418× |
| S4ConvD : somme des temps des kernels de convolution | 3,26× | 6,26× | 2,31× | 2,31× | 7,62× | 3,2997× | 3,2464× – 3,3410× |

Le gagnant affiché est celui confirmé par le moteur avant cette comparaison. Les résultats de G sont conservés séparément dans le classeur, le CSV et les preuves ; aucun gagnant n’est choisi après lecture des mesures finales.

Si les sources ou les binaires des deux gagnants ont la même empreinte SHA-256, leurs écarts de mesure ne sont pas comptés comme une amélioration ou une régression algorithmique. Les empreintes et ce constat figurent dans le CSV et le JSON.

## Contrôle complémentaire de Black–Scholes

La forte variabilité observée à 40 cœurs a motivé une répétition supplémentaire sur 21 blocs, dans une autre allocation ROMEO, avec les mêmes sources et pilotes protégés. Le tableau principal conserve ses sept blocs initiaux. Cette vérification décidée après observation ne constitue pas une répétition préenregistrée de toute l’étude.

| Cœurs | Nouveau / ancien : 7 blocs initiaux | Nouveau / ancien : 21 blocs supplémentaires | Étendue supplémentaire | Blocs supplémentaires favorables au nouveau |
| --- | --- | --- | --- | --- |
| 1 | 1,0470× | 1,0270× | 1,0226× – 1,0780× | 21 / 21 |
| 4 | 1,0490× | 1,0484× | 0,9012× – 1,0571× | 20 / 21 |
| 40 | 0,5658× | 0,1149× | 0,0925× – 11,0560× | 7 / 21 |

À 40 cœurs, les médianes et les rapports varient fortement entre allocations et entre blocs : le résultat ne permet pas une conclusion robuste sur un gain ou une régression reproductible. Les contrôles de correction passent. Les affinités ont changé (20–59, puis 0–39) ; les données ne permettent pas d’attribuer la variabilité à ce seul changement, à la charge du nœud ou à un autre effet. Aucun candidat n’est modifié à la suite de ce contrôle.

## Changements dans les programmes retenus

Cette lecture des sources décrit les différences entre les deux gagnants. Elle ne démontre pas quelle transformation a causé le gain : les variantes combinent parfois plusieurs changements, et les hypothèses de chaque essai sont conservées dans l’historique.

| Programme | Différences observées | Contrat et contrôles |
| --- | --- | --- |
| aobench | Parallélisation des lignes avec OpenMP, générateur PCG32 par thread et arrêt du test d'occlusion dès le premier objet touché. | Les dimensions, les boucles de sous-échantillonnage primaire et le nombre de rayons ambiants (NAO_SAMPLES au carré) sont conservés. La séquence aléatoire change ; les tolérances statistiques du protocole restent nécessaires. |
| base64 | Remplacement du décodage scalaire par un préfixe AVX2 de 32 caractères vers 24 octets, puis un traitement scalaire de la fin et du padding. Écritures bornées à 24 octets par bloc. | Le benchmark et ses contrôles utilisent des entrées Base64 valides, dont l'image documentaire et des données encodées aléatoires. Le préfixe AVX2 ne valide pas tous les caractères : ce résultat ne démontre pas un décodeur strict correct sur des entrées malformées. Les octets décodés, la longueur, les entrées et les gardes restent contrôlés sur le domaine testé. |
| blackscholes | Réassociation du polynôme CND, directive SIMD sur le parcours séquentiel et plafonnement du nombre de threads selon la taille, avec répartition statique simple. | Tous les contrats d'option sont recalculés. Les fonctions log, racine et exponentielle restent utilisées ; les arrondis du polynôme sont contrôlés par les mêmes tolérances. |
| deferred | Ordonnancement statique cyclique des tuiles racines ; construction de l'arbre de profondeur séquentielle, alors que le précédent gagnant parallélisait aussi cette étape. | L'arbre de profondeur est mis à jour à chaque appel et les couleurs des lumières sont relues. Les contrôles avec couleurs modifiées sont conservés ; aucune réutilisation de l'image finale n'a été introduite. |
| gemm_cpu | Passage d'un noyau AVX2 4×16 à un noyau AVX-512 8×32 et répartition OpenMP des tuiles dans les deux dimensions. | Les bordures sont calculées par une boucle scalaire, sans réduire la dimension de la multiplication. Ce candidat cible les instructions AVX-512 disponibles sur le CPU ROMEO testé ; sa portabilité vers un CPU sans AVX-512 n'est pas revendiquée. |
| mandelbrot | Évolution simultanée de blocs de 128 pixels avec masque d'activité et directives SIMD ; distribution dynamique des lignes plutôt que des tuiles 32×8. | Les dimensions, coordonnées, seuil d'échappement et maximum d'itérations restent identiques. Les pixels déjà échappés ne sont plus mis à jour, et leurs nombres d'itérations restent vérifiés. |
| raytracer | Ordonnancement OpenMP par bandes de deux lignes, pile BVH d'indices plutôt que de pointeurs et retour à un test scalaire des boîtes plus simple. | Les dimensions, la géométrie et les tests de triangles sont conservés. Les distances et identifiants des intersections restent contrôlés. |
| reduction | Réduction entière par warp de 32 threads sur 128 valeurs, chargements int2 lorsque l'alignement le permet et écriture du dernier bloc directement dans la sortie. Pour 4 194 304 valeurs, les tuiles de 128 imposent quatre lancements successifs (32 768, 256, 2 puis 1 blocs), contre deux lancements avec les anciennes tuiles de 4 096 valeurs. Cette différence est une explication plausible de la régression, sans essai isolant sa causalité. | Le parcours couvre tous les éléments et les restes de tuiles. Les résultats entiers sont vérifiés par le protocole figé. |
| s4convd | Boucles déroulées par quatre pour la passe avant et le gradient d'entrée ; gradient du noyau calculé par tuiles de 16 384 positions et groupes de 16 coefficients, puis finalisé dans un second noyau. | Les trois sorties (avant, gradient d'entrée et gradient du noyau) sont calculées. Le réordonnancement des additions est soumis aux mêmes tolérances numériques. |
| softmax | Passage des groupes de lignes à une réduction en ligne par ligne, avec blocs bornés à 4 096 colonnes, deux warps et deux passes sur l'entrée. | Le maximum et la somme sont stabilisés numériquement ; les strides sont pris en compte. Le domaine testé conserve des dimensions positives, sans conclure sur toutes les formes de tenseurs possibles. |
| stencil3d | Remplacement du seul SIMD automatique par des opérations AVX explicites déroulées sur 32 valeurs, puis des fins AVX, SSE et scalaires ; chemin séquentiel sans région parallèle. | Les six pas de temps, les coefficients, le domaine intérieur et les tampons alternés sont conservés. Une barrière de la boucle OpenMP synchronise chaque pas. |
| sumabs | Chargements float4, huit accumulateurs, 512 threads par bloc et jusqu'à 8 192 blocs. La réduction par bloc utilise CUB, comme le précédent gagnant. | Le préfixe non aligné et la fin du tableau sont traités ; la sortie est remise à zéro à chaque appel avant les additions atomiques. Les tolérances de somme flottante restent inchangées. |
| utf8 | Deux blocs SSE2 de 16 octets par tour, propagation des octets de continuation et restrictions vectorielles. Le raccourci ASCII de l'ancien gagnant disparaît. | Les séquences tronquées, surlongues, substituts Unicode et limites U+10FFFF sont contrôlés. Le contrôle indépendant de 79 729 chaînes passe pour les deux gagnants et les deux G. La disparition du raccourci ASCII peut affecter différemment les catégories d'entrée ; les lignes documentaires mesurent ici du texte UTF-8 aléatoire. |
| volume | Pré-calcul des facteurs de conversion et des strides de la grille, accès direct aux huit voisins pour les voxels intérieurs, et répartition dynamique OpenMP par blocs de 64 pixels. | Les pas d'intégration, le seuil d'arrêt du rayon et les dimensions sont conservés. Les transformations de coordonnées peuvent changer les arrondis flottants ; les contrôles numériques et d'image sont conservés. |

Les diffs et leurs empreintes sont conservés dans `source-review/` dans les preuves. Aucun candidat n’a été corrigé manuellement après lecture des mesures finales.

## Ce qui a été corrigé

- Le validateur reconnaît les appels MCP de découverte autorisés (`list_mcp_resources` et `list_mcp_resource_templates`). Les arguments et les serveurs restent contrôlés ; cela ne donne aucun nouvel accès à un shell ou à des fichiers arbitraires.
- La source fournie à la planification peut atteindre 128 000 caractères au lieu de 32 000. Une régression vérifie la transmission exacte d’une source dépassant l’ancienne limite.
- La fenêtre de mémoire/contexte des essais passe de 12 000 à 64 000 caractères pour les 14 programmes. Le réglage précédent découpait les longues sources et perdait des pages entre appels éphémères, notamment pour Deferred. Un contrôle vérifie la transmission complète et exacte des 14 sources ; les appels natifs de Deferred confirment la présence du fichier complet.
- Les wrappers Linux des nouvelles campagnes utilisent LF. Les trois anciens cas GPU dont l’empaquetage manquait de Makefile/run.sh disposent de wrappers vérifiés dans le précontrôle séparé.
- Les sept anciennes erreurs causées uniquement par la découverte MCP ont été rejouées avec le parseur corrigé. Leur statut historique reste inchangé.

- Base64 : un échec natif `max_output_tokens` est désormais un échec de génération, avec rejet du code incomplet. Il n’arrête plus tous les arbres comme une panne d’infrastructure. Les vraies pannes et appels interdits restent bloquants. Le journal réel a été rejoué hors ligne, et une nouvelle campagne vide utilise le correctif ; l’ancienne tentative conserve ses statuts historiques.

Validation locale du moteur : **838 passed in 1066.59s (0:17:46)**, Ruff et la vérification du patch passent. Le premier profil avait déjà passé 829 tests ; neuf régressions supplémentaires vérifient le traitement de la limite de sortie. Sur ROMEO, les 68 étapes de précontrôle (construction, livraison, construction protégée et validation pour 17 programmes) ont réussi après correction de deux défauts du script de précontrôle : variable du rendu et chemin de bibliothèque CUDA. Les sources algorithmiques initiales et les contrôles protégés sont inchangés.

Deux empreintes de moteur sont présentes dans les campagnes finales : les 13 campagnes non touchées par cet incident conservent leur version figée ; la nouvelle campagne Base64 ajoute uniquement le correctif de classement des réponses tronquées. Les versions et empreintes exactes figurent dans l’audit.

## Exploration avant / après

Sur les 14 programmes retenus, les essais enregistrés passent de 73 à 819, intégrations G comprises. Le nombre d’arbres n’ayant qu’un essai passe de 30 à 0. Ces totaux ne comptent pas les simples lectures de mémoire comme des essais de code.

| Programme | Job nouveau | Arbres ancien → nouveau | Essais ancien → nouveau | Essais nouveaux par arbre | G | Profondeur max | Statuts de tous les essais | Durée SLURM (min) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| aobench | 781307 | 3 → 3 | 4 → 13 | T1: 5; T2: 4; T3: 3 | 1 | 3 | valid: 13 | 97,2 |
| base64 | 781452 | 2 → 2 | 3 → 61 | T1: 23; T2: 36 | 2 | 3 | valid: 60; incorrect: 1 | 119,2 |
| blackscholes | 781329 | 2 → 3 | 7 → 79 | T1: 32; T2: 25; T3: 21 | 1 | 3 | valid: 77; incorrect: 1; duplicate: 1 | 115,8 |
| deferred | 781306 | 3 → 4 | 6 → 80 | T1: 23; T2: 19; T3: 13; T4: 24 | 1 | 4 | valid: 73; build_failed: 6; generation_failed: 1 | 117,9 |
| gemm_cpu | 781327 | 3 → 3 | 6 → 85 | T1: 31; T2: 30; T3: 23 | 1 | 3 | valid: 85 | 113,8 |
| mandelbrot | 781328 | 3 → 2 | 5 → 59 | T1: 37; T2: 21 | 1 | 3 | valid: 58; incorrect: 1 | 114,7 |
| raytracer | 781308 | 3 → 3 | 11 → 74 | T1: 33; T2: 29; T3: 11 | 1 | 3 | valid: 69; incorrect: 5 | 116,2 |
| reduction | 781309 | 3 → 3 | 4 → 64 | T1: 21; T2: 22; T3: 20 | 1 | 4 | valid: 64 | 117,3 |
| s4convd | 781310 | 4 → 3 | 5 → 58 | T1: 18; T2: 20; T3: 19 | 1 | 3 | valid: 57; build_failed: 1 | 116,5 |
| softmax | 781311 | 2 → 2 | 3 → 51 | T1: 26; T2: 24 | 1 | 3 | valid: 51 | 114,0 |
| stencil3d | 781312 | 3 → 3 | 4 → 59 | T1: 23; T2: 22; T3: 13 | 1 | 3 | valid: 58; incorrect: 1 | 115,3 |
| sumabs | 781313 | 2 → 2 | 4 → 54 | T1: 26; T2: 27 | 1 | 3 | valid: 54 | 115,3 |
| utf8 | 781330 | 3 → 2 | 7 → 63 | T1: 25; T2: 37 | 1 | 4 | valid: 63 | 117,8 |
| volume | 781315 | 3 → 4 | 4 → 19 | T1: 6; T2: 4; T3: 4; T4: 4 | 1 | 3 | valid: 19 | 106,2 |

Les rôles T1, T2… sont propres à chaque nouvelle campagne ; un T1 ancien n’a pas nécessairement le même sujet qu’un T1 nouveau. Mother choisit le nombre d’arbres. Les sujets, objectifs, parentés, profondeurs et statuts sont conservés dans les preuves et dans l’audit.

Les compteurs de jetons et les durées par phase sont également conservés dans `AUDIT-FOREST.json`. Les phases pouvant se chevaucher, la somme de leurs durées ne représente pas le temps mural. Les compteurs de jetons du moteur ne constituent pas une facture du service de modèle.

La cible de deux heures inclut la réserve adaptative pour l’intégration et la confirmation. Elle ne signifie pas deux heures pleines consacrées à proposer des candidats. L’efficacité CPU moyenne de SLURM inclut aussi les attentes du modèle et, dans les comparaisons, les variantes séquentielles ; elle ne mesure pas directement le parallélisme du noyau gagnant. Les allocations de 40 cœurs restent nécessaires pour comparer les configurations à 1, 4 et 40 cœurs.

## Quand la recherche a progressé

Ce tableau observe chaque nouvelle campagne à trente minutes puis à la fin de sa recherche. Ce ne sont pas deux recherches indépendantes à budgets différents. Les speedups ci-dessous utilisent l’objectif interne du moteur, parfois agrégé sur plusieurs configurations ; ils ne remplacent pas les speedups documentaires remesurés plus haut. Le meilleur score observé peut aussi bénéficier du bruit de mesure. G est exclu de cette courbe et confirmé séparément.

| Programme | Essais terminés à 30 min | Essais de recherche totaux | Meilleur speedup recherche à 30 min | Meilleur speedup recherche final | Ratio final / 30 min | Dernier essai terminé (min) |
| --- | --- | --- | --- | --- | --- | --- |
| aobench | 4 | 12 | 8,41× | 8,41× | 1,000× | 68,2 |
| base64 | 8 | 59 | 5,19× | 5,62× | 1,082× | 110,0 |
| blackscholes | 22 | 78 | 5,31× | 5,34× | 1,005× | 107,6 |
| deferred | 22 | 79 | 1,87× | 1,91× | 1,026× | 113,3 |
| gemm_cpu | 21 | 84 | 1082,44× | 2172,12× | 2,007× | 103,3 |
| mandelbrot | 16 | 58 | 8,89× | 18,68× | 2,101× | 107,5 |
| raytracer | 20 | 73 | 5,15× | 5,17× | 1,003× | 106,2 |
| reduction | 17 | 63 | 1,60× | 1,62× | 1,012× | 106,3 |
| s4convd | 15 | 57 | 2,80× | 5,80× | 2,071× | 106,2 |
| softmax | 15 | 50 | 5,09× | 5,17× | 1,015× | 104,2 |
| stencil3d | 17 | 58 | 5,38× | 6,06× | 1,127× | 105,1 |
| sumabs | 15 | 53 | 4,33× | 4,37× | 1,008× | 105,9 |
| utf8 | 18 | 62 | 2,62× | 3,71× | 1,416× | 110,6 |
| volume | 5 | 18 | 5,57× | 5,57× | 1,000× | 80,3 |

Le détail de chaque nouveau record, avec son arbre, sa profondeur et sa minute d’observation, est conservé dans `PROGRESSION-RECHERCHE.json`. Une intégration G peut encore améliorer le résultat au-delà du meilleur essai de recherche.

## Mémoire, intervention et lieu des calculs

Chaque programme possède une nouvelle session, un nouveau dépôt de campagne, une nouvelle base SQLite et une nouvelle conversation Mother. Les 14 reçus de démarrage attestent zéro essai et zéro document avant l’exploration. L’audit vérifie l’absence de réutilisation des sessions et conversations précédentes, ainsi que l’absence de partage de contexte entre programmes. Les métadonnées initiales et la source naïve sont présentes : une base neuve ne signifie pas une base sans métadonnées.

La mémoire est ensuite conservée entre les essais d’un même programme : c’est le fonctionnement de Forest. Les appels de recherche sont éphémères ; Mother garde sa conversation pour planifier et intégrer. Les mémoires automatiques de Codex et le chargement des documents du projet sont désactivés. Les anciens candidats optimisés ne sont pas fournis au modèle.

Pour les comparaisons de performance, chaque variante démarre dans un nouveau processus et reconstruit ses entrées. Les contrôles vérifient les sorties, et les gardes et empreintes d’entrée lorsqu’elles sont prévues par le pilote. Les caches du système et du JIT restent gérés normalement : aucune purge globale ni réinitialisation physique du GPU n’est effectuée. Les échauffements précèdent les mesures. Une mémoire Forest neuve ne signifie donc pas une machine matériellement remise à froid.

L’intervention de l’opérateur concerne les correctifs du moteur, la capacité du contexte, les wrappers, le lancement, la surveillance des transferts et les analyses. Aucun conseil d’optimisation ni modification manuelle des candidats n’a été ajouté pendant ces recherches.

Le contrôleur, TreeQuest AB-MCTS, les compilations, les validations et les chronométrages s’exécutent sur ROMEO sous SLURM. Le relais Codex est local et l’inférence du modèle `gpt-6-luna`, effort `max`, est hébergée. Les mesures CPU utilisent EPYC 9654 ; les mesures GPU utilisent GH200. Dire que « tout est sur ROMEO » serait donc inexact pour l’inférence du modèle.

## Comparabilité et limites

| Allocation actuelle | Programmes | Job précédent → actuel | CPU observé | GPU observé | Même modèle CPU | Même sortie de version du compilateur |
| --- | --- | --- | --- | --- | --- | --- |
| paired-cpu | blackscholes, gemm_cpu, mandelbrot, stencil3d, utf8 | 781188 → 781608 | AMD EPYC 9654 96-Core Processor | — | oui | oui |
| paired-cpu-base64 | base64 | 781188 → 781692 | AMD EPYC 9654 96-Core Processor | — | oui | oui |
| paired-extra | reduction, s4convd, softmax, sumabs | 781189 → 781603 | Neoverse-V2 | NVIDIA GH200 120GB | oui | oui |
| paired-cpu-blackscholes-stability | blackscholes | 781188 → 781637 | AMD EPYC 9654 96-Core Processor | — | oui | oui |
| paired-render-aobench | aobench | 781213 → 781530 | AMD EPYC 9654 96-Core Processor | — | oui | oui |
| paired-render-deferred | deferred | 781207 → 781599 | AMD EPYC 9654 96-Core Processor | — | oui | oui |
| paired-render-raytracer | raytracer | 781200 → 781600 | AMD EPYC 9654 96-Core Processor | — | oui | oui |
| paired-render-volume | volume | 781208 → 781548 | AMD EPYC 9654 96-Core Processor | — | oui | oui |

Les instantanés matériels, affinités CPU, versions, UUID GPU et limites de puissance observées sont conservés dans `AUDIT-MATERIEL.json`. Ils sont relevés au démarrage des jobs : ils ne constituent pas un suivi continu des fréquences ou de la température pendant les mesures. Le nom commercial du GPU et sa mémoire visible sont conservés séparément. La version CUDA affichée par le pilote décrit sa compatibilité ; le compilateur réellement chargé est nvcc V12.6.85, issu du paquet CUDA 12.6.3.

- Ancien et nouveau candidats, naïf et référence sont exécutés dans la même allocation de comparaison, avec compilateurs et entrées identiques. Les sommes de contrôle des suites figées sont vérifiées avant exécution.
- Les cinq programmes CPU disponibles sont comparés dans une première allocation ; Base64 utilise une seconde allocation après sa relance plus tardive. Pour chaque programme, tous les codes à comparer restent réunis sur le même matériel. Aucun ratio ne divise un temps d’un programme par celui d’un autre.
- Sept blocs CPU, neuf blocs GPU et trois blocs de rendu, avec ordre pseudo-aléatoire des variantes. Chaque variante démarre dans un processus distinct. Les échauffements existants sont conservés. Aucun redémarrage du nœud, vidage global des caches, verrouillage des fréquences ou nœud physique exclusif n’est revendiqué.
- Agrégation par médiane, sauf les lignes UTF-8 BEST (minimum) et MEAN (moyenne), reprises de la définition documentaire. Les valeurs absolues, blocs, tailles, graines et codes de sortie sont conservés.
- Les speedups publiés et ROMEO ne diffèrent pas seulement par le matériel : les versions, compilateurs, entrées et protocoles peuvent aussi changer. Aucune normalisation par les FLOPS théoriques n’est appliquée.
- Ces reprises changent à la fois l’infrastructure, la capacité du contexte et le temps de recherche. Elles ne permettent pas d’attribuer isolément un gain au temps supplémentaire. Des répétitions de recherche indépendantes et des essais à budget égal seraient nécessaires pour séparer ces effets.
- Les diagnostics de la référence Volume hors de son domaine (dimensions non multiples de quatre) et du naïf UTF-8 historique sur texte malformé sont conservés. Ils ne sont pas transformés en speedups.

## Diagnostics conservés

Statuts des essais nouveaux : `{"build_failed": 7, "duplicate": 1, "generation_failed": 1, "incorrect": 9, "valid": 801}`.

Les journaux des relais comptabilisent 106 opérations de transport en échec sur 75527 opérations observées, tentatives remplacées comprises. Ce compteur est distinct des statuts d’essais : une opération de transfert ratée peut être suivie d’une opération réussie. L’audit fournit chaque incident et les succès ultérieurs observés sur le même outil et le même chemin, sans prétendre que chaque appel a été rejoué à l’identique. Les transferts MCP manuels de préparation et de collecte ne font pas partie de ce journal.

- aobench : 3 appel(s) natif(s) avec le diagnostic `Reconnecting... 2/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- aobench : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (request timed out)`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- aobench : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 4/5 (request timed out)`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- blackscholes : 7 appel(s) natif(s) avec le diagnostic `Reconnecting... 2/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- blackscholes : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- blackscholes : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 4/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- blackscholes : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 5/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- blackscholes : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 1/5 (Connection failed: error sending request)`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- blackscholes : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (request timed out)`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- blackscholes : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: IO error: An existing connection was forcibly closed by the remote host. (os error 10054))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- deferred : 7 appel(s) natif(s) avec le diagnostic `Reconnecting... 2/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- deferred : 2 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (request timed out)`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- deferred : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: IO error: An existing connection was forcibly closed by the remote host. (os error 10054))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- deferred : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: websocket closed by server before response.completed)`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- gemm_cpu : 6 appel(s) natif(s) avec le diagnostic `Reconnecting... 2/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- gemm_cpu : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: IO error: An existing connection was forcibly closed by the remote host. (os error 10054))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- gemm_cpu : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (request timed out)`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- gemm_cpu : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: IO error: An established connection was aborted by the software in your host machine. (os error 10053))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- mandelbrot : 3 appel(s) natif(s) avec le diagnostic `Reconnecting... 2/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- mandelbrot : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: IO error: An existing connection was forcibly closed by the remote host. (os error 10054))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- raytracer : 6 appel(s) natif(s) avec le diagnostic `Reconnecting... 2/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- raytracer : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- raytracer : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 4/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- raytracer : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 5/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- raytracer : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 1/5 (Connection failed: error sending request)`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- raytracer : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: IO error: An existing connection was forcibly closed by the remote host. (os error 10054))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- reduction : 5 appel(s) natif(s) avec le diagnostic `Reconnecting... 2/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- reduction : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: IO error: An existing connection was forcibly closed by the remote host. (os error 10054))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- reduction : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (request timed out)`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- reduction : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 4/5 (request timed out)`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- reduction : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: IO error: An established connection was aborted by the software in your host machine. (os error 10053))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- s4convd : 5 appel(s) natif(s) avec le diagnostic `Reconnecting... 2/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- s4convd : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: IO error: An existing connection was forcibly closed by the remote host. (os error 10054))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- softmax : 4 appel(s) natif(s) avec le diagnostic `Reconnecting... 2/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- softmax : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: IO error: An existing connection was forcibly closed by the remote host. (os error 10054))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- stencil3d : 7 appel(s) natif(s) avec le diagnostic `Reconnecting... 2/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- stencil3d : 2 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: IO error: An existing connection was forcibly closed by the remote host. (os error 10054))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- stencil3d : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: websocket closed by server before response.completed)`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- stencil3d : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (request timed out)`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- sumabs : 4 appel(s) natif(s) avec le diagnostic `Reconnecting... 2/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- sumabs : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (stream disconnected before completion: IO error: An existing connection was forcibly closed by the remote host. (os error 10054))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- sumabs : 1 appel(s) natif(s) avec le diagnostic `Reconnecting... 3/5 (request timed out)`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- utf8 : 2 appel(s) natif(s) avec le diagnostic `Reconnecting... 2/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- volume : 2 appel(s) natif(s) avec le diagnostic `Reconnecting... 2/5 (stream disconnected before completion: No such host is known. (os error 11001))`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle.
- Contrôle final utf8 / naive, n=65536, bloc=-1 : correct=False, sortie=1, détail=voir le résultat brut.
- Contrôle final volume / optimized, n=None, bloc=-1 : correct=None, sortie=-6, détail=free(): invalid pointer
.
- Contrôle final volume / optimized, n=None, bloc=-1 : correct=None, sortie=-6, détail=free(): invalid pointer
.

Le contrôle UTF-8 supplémentaire utilise les mêmes 79 729 chaînes que précédemment, avec entrées alignées sur 64 octets conformément au contrat et gardes mémoire autour des tampons.

| Variante UTF-8 | Cas contrôlés | Échecs |
| --- | --- | --- |
| historical | 79729 | 5773 |
| repaired | 79729 | 0 |
| reference_avx | 79729 | 0 |
| old_selected | 79729 | 0 |
| new_selected | 79729 | 0 |
| old_g | 79729 | 0 |
| new_g | 79729 | 0 |


## Fichiers

- `COMPARAISON.xlsx` : speedups, temps de calcul, détails Forest et mesures brutes.
- `COMPARAISON.csv` et `RESULTATS.json` : résultats exploitables.
- `AUDIT-FOREST.json` et `DETAILS-FOREST.csv` : contextes, mémoire, arbres et exécution.
- `AUDIT-MATERIEL.json` : matériel, compilateurs, affinités et instantanés GPU comparés entre études.
- `PROGRESSION-RECHERCHE.json` : évolution de chaque recherche, essais à trente minutes et nouveaux records.
- `STABILITE-BLACKSCHOLES.json` : répétition complémentaire de 21 blocs et données brutes, séparées du tableau principal.
- `AUDIT-TRANSPORT.json` : opérations des relais et incidents de transfert, distincts des échecs des programmes.
- `ESSAIS-FOREST.json` et `ESSAIS-FOREST.csv` : chaque essai ancien et nouveau, parenté, profondeur, hypothèse et diagnostic.
- `DEMARRAGE-MEMOIRES.json` : les 14 reçus avant exploration.
- `TENTATIVE-INTERROMPUE.json` : la première tentative à contexte de 12 000 caractères, conservée avec ses 507 essais enregistrés, dont 39 encore en attente à l’arrêt.
- `TENTATIVE-BASE64-LIMITE.json` et `VALIDATION-LIMITE-SORTIE.json` : arrêt précoce de Base64, diagnostic et vérification du correctif.
- `VALIDATION-CONTEXTE.json` : transmission exacte des sources au nouveau réglage de 64 000 caractères.
- `CORRECTIFS.patch` et `VALIDATION-INFRASTRUCTURE.json` : changements et validation.
- `PREUVES-ET-CODES.zip` : sources, scripts, journaux, résultats et manifestes de reproductibilité.
