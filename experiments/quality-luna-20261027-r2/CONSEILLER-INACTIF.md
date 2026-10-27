# Pourquoi TabPFN n'a pas décidé dans cette tentative

Les deux recherches où le conseiller était activé ont accumulé des observations,
mais aucun appel de prédiction n'a passé la prévalidation. Elles n'ont donc ni
mesuré la qualité de son classement ni démontré son utilité pour ces programmes.
Le contrôle préalable du runtime, effectué sur des données synthétiques séparées,
prouve seulement que la bibliothèque et les poids fonctionnent sur ROMEO.

| Observation | GEMM avec conseiller | Black–Scholes avec conseiller |
|---|---:|---:|
| Transitions enregistrées dans la campagne | 58 | 81 |
| Sources parentes distinctes, tous arbres réunis | 12 | 16 |
| Opportunités avec plusieurs propositions | 50 | 66 |
| Prévalidations refusées | 26 | 33 |
| Prédictions / changements de parent | 0 / 0 | 0 / 0 |
| Temps du conseiller enregistré | 2,55 s | 4,12 s |

Le motif des 59 refus est `insufficient_independent_parent_context`.
Le [CSV complémentaire](results/adviser-preflight.csv) lit directement le motif
enregistré dans `payload.validation.reason` ; ses empreintes et sa provenance
sont dans [le reçu d'export](results/adviser-preflight-provenance.json).

Le nombre total de variantes ne correspond pas au nombre de preuves indépendantes
utilisables. La politique `runtime_calibrated_v2` prend les observations d'un même
arbre, réserve les plus récentes pour la validation, puis retire du contexte
d'ajustement les transitions dont le code parent apparaît dans cette validation.
Elle exige au moins cinq transitions et trois parents distincts pour l'ajustement,
six transitions et trois parents distincts pour la validation. Il faut donc au
minimum six groupes parents disjoints et onze transitions utilisables dans cet
arbre, plus des écarts mesurés permettant de comparer des paires. Ce minimum est
nécessaire, mais ne suffit pas à autoriser une décision.

Sur GEMM, après cette séparation, les 26 tentatives ne conservaient que 0 à 2
transitions pour l'ajustement. Sur Black–Scholes, certaines en conservaient jusqu'à
8, mais jamais simultanément les effectifs et le nombre de parents requis des
deux côtés. Beaucoup d'enfants viennent des mêmes parents ; des données plus
nombreuses restent donc insuffisantes si leur filiation change peu.

Le surcoût mesuré de ces abstentions est de quelques secondes, alors que les
recherches durent environ une heure à une heure vingt. Il ne peut pas expliquer
à lui seul une différence importante de vitesse du programme livré. Le blocage
GEMM provient d'une action Mother non exécutable et de sa gestion par le contrôleur,
documentées séparément. La différence Black–Scholes provient de trajectoires de
recherche différentes ; sans décisions du conseiller et sans plusieurs répétitions,
on ne peut pas lui attribuer le gain observé.

La lecture des programmes livrés fournit une explication technique compatible
avec les mesures Black–Scholes. Le candidat de la condition activée emploie un
noyau AVX2 de huit éléments, avec des approximations vectorielles du logarithme
et de l'exponentielle, des gardes et des replis scalaires. Son point d'entrée
utilise ce noyau aussi à un thread. Le candidat sans conseiller combine plusieurs
chemins spécialisés ; son chemin parallèle conserve notamment des appels
`logf`/`expf` scalaires par voie pour une partie des calculs. Les deux programmes
utilisent le même Makefile protégé (`-O3 -march=native -fopenmp`).

Les speedups à un thread sont de 5,76× et 7,62× pour le premier, contre 2,68× et
3,18× pour le second, sur les deux tailles enregistrées. À quatre threads, ils
atteignent respectivement 23,24×/29,91× et 7,46×/7,04×. Ces différences confirment
que l'écart agrégé ne provient pas seulement du nombre de threads. Cette lecture
des sources n'isole pas causalement le bénéfice de chaque transformation ; elle
ne remplace ni le profilage ni des ablations du code. Aucun programme n'a été
modifié pour cette analyse.

Sources : [candidat activé](delivered-codes/blackscholes-r1-corrected.cpp),
[candidat désactivé](delivered-codes/blackscholes-r1-off.cpp),
[mesures appariées par configuration](results/configuration-timings.csv).

L'abstention conserve la première proposition TreeQuest et son état aléatoire
initialement avancé : les propositions supplémentaires ne sont pas inscrites
comme des essais ni comme des récompenses. Le test
`test_fallback_keeps_exact_original_parent_rng_and_rollback` vérifie cette
propriété à partir d'un même état de recherche ; il passe dans la suite complète.
Cela ne rend pas deux recherches réelles identiques : leurs réponses Luna,
chronométrages, ordres de fin et décisions Mother peuvent différer.

Les poids TabPFN ne sont pas entraînés pendant Forest. Le modèle préentraîné
utilise les exemples disponibles pour adapter sa prédiction au contexte. Laisser
tourner plus longtemps peut enrichir ce contexte, mais ne garantit pas des parents
plus diversifiés ni le passage de la validation. La nouvelle tentative conserve
les mêmes garde-fous ; aucun seuil n'est abaissé pour fabriquer une activation.
