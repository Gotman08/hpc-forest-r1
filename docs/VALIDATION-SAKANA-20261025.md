# Validation de l'intégration Sakana — 25 octobre 2026

Cette validation porte sur les fonctions décrites dans [SAKANA-INTEGRATION.md](SAKANA-INTEGRATION.md).
Elle ne mesure pas une amélioration des speedups sur ROMEO.

## Portée

- Les cinq politiques principales passent un parcours local complet : génération
  par recettes de test, compilation réelle, vérification, recherche, confirmation
  et création de l'archive du code. Les modèles hébergés ne participent pas à ces
  tests déterministes.
- Le groupe optionnel de modèles est vérifié du contrat préparé au worker et à
  la commande Codex, avec un exécuteur de modèle simulé. Les identités autorisées,
  les rôles, les reprises et les refus de configuration incohérente sont testés.
- AB-MCTS-M est exercé avec le véritable TreeQuest et ses dépendances dans un
  environnement Python 3.11 isolé. Un essai de quatre générations et un test de
  sauvegarde/reprise passent. Sous Windows, le premier test pytest a révélé un
  chemin de cache PyTensor trop long ; il passe avec un cache court explicite.
- L'interface est vérifiée dans une instance distincte sur le port 8768, avec
  une copie cohérente du magasin de données. Le contrat mêlant trois modèles
  est préparé, sans soumission. Le projet de vérification est ensuite remis à
  Luna/max seul et AB-MCTS-A gaussien.
- La lecture d'une campagne ROMEO historique affiche correctement 23 essais de
  recherche : 13 depuis la racine, 10 depuis un parent, profondeur maximale 3,
  tous générés avec Luna/max. Il s'agit d'une preuve de compatibilité de
  l'affichage, pas d'une nouvelle campagne Sakana.

## Résultats automatisés

| Exécution | Résultat |
| --- | --- |
| Suite complète, avant les derniers correctifs | 996 réussites, 4 échecs, 1 test optionnel ignoré ; 1 149,64 s. |
| Relance ciblée après correction, incluant 13 nouveaux cas | 220 réussites, aucun échec, 1 test optionnel ignoré ; 396,11 s. |
| AB-MCTS-M avec ses dépendances, après correction | 1 réussite, aucun échec ; 13,96 s. |
| Interface JavaScript | 8 réussites, aucun échec. |
| `python -m ruff check src tests` | Réussi. |
| Construction du wheel et contrôle de son contenu | Réussi ; nouveaux modules, interface et extra `sakana-m` présents. |

Les quatre échecs de la première passe provenaient d'un accès à `.get()` avant
validation du type de `binary_tree`. Les quatre valeurs mal formées sont
maintenant refusées par une erreur de configuration explicite, et leurs tests
passent dans la relance ciblée. Cette relance vérifie aussi les paramètres de
modèles vides invalides, l'accès effectif des analystes à l'archive, les frontières
entre arbres et l'absence d'attribution d'un essai par recette à un LLM.

Il s'agit d'une suite complète suivie d'une relance des composants concernés,
pas d'une seconde exécution intégrale de toute la suite. L'avertissement restant
est une dépréciation de l'adaptateur de test Starlette/httpx.

Les rapports JUnit et le manifeste sont conservés dans
[`evidence/sakana-integration-20261025/`](../evidence/sakana-integration-20261025/).
Le manifeste compare les sources à leur sauvegarde au début de cette tâche,
car le dépôt contenait déjà des modifications.

![Réglages de recherche avec Luna Max par défaut](images/application-sakana.png)

### Commandes principales

```text
python -m pytest -q --junitxml=pytest-full.xml
python -m pytest -q tests/test_binary_search.py tests/test_sakana_search.py tests/test_sakana_active.py tests/test_evolution_archive.py tests/test_webapp.py tests/test_web_execution.py tests/test_active_architecture.py tests/test_active_corrections.py tests/test_active_pipeline.py tests/test_sakana_pipeline.py --junitxml=pytest-final-targeted.xml
python -m pytest -q tests/test_sakana_search.py -k optional_mixed_model_sampler_roundtrip --junitxml=pytest-optional-m.xml
node --test tests/test_web_frontend.mjs
python -m ruff check src tests
python -m build --wheel
```

Le test optionnel utilise l'environnement `sakana-m` isolé, avec un répertoire
court déclaré par `PYTENSOR_FLAGS`. Aucune variable globale du poste n'est modifiée.

## Limites

Aucun nouvel appel de génération hébergé ni allocation ROMEO n'a été effectué
pour cette intégration. Le profil ROMEO ne déclare pas encore le support de
AB-MCTS-M : l'application le laisse indisponible. Les autres politiques utilisent
la dépendance TreeQuest déjà requise par Forest.

La diversité lexicale aide à choisir des sources à examiner ; elle ne prouve
ni leur potentiel de gain ni la qualité de l'analyse d'un modèle. Pour mesurer
l'utilité réelle, il faut des campagnes répétées, à matériel, entrées, budget,
effort et protocole identiques, avec des mémoires neuves.
