# Validation des corrections du 27 octobre 2026

Ce rapport conserve la première qualification locale. Le pilote réel a ensuite
révélé un défaut d'alias dans le schéma des citations. La
[validation après correction](VALIDATION-CITATIONS-20261027.md) compte
1 145 tests réussis et des rapports réels Luna acceptés sur les quatre recherches.

Validation locale terminée : **1 142 tests Python réussis, aucun échec, trois tests
ignorés**, puis Ruff et les neuf tests d'interface réussis. Durée de la suite
Python : **24 min 29 s**. Les empreintes des fichiers testés sont vérifiées à la fin.

## Périmètre

Les [corrections](CORRECTIONS-QUALITE-20261027.md) conservent un seul Forest,
le véritable TreeQuest 0.3.2, les récompenses de l'évaluateur et les confirmations
indépendantes. Le défaut des rôles LLM est `gpt-6-luna`, effort `max`.
TabPFN reste un conseiller facultatif dans ce contrôleur.

Contrats testés : `hpc-forest-active-v2-evidence` et
`forest-tabpfn-advisor-v3-runtime-evidence`, avec 94 caractéristiques.

## Environnement et commandes

Validation locale sous Windows 11, Python 3.13.12, GCC de MSYS2 UCRT64.
Les versions et les empreintes des sources et tests sont conservées dans
[le manifeste](../evidence/quality-corrections-20261027/manifest.json).

```text
python -m pytest -q -ra --durations=12 --junitxml=evidence/quality-corrections-20261027/pytest.xml
python -m ruff check src tests
node --test tests/test_web_frontend.mjs
git diff --check
```

| Vérification | Résultat |
|---|---|
| Suite Python complète | 1 142 réussis, 0 échec, 3 ignorés ; 1 145 collectés |
| Ruff, moteur et tests | Réussi |
| Interface JavaScript | 9 réussis, aucun échec |
| Diff : erreurs d'espacement | Aucune |

Preuves : [journal Python](../evidence/quality-corrections-20261027/pytest.log),
[JUnit](../evidence/quality-corrections-20261027/pytest.xml),
[Ruff](../evidence/quality-corrections-20261027/ruff.log),
[interface](../evidence/quality-corrections-20261027/frontend.log),
[résultat et vérification des empreintes](../evidence/quality-corrections-20261027/result.json).

Tests ignorés explicitement : deux scénarios de déplacement d'archives et de
worktrees avec liens symboliques POSIX, non applicables sous Windows ; un scénario
du mode facultatif AB-MCTS-M, dont l'environnement `sakana-m` et `numpyro` ne sont
pas installés dans cet interpréteur. Ce mode n'est pas utilisé par la configuration
Luna Max / AB-MCTS-A testée. Aucune dépendance n'a été installée pour masquer un saut.

Un avertissement de dépréciation provient de `starlette.testclient` utilisant
`httpx` lors du test de l'API d'import. Le test réussit ; cet avertissement ne
concerne pas le contrat du conseiller et les dépendances web n'ont pas été changées.

## Régressions couvertes

- La valeur logarithmique distingue des speedups élevés sans modifier la
  récompense transmise à TreeQuest. Les prévisions impossibles, valeurs non
  finies et contextes incompatibles sont rejetés.
- Les caractéristiques sont capturées avant la génération. La filiation,
  les dates, le protocole et les parents distincts protègent la validation.
  Une meilleure erreur que le repère parent et une marge suffisante sont exigées.
- Un contexte sans parents ou paires comparables ne lance pas de worker et ne
  lit pas de poids. Le repli conserve la proposition TreeQuest et son état.
- Les temps par configuration conservent leur provenance. Un changement
  d'identité d'entrée ne devient pas un speedup ; les données manquantes ou
  partielles ne deviennent pas des temps nuls.
- L'analyste reçoit le point d'entrée tardif d'un fichier. Les citations sont
  limitées aux versions et aux lignes réellement exposées.
- Mother reçoit les lignes citées par ses analystes, même lorsque ces références
  ont quitté la première page du catalogue. Un ID connu ne suffit pas à citer
  des lignes non lues ; les pages explicites permettent de compléter le dossier.
- Une hypothèse « testée » exige une comparaison parent-enfant mesurée et liée
  à son code. Une mesure arbitraire ou une opinion seule ne ferme pas la recherche.
- Une nouvelle branche doit disposer de temps pour l'essai et sa revue. Les
  résultats tardifs et les reprises conservent les protections de clôture.
- Les anciens exemples restent consultables sans alimenter le nouveau contrat.
  La reprise d'une campagne avec un moteur incompatible est explicitement refusée.
- Les parcours intégrés utilisent de vraies compilations C, TreeQuest et des
  confirmations. Les réponses des modèles sont simulées de manière déterministe,
  avec et sans conseiller activé, y compris des pannes et une intégration invalide.

La première exécution de la suite a été interrompue pour traiter une fixture
de version périmée et un problème de visibilité des références d'analystes pour
Mother. Le [journal initial incomplet](../evidence/quality-corrections-20261027/pytest-initial-incomplete.log)
est conservé ; il ne constitue pas la validation finale. La suite finale est
relancée sur des fichiers figés, sans modification du moteur pendant son exécution.

## Limites

Aucun nouveau résultat de performance ROMEO n'est produit par cette vérification.
Les tests logiciels ne démontrent pas que TabPFN choisit de meilleurs parents ou
que Luna produit systématiquement un meilleur programme. Il n'y a pas de nouvel
appel réel à Luna ni de nouvelle inférence TabPFN sur ROMEO dans cette validation.

La qualité sémantique d'une analyse ne peut être prouvée par une citation valide.
Les signaux statiques ajoutés ne sont ni un profileur ni une analyse complète des
chemins exécutés. Les diagnostics temporels dépendent de ce que les journaux
d'évaluation fournissent ; leur absence reste explicitement signalée.

La validation du conseiller est prudente : elle peut laisser TreeQuest seul
pendant une grande partie d'une petite recherche. Il faut mesurer le coût réel,
les décisions, les taux de refus et les performances finales sur une nouvelle
campagne à budgets comparables et mémoires neuves avant de conclure à un gain.

Les preuves et candidats de la tentative contrôlée 2 restent inchangés. Les dix
sources moteur citées par son diagnostic ont été conservées depuis l'archive
testée, après comparaison de leurs SHA-256, dans
[engine-attempt-2](../experiments/controlled-advisor-20261026/analysis-20261027/engine-attempt-2/).
Le [contrôle de préservation](../evidence/quality-corrections-20261027/historical-preservation.json)
confirme les empreintes des trente programmes livrés et de ces dix fichiers moteur.
