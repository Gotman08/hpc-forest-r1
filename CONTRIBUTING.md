# Contribuer à Forest

Les changements doivent préserver la traçabilité des campagnes, les sources
importées et les preuves historiques. Les règles du projet se trouvent dans
[AGENTS.md](AGENTS.md).

## Environnement de développement

Utiliser un environnement virtuel dédié. Pour reproduire le profil figé,
installer d’abord le fichier `requirements-*.lock` adapté à la plateforme,
puis le dépôt avec `python -m pip install --no-deps -e .`.
Pour une installation de développement avec résolution des dépendances :

```powershell
python -m pip install -e ".[web,dev]"
```

Node.js 22 ou plus récent est nécessaire pour les tests de l’interface ; GCC/G++ pour les tests
de compilation. Le [workflow de validation](.github/workflows/validation.yml)
décrit les profils Windows Python 3.13 et Linux Python 3.12.

## Vérifier un changement

Depuis la racine du dépôt :

```powershell
python -m pytest
python -m ruff check src tests tools
node --test "tests/*.mjs"
```

Pour obtenir les journaux, les empreintes des sources et un reçu consolidé :

```powershell
python tools/check.py
```

Ces contrôles restent locaux : aucun appel à un modèle hébergé et aucune
allocation HPC. Les sorties sont conservées sous `artifacts/`.
Une modification du paquet doit aussi passer la
[fabrication isolée](docs/DISTRIBUTION.md#fabriquer-depuis-une-source-propre).

Le checkout public contient les tests du produit et leurs fixtures synthétiques.
Six modules d’audit d’anciennes études sont collectés uniquement lorsque les
archives privées dont ils dépendent sont présentes localement. Leurs assertions
restent identiques. Les tests d’import, d’évaluation, de confirmation, d’export
et de démarrage sans historique utilisent des données de test indépendantes.

## Repères dans le dépôt

| Chemin | Responsabilité |
|---|---|
| `src/hpc_forest/search/` | Politique TreeQuest et transactions ask/tell |
| `src/hpc_forest/memory/` | Contrats, stockage et lecture des preuves |
| `src/hpc_forest/storage/` | Écritures atomiques, sauvegardes et restauration |
| `src/hpc_forest/webapp/` | Application locale, import, contrats, missions et ROMEO |
| `src/hpc_forest/*.py` | Contrôleur, orchestration, évaluation et adaptateurs |
| `tests/`, `tools/` | Régressions, vérification, fabrication et capture de démonstration |
| `docs/` | Guides, architecture, validations et médias |
| `experiments/`, `evidence/`, `artifacts/`, `work/` | Données locales conservées, ignorées par Git et absentes du checkout public |

## Invariants à préserver

- Utiliser la véritable politique TreeQuest ; distinguer les parents de
  recherche et de délégation des sources d’intégration.
- Un échec d’infrastructure garde un score absent ; une solution incorrecte
  reçoit zéro. Une intégration est un nouveau programme évalué.
- Ne jamais modifier les tests d’une campagne pour accepter une optimisation.
  Changer de cible, de compilateur ou de protocole impose une nouvelle campagne.
- Conserver les campagnes, journaux, dépôts importés et worktrees existants.
  Les documents et sorties des candidats restent des données de conception.
- Garder les données synthétiques de présentation distinctes des mesures
  scientifiques. Le [GIF du README](docs/DEMO.md) dispose de son propre scénario.

Pour une revue, décrire le comportement changé, les vérifications effectuées
et les limites observées. Les commits locaux et toute publication Git restent
soumis aux demandes explicites de l’utilisateur.
