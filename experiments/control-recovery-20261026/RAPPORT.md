# Mother et arrêts de recherche — résultats du 26 octobre 2026

Les huit nouvelles exécutions UTF-8/Mandelbrot ont livré un code confirmé dans le plafond autorisé, contre quatre sur huit dans le lot principal précédent. Les reprises de contrôle ont réellement été exercées. Cela améliore la continuité observée, mais ne garantit ni un meilleur code à chaque recherche ni la disparition de toutes les pannes de Mother : le lot diversifié a ensuite révélé un échec distinct de plan initial sur Popcount.

## Conditions et mesures

Un seul Forest, GPT-6 Luna avec effort **max** pour Mother, les arbres, les analystes et l'intégration. AB-MCTS-A et sa distribution gaussienne restent la politique existante. TabPFN est un conseiller optionnel du choix du parent avant génération, jamais un deuxième moteur.

Chaque condition commence au naïf avec base, conversations et exemples TabPFN vides. Aucun conseil algorithmique manuel n'a été envoyé pendant la recherche. Luna fonctionne directement depuis ROMEO, sans relais du PC. Les codes, prompts et conditions sont figés pendant le lot.

Les deux conditions disposent des mêmes plafonds : **5 400 s de recherche, 7 200 s du lancement à la livraison**, coût des modèles et du conseiller compris. Ce sont des plafonds, pas des durées minimales à remplir. Deux graines (23 et 61), ordre sans/avec inversé à la deuxième graine. Même AMD EPYC 9654, GCC 14.2, mêmes entrées et oracle. Les recherches partagent un nœud avec des ensembles de CPU disjoints ; le nœud entier n'est pas déclaré exclusif.

La remesure **784760**, sur romeo-c021 après la fin de toutes nos recherches, compare dans une même allocation les anciennes livraisons, les nouvelles et le naïf. Cinq rondes par programme, contrôles de correction avant chronométrage ; **110 lignes de mesure détaillées**, empreintes d'entrée et affinités déclarées identiques. Pour Mandelbrot, le temps agrégé combine géométriquement les régimes 1 et 4 threads à chaque ronde, puis moyenne les cinq rondes. Ce n'est pas le temps d'un seul régime.

## Résultats finaux, avec et sans conseiller

Speedup = temps du naïf / temps du code livré. Le rapport avec/sans supérieur à 1 favorise la livraison obtenue avec le conseiller.

| Programme | Graine | Sans TabPFN | Avec TabPFN | Rapport avec/sans |
| --- | ---: | ---: | ---: | ---: |
| UTF-8 | 23 | 6,475× | 7,123× | 1,100 |
| UTF-8 | 61 | 8,433× | 8,690× | 1,031 |
| Mandelbrot | 23 | 5,272× | 5,343× | 1,013 |
| Mandelbrot | 61 | 3,730× | 7,396× | 1,983 |

Ces quatre paires favorisent la condition avec conseiller dans ce lot. Deux recherches par programme ne suffisent pas à estimer sa supériorité générale. Les réponses de Luna et les plans initiaux de Mother ne sont pas rendus déterministes par la graine TreeQuest.

[CSV final](results/common-comparison.csv) · [temps par nombre de threads](results/common-thread-times.csv) · [échantillons bruts](results/common-raw-samples.csv) · [audit des entrées](results/common-input-audit.json).

## Comparaison aux anciennes livraisons, remesurées ensemble

| Programme et graine | Condition | Ancien speedup | Nouveau speedup | Nouveau / ancien |
| --- | --- | ---: | ---: | ---: |
| UTF-8, 23 | sans | Échec, aucune livraison | 6,475× | — |
| UTF-8, 23 | avec | 6,852× | 7,123× | 1,040 |
| UTF-8, 61 | sans | 4,276× | 8,433× | 1,972 |
| UTF-8, 61 | avec | 3,075× | 8,690× | 2,826 |
| Mandelbrot, 23 | sans | Échec, aucune livraison | 5,272× | — |
| Mandelbrot, 23 | avec | Échec, aucune livraison | 5,343× | — |
| Mandelbrot, 61 | sans | Échec, aucune livraison | 3,730× | — |
| Mandelbrot, 61 | avec | 9,735× | 7,396× | 0,760 |

