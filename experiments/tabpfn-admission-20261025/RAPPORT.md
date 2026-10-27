# TabPFN au choix du parent — résultats sur ROMEO

**Rapport final de cette campagne, 26 octobre 2026.** La correction est fonctionnelle :
TabPFN intervient avant la génération et a changé 34 choix de parent.
Dix exécutions sont terminées, six ont livré un code confirmé. Les quatre autres
ont échoué sur une réponse de Mother. Les six livraisons ont ensuite été
recompilées, vérifiées et remesurées ensemble sur ROMEO.

**Le bénéfice général de TabPFN n'est pas démontré.** La paire UTF-8 complémentaire
donne un résultat favorable (+15,9 % de speedup), avec environ deux fois plus de
temps réellement consommé. La seule paire complète de la cohorte principale
favorise le témoin, mais son bras avec conseiller s'est arrêté avant le premier
appel au modèle. Mandelbrot n'a aucun témoin livré permettant une comparaison finale.

## Correction et limites de ce qu'elle apprend

Un seul Forest conserve Mother, les arbres TreeQuest AB-MCTS-A, les analystes JEV,
les mesures et la confirmation. Tous les rôles LLM utilisent **GPT-6 Luna, effort max**.
Le conseiller demeure une option du contrôleur, désactivée par défaut.

Avant un nouvel essai, TreeQuest propose jusqu'à huit parents/actions à partir
du même arbre mesuré. TabPFN peut choisir parmi ces propositions ; un seul essai
est engagé et génère du code. Son estimation est le score connu du parent plus
le gain attendu de son prochain enfant, borné à [0, 1]. Les récompenses des arbres
restent exclusivement les résultats mesurés.

Les 80 caractéristiques décrivent le parent immuable, sa structure lexicale et
sa trajectoire connue avant génération. La cible est le score mesuré de l'enfant
moins le score connu du parent. Les erreurs réelles de candidat sont informatives ;
pannes, annulations et doublons sans nouveau résultat sont exclus. Ce vecteur
ne constitue pas une compréhension sémantique complète du code.

L'audit a vérifié l'ordre capture → génération → observation et l'absence de
résultat futur dans les requêtes. La validation utilise uniquement des exemples
observés avant la capture de ses exemples réservés. Il faut au moins huit exemples
au total et cinq exemples strictement antérieurs pour ajuster cette validation.

Les poids de TabPFN et de Luna ne sont pas entraînés pendant Forest. TabPFN utilise
les exemples disponibles en contexte. Un contexte plus riche peut aider, sans
garantir que ses prédictions ou les nouveaux codes s'améliorent à chaque étape.
Les archives, requêtes et réponses sont conservées ; aucun résultat n'est inventé
pour les enfants des parents non sélectionnés.

## Budgets, autonomie et matériel

Chaque bras dispose de **90 minutes de recherche et de 120 minutes au total**,
confirmation comprise. Le conseiller consomme ce même budget, avec une enveloppe
de 5 % du budget de recherche et 20 secondes maximum par invocation. Une occasion
sur quatre conserve la proposition initiale pour l'exploration. Les autres replis
couvrent les données insuffisantes, la validation refusée et la cible occupée.

Même code naïf, mêmes entrées, oracle, compilateur GCC 14.2 et ressources au sein
de chaque paire. Les conditions sont inversées entre les graines 23 et 61.
Chaque bras démarre avec une base de mémoire vide et des conversations neuves.
Le contrôle des cinq paires confirme que leurs configurations diffèrent seulement
par l'activation du conseiller et les identités des sessions isolées.

Les recherches tournent sur **romeo-c021, AMD EPYC 9654**, avec des cœurs distincts :
UTF-8 reçoit un cœur de calcul et un cœur pour le client Luna ; Mandelbrot quatre
cœurs de calcul et un pour ce client. TabPFN utilise un thread CPU sous le verrou
des mesures de sa campagne. Ce verrou ne supprime pas les interférences éventuelles
des autres campagnes sur le même nœud partagé.

