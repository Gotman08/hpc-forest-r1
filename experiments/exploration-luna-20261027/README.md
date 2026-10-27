# Forest : essais et diversité, Luna Max

État : **terminé le 28 octobre 2026**. Les huit recherches ROMEO (786906–786913) et la remesure commune (786914) sont achevées et auditées : 639 essais corrects sur 642, huit codes livrés et aucun échec d'infrastructure.

Le nombre moyen d'essais corrects par recherche augmente de 65,5 % face à la référence historique R3. Les performances finales restent variables. TabPFN effectue 13 appels, dont un validé, et ne change aucun choix ; son bénéfice n'est pas démontré. La régression Black–Scholes de la seconde répétition est incluse.

Lire le [rapport complet et les résultats comparés](RESULTATS.md), les [résultats CSV](results/arms.csv) et l'[audit final](results/final-verification.json). Les [huit codes livrés](delivered-codes/) sont conservés sans retouche.

Cette étude conserve un seul Forest et `gpt-6-luna` avec l'effort `max`. Elle compare TabPFN activé/désactivé dans le même moteur corrigé : revues de progrès non répétées inutilement, bilans ordinaires regroupés avant Mother, archive de sources activée dans les deux conditions.

GEMM CPU et Black–Scholes ont chacun deux répétitions indépendantes par condition. Chaque paire utilise le même plan initial de Mother, les mêmes entrées et la même cible de temps de 5 400 s, avec un plafond total de 7 200 s. Les campagnes ont des mémoires et conversations neuves. Les huit codes finaux ont été remesurés séquentiellement sur une allocation commune, avec les entrées enregistrées et réservées. Égalité des budgets configurés ne signifie pas égalité des temps consommés ou des tokens.

- [Protocole avant lancement](protocol.json)
- [Contrôle des quatre paires](paired-configuration-audit.json)
- [Plan SLURM préparé](pipeline-prepared.json)
- [Empreintes des transferts](upload-receipts.json)
- [Détails des corrections et validation](../../docs/VALIDATION-EXPLORATION-20261027.md)
- [Mesures de référence R3](baseline-r3/)

Les textes de code distincts et les identités de parents sont des indicateurs limités : ils ne démontrent pas une diversité algorithmique. Les durées des appels aux modèles se chevauchent avec la recherche. Les comparaisons avec R3 restent descriptives, car tout le lot de corrections change ; les paires internes comparent l'activation du conseiller, sans masquer la condition ni contrôler l'aléa du modèle. Deux répétitions ne permettent pas une attribution causale générale.
