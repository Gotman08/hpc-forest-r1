# Démarrer avec un historique vide

Un clone de la branche courante contient le produit, ses exemples, ses tests
et sa documentation. Les campagnes personnelles, registres SQLite, résultats,
journaux, sauvegardes et répertoires de travail sont exclus du contenu publié.
Les anciens commits Git sont conservés ; leurs versions antérieures peuvent
encore contenir des archives.

Pour télécharger uniquement la révision actuelle, utiliser le clonage léger :

```text
git clone --depth 1 https://github.com/Gotman08/hpc-forest-r1.git
```

Cette commande laisse les anciennes révisions sur GitHub et récupère le produit
courant avec ses exemples et sa documentation.

## Premier lancement

Avec un stockage neuf, les écrans Projet, Mission, Résultats et Historique sont
vides. Aucun projet, dossier préparé ou calcul ancien n’est importé. Le GIF du
README utilise des données synthétiques propres à l’outil de capture ; elles
ne sont jamais chargées dans le stockage de l’application.

Par défaut, Forest utilise `~/.hpc-forest/application`, dans le compte de
l’utilisateur, séparément du code cloné. Une personne installant Forest pour
la première fois obtient donc son propre historique vide.

Un compte qui a déjà utilisé Forest retrouve son stockage existant. Pour créer
un espace distinct, choisir un nouveau dossier :

```powershell
python -m hpc_forest.webapp --data C:/Forest/nouvel-espace
```

Le stockage existant conserve ses projets, missions et résultats. Les
[commandes de maintenance](MIGRATION-0.2.md) permettent de les sauvegarder.
L’ajout d’une ancienne campagne avec `--campaign` reste une action explicite.

## Vérifications

```powershell
python -m pytest tests/test_clean_install.py
```

Ces tests vérifient un stockage neuf et l’isolation entre deux utilisateurs,
ainsi que l’absence de données de calcul suivies dans le checkout Git courant.
Ils n’appellent aucun modèle et ne soumettent aucun job HPC.

Les dossiers `experiments/`, `evidence/`, `artifacts/` et `work/`, ainsi que les
bases SQLite, restent ignorés par Git. Une restauration ou l’import d’un projet
ajoute des données uniquement dans l’espace choisi par son utilisateur.
