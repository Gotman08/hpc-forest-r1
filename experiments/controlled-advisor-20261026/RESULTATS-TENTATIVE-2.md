# Résultats — tentative 2 terminée le 27 octobre 2026

Les **30 recherches ont livré** et la remesure commune a terminé à **04 h 57 min 30 s
(Europe/Paris)**. Les six blocs de recherche et le job de comparaison sont
`COMPLETED`, code de sortie `0:0`. La vérification finale indique zéro erreur
d’audit, trente conversations Mother distinctes et les deux plans initiaux attendus.

Un seul Forest, GPT-6 Luna effort max partout, mémoires neuves, sans relais du PC.
Les plafonds restent identiques : 90 minutes de recherche et 120 minutes de bout
en bout, préparation commune imputée. Les durées réellement consommées diffèrent.

## Speedups remesurés

Moyennes géométriques de trois recherches par condition et par problème.
Chaque nombre est le rapport du temps du programme naïf au temps du code livré.
Les entrées réservées n’ont pas été transmises aux modèles et n’ont pas servi
à sélectionner à nouveau un code.

| Condition | GEMM, entrées de recherche | GEMM, entrées réservées | Black–Scholes, entrées de recherche | Black–Scholes, entrées réservées |
|---|---:|---:|---:|---:|
| Sans conseiller (`off`) | 86,33× | 68,75× | 12,75× | 13,86× |
| Conseiller actuel (`current`) | 90,78× | 77,10× | 10,20× | 11,11× |
| Données du même arbre (`data`) | 89,02× | 72,02× | 9,04× | 9,83× |
| Validation renforcée (`validation`) | 85,07× | 67,46× | 8,46× | 9,17× |
| Données du même arbre + validation renforcée (`both`) | 93,76× | 75,51× | 6,29× | 6,84× |

Sources : [30 résultats individuels](results-attempt-2/comparison/arms.csv),
[agrégats](results-attempt-2/group-summary.json),
[contrastes appariés](results-attempt-2/comparison/paired-contrasts.csv),
[dispersion des contrastes](results-attempt-2/comparison/contrast-summary.csv).

## Ce que montre cette campagne

Pour le conseiller actuel par rapport au même Forest sans conseiller :

- **GEMM : speedup moyen supérieur de 5,1 %** sur les entrées de recherche,
  et de 12,1 % sur les entrées réservées. Cependant, il ne gagne qu’une paire
  sur trois sur les entrées de recherche, et deux sur trois sur les réservées.
- **Black–Scholes : speedup moyen inférieur de 20,0 %** sur les entrées de recherche,
  et de 19,9 % sur les réservées. Une paire gagne, deux perdent. Une baisse de
  speedup de 20 % correspond approximativement à un temps d’exécution 25 % plus long.

Les deux changements réunis (`both`) donnent +8,6 % de speedup sur GEMM mais
−50,7 % sur Black–Scholes, par rapport à `off`, sur les entrées de recherche.
Cette comparaison additionnelle est descriptive. Elle ne justifie pas une
recommandation générale sur la base de trois répétitions.

Les effets du changement de données seul et de la validation seule ne sont pas
uniformément favorables : sur les entrées de recherche, `data/current` vaut
0,981 pour GEMM et 0,886 pour Black–Scholes ; `validation/current` vaut
0,937 et 0,829 respectivement.

## Interventions réellement observées

Totaux sur les deux problèmes et leurs trois répétitions :

| Condition | Appels TabPFN | Changements de classement des parents |
|---|---:|---:|
| `off` | 0 | 0 |
| `current` | 151 | 60 |
| `data` | 89 | 55 |
| `validation` | 179 | 0 |
| `both` | 147 | 0 |

La validation renforcée n’a autorisé **aucun changement de classement**.
Les bons ou mauvais résultats de ces conditions ne prouvent donc pas un meilleur
ou un moins bon choix de parent par TabPFN. Les appels consomment néanmoins du
temps et les générations Luna ainsi que les décisions ultérieures de Mother
restent variables. Fixer le plan initial ne rend pas ces recherches identiques.

Pour cette raison, la régression de Black–Scholes ne peut pas être attribuée
uniquement à de mauvais changements de parent. L’étude isole les conditions
expérimentales ; elle n’identifie pas séparément tous les mécanismes causaux.

## Arrêts et diagnostics

- 21 recherches se terminent sur `final_reserve_or_deadline` : réservation de
  temps pour la clôture ou limite de recherche.
- 9 se terminent sur `reviewed_closure`, une clôture revue par la boucle de contrôle.
- Les plus courtes restent GEMM r2 avec validation renforcée (**38,04 minutes**)
  et Black–Scholes r2 sans conseiller (**40,88 minutes**). Ce sont des durées
  réelles de bout en bout, avant imputation de la préparation commune.
- Tous les résultats respectent leur plafond ; aucun échec d’infrastructure de
  candidat n’est recensé dans `arms.csv`. Le diagnostic `mother_broken` est faux
  pour les trente recherches.
- Les rapports recensent **44 tâches d’analyste indisponibles** au total.
  Ce compteur exige un examen des motifs dans les chronologies ; zéro erreur
  d’audit ne signifie pas que toutes les analyses demandées ont été produites.

Sources : [contrôle Mother](results-attempt-2/comparison/mother-control.csv),
[événements Mother](results-attempt-2/comparison/mother-events.csv),
[décisions du conseiller](results-attempt-2/comparison/adviser-decisions.csv),
[trajectoires](results-attempt-2/comparison/trajectory.csv).

## Preuves, conservation et limites

[Reçu de fin](results-attempt-2/completion.json),
[rapport automatique](results-attempt-2/comparison/RAPPORT.md),
[archives vérifiées sur ROMEO](results-attempt-2/recovered-archives.json),
[reçu du téléchargement vérifié](results-attempt-2/transfer-receipt.json).

L’archive des résultats, qui inclut les mesures et les codes remesurés, a été
rapatriée sur le PC : SHA-256
`82f268b9cf5d6012712a5f31de20e0a23c8fc0c5fdcb62ac25129fd4f721c895`.
Les trente archives complètes des recherches restent conservées sur ROMEO ;
ce téléchargement de résultats ne constitue pas leur copie complète hors cluster.

Les recherches partagent un nœud avec des CPU distincts. Trois répétitions par
condition et deux problèmes ne permettent pas de conclure à une supériorité
universelle, ni à une significativité non testée. Les répétitions de chronométrage
ne sont pas des recherches indépendantes. Mother reste un intermédiaire de la
boucle active, pas un facteur causal séparément randomisé.
