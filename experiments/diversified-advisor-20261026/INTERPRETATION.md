# Interprétation du lot diversifié

Ce document décrit les limites à conserver dans le rapport final ; les chiffres de performance proviennent exclusivement de la remesure finale.

## Ce que cette expérience change

Six familles supplémentaires pour le comparatif TabPFN, une paire avec/sans par famille. Plusieurs tailles pendant la recherche, autres tailles et graines réservées à la fin, ordre des conditions équilibré, mémoires neuves et même plafond de temps. Ces familles proviennent de la suite historique de référence ; on ne peut donc pas les qualifier de problèmes jamais vus par Forest ou par les modèles préentraînés.

Les entrées réservées modifient tailles et graines au sein des mêmes générateurs. Cela mesure un transfert de taille et de données, pas une généralisation à toutes les distributions. Par exemple, l'Argmin chronométré est une suite décroissante : changer sa graine ne change pas cette distribution déterministe. La correction comprend d'autres motifs, notamment les égalités et extrêmes.

Les deux conditions sont deux recherches autonomes. Le plan initial de Mother peut différer avant le premier appel au conseiller, tout comme le nombre d'arbres. Le contraste observé concerne la politique complète activée ou désactivée, avec cette variabilité. Une paire ne permet pas d'isoler l'effet causal propre d'une décision TabPFN ni d'estimer la variance d'une famille.

## Échecs et clôtures conservés

Popcount avec conseiller échoue au plan initial : la réponse comporte des pistes, mais le champ G est vide ; le contrat exige des indications de recherche non vides. Une seule tentative de planification, zéro essai de recherche et zéro appel TabPFN. L'échec appartient à la robustesse du lancement de Forest, pas à une prédiction numérique du conseiller. Aucun speedup n'est imputé et aucun essai de remplacement ne masque cet échec.

Les reprises de pilotage en cours de recherche ne constituent pas un mécanisme de réparation de cette première réponse. Une future correction du plan initial doit être une version distincte, vérifiée avant une nouvelle campagne.

Stencil avec conseiller se clôt après 32,3 minutes avec une analyse T3 déclarée indisponible. Les erreurs portent notamment sur un mécanisme absent ou des citations de source non admissibles, après les tentatives bornées. Les quatre hypothèses effectivement disponibles sont examinées, mais la clôture conforme au protocole ne prouve pas une analyse suffisante de toutes les pistes.

## Code produit : observations après recherche

- Base64 : les deux livraisons vectorisent. La version sans utilise une conversion AVX2, des regroupements d'octets et des écritures directes ; celle avec ajoute notamment des contrôles de caractères et des voies AVX-512/AVX2. Le contrat exige des entrées Base64 valides : l'absence de rejet des caractères invalides dans une voie rapide n'est pas une violation de ce contrat. Le coût propre de ces différences n'a pas été isolé par ablation. Le générateur chronométré produit des messages valides sans suffixe '=' ; il ne couvre pas toutes les frontières et variantes de padding.
- GEMM : la version sans utilise empaquetage de B, AVX-512/FMA et un micro-noyau en registres ; la version avec utilise une organisation différente, par paires de lignes et panneaux/tuiles. La source sans contient aussi des branches de repli AVX/SSE inactives sur la cible dont la syntaxe n'est pas portable telle quelle. Le résultat concerne EPYC 9654 et cette compilation, pas tous les processeurs.
- Black–Scholes : la version sans emploie une voie AVX2 incluant approximations vectorielles de fonctions mathématiques, avec repli scalaire ; celle avec conserve notamment logf/expf/sqrtf scalaires et travaille une approximation centrale de CND. Les plans initiaux étaient déjà différents : le plan avec limitait d'abord sa piste SIMD aux calculs hors CND, tandis que le plan sans couvrait le noyau complet. On ne peut attribuer tout l'écart final au conseiller.
- Stencil : les deux livraisons réutilisent une équipe OpenMP persistante sur les pas de temps et vectorisent la boucle intérieure. Un faible écart entre elles ne prouve pas une meilleure stratégie de recherche.
- Argmin : un temps de recherche plus long avec conseiller ne suffit pas à garantir un meilleur programme ; comparer la livraison finale, les tailles et les arrêts, pas seulement le nombre d'essais.
- Popcount : seule la condition sans livre un programme ; aucune comparaison du conseiller n'est possible.

Aucune de ces lectures n'a été renvoyée aux agents ni utilisée pour modifier les livraisons ou sélectionner un autre code.

## TabPFN n'apprend pas de nouveaux poids pendant la recherche

Le conseiller reçoit des observations de transitions parent → enfant mesuré et des caractéristiques disponibles avant génération. Il conditionne ses prédictions sur ce contexte croissant ; les poids de TabPFN et de Luna restent fixes. Toutes les campagnes commencent sans exemple importé.

La taille et la diversité de ce contexte restent limitées : entre 17 et 62 observations dans les cinq conditions diversifiées où le conseiller a été exercé, avec plusieurs descendants d'un même parent. Les caractéristiques de code sont surtout statiques et lexicales, pas une compréhension sémantique exhaustive. Le filtre interne de validation sur ces exemples n'est pas une preuve de gain futur.

La latence du conseiller est incluse dans les plafonds. Plus de temps ou plus d'essais ne rend pas automatiquement son classement meilleur. Les courbes à 10/30/60/90 minutes sont des préfixes d'une même recherche, pas quatre recherches indépendantes. Leurs temps de recherche ne remplacent pas les confirmations finales.

## Validation et limites

Cinq rondes de chronométrage par code évaluent la variation de mesure, pas la variance des recherches LLM. Les échecs restent dans les taux de livraison. Les speedups sont relatifs au naïf remesuré sur ROMEO ; ils ne sont pas comparés directement à des publications sur un autre matériel.

Le naïf GEMM historique ne supportait pas les tailles ajoutées. Le prétest l'a rejeté avant toute optimisation. L'amendement conserve la boucle naïve r,c,k pour les autres tailles ; il ne modifie ni les oracles ni les tolérances. Cette intervention de l'opérateur, déclarée dans le protocole, est distincte d'une suggestion d'optimisation aux chercheurs.

Les preuves de correction concernent les tests exécutés et les tolérances fixées. Elles ne constituent pas une preuve mathématique générale. Une modification de ces contrôles ou des règles de clôture nécessitera une autre campagne et ne doit pas être mélangée aux résultats figés ici.
