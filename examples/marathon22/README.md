# Adaptateurs et préparation de programmes

Ce dossier contient des exemples de préparation, des adaptateurs de transport
et des générateurs de jeux de test utilisés par les tests du produit.
Les campagnes, journaux et résultats personnels sont conservés séparément.

| Fichier | Usage |
|---|---|
| `archive_preparation.py` | Préparation de programmes et de leurs entrées de test |
| `archive_matrix.py` | Sélection et organisation des programmes préparés |
| `romeo_codex.py` | Adaptateur Codex pour une campagne explicitement configurée |
| `local_model.py` | Préparation et vérification d’un modèle local épinglé |
| `models/` | Spécifications de modèles, versions et empreintes |

Les tests locaux utilisent des fixtures indépendantes et des connecteurs simulés.
Pour utiliser les lanceurs avancés, consulter leurs options et préparer un
nouveau contrat avec ses propres sources, commandes, ressources et identifiants.
Toute allocation ou exécution distante exige une autorisation explicite.

Pour un premier projet, suivre le [guide de l’application](../../docs/APPLICATION.md).
Le [démarrage propre](../../docs/CLEAN-INSTALL.md) décrit le stockage personnel
et l’historique vide d’une nouvelle installation.
