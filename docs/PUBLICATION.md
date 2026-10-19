# Contenu du dépôt privé

Ce dépôt rassemble la reconstruction isolée de R1 : sources, tests, helpers,
configurations, exemples, documentation et provenance de la base historique.
AB-MCTS-A reste le défaut ; le mode binaire est optionnel.

Les preuves conservées dans `artifacts/` comprennent les rapports de validation,
les deux wheels, la sauvegarde du code avant le mode binaire et les dossiers des
pilotes. Les journaux de génération, les registres, les mesures, les sources
retenues et les reçus permettent de relire les résultats officiels. Les premiers
essais synthétiques restent identifiés comme diagnostics et sont exclus de la
comparaison officielle.

Les environnements Python, caches, répertoires temporaires des tests et copies
intermédiaires de construction restent locaux. Les autorisations d'exécution et
les fichiers de possession des workers restent également locaux. Rien n'a été
supprimé pour publier le dépôt. Les preuves sont archivées sans conversion de
fins de ligne afin de conserver leurs empreintes.

Cloner ce dépôt ou lire les preuves ne relance aucune campagne. Pour travailler
sur le code, créer un environnement Python dédié, installer `.[dev]`, puis
exécuter `python tools/check.py`. Les pilotes requièrent de nouvelles sessions
et autorisations ; les identités historiques ne doivent pas être rejouées.

La dernière validation complète a donné 294 tests réussis, trois ignorés faute
de GCC/G++ sous Windows et Ruff sans erreur. Les résultats scientifiques et
leurs limites sont détaillés dans [la validation](VALIDATION.md) et dans
[le rapport du mode binaire](ARBRE-BINAIRE.md).
