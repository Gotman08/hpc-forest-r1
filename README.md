# R1 — reconstruction isolée du moteur

Ce projet reprend la version figée de R1 utilisée pour les campagnes historiques.
Les 89 fichiers de départ ont été vérifiés avant copie. Le reçu est dans
docs/provenance-baseline.json ; la documentation originale est conservée dans
docs/reference/README-original.md.

Le travail porte sur le code : simplification, helpers partagés et correction des
validations. Par défaut, la méthode reste celle de R1 : mère de préparation puis
de synthèse, rôles A/B/C et intégration G, véritable TreeQuest AB-MCTS-A 0.3.2,
évaluateur externe et confirmations séparées. La lecture du code ne lance aucun
modèle, aucune campagne ni allocation.

## Organisation

| Emplacement | Responsabilité |
| --- | --- |
| src/hpc_forest/controller.py | Ordonnancement et vie de la campagne |
| src/hpc_forest/completion.py | Synthèse et intégration finales après fermeture des admissions |
| src/hpc_forest/search.py | TreeQuest et persistance ask/tell |
| src/hpc_forest/binary_search.py | Politique binaire gloutonne optionnelle |
| src/hpc_forest/mother.py | Préparation et synthèse de la mère |
| src/hpc_forest/node_harness.py | Développement borné d'un candidat |
| src/hpc_forest/assets/skills/ | Six skills génériques pour Mother, les enfants et la fusion |
| src/hpc_forest/model_skills.py | Chargement par rôle, empreintes et traces d'utilisation |
| src/hpc_forest/evaluator.py | Compilation, correction et mesures |
| src/hpc_forest/registry.py | Registre, réservations et consommation |
| src/hpc_forest/support/ | Sources bornées, échéances et validation numérique |
| tests/ | Régressions historiques et nouvelles gardes |
| tools/check.py | Vérification locale avec imports du nouveau projet |
| tools/prepare_smoke.py | Préparation d'un pilote officiel Luna MAX ; Count 2023 par défaut |
| tools/native_smoke.py | Pilote court ARM64 et worker local lié à sa seule session |
| tools/official_pilot.py | Sujet officiel avec le protocole complet du R1 historique |
| tools/compare_tree_reports.py | Comparaison contrôlée de deux rapports de politiques |
| docs/ | Provenance et décisions de reconstruction |
| artifacts/ | Reçus locaux de vérification, exclus des sources |
| experiments/ | Campagnes sélectionnées, sources gelées et résultats mesurés |

Les nouvelles campagnes `--mother-trees` chargent explicitement les skills adaptés
à chaque rôle, y compris pendant les réparations et la fusion dans la même
conversation Mother. Leurs contenus et les preuves de chargement, déclarations
du modèle et appels MCP observés sont décrits dans
[les skills des modèles](docs/SKILLS-MODELES.md).

## Développement

Python 3.11 ou supérieur et les dépendances de pyproject.toml sont nécessaires.
Utiliser un environnement Python propre au projet pour toute installation future.
Le module importé reste hpc_forest pour conserver les interfaces existantes ; la
distribution et la commande installée se nomment hpc-forest-r1.

Le point d'entrée de vérification est tools/check.py. Il vérifie Ruff puis les
tests, impose les sources de ce dossier aux sous-processus Python, et écrit ses
rapports dans un dossier neuf sous artifacts/. Les tests utilisent des doubles de
transport ; ils n'appellent pas de modèle hébergé.

Le contrôle local complet de la reconstruction a donné 252 réussites et trois
sauts faute de GCC/G++. La wheel reconstruite a été comparée aux 38 fichiers du
paquet. Les reçus détaillés sont conservés dans artifacts/.

Le pilote demandé porte sur un sujet officiel déjà étudié : **Number of Ways to
Traverse a Grid, Marathon 2023**. Il emploie la source initiale et les tests figés,
Luna MAX pour la mère et les fils, deux missions par rôle A/B/C/G, deux interventions
de la mère et le budget historique de 30 minutes et 1,5 million de tokens.

Le pilote AB-MCTS de reconstruction est terminé : huit candidats valides, onze appels Luna MAX
avec une réparation, 266 005 tokens exacts et un programme confirmé à 20,058 ms
contre 80,102 ms pour la source initiale, soit 74,959 % de réduction du temps.
L'ancien essai comparable atteignait 89,979 %. Le nouveau résultat est donc
inférieur sur cette exécution. Les conditions, limites de comparaison et preuves
d'isolement des branches sont dans [la validation](docs/VALIDATION.md).