**Le meilleur ancien Mandelbrot reste meilleur** : son temps agrégé est 57,820 ms, contre 76,110 ms pour la nouvelle condition avec conseiller à la graine 61, soit environ 31,6 % de temps en plus. La correction des arrêts n'assure pas de retrouver une ancienne trajectoire favorable. Cette nouvelle exécution se clôt après 67,6 minutes avec 29 essais, contre 79,8 minutes et 55 essais auparavant.

Les deux anciens UTF-8 de graine supplémentaire restent dans la remesure et les preuves, mais ne remplacent aucun échec du lot principal. [Comparaison historique](results/historical-comparison.csv) · [historique des arrêts](results/historical-stops.csv).

## Arbres, essais et décisions d'arrêt

Le nombre final d'arbres inclut les pistes ouvertes pendant la recherche. Les essais ci-dessous sont les essais de recherche, distincts des intégrations et confirmations.

| Programme/graine | Conseiller | Durée totale (min) | Arbres initiaux → finaux | Essais | Profondeur max. | Analyses complètes | Arrêt |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| UTF-8/23 | sans | 68,6 | 3 → 3 | 30 | 4 | 18 | Clôture revue |
| UTF-8/23 | avec | 84,0 | 2 → 2 | 26 | 3 | 15 | Clôture revue |
| UTF-8/61 | sans | 84,8 | 3 → 5 | 52 | 3 | 26 | Réserve finale / échéance |
| UTF-8/61 | avec | 83,9 | 3 → 3 | 34 | 3 | 22 | Clôture revue |
| Mandelbrot/23 | sans | 84,8 | 3 → 4 | 37 | 3 | 19 | Réserve finale / échéance |
| Mandelbrot/23 | avec | 84,0 | 3 → 4 | 47 | 3 | 18 | Clôture revue |
| Mandelbrot/61 | sans | 82,7 | 3 → 4 | 42 | 2 | 25 | Réserve finale / échéance |
| Mandelbrot/61 | avec | 67,6 | 3 → 4 | 29 | 3 | 15 | Clôture revue |

Les arrêts à la réserve préservent le temps d'intégration et de confirmation. Ils ne sont pas présentés comme une preuve que toutes les idées ont été épuisées.

**Sept réouvertures** après une revue sans clôture admissible ont été suivies de **87 admissions de recherche supplémentaires** :
- UTF-8/61 avec : trois réouvertures, 8 puis 10 puis 4 admissions ; la deuxième période améliore le meilleur temps de recherche d'environ 6,187 à 5,680 µs.
- UTF-8/61 sans : une réouverture, 30 admissions ; meilleur temps d'environ 5,985 à 5,837 µs.
- Mandelbrot/23 sans : une réouverture, 13 admissions, sans amélioration mesurée du meilleur.
- Mandelbrot/61 sans : deux réouvertures, 15 puis 7 admissions ; la première améliore légèrement le meilleur, la seconde non.

Ce sont des observations après reprise, pas une estimation causale du gain qu'aurait apporté la reprise à la même trajectoire interrompue. [Effets des réouvertures](results/idle-recovery-effects.csv).

## Mother et analystes

Les **270 reçus natifs de pilotage** vérifiés conservent leur chaîne ; aucun reçu manquant ou invalide. UTF-8/61 avec a exercé une continuation après limite de sortie, dans la même conversation native, et un événement d'attente vide reconnu sans délégation. La tentative longue reste comptée ; ses deux emplacements de consommation inconnue ne deviennent pas des zéros.

