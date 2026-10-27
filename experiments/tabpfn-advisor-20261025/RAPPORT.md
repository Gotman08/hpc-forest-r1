# Forest + TabPFN : comparaison réelle sur ROMEO

25 octobre 2026. **Intégration fonctionnelle, bénéfice en recherche non démontré.**
Forest reste un seul système, avec GPT-6 Luna, effort max, pour Mother, les
générateurs et les analystes. TabPFN-3.5 fonctionne réellement sur ROMEO, mais
aucun des quatre essais activés n'a rencontré plusieurs candidats déjà prêts à
départager : **zéro opportunité de classement, zéro appel en ligne, zéro changement
d'ordre prédit**. Les gains et régressions ci-dessous ne sont donc pas des gains
d'apprentissage de TabPFN.

Huit recherches ont été exécutées ; sept ont livré un code confirmé. L'échec
restant est conservé et n'est pas remplacé par une nouvelle exécution favorable.
Le conseiller reste optionnel et désactivé par défaut.

## Comparaison primaire, remesure à la fin de chaque paire

Speedup = temps du code naïf / temps du code livré. Plus grand est meilleur.
Le naïf et les deux codes livrés sont remesurés dans la même allocation, avec
cinq tours entrelacés. Aucune valeur n'est attribuée à une livraison manquante.

| Programme | Répétition | Sans conseiller | Option activée | Rapport avec / sans |
| --- | ---: | ---: | ---: | ---: |
| UTF-8 | 1 | 6,66× | 1,08× | 0,162 |
| UTF-8 | 2 | Échec de livraison | 2,06× | Non comparable |
| Mandelbrot | 1 | 3,85× | 7,06× | 1,832 |
| Mandelbrot | 2 | 14,74× | 9,06× | 0,615 |

Sur les trois paires complètes, l'option produit un meilleur code une fois et un
moins bon code deux fois. **Ce très petit échantillon ne permet pas d'estimer un
effet moyen fiable.** Les générations Luna sont stochastiques. L'option active
également une file donnant priorité aux retours Mother/JEV déjà prêts ; ce
comportement peut agir avant toute prédiction. Le contraste porte sur l'option
entière, pas sur le seul modèle prédictif.

Sources : [comparaison par paire](results/paired-comparison.csv),
[huit essais](results/arms.csv), [analyse et décisions](results/analysis.json).

## Remesure supplémentaire commune, après toutes les recherches

Job **784264**, nœud `romeo-c021`, AMD EPYC 9654, GCC 14.2. Les recherches de cette
étude étaient toutes arrêtées. Tous les codes livrés d'un programme ont été
remesurés ensemble avec le même naïf, les mêmes entrées et le même protocole.

| Programme | Répétition | Temps sans | Temps avec | Speedup sans | Speedup avec |
| --- | ---: | ---: | ---: | ---: | ---: |
| UTF-8 | 1 | 7,374 µs | 45,649 µs | 6,94× | 1,12× |
| UTF-8 | 2 | — | 23,995 µs | — | 2,13× |
| Mandelbrot | 1 | 146,543 ms | 79,851 ms | 3,85× | 7,06× |
| Mandelbrot | 2 | 38,258 ms | 62,234 ms | 14,74× | 9,06× |

Références communes : UTF-8 **51,168 µs** ; Mandelbrot **563,910 ms**.
Le temps Mandelbrot est l'indicateur historique combinant les régimes à un et
quatre threads par moyenne géométrique, puis moyennant cinq tours. Il ne s'agit
pas du temps d'un seul régime. Voici les speedups séparés :

| Mandelbrot | Sans, 1 thread | Avec, 1 thread | Sans, 4 threads | Avec, 4 threads |
| --- | ---: | ---: | ---: | ---: |
| Répétition 1 | 1,92× | 3,53× | 7,69× | 14,11× |
| Répétition 2 | 7,38× | 4,54× | 29,45× | 18,10× |

Le naïf Mandelbrot reste sériel même quand quatre threads sont autorisés. Les
gains à quatre threads comprennent donc la parallélisation ajoutée par Forest ;
la colonne à un thread permet de lire séparément le gain sur un seul cœur.

L'audit vérifie **70 mesures détaillées** avec des empreintes d'entrée identiques
par régime et une affinité du fil principal identique entre candidats. Le parent
du programme est limité au CPU 41 pour UTF-8 et aux CPU 41–44 pour Mandelbrot.
Après la liaison OpenMP, le journal du driver expose seulement l'affinité du fil
principal ; cette valeur ne décrit pas tous les threads OpenMP.