Luna est appelé directement depuis ROMEO ; ses poids ne sont pas exécutés sur le
cluster. TabPFN et les programmes compilés s'exécutent dans l'allocation ROMEO.
Aucun relais du PC, aucune indication algorithmique manuelle ni modification
manuelle d'un code candidat pendant les essais. Les 90 fichiers Python du moteur
sont identiques dans la suite validée, les cinq payloads et la source locale finale.
Les ajouts après le gel concernent uniquement les exports, preuves et documents.

Les plafonds égaux n'imposent ni le même nombre d'arbres décidé par Mother, ni le
même nombre d'essais, de tokens ou de minutes réellement utilisés. Les graines
ne rendent pas les réponses hébergées de Luna déterministes.

## Speedups après remesure commune

Job **784366**, terminé avec code 0 sur le même nœud, après la fin des cinq jobs de
recherche. Six codes livrés et deux codes naïfs, cinq répétitions par régime,
mêmes entrées vérifiées par SHA-256, même compilateur et affinité autorisée.
Aucune recherche de cette étude ne tournait pendant cette remesure ; le nœud
n'était toutefois pas réservé exclusivement.

Le speedup est le temps du naïf divisé par le temps du code confirmé.
Pour Mandelbrot, la métrique agrégée est la moyenne géométrique des temps à
un et quatre threads.

| Cas | Cohorte | Sans conseiller | Avec conseiller | Rapport avec / sans |
| --- | --- | --- | --- | --- |
| UTF-8 r1 | principale | aucune livraison | 6,85× | non calculable |
| UTF-8 r2 | principale | 4,28× | 3,08× | 0,720× |
| UTF-8 r3 | complémentaire | 6,11× | 7,08× | 1,159× |
| Mandelbrot r1 | principale | aucune livraison | aucune livraison | non calculable |
| Mandelbrot r2 | principale | aucune livraison | 9,75× | non calculable |

- **UTF-8 r1** : code avec conseiller à 7,204 µs contre 49,376 µs pour le naïf.
  Son témoin a échoué : ce n'est pas une victoire comparée.
- **UTF-8 r2** : 16,039 µs avec contre 11,549 µs sans. Le code livré avec l'option
  est 38,9 % plus lent ; son speedup est inférieur de 28,0 %. Mais TabPFN n'a
  effectué aucun appel : cette différence n'établit pas une erreur de prédiction.
- **UTF-8 r3, complémentaire** : 6,973 µs avec contre 8,079 µs sans,
  soit 13,7 % de temps d'exécution en moins et 15,9 % de speedup supplémentaire.
  Le bras avec a consommé 54,4 minutes contre 27,1 minutes. Ce résultat positif
  isolé ne mesure pas un avantage général à dépense effectivement identique.
- **Mandelbrot r2** : agrégat 57,756 ms contre 562,952 ms pour le naïf (9,75×).
  À un thread : 115,329 ms, soit 4,88× ; à quatre threads : 28,924 ms, soit 19,46×.
  Aucun témoin livré ne permet d'attribuer ce résultat au conseiller.

CSV de référence : [common-comparison.csv](results/common-comparison.csv),
[temps par régime](results/common-thread-times.csv),
[mesures brutes](results/common-raw-samples.csv),
[audit des entrées](results/common-input-audit.json).
Les colonnes historiques nommées `speedup_common` dans `arms.csv` correspondent
aux remesures **par paire**, effectuées plus tôt ; le tableau ci-dessus utilise
la remesure commune à tous les codes, plus propre pour la comparaison finale.

## Recherche et décisions d'arrêt

