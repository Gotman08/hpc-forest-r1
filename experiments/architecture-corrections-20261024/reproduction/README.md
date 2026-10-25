# Reproduction et portée

Le moteur et ses tests exacts sont conservés dans `moteur-et-tests.tar.gz`. `engine-files.json` donne les SHA-256 du paquet exécuté. Le commit de base et le manifeste sont dans `implementation.json`.

Dans un nouveau clone du commit de base, extraire cette archive, puis installer les dépendances déclarées par `pyproject.toml`, puis exécuter `python -m pytest` et `python -m ruff check src tests`. Le journal JUnit complet est conservé.

Les comparaisons contiennent les exports immuables disponibles (sélection et G final des trois générations ; une absence est explicite dans le manifeste), les empreintes des protocoles, le pilote de comparaison, les blocs bruts et l’environnement observé sur le nœud de calcul. Les chemins ROMEO des scripts désignent les suites protégées de la campagne historique. Ne pas substituer un compilateur ou un pilote sans créer un nouveau protocole.

Les archives complètes, registres et journaux des tentatives restent dans le dossier de travail local. Les conversations natives privées et les identifiants d’accès du relais ne sont pas copiés dans le dépôt.
