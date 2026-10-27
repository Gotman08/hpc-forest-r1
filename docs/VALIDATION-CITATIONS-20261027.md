# Validation du schéma de citations avec Luna Max

Ce rapport conserve la validation du contrat v3. La validation du contrat v4
actuellement déployé est dans [le rapport de reprise](VALIDATION-REPRISE-20261027.md).

Le 27 octobre 2026, le premier pilote réel a révélé un défaut absent des réponses
simulées : les champs `evidence_id`, `path` et `sha256` partageaient le même objet
de schéma. `deepcopy` conservait cet alias et le dernier remplacement de `enum`
rendait les identités incompatibles avec le validateur. Les réponses Luna
conformes à ce schéma étaient donc rejetées.

La correction remplace chaque propriété avant de la spécialiser. Le contrat
actif passe à `hpc-forest-active-v3-citation-identities` afin d'éviter une reprise
silencieuse d'une campagne créée avec les anciennes contraintes.

## Vérifications terminées

| Vérification | Résultat |
|---|---|
| Reproduction du défaut | Les trois nouveaux tests échouent avant correction |
| Régressions ciblées après correction | 65 tests réussis ; 17 min 32 s |
| Suite Python complète après correction | 1 145 réussis, 0 échec, 3 ignorés ; 1 148 collectés |
| Temps pytest | 37 min 22 s ; 37 min 25 s pour le processus de validation |
| Empreintes des sources et tests avant/après | Identiques |
| Ruff sur le moteur et les tests | Réussi |
| Vérification des espacements du diff | Réussie |
| Rapports réels Luna acceptés | Au moins un dans chacune des quatre recherches relancées |

Les nouveaux tests vérifient le schéma natif transmis à Luna et sa compatibilité
avec le validateur de sources, pour les analystes et pour Mother. Ils vérifient
aussi l'indépendance des propriétés, pages et requêtes successives.

Preuves : [résultat complet](../evidence/citation-schema-20261027/result.json),
[manifeste](../evidence/citation-schema-20261027/manifest.json),
[journal](../evidence/citation-schema-20261027/pytest.log),
[JUnit](../evidence/citation-schema-20261027/pytest.xml),
[Ruff](../evidence/citation-schema-20261027/ruff.log),
[régressions avant/après](../experiments/quality-luna-20261027/defect-evidence/),
[rapports réels acceptés](../experiments/quality-luna-20261027-r2/live-citation-proof.json).

Les trois sauts sont explicites : deux tests de déplacement/préservation avec
liens symboliques POSIX sous Windows et le mode facultatif AB-MCTS-M sans son
environnement. Les campagnes présentes utilisent AB-MCTS-A. Un avertissement
de dépréciation Starlette/httpx subsiste dans un test web réussi. Les neuf tests
JavaScript de la [validation précédente](VALIDATION-QUALITE-20261027.md) restent
la preuve pour l'interface, qui n'a pas changé dans cette correction.

## Preuves réelles et limites

Les quatre premières recherches ont été arrêtées après identification du défaut,
puis archivées sans effacer leurs journaux. Les quatre nouvelles recherches ont
des mémoires et conversations neuves, le même plan initial par problème et les
mêmes budgets. Tous les rôles LLM utilisent GPT-6 Luna, effort max, directement
sur ROMEO. Aucun candidat ni conseil algorithmique de l'opérateur n'est injecté.

Le [pilote relancé](../experiments/quality-luna-20261027-r2/README.md) compare GEMM
CPU et Black–Scholes avec et sans conseiller. Il reste distinct de la tentative
interrompue. Une citation acceptée prouve sa provenance et ses bornes, pas la
justesse sémantique de toute l'analyse. Une réponse réelle contenant cinq
citations pour une conclusion limitée à quatre a notamment été refusée ; ce
refus est conservé et n'a pas entraîné de relâchement du validateur.

La validation logicielle et les premiers rapports acceptés ne prouvent pas un
gain de speedup. Les trois programmes livrés par R2 ont ensuite été comparés par
une [remesure commune](../experiments/quality-luna-20261027-r2/README.md).
Une seule paire par problème reste un pilote de fonctionnement.
