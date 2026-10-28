# Installer et fabriquer Forest 0.2

La livraison est une application Python personnelle. Elle ne nécessite ni
compilation JavaScript ni service public. La wheel contient le moteur courant,
les adaptateurs et l'interface ; les données personnelles restent dans le
répertoire choisi par `--data`.

## Environnement figé

`requirements-windows-py313.lock` fige la fermeture des dépendances web et dev
de l'environnement Windows Python 3.13. `requirements-linux-py312.lock` contient
la résolution des mêmes versions avec les marqueurs Linux Python 3.12. Ce second
profil doit passer la CI Linux avant d'être présenté comme installé et vérifié.
Les fichiers sont des versions exactes, sans empreintes de wheels : ils ne
constituent pas un miroir immuable des paquets ni une garantie d'identité binaire.

Dans un environnement virtuel neuf, utiliser le fichier adapté, puis installer
la wheel locale sans résoudre une seconde fois les dépendances :

```powershell
python -m venv C:/forest-runtime
C:/forest-runtime/Scripts/python -m pip install -r requirements-windows-py313.lock
C:/forest-runtime/Scripts/python -m pip install --no-deps CHEMIN/hpc_forest_r1-0.2.0-py3-none-any.whl
C:/forest-runtime/Scripts/python -m pip check
C:/forest-runtime/Scripts/python -m hpc_forest.webapp --data C:/forest-data
```

Sous Linux, les exécutables du venv sont dans `bin/`. Le minimum déclaré Python
3.11 n'équivaut pas à une matrice testée de toutes ses versions.

## Fabriquer depuis une source propre

```powershell
python tools/check.py
python tools/build_release.py artifacts/release-NOUVEAU
```

Ces outils s'exécutent depuis le checkout du produit, qui contient les tests
et leurs fixtures. Les archives privées de calcul ne sont pas nécessaires.
Le sdist est une source installable du produit ; il n'inclut pas les données
personnelles ni l'infrastructure privée de recherche.

Le second outil exige une destination neuve, copie les sources dans un répertoire
de fabrication indépendant et construit sdist puis wheel. Il compare l'inventaire
et les octets du paquet avec `src/hpc_forest`, refuse les anciens modules advisor
et écrit `receipt.json` avec l'empreinte de la wheel. Il évite ainsi d'inclure un
ancien fichier de `build/lib` après une réorganisation. Aucune commande ne publie.
`SOURCE_DATE_EPOCH` fixe les dates internes de la wheel ; à défaut, l'outil prend
la date du commit de base et l'enregistre dans le reçu. Reprendre cette valeur
pour comparer deux fabrications du même contenu et du même environnement.

Les campagnes, sauvegardes, worktrees, expériences et environnements virtuels
n'entrent pas dans la distribution. `tools/dependency_inventory.py` régénère
l'inventaire depuis les métadonnées installées ; une mise à jour exige un nouvel
environnement vérifié, pas une modification arbitraire des versions figées.

## Vérification avant diffusion

La CI définit Windows/Python 3.13 et Linux/Python 3.12, GCC, Ruff, pytest, les tests
JavaScript et la fabrication. Elle est configurée mais n'est pas réputée exécutée
tant que son résultat n'a pas été observé. Les reçus locaux et les résultats
de CI doivent être distingués des anciennes mesures ROMEO conservées séparément.

Une livraison autorisée doit inclure un reçu de tests, la wheel vérifiée, les
versions figées, les notes de migration et les notices. Il reste à choisir et
vérifier les droits de distribution du projet et des entrées importées ; voir
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). L'usage commercial hébergé et les
comptes partagés ne font pas partie du déploiement validé.
