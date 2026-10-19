# HPC Forest

Orchestrateur local de recherche HPC fondé sur le cahier des charges **« Sous-arbres AB-MCTS coopératifs », révision 3**. Le projet fournit une première version exécutable de la chaîne complète : missions, recherches persistantes, variantes Git isolées, évaluation, intégration, confirmation et archive de sources.

Le contrôleur utilise **TreeQuest 0.3.2 / AB-MCTS-A**. Le mode de démonstration transforme un vrai programme **C/OpenMP** sans appel à un LLM. Deux autres moteurs lancent des missions avec **Codex CLI** ou un modèle **Ollama local**, lorsqu'on les sélectionne explicitement.

## Préparation opérateur et sujets Marathon

La préparation technique appartient à l’opérateur : matériel, compilation, formats, entrées, oracle, tests et lancement. Le modèle de recherche choisit et écrit les modifications des programmes candidats. Aucun correctif manuel de candidat n’est appliqué. Le module [de contrats d’exécution](docs/execution-contracts.md) conserve notamment les sorties binaires en octets et les références figées.

Le [lanceur Marathon 2022](examples/marathon22/README.md) prépare et traite les quatre sujets officiels sur une allocation CPU ARM64 ROMEO avec modèle local sur GPU. Il fournit les diagnostics automatiques, les mesures, la confirmation indépendante et l’archive. Le mode de démonstration décrit ci-dessous reste un essai distinct avec recettes déterministes.

## Démarrer sous Windows

Dans ce dossier, avec Python 3.11 ou plus récent et Git :

```powershell
.\scripts\Setup.ps1
.\.venv\Scripts\python.exe -m hpc_forest doctor
.\scripts\Demo.ps1
```

Le script détecte Visual Studio/MSVC installé, ou un compilateur GCC/Clang présent dans le PATH. Pour MSVC, l'environnement de compilation est chargé uniquement dans les sous-processus. Le projet ne modifie pas le PATH global.

La démonstration crée un dossier neuf dans `runs/`. Elle réalise au maximum **39 créneaux de recherche + 3 de confirmation**. Elle produit un registre SQLite, les branches et worktrees, les journaux, un rapport et `submission.zip` avec son empreinte SHA-256. Le coût LLM du moteur de démonstration est zéro.

Sous Linux :

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,mcp]'
python -m hpc_forest doctor
python -m hpc_forest demo runs/demo
```

Un compilateur C avec OpenMP est nécessaire. La création refuse tout dossier déjà existant.

## Utiliser la chaîne pas à pas

```powershell
$py = '.\.venv\Scripts\python.exe'
& $py -m hpc_forest init runs\essai --config configs\demo.toml
& $py -m hpc_forest run runs\essai --max-batches 1
& $py -m hpc_forest status runs\essai
& $py -m hpc_forest run runs\essai
& $py -m hpc_forest confirm runs\essai
& $py -m hpc_forest report runs\essai
& $py -m hpc_forest package runs\essai runs\essai\submission.zip
```

La commande `run` reprend le registre existant. Un créneau réservé reste consommé après une interruption. Les mesures finales sont indépendantes : nouveaux cas de correction, reconstruction des commits et ordre entrelacé des chronométrages. Avec trois créneaux, la confirmation compare **la référence et les deux meilleurs candidats distincts**. Si aucun gain suffisamment grand n'est confirmé, la référence est conservée.

## Organisation de la recherche

| Rôle | Responsabilité |
|---|---|
| R / contrôleur | Ordonnancement, admissions, budgets et autorisations |
| A | Mémoire, localité, ordre des boucles et blocage |
| B | Vectorisation et dépendances |
| C | OpenMP et répartition du travail |
| D / E | Missions MPI / GPU, activées explicitement avec un protocole adapté |
| F | Corpus documentaire partagé, extraits bornés et sources versionnées |
| G | Combinaisons de variantes et mesure du programme complet |

La méthode H possède un arbre persistant par spécialité et un arbre G. La méthode U utilise un seul arbre avec les mêmes actions A/B/C/G, les mêmes sources et le même évaluateur. Les méthodes `H-no-feedback` et `H-enumeration` sont également disponibles. Chaque mesure de G ne met à jour que G ; ses sources reçoivent une observation d'interaction, sans duplication de score.

## Brancher Codex et un autre problème

```powershell
& $py -m hpc_forest init runs\codex --config configs\codex.toml
& $py -m hpc_forest run runs\codex --max-batches 1
```

Cette seconde commande lance de vraies missions Codex et utilise l'authentification de la CLI installée. Le modèle configuré par l'utilisateur est conservé ; aucun modèle n'est imposé par défaut. Le contrôleur limite les écritures acceptées à `src/` et conserve le prompt et les événements JSONL.

Pour importer son propre code :

```powershell
& $py -m hpc_forest init runs\mon-probleme --config mon-protocole.toml `
    --source C:\chemin\sources --validation C:\chemin\validation --backend codex
```