| Cas | Conseiller | Durée totale (min) | Arbres initial → total | Essais corrects / total | Profondeur max | Fin |
| --- | --- | --- | --- | --- | --- | --- |
| UTF-8 r1 | sans | 8,9 | 3 → 3 | 6 / 6 | 2 | échec de Mother |
| UTF-8 r1 | avec | 73,7 | 3 → 4 | 33 / 33 | 3 | clôture révisée |
| UTF-8 r2 | avec | 19,0 | 2 → 2 | 4 / 4 | 2 | aucun travail admissible après revue |
| UTF-8 r2 | sans | 88,7 | 3 → 3 | 36 / 36 | 2 | réserve finale / limite |
| Mandelbrot r1 | sans | 33,7 | 4 → 4 | 30 / 35 | 3 | échec de Mother |
| Mandelbrot r1 | avec | 21,2 | 2 → 2 | 4 / 4 | 2 | échec de Mother |
| Mandelbrot r2 | avec | 79,8 | 3 → 4 | 52 / 55 | 4 | clôture révisée |
| Mandelbrot r2 | sans | 8,2 | 3 → 3 | 5 / 5 | 2 | échec de Mother |
| UTF-8 r3 | sans | 27,1 | 3 → 3 | 13 / 14 | 3 | clôture révisée |
| UTF-8 r3 | avec | 54,4 | 3 → 3 | 22 / 22 | 3 | aucun travail admissible après revue |

Ces nombres comptent les essais des arbres de recherche, hors contrôles internes
du harness, intégrations Gm et assemblage final G. Les profondeurs sont celles
enregistrées dans les essais. Les durées incluent le parcours jusqu'à livraison
ou échec ; elles ne sont pas les temps d'exécution des codes optimisés.

La paire r3 est une répétition complémentaire déclarée après l'échec du témoin
UTF-8 r1, avec les mêmes conditions et la graine 23. Elle n'efface pas ce témoin
et n'est pas fusionnée discrètement avec les résultats principaux.

Quatre échecs bloquent la livraison :
- UTF-8 r1 sans et Mandelbrot r2 sans : Mother a émis un événement natif `wait`
  hors des outils autorisés. Les listes de destinataires sont vides ; aucun
  sous-agent n'a été lancé par ces appels. Le garde-fou a rejeté la réponse.
- Mandelbrot r1 sans **et avec** : réponse de Mother incomplète à cause de
  `max_output_tokens`. Le coût en tokens de ces appels est inconnu, pas nul.
  Le contrôleur n'a pas remplacé ni rejoué sa conversation sans reçu vérifiable.

Deux livraisons utilisent `no_admissible_work_after_idle_review` alors que
`closed=false` et la clôture implicite reste en attente :
- UTF-8 r2 avec : seulement quatre essais, deux arbres, trois essais protégés
  restants et environ 4 259 secondes disponibles au passage vers la confirmation.
  L'augmentation du plafond n'a donc pas produit plus de données.
- UTF-8 r3 avec : 22 essais et toutes les protections consommées ; le même motif
  d'arrêt apparaît, mais on ne retrouve pas les trois essais protégés abandonnés
  du cas r2. Une analyse d'analyste est signalée indisponible dans ses diagnostics.

Ces problèmes du contrôle et de la clôture sont conservés dans les deux conditions.
Ils n'ont pas été corrigés en cours d'étude, ce qui aurait changé le protocole.
Les journaux restent disponibles dans les [preuves des campagnes](../../evidence/tabpfn-admission-20261025/campaigns/),
et les causes vérifiées dans [observed-worker-failures.json](../../evidence/tabpfn-admission-20261025/observed-worker-failures.json).

## TabPFN effectivement exercé

