# Architecture active : campagne ROMEO du 24 octobre 2026

21 / 21 programmes ont terminé leur recherche. 57 / 57 lignes exécutables du tableau ont été remesurées ; les 5 lignes sans source ou données exactes restent explicitement indisponibles.

La campagne emploie le mode `full`, GPT-6 Luna avec l’effort `max`, une mémoire neuve par programme et les mêmes budgets nominaux que les essais précédents. Les anciens et nouveaux candidats sont ensuite comparés au naïf et à la référence dans une même allocation.

- [Rapport de comparaison](RAPPORT.md) : protocole, speedups publiés et remesurés, coûts, incidents et limites.
- [Diagnostic détaillé](ANALYSE.md) : chaque programme, chaque arbre, décisions de Mother et lecture des sources.
- [Classeur Excel](COMPARAISON-ROMEO.xlsx) : comparaison par formules et onglets de données filtrables.
- [Niveau face aux références les plus rapides du tableau](REFERENCES-LES-PLUS-RAPIDES.csv), pour chaque entrée remesurée.
- [CSV principal](COMPARAISON.csv) et [données JSON](RESULTATS.json) : toutes les valeurs et leur provenance.
- [Tableau de bord HTML](TABLEAU-DE-BORD.html) : filtres par programme et résultat ; ouvrir le fichier téléchargé dans un navigateur.
- [Graphique des gains et régressions](GAINS-REGRESSIONS.png), [SVG](GAINS-REGRESSIONS.svg) et [PDF](GAINS-REGRESSIONS.pdf).
- [Durées des campagnes et coût des échecs](DUREES-CAMPAGNES.png), [SVG](DUREES-CAMPAGNES.svg) et [PDF](DUREES-CAMPAGNES.pdf).
- [Matériel enregistré](ENVIRONNEMENTS.csv), [durées par phase](DUREES-PHASES.csv) et [tentatives préalables](TENTATIVES-PREALABLES.csv).

[Ressources SLURM](RESSOURCES-SLURM.csv) : allocations, heures CPU utilisées ou réservées et heures GPU réservées, séparées par périmètre.

Le dossier publié contient `campagnes/` pour les recherches retenues, `mesures/` pour les comparaisons appariées, `validation/` pour les contrôles, `moteur/` pour le code exact exécuté et `reproduction/` pour les scripts de cette étude. Les pilotes et tentatives interrompues restent conservés séparément. `MANIFESTE-PUBLICATION.json` recense les empreintes des fichiers et les exclusions.

Les gains et régressions sont tous conservés. Une recherche terminée par programme ne démontre pas une supériorité causale de l’architecture ; les répétitions de chronométrage mesurent la variabilité temporelle. Les échecs et relances ne sont pas gratuits : leur coût est publié séparément.