Le dossier source doit fournir `src/`, `Makefile` et `run.sh`. Le dossier de validation fournit les outils indépendants référencés par le protocole. L'import copie un instantané ; il ne modifie pas le dépôt d'origine. Voir [le contrat d'évaluation](docs/EVALUATION.md).

## Utiliser un modèle local

Avec Ollama démarré sur la machine et `qwen2.5-coder:7b` déjà téléchargé :

```powershell
& $py -m hpc_forest init runs\qwen7 --config configs\ollama.toml
& $py -m hpc_forest run runs\qwen7 --confirm
& $py -m hpc_forest report runs\qwen7
& $py -m hpc_forest package runs\qwen7 runs\qwen7\submission.zip
```

La configuration fournit un essai court de six créneaux de recherche, référence comprise, et trois de confirmation. Le backend impose une adresse de boucle locale, fige le digest des poids et la version du serveur, puis demande des fichiers complets en JSON structuré. Le contrôleur vérifie les chemins avant d'appliquer la réponse, ne lance aucune commande proposée par le modèle et conserve les compteurs réels d'Ollama. Une réponse tronquée ou invalide reste un échec documenté.

Sur ROMEO, Ollama tourne dans l'allocation GPU. Le protocole de démonstration mesure le programme C sur CPU ; le GPU sert à l'inférence. Voir [les essais et le mode opératoire ROMEO](docs/ROMEO.md).

## État et périmètre

Le périmètre livré et ses preuves sont détaillés dans [VALIDATION.md](docs/VALIDATION.md) et [la correspondance au rapport](docs/ACCEPTATION.md). Les campagnes locales démontrent le fonctionnement du logiciel. Elles ne démontrent pas la supériorité scientifique de H sur U. Le moteur Codex est vérifié par contrat et par tests simulant ses événements ; aucune campagne LLM payante n'est nécessaire au démarrage.

Le raccordement à un concours précis demande son programme, ses tests et sa cible. Les règles 2025 du rapport restent historiques. Les scripts génériques de cluster sont des modèles à adapter. Les essais locaux de modèles sur ROMEO sont documentés séparément ; aucune soumission de concours ou publication distante n'est effectuée.

Le budget global de tokens est un **contrôle d'admission et d'arrêt à partir des compteurs remontés** : une mission peut dépasser sa réservation avant de rendre son compteur. Ollama borne aussi chaque réponse avec `num_predict`. Un compteur manquant est signalé, imputé à hauteur de la réservation et bloque la suite des générations. Voir [BUDGETS.md](docs/BUDGETS.md).

## Documentation

- [Architecture et persistance](docs/ARCHITECTURE.md)
- [Contrat de compilation, correction et mesure](docs/EVALUATION.md)
- [Budgets, arrêts et reprise](docs/BUDGETS.md)
- [Guide opératoire](docs/OPERATIONS.md)
- [Pilote comparatif U/H](docs/PILOT.md)
- [MCP et corpus documentaire](docs/MCP.md)
- [Adaptation Linux / Slurm](cluster/README.md)
- [Modèles Ollama et essais ROMEO](docs/ROMEO.md)
- [Sources et versions](sources/README.md)

## Vérifier et construire une distribution

```powershell
& $py -m pytest
& $py -m ruff check src tests
& $py -m build
```

Les tests de bout en bout compilent du C et ont besoin du compilateur. Ils sont signalés comme ignorés si ce prérequis manque. Les autres tests contrôlent notamment l'idempotence, les budgets, la reprise, les preuves d'intégration et la protection des validations.