Trois jobs de pilotage deviennent indisponibles après leurs tentatives bornées, sans empêcher la livraison. Cela ne signifie donc pas « tous les appels Mother réussissent ».

Les analystes ont produit **158 analyses complètes**, avec **6 jobs indisponibles**. Les cinq clôtures confirmées ne déclarent aucune analyse encore indisponible à leur revue finale. Les citations vérifiées prouvent un rattachement aux sources ; elles ne garantissent pas à elles seules la pertinence de chaque hypothèse.

Mandelbrot/23 avec se clôt avec deux compteurs d'essais protégés restants. Les six hypothèses sont examinées (cinq reportées pour budget, une rejetée) et l'admission reste soumise à l'enveloppe temporelle et à la réserve finale. Un compteur positif n'est pas une autorisation de dépasser ces limites. Cette clôture est conforme aux règles contrôlées ; elle ne démontre pas l'optimalité des choix.

[Audit Mother](results/control-recovery.csv) · [décisions et reçus](results/control-events.csv) · [qualité des analyses](results/analyst-quality.csv) · [revues de clôture](results/closure-quality.csv).

## Intervention réelle de TabPFN

| Programme/graine | Appels | Avis acceptés | Parents changés | Temps du conseiller |
| --- | ---: | ---: | ---: | ---: |
| UTF-8/23 | 14 | 8 | 4 | 86,4 s |
| UTF-8/61 | 19 | 15 | 8 | 124,7 s |
| Mandelbrot/23 | 22 | 20 | 7 | 154,6 s |
| Mandelbrot/61 | 11 | 5 | 4 | 69,2 s |
| Total | 66 | 48 | 23 | 434,9 s |

Les poids de TabPFN et de Luna ne sont pas entraînés pendant ces essais. TabPFN utilise les transitions déjà mesurées de la campagne pour prédire la valeur d'un prochain enfant ; son contexte se remplit, puis repart vide au programme suivant. Ses prédictions ne remplacent jamais les mesures de TreeQuest. Un appel sans avis accepté et un avis qui conserve le parent initial ne sont pas des changements de trajectoire.

## Lecture du code et portée

L'inspection après recherche observe des validateurs UTF-8 à masques SIMD, avec variantes AVX2 et AVX-512 et traitement des frontières. Les Mandelbrot finaux emploient des combinaisons différentes de tests de non-échappement, détection de cycles, calcul par paquets et ordonnancement OpenMP. Le Mandelbrot/61 avec termine notamment en scalaire lorsqu'une seule voie du paquet reste active ; la version sans conserve une autre organisation par lignes.

Ces observations rendent les différences plausibles mais ne constituent pas une ablation : plusieurs éléments changent ensemble. Tous les résultats annoncés portent sur le contrat, la cible et les contrôles exécutés, sans preuve formelle de correction sur tout domaine possible.

## Validation et reproductibilité

La validation du moteur utilisé est **1 095 tests réussis, 2 ignorés** sur ROMEO, complétée par les scénarios de pipeline, le test Windows concerné et les 9 tests d'interface. Les scripts d'export sont contrôlés séparément. Voir [validation](../../docs/VALIDATION-CONTROL-RECOVERY-20261026.md).

Les CSV de [results](results/README.md), les sources livrées et les preuves sélectionnées dans [evidence](../../evidence/control-recovery-20261026/campaigns/) permettent de relire les conclusions. Les archives brutes locales restent conservées. Les identifiants, poids, transcriptions natives et bases de campagne ne sont pas publiés. Les sources exactes testées sont également sauvegardées dans la [release d'archives](https://github.com/Gotman08/hpc-forest-r1/releases/tag/archives-forest-20261026).

Le lot de six familles supplémentaires et ses entrées réservées sont analysés [séparément](../diversified-advisor-20261026/RAPPORT.md), pour ne pas confondre réparation des cas connus et généralisation.
