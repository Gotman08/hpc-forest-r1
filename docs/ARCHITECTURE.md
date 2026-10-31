# Architecture du produit Forest 0.2

Un seul contrôleur orchestre chaque campagne. L'application prépare un contrat
et transporte une copie figée du même paquet sur ROMEO. Les expériences
archivées ne sont pas incluses dans la wheel.

| Domaine | Modules | Frontière |
|---|---|---|
| Recherche | `search/` | Une proposition TreeQuest par admission ; seuls les résultats mesurés passent à `tell` |
| Orchestration | `controller.py`, `forest_scheduler.py`, `active_scheduler.py`, `completion.py` | Concurrence des générations, drainage, intégration et confirmation |
| Contrôle scientifique | `active_*.py`, `mother*.py` | Décisions versionnées ; analyses et citations distinguées des mesures |
| Évaluation | `evaluator.py`, `toolchain.py`, `submission.py` | Compilation, correction, mesure et exécutable exact |
| Preuves | `registry.py`, `memory/`, `evolution_archive.py`, `reporting.py` | Registre transactionnel ; mémoire issue de ce registre ; rapports |
| I/O durable | `storage/`, verrou OS de `core.py` | Publication atomique, sauvegarde SQLite et restauration vérifiée |
| Modèles | `codex_*.py`, `model_*.py`, `request_pool.py`, `ollama_backend.py` | Identité figée, requêtes et reçus ; aucune attribution de score par le modèle |
| Application | `webapp/api.py`, `projects.py`, `store.py`, `campaigns.py` | API locale, import comme données, consultation sans pickle |
| ROMEO | `webapp/execution.py`, `remote_runner.py`, `runner_support.py`, `project_protocol.py` | Plan et soumission explicites, exécution autonome, collecte |

L'API `hpc_forest.search.Search` et les points d'entrée CLI sont conservés.
Les modules internes `memory_*`, `search_policy`, `search_baselines`,
`search_diagnostics` et `binary_search` ont été regroupés ; les outils et tests
suivent les nouveaux chemins. Les reproductions historiques utilisent leur
révision figée. Les autres fichiers conservent leurs noms pour limiter les
changements sans valeur fonctionnelle.

Les parents de recherche et de délégation et les sources d'intégration restent
distincts. Un échec d'infrastructure ne porte pas de score ; un programme
incorrect reçoit zéro. Une combinaison est évaluée comme nouveau programme.
Les validations importées ne sont pas modifiées pour accepter un candidat.
Les réserves finales et la confirmation restent des phases séparées.

Une campagne fige cible, compilateur, protocole, dépendances, code contrôleur
et modèle. Une reprise vérifie ces identités. Les anciennes clés du conseiller
sont refusées à l'exécution ; `compatibility.py` ne contient que refus, copie
explicite et lecture historique.

## Protocole d'évaluation 2

Les nouvelles campagnes figent `protocol.version = 2` ; une configuration figée
sans version garde le protocole 1, y compris à la reprise.

- **Faute ou panne.** Le binaire est compilé depuis un export exact du commit et
  s'exécute hors du worktree. Un délai dépassé, une écriture dans les sources, un
  exécutable modifié ou un code de sortie du candidat reçoivent 0. Seul
  l'outillage (runner, sonde, stockage) produit le code 70 et un score absent.
- **Disjoncteur.** La recherche s'arrête après `budget.infrastructure_breaker`
  pannes consécutives (3 par défaut). En confirmation, une panne n'écarte que le
  finaliste concerné ; sans référence, la confirmation est réessayée.
- **Mesures vérifiées.** Chaque exécution chronométrée est comparée à la sortie
  stable de la référence, avec une tolérance numérique de 1e-9, ou au
  vérificateur `protocol.benchmark_verify` lorsqu'il est configuré
  (`contract_tool.py verify` pour un contrat à tolérances). Une référence instable
  est enregistrée comme non vérifiable, jamais supposée correcte.
- **Statistique.** Les décisions utilisent la médiane. Après la confirmation, le
  vainqueur et la référence sont remesurés en série entrelacée neuve ; la
  promotion exige une borne basse bootstrap à 95 % du gain au moins égale à
  `minimum_gain`. La série et sa décision sont durables.
- **Calme.** Les compilations de développement attendent le verrou de la cible :
  aucune ne tourne pendant une mesure.
- **Confirmation cachée.** Les graines de confirmation du vérificateur par défaut
  sont tirées au moment de chaque confirmation ; un contrat ne stocke plus les
  sorties attendues de confirmation, recalculées par la référence protégée.

## Persistance

`staging → planned → submitting → queued → running → confirming → completed`.
`submitting` est écrit avant la requête réseau. Après résultat inconnu,
la réconciliation cherche l'identité existante sans nouvelle soumission.
Une transition conditionnelle SQLite empêche deux lecteurs d'utiliser le même
état `planned`. Des verrous OS protègent chaque lancement et instance locale.

Les mises à jour par champ utilisent `BEGIN IMMEDIATE`. L'installation d'une
vue et son lien à la mission sont enregistrés ensemble. Les fichiers complets
sont publiés par remplacement atomique sur le même volume, après synchronisation
du contenu temporaire. POSIX synchronise aussi le répertoire ; Windows ne
fournit pas ici cette dernière opération. Les refus transitoires Windows ont
une reprise bornée, sans effacement du fichier précédent.

Une restauration peut être plus ancienne qu'une soumission réelle. Ses missions
inachevées deviennent `recovery_required`. « Reprendre le suivi » recherche ou
suit le job existant ; cette action ne recrée pas une allocation.