| Cas avec conseiller | Exemples / sources parent distinctes | Lancements | Validations avec prédiction | Parents changés | Coût (s) | MAE enfant choisi |
| --- | --- | --- | --- | --- | --- | --- |
| UTF-8 r1 | 33 / 13 | 19 | 13 | 10 | 121,6 | 0,039 |
| UTF-8 r2 | 4 / 2 | 0 | 0 | 0 | 0,1 | — |
| Mandelbrot r1 | 4 / 2 | 0 | 0 | 0 | 0,1 | — |
| Mandelbrot r2 | 55 / 22 | 27 | 25 | 18 | 198,6 | 0,076 |
| UTF-8 r3 | 22 / 10 | 10 | 9 | 6 | 64,1 | 0,054 |

Au total : **56 lancements**, dont **54 validations avec prédiction sur les exemples
réservés**, **47 sélections avec prédiction validée** et **34 changements de parent**.
Un lancement ne signifie donc pas nécessairement une inférence acceptée, et un avis
accepté peut conserver le parent initial. Deux validations ont été refusées faute
d'au moins cinq exemples strictement antérieurs ; sept autres ont échoué au filtre
de validation. Vingt occasions ont conservé TreeQuest pour l'exploration ; sept
ont évité une inférence pendant une mesure de leur campagne.

Le coût enregistré est de 121,6 s, 198,6 s et 64,1 s dans les trois bras où
le modèle a été utilisé, soit respectivement 2,25 %, 3,68 % et 1,19 % du budget
de recherche autorisé. Les bras de quatre exemples restent sous 0,1 s.

La MAE compare le score final prédit et mesuré du seul enfant effectivement choisi,
sur une échelle bornée [0, 1]. Elle ne mesure pas ce qu'auraient produit les parents
écartés. Les exemples d'une même trajectoire sont corrélés. Le filtre de classement
et ces petites tailles ne constituent pas une preuve statistique de supériorité.
L'audit ne montre pas que la précision croît de façon monotone avec le temps.

[Décisions détaillées](results/parent-decisions.csv) ·
[Audit chronologique et prédictif](results/advice-audit.json)

## Ce qu'apporte réellement le temps supplémentaire

| Cas | Conseiller | 10 min | 30 min | 60 min | 90 min |
| --- | --- | --- | --- | --- | --- |
| UTF-8 r1 | avec | 4,76× | 5,45× | 6,29× | 6,85× † |
| UTF-8 r2 | avec | 3,11× | 3,11× † | 3,11× † | 3,11× † |
| UTF-8 r2 | sans | 1,26× | 3,53× | 4,19× | 4,28× † |
| Mandelbrot r2 | avec | 6,18× | 8,52× | 8,54× | 8,54× † |
| UTF-8 r3 | sans | 2,65× | 6,11× † | 6,11× † | 6,11× † |
| UTF-8 r3 | avec | 2,73× | 7,13× | 7,13× † | 7,13× † |

Meilleur résultat de **recherche** déjà mesuré à chaque minute, rapporté au naïf
de sa propre campagne. Les contrôles de développement et les observations futures
sont exclus ; les intégrations intermédiaires de la phase de recherche sont incluses.
Ce tableau n'est pas la confirmation finale ni la remesure commune.
† La campagne était déjà terminée : la valeur est conservée, sans activité supposée.
Les campagnes échouées sont également conservées, avec leur état, dans le
[CSV complet des courbes](results/learning-curves.csv).

UTF-8 r1 avec passe de 5,45× à 30 minutes à 6,85× en fin de recherche :
le temps supplémentaire a effectivement permis un meilleur code dans cette
trajectoire. Mandelbrot r2 avec passe de 8,52× à 8,54× entre 30 et 60 minutes ;
les 9,75× finaux viennent du code ensuite confirmé, pas d'une extrapolation.
UTF-8 r3 avec avait déjà trouvé son meilleur candidat observé à 30 minutes.
Ce sont des préfixes de recherches longues, pas des expériences indépendantes
optimisées pour chacun de ces budgets.

## Coût LLM et analystes

