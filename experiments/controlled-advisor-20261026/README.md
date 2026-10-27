# Comparaison contrôlée du conseiller TabPFN

Étude lancée le 26 octobre 2026 pour distinguer les effets du plan initial de
Mother, du contexte fourni au conseiller et de sa validation. **Un seul Forest**,
avec GPT-6 Luna, effort max, pour tous les rôles LLM.

**Tentative 2 terminée — [résultats et limites](RESULTATS-TENTATIVE-2.md).**
Les trente recherches ont livré ; la remesure commune a terminé le 27 octobre
à 04 h 57, avec zéro erreur d’audit. Le conseiller actuel donne +5,1 % de speedup
moyen sur GEMM et −20,0 % sur Black–Scholes par rapport à Forest sans conseiller,
sur les entrées de recherche. Trois répétitions par condition : aucune supériorité
générale démontrée. [CSV](results-attempt-2/comparison/arms.csv) · [Suivi](SUIVI.md).

[Analyse complète des régressions](ANALYSE-REGRESSIONS-TABPFN.md) : codes livrés,
prédictions, données, Mother, analystes, coûts et fermetures. Les calculs
reproductibles et les sources livrées sont conservés dans `analysis-20261027/`.

La tentative 1 reste conservée : six recherches interrompues par une panne de
stockage, vingt-quatre non démarrées, aucune livraison finale ni comparaison valide
des speedups. [Résultats et diagnostic](RESULTATS-TENTATIVE-1.md).

| Condition | Conseiller | Données d'apprentissage en contexte | Validation |
|---|---|---|---|
| `off` | Désactivé | Aucune intervention | — |
| `current` | Actuel | Campagne, protocole et epoch courants | Classement des gains v2 |
| `data` | Actif | Même arbre uniquement | Classement des gains v2 |
| `validation` | Actif | Campagne, protocole et epoch courants | Validation des décisions renforcée |
| `both` | Actif | Même arbre uniquement | Validation des décisions renforcée |

Les caractéristiques du code et la cible de régression sont identiques entre
ces conditions : on teste ici **l'homogénéité du contexte**, pas une nouvelle
représentation sémantique du code ni un nouveau modèle. Les poids de TabPFN ne
sont pas réentraînés.

## Comparabilité

- GEMM CPU et Black–Scholes ; trois répétitions par condition, soit 30 recherches.
- Un plan nouvellement produit et relu par Luna par problème, repris à l'identique
  dans les quinze recherches correspondantes. Aucun plan n'est choisi pour son
  score : il n'existe encore aucun candidat à cette étape.
- Conversations Mother, sessions LLM et bases de données distinctes. Le plan
  partagé est leur seul apport commun issu de la préparation ; aucun code
  optimisé, échantillon TabPFN ou résultat d'une autre recherche n'est importé.
- Mother garde ensuite les décisions actives habituelles. Ces décisions peuvent
  transmettre les effets du conseiller ; elles ne constituent pas un facteur
  causal séparément randomisé.
- Graines TreeQuest 307, 401 et 503. Elles ne rendent pas Luna déterministe.
- Plafonds de 5 400 secondes de recherche et 7 200 secondes de bout en bout.
  Toute la préparation commune, échecs compris, est imputée à chaque recherche.
  Les durées effectivement consommées peuvent différer.
- Cinq CPU alloués par bloc : quatre pour le contrôleur et les programmes,
  un pour le worker natif OAuth. Même allocation pour les cinq conditions d'un
  bloc, exécutées successivement dans un ordre fixé avant le lancement.
- Même GCC 14.2, même oracle et mêmes tolérances. Nouvelles graines de données
  4409/5501 et entrées réservées distinctes, jamais transmises aux modèles.
- Remesure commune après la fin des six blocs, sur les entrées enregistrées puis
  réservées, sans sélectionner à nouveau un gagnant grâce aux entrées réservées.

Le placement est sur un nœud partagé : des interférences externes restent possibles.
Les répétitions de chronométrage ne comptent pas comme des recherches indépendantes.

## Validation expérimentale du conseiller

La variante renforcée garde des exemples récents du même arbre pour validation,
exclut de l'ajustement leurs empreintes de code parent, et n'utilise que les
observations disponibles avant leur capture. Elle exige cinq exemples antérieurs,
trois parents distincts dans chaque groupe et trois paires comparables entre
parents. Elle vérifie le classement des **scores des enfants**, puis exige une
erreur absolue moyenne inférieure à la prédiction « l'enfant vaut son parent ».

Pour changer le choix de TreeQuest, l'écart prédit doit dépasser
`max(0.005, 2 × erreur absolue moyenne de validation)`. Cette marge empirique
**n'est pas un intervalle de confiance**. Une prédiction hors de [0,1] provoque
un repli au choix initial ; elle n'est pas écrêtée pour créer une égalité à 1.

Ces critères conservateurs peuvent conduire à très peu d'interventions. Ce sera
un résultat à mesurer, pas une preuve automatique que cette variante est meilleure.

## Exécution et preuves — tentative 2

- Qualification réelle : **785405**, huit contrats vérifiés ; OAuth natif actif.
- GEMM : **785406, 785407, 785408** ; Black–Scholes : **785409, 785410, 785411**.
- Remesure : **785412**, après terminaison des six blocs, même en cas d’échec.
- [Soumission exacte](submission-attempt-2.json),
  [amendement de relance](AMENDMENT-03.md),
  [validation avant relance](VALIDATION-TENTATIVE-2.md),
  [audit des six démarrages](validation-attempt-2/first-six-starts.json).

## Exécution et preuves — tentative 1

- Qualification réelle de TabPFN : job **784835**. Rejeu de données historiques
  séparé des nouvelles campagnes ; il ne prouve aucun gain prédictif.
- GEMM : jobs **784836, 784837, 784838**.
- Black–Scholes : jobs **784839, 784840, 784841**.
- Remesure et tableaux après tous les blocs : job **784842**, dépendance `afterany`.
- [Protocole enregistré](protocol.json), [plans](plans/), [soumission](submission.json),
  [validation](VALIDATION.md), [amendement de préparation](AMENDMENT-01.md),
  [amendement de stockage](AMENDMENT-02.md).

Les programmes proposés sont générés et évalués par Forest. L'opérateur prépare
les contrôles expérimentaux et traite l'infrastructure ; il ne retouche pas les
candidats et n'ajoute pas de suggestion algorithmique pendant les recherches.

## Lecture des résultats

Comparer `current/off` à plan fixé ; puis `data/current` et `validation/current`.
`both/validation` et `both/data` indiquent si l'effet d'un changement dépend de
l'autre. Les ratios sont calculés par problème et par répétition, avec les taux
de livraison, tous les échecs, la médiane et l'étendue. Aucun résultat manquant
n'est transformé en speedup.

Trois répétitions réduisent la fragilité d'une seule paire, mais restent insuffisantes
pour revendiquer une supériorité générale. Cette étude est conditionnelle aux deux
plans communs : elle ne mesure pas à elle seule la qualité de tous les plans Mother.