Les nœuds n'étaient pas réservés exclusivement : une charge extérieure reste
possible. La référence UTF-8 varie de 49,220 à 57,849 µs sur les cinq tours. Les
petits écarts de speedup absolu entre les deux remesures doivent donc être lus avec
cette variabilité. Le sens des trois comparaisons complètes reste identique.

Sources : [remesure commune](results/common-comparison.csv),
[temps par nombre de threads](results/common-thread-times.csv),
[mesures brutes](results/common-raw-samples.csv),
[audit des entrées et CPU](results/common-input-audit.json).

## Budgets, arbres et arrêts

Chaque essai dispose du même budget cible de **1 800 s** et du même plafond total
de **3 600 s**, confirmation comprise. Le mode existant `finish-started` est
conservé. Les dépenses réelles et le nombre de tokens ne sont pas égalisés.
Les deux répétitions inversent l'ordre : sans/avec, puis avec/sans ; graines
TreeQuest 23 et 61. Ces graines ne figent pas les réponses du service Luna.

| Programme | Rép. | Option | Durée totale | Arbres de recherche | Essais corrects / total | Arrêt |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| UTF-8 | 1 | Sans | 26 min 54 s | 3 | 18/18 | Clôture revue |
| UTF-8 | 1 | Avec | 23 min 50 s | 4, dont 1 ajouté | 17/17 | Clôture revue |
| UTF-8 | 2 | Avec | 23 min 14 s | 2 | 9/10 | Timeout candidat classé infrastructure |
| UTF-8 | 2 | Sans | 21 min 35 s | 3 | 20/20 | Échec Mother, pas de livraison |
| Mandelbrot | 1 | Sans | 22 min 42 s | 2 | 20/20 | Réserve finale / budget |
| Mandelbrot | 1 | Avec | 23 min 12 s | 3 | 12/15 | Réserve finale / budget |
| Mandelbrot | 2 | Avec | 27 min 23 s | 3 | 20/21 | Réserve finale / budget |
| Mandelbrot | 2 | Sans | 23 min 49 s | 2 | 13/13 | Clôture revue |

Les essais ci-dessus excluent les combinaisons Gm et l'assemblage G ; ceux-ci sont
tracés séparément dans les rapports. Les trois clôtures revues examinent
respectivement cinq, cinq et trois hypothèses. Des demandes de fermeture ont été
rejetées : cinq dans UTF-8 sans/r1, une dans UTF-8 avec/r1, une dans Mandelbrot
sans/r1 et quatre dans Mandelbrot sans/r2. La fin de réserve n'est pas une preuve
de convergence ; elle protège l'assemblage et la confirmation.

Le total enregistré est de **26 101 688 tokens**, entrées en cache incluses,
avec **un appel dont l'usage manque**. Ce total n'est ni une facture ni une
consommation entièrement connue. Voir `known_tokens` et `unknown_usage_slots`
dans le CSV. Aucune correction de code candidat ni direction algorithmique n'a
été fournie par l'opérateur pendant ces recherches.

## Analystes et incidents observés

Les rapports d'analyse du code acceptés sont au nombre de 5/9 pour UTF-8 r1
sans/avec, 1/7 pour UTF-8 r2 sans/avec, 4/4 pour Mandelbrot r1 sans/avec et 7/5 pour
Mandelbrot r2 sans/avec. Ce sont des rapports, pas des nombres d'arbres distincts.
Les lectures et citations de sources sont conservées dans les rapports actifs.

- **UTF-8 r2 avec** : un candidat généré place son traitement scalaire dans la
  condition réservée aux blocs de seize octets. Avec un octet, sa boucle n'avance
  plus. Le validateur historique classe ce timeout comme infrastructure ; cela
  abrège la recherche, qui livre néanmoins un autre code correct et confirmé.
  [Preuve](../../evidence/tabpfn-integration-20261025/utf8-r2-timeout/README.md).
- **UTF-8 r2 sans** : un appel Mother de 925,544 s se termine par
  `max_output_tokens`. Sans réponse complète et preuve native utilisable, Forest
  arrête le parcours. Les 20 essais corrects restent archivés ; leur meilleur
  résultat de recherche, environ 8,34×, **n'est pas une livraison confirmée**.
  [Preuve](../../evidence/tabpfn-integration-20261025/utf8-r2-mother-output-limit/README.md).
- **Mandelbrot r1 avec** : un rapport T3 est refusé faute de mécanisme et de
  citations bornées ; une revue d'hypothèses Mother est également invalide.