| Cas | Conseiller | Tokens connus (millions) | Appels à usage inconnu | Analyses du code complètes / citations |
| --- | --- | --- | --- | --- |
| UTF-8 r1 | sans | 0,942 | 0 | 3 / 8 |
| UTF-8 r1 | avec | 10,490 | 0 | 25 / 86 |
| UTF-8 r2 | avec | 3,479 | 0 | 4 / 19 |
| UTF-8 r2 | sans | 11,910 | 0 | 20 / 66 |
| Mandelbrot r1 | sans | 3,426 | 1 | 5 / 22 |
| Mandelbrot r1 | avec | 0,359 | 1 | 2 / 9 |
| Mandelbrot r2 | avec | 18,481 | 0 | 22 / 80 |
| Mandelbrot r2 | sans | 0,384 | 0 | 2 / 6 |
| UTF-8 r3 | sans | 4,406 | 0 | 8 / 27 |
| UTF-8 r3 | avec | 7,833 | 0 | 13 / 54 |

Les tokens connus additionnent les compteurs natifs vérifiés ; les tokens d'entrée
en cache sont déjà inclus dans l'entrée. Ce ne sont ni des euros ni une consommation
de calcul GPU local. Les compteurs inconnus ne valent jamais zéro. Les citations et
analyses complètes attestent des références au code selon le contrat de contrôle,
pas de la justesse de toutes les hypothèses des analystes.

Les faibles taux d'utilisation CPU Slurm (3,5 à 8,6 % pour les recherches) reflètent
notamment l'attente des réponses hébergées. Réduire les cœurs sans tenir compte du
benchmark Mandelbrot à quatre threads changerait les conditions expérimentales.
Les relevés CPU et mémoire sont conservés dans les
[reçus finaux](../../evidence/tabpfn-admission-20261025/final-retrieval-and-efficiency.json).

## Validation et conclusion pratique

- ROMEO, job 784271 : **1 072 tests réussis, 2 ignorés**, aucun échec.
- Neuf tests d'interface locaux réussis ; Ruff local réussi.
- Six tests locaux d'exports/audit/protocole réussis après le gel, dont deux
  tests de protocole déjà présents dans la suite distante.
- Cinq paires de configurations vérifiées, mémoires neuves, modèle/effort contrôlés,
  90 sources Python identiques et six archives rapatriées avec SHA-256 concordants.
- Remesure commune : compilation, correction et cinq répétitions réussies pour
  les six livraisons et leurs deux références naïves.

L'ancien essai utilisait une file de générations terminées et n'avait déclenché
aucun appel TabPFN. Le nouveau point d'intervention est donc réellement testé.
On ne peut cependant pas expliquer les différences avec l'ancien rapport par
TabPFN seul : les plafonds passent de 30 à 90 minutes, et la classification du
timeout candidat change dans ce nouveau protocole.

**La prochaine priorité est la fiabilité du contrôle et des arrêts**, avant de
dépenser davantage sur une démonstration de gain. Il faut ensuite refaire plusieurs
paires complètes sous ce protocole corrigé, en gardant les échecs et en séparant
les gains finaux du coût pour les obtenir. Davantage de temps autorisé ne suffit
pas si Forest s'arrête, si Mother échoue ou si les nouvelles données n'apportent
pas d'information utile au conseiller.

La coupure d'accès au poste n'a pas arrêté les recherches autonomes : après le
message « ressaye », les résultats ont été récupérés et la remesure a été exécutée.
Le diagnostic initial est conservé avec son [reçu de résolution](../../evidence/tabpfn-admission-20261025/retrieval-resolved-20261026.json).

[Protocole figé](protocol.json) · [Complément UTF-8](supplementary-protocol.json) ·
[Validation technique](../../docs/VALIDATION-TABPFN-ADMISSION-20261025.md) ·
[Description du conseiller](../../docs/TABPFN-ADVISOR.md)

Le champ `prepared_not_started` du protocole est son état **au gel**, conservé pour
la traçabilité. L'état final est séparé dans [results/status.json](results/status.json).