Un exemple synthétique de matrices a été choisi à tort lors du premier contrôle.
Ses reçus sont conservés comme diagnostics du transport et sont exclus de toute
comparaison avec les résultats des sujets officiels.

## Fin de recherche

La durée cible est configurable (`30m`, `2h`, `5h`, `24h`, etc.). Les nouveaux
profils répètent les cycles sans plafond d'essais, avec une réserve recalculée
à partir des durées observées. Les modèles engagés finissent ; puis Mother
effectue sa synthèse finale, G produit son programme et **G final est toujours
inclus dans la confirmation indépendante**, en plus des finalistes ordinaires.
Cette séquence peut dépasser la durée cible. Aucun quota applicatif de tokens
n'est imposé. `python tools/prepare_smoke.py --duration 2h --mother-trees` prépare le prochain
profil Luna MAX avec N arbres choisis par Mother. Cette commande ne
lance aucun job. Le [contrat de fin de recherche](docs/FIN-DE-RECHERCHE.md)
décrit les prévisions de temps, la confirmation et les contrats historiques.

## N arbres choisis par Mother

Avec `--mother-trees`, Mother choisit le nombre d'arbres AB-MCTS et attribue un
sujet précis à chacun selon le code et le problème, sans recevoir la durée
cible ni le temps restant. **Tous les N arbres sont
lancés en parallèle**, sans réglage de concurrence distinct. Ils développent
leurs recherches selon le temps disponible. Ensuite, **la même conversation
Mother reprend et assemble les programmes deux par deux**, sans pouvoir lancer
ou relancer les arbres. Chaque fusion intermédiaire est mesurée ; la meilleure
entrée reste disponible si elle régresse. La compaction de l'historique reste
automatique dans Codex CLI, avec le même UUID. G final est mesuré puis confirmé
indépendamment. Le [fonctionnement de la forêt](docs/FORET-MOTHER.md)
décrit l'admission commune, le relais parallèle et les preuves de reprise.

Les nouvelles campagnes de ce mode donnent aussi à Mother et aux enfants accès
au **MCP-ROMEO existant**, avec le profil et l'identité SSH du fichier fourni au
relais par `--codex-config`. Les appels sont tracés ; le contrôleur conserve les
mesures officielles et Mother ne peut pas relancer les modèles pendant la fusion.
Les campagnes historiques ne changent pas d'accès.

Les nouveaux plans fournissent aussi un [accès aux références officielles](docs/DOCUMENTATION-OFFICIELLE.md)
NVIDIA, OpenMP, MPI, SIMD et compilateurs par le MCP `hpc_docs`. Le cache et les
preuves de lecture sont communs à Mother, aux N enfants et à la fusion finale.
La documentation du cluster reste servie par le MCP-ROMEO existant.

## Limites à conserver

Le [test CUDA N-corps du 21 octobre 2026](experiments/cuda-nbody-20261021/README.md)
archive les sources, le protocole, les contrôles et les résultats d'un lancement
Luna MAX avec quatre arbres parallèles et G final confirmé. Son rapport conserve
aussi la réserve encore prudente et l'échec de l'export standard, dont les sources
confirmées ont été récupérées. Il s'agit d'un cas historique, pas d'un lanceur GPU générique.

Un [mode binaire optionnel](docs/ARBRE-BINAIRE.md) est disponible pour les nouveaux
essais : `binary_tree.enabled=true` ou `init --binary-tree`. Il compare deux enfants
du même parent et poursuit le plus rapide parmi ceux qui sont corrects. AB-MCTS-A
reste activé par défaut ; `--no-binary-tree` permet de le choisir explicitement.
Les branches écartées restent dans les preuves. La mère conserve son rôle R1.
La suite logicielle du mode binaire passe avec 294 tests et Ruff. Son premier
pilote officiel confirme 71,776 % de réduction du temps contre 74,959 % pour
AB-MCTS-A, sur une paire par arbre : le mode actuel conserve donc le défaut.

Une réussite des tests logiciels ne démontre aucun gain HPC, aucune activation
native sur ROMEO et aucune conformité universelle aux énoncés. La conformité
algorithmique stricte d'un sujet demande son propre contrat : comparer les sorties
ne suffit notamment pas à imposer l'utilisation de quicksort.

Les résultats, caches, sessions, autorisations et intentions historiques ne sont
pas importés. Les transports hérités et les scripts d'exemples restent du code de
référence ; leur présence n'autorise pas leur exécution ni la réutilisation d'une
ancienne identité de campagne.