- **Mandelbrot r2 avec** : un rapport T1 cite hors de la version ou des lignes
  de code fournies. Le contrôleur le rejette. Ce rapport n'est pas compté comme
  une analyse réussie.

Ces défauts sont observés et conservés. Aucun candidat ou validateur n'a été
corrigé au milieu de la comparaison pour faire disparaître un échec.

## Ce que TabPFN a effectivement fait

La collecte a conservé 17, 9, 15 et 23 codes corrects distincts dans les quatre
essais activés, avec les combinaisons intermédiaires éligibles. Son coût total
en ligne est **0,535 s**, exclusivement pour les caractéristiques et le contexte.
Les prédictions exigent au moins huit exemples et plusieurs candidats déjà prêts.
La seconde condition ne s'est jamais produite. Augmenter le seul nombre d'exemples
ne résout donc pas la limite de ce raccordement.

Un diagnostic rétrospectif séparé, préparé avant les résultats et exécuté après
les remesures (job **784265**), utilise les deux derniers codes corrects distincts
de chaque essai activé. Leurs temps sont cachés ; seuls les exemples mesurés avant
leur capture alimentent le contexte. Il conserve le filtre de validation interne.

| Données | Exemples antérieurs | Durée de l'appel | Ordre des deux codes prédits |
| --- | ---: | ---: | --- |
| UTF-8 r1 | 15 | 11,285 s | Correct |
| UTF-8 r2 | Insuffisant | Aucun appel | Non évalué |
| Mandelbrot r1 | 13 | 5,475 s | Incorrect |
| Mandelbrot r2 | 21 | 5,675 s | Correct |

**Deux classements corrects sur trois ne constituent pas une validation de
performance.** Le cas Mandelbrot r1 passe même la validation interne avant de
mal classer les deux nouveaux codes : ce filtre reste fragile avec peu de données.
Ce diagnostic a un budget séparé et n'a changé aucune décision de recherche.
TabPFN conditionne ses prédictions sur des exemples ; ses poids et ceux de Luna
n'ont pas été entraînés pendant cette étude.

[Requêtes, réponses et diagnostic](results/evidence/offline-diagnostic/diagnostic.json).

## Vérifications et portée

- 1 057 tests Python réussis, deux ignorés, aucun échec dans la suite finale
  ROMEO ; neuf tests JavaScript réussis ; Ruff réussi.
- Les 89 sources Python testées sont celles des campagnes. Les quatre paires
  utilisent le même moteur figé. L'audit des configurations ne trouve que les
  différences prévues : activation du conseiller et identités isolées.
- Bases et conversations neuves par essai. Mémoires personnelles Codex et
  instructions utilisateur locales désactivées ; aucun ancien optimisé importé.
- Luna est appelé directement depuis ROMEO avec OAuth ; ses poids sont hébergés
  par le service. TabPFN effectue ses inférences CPU sur le nœud ROMEO. Aucun relais
  PC ne participe à la recherche.
- UTF-8 et Mandelbrot CPU uniquement. SGEMM CUDA et le runtime ARM ne sont pas
  couverts par cette comparaison.

[Validation complète](../../docs/VALIDATION-TABPFN-20261025.md) ;
[empreintes des archives originales](../../evidence/tabpfn-integration-20261025/comparison-archives.json) ;
[audit des copies sélectionnées](results/evidence/copy-manifest.json).

Les sept codes livrés sont sous
[`results/evidence/pairs/`](results/evidence/pairs/), dans les dossiers
`advisor_on/confirmed-code/` ou `advisor_off/confirmed-code/` de chaque paire.
Les poids, jetons d'authentification et autorisations ne sont pas dans le dépôt.

## Conséquence pour la suite

Le point d'intervention actuel — départager des mesures déjà prêtes — est trop
peu sollicité ici. Un conseiller utile devra être évalué sur un choix réellement
présent dans la boucle, par exemple parmi plusieurs propositions avant admission,
tout en laissant les mesures réelles décider des récompenses et de la livraison.
Cela demandera une nouvelle version et une nouvelle comparaison ; ces résultats
ne justifient pas d'activer TabPFN par défaut.

Il faut également traiter séparément la classification des timeouts de programme
et la récupération après une sortie Mother incomplète. Changer le validateur
exigera un nouveau protocole. Les résultats actuels restent la trace de la version
effectivement testée.

Le contrôle d'approbation automatique a refusé le redémarrage du serveur local,
avec « blocked by policy » et sans motif détaillé. L'ancien serveur reste en place ;
le nouveau backend et son option devront être chargés par un redémarrage autorisé.
