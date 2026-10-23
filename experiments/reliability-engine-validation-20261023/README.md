# Vérification locale du harnais de fiabilité — 23 octobre 2026

Cette vérification couvre les cinq chantiers décrits dans [FIABILITE.md](../../docs/FIABILITE.md). Elle n'appelle aucun modèle distant et n'alloue aucun GPU. Les résultats des campagnes historiques restent distincts de ces tests fonctionnels.

## Résultats

| Contrôle | Résultat |
|---|---|
| Suite complète `python -m pytest` | 791 tests collectés : 790 réussis, une attente de configuration CLI obsolète |
| Reprise du test CLI après correction | 3 réussis : valeur par défaut de la critique (2), désactivation (0), valeur explicite (5) |
| Tests ciblés après correction de la réserve avant critique | 66 réussis |
| `python -m ruff check src tests` | Réussi |
| `git diff --check` | Réussi |

La suite complète a pris 824,68 secondes. Son unique échec provenait de l'égalité attendue du dictionnaire de configuration, qui ne contenait pas le nouveau champ `forest.plan_review_calls`. Le test unitaire a été actualisé et étendu aux deux options explicites. Aucun test de correction d'un programme candidat n'a été modifié.

Le dernier correctif du moteur réserve les intégrations du plan provisoire avant sa publication : N−1 fusions (au moins une) dans le mode deux par deux, sélection et tours nominaux de code dans le mode guidé par mémoire. Les tests ajoutés couvrent N=2, 20 et 600 et l'absence de plan/ordonnanceur encore enregistré. La suite complète n'a pas été répétée après ce correctif local ; les 66 tests ciblés portent sur les modules affectés.

## Commandes des reprises

```powershell
python -m pytest tests/test_mother_forest_launch.py -k cli -q
python -m pytest tests/test_mother_review.py tests/test_mother_review_budget.py tests/test_memory_budget.py tests/test_independent_budget.py tests/test_reserve_forecast.py -q
python -m ruff check src tests
git diff --check
```

Environnement : Windows, Python 3.13.12, pytest 9.1.1 ; exécutable du workspace `../../work/hpc-forest-mcp-venv/Scripts/python.exe`, `PYTHONPATH=src`. Les fichiers Python du moteur étaient figés pendant chaque exécution : leur empreinte fait partie de l'identité de cible, et une modification concurrente invalide légitimement les campagnes de test.

Les sorties de la suite complète et de la reprise budgétaire sont archivées dans ce dossier. Les trois succès CLI et les contrôles Ruff/diff sont consignés ci-dessus d'après leurs sorties d'exécution. Tous les nouveaux changements de code ont été commités localement par lots ; aucun push n'a été demandé ni exécuté. `A_FAIRE.md`, extérieur à ces lots, reste intact hors commit.

## Limite des conclusions

Ces tests vérifient la conservation des faits, des consultations et des budgets, les décisions et les compilations locales. Ils ne démontrent pas une meilleure régularité de Luna Max. L'outil de comparaison et la préparation de répétitions sont disponibles ; démontrer ce gain demande plusieurs campagnes indépendantes, repartant des programmes originaux, avec le même protocole et sans réinjecter les anciens candidats.
