# Investigation et profilage

Les nouvelles missions de l'application ROMEO vérifient la référence, exécutent
un diagnostic initial, puis interrogent Mother **avant** le choix des N sujets.
Cette investigation a son propre schéma : observations, hypothèses,
informations manquantes, prochaines mesures. Elle ne choisit ni N ni des sujets.
Le tour de préparation reçoit ce rapport comme une interprétation et peut
approfondir les preuves avant de définir la forêt. Aucun catalogue de recettes
d'optimisation n'est injecté. Les anciennes campagnes restent lisibles et ne
sont pas migrées implicitement.

Le contrat `investigation` est figé dans la nouvelle campagne. Valeurs par
défaut : douze collectes par requête, 120 secondes par collecte (attente du verrou,
compilation, test et analyse inclus), 300 secondes de validité par requête,
256 Mio de fichiers par collecte. La fin de recherche ferme les droits de
collecte ; l'assemblage lit les preuves déjà acquises. Ces limites encadrent
uniquement le diagnostic et ne changent pas la politique AB-MCTS ni le mode de
durée de la recherche.

Dans une campagne générique neuve, l’activation est explicite :
`"investigation": {"enabled": true, "require_allocation": true}`,
avec `backend: "codex"` et `forest.policy: "mother"`. L’application ROMEO
prépare cette configuration automatiquement pour les nouvelles missions.
`require_allocation: false` est réservé à un essai local choisi explicitement.
Hors application, l’intégrateur doit fournir `diagnostics_root` au `Worker`
sur le nœud où la campagne est montée. L’ancien relais CLI de fichiers depuis
le poste client ne transporte pas implicitement ce service : activer seulement
la configuration sans ce raccordement provoque un refus explicite.
Les contrôles reproductibles sont décrits ci-dessous. Leurs reçus restent dans
le répertoire local de validation choisi par l’utilisateur.

## Parcours effectif et permissions

`webapp.remote_runner.work` construit désormais `Worker` avec le MCP de
documentation et la racine locale de la campagne pour le MCP de diagnostic.
Chaque requête reçoit un grant du contrôleur : nonce, mission, session,
protocole, manifeste protégé, sources déjà évaluées et commits, rôle, échéance,
identité du nœud, allocation et affinité. Le worker vérifie son empreinte avant
de démarrer `python -m hpc_forest.diagnostics_mcp`.

`codex_process.command_for` active `code_mode_host`, marque le serveur comme
obligatoire et expose uniquement les outils accordés. L'environnement Python
du moteur est transmis explicitement, y compris pour un moteur extrait d'un
bundle ROMEO sans installation globale. L'environnement de calcul est conservé
sans les variables d'authentification usuelles. Les outils shell, les plugins
généraux, les applications et les autres agents restent désactivés. Un serveur
manquant ou un runtime MCP indisponible est une erreur d'interface, pas une
preuve de performance.

| Rôle | Sources | Lecture | Collecte |
|---|---|---|---|
| Mother, investigation et préparation | Programmes évalués du snapshot | Sources, interfaces et preuves paginées | Oui, dans le grant |
| Analyste vivant, Mother aux jalons | IDs visibles dans son dossier figé | Idem | Oui, diagnostic ciblé sur ces programmes |
| Générateur de recherche | Programmes évalués du snapshot | Idem | Oui ; aucun brouillon non évalué ni chemin arbitraire |
| Mother après fermeture | Programmes évalués | Idem | Non |

Un analyste peut donc reprendre une mesure après un essai qui laisse une
question ouverte. Ce droit ne donne aucun moyen de modifier un objectif, un
parent de recherche, une source d'intégration, les tests ou un score. Les
anciens outils ROMEO qui soumettent des jobs ne sont pas activés dans ce
parcours. Les diagnostics utilisent l'allocation courante seulement.

Une suspension bloque les nouvelles admissions, mais laisse terminer les essais
déjà engagés. Un progrès mesuré tardif peut rouvrir l'arbre avant sa clôture.
Lorsqu'un nouvel essai tient encore dans le budget, un arbre de
recherche conserve une fenêtre de trois programmes évalués pour distinguer
un premier échec d'une piste épuisée. Les échecs d'infrastructure sans score
ne remplissent pas cette fenêtre. Les intégrations intermédiaires conservent
leur contrat d'un seul programme. TreeQuest continue à choisir les parents :
ces garde-fous ne changent ni ses scores, ni sa politique AB-MCTS.

La réserve de recherche protège un programme final, ses lectures de sélection
estimées et la confirmation indépendante. Les autres tours d'assemblage sont
optionnels et passent leur propre contrôle d'admission. Leur nombre nominal
reste visible dans la prévision, sans être prélevé d'avance sur tous les essais.
Les analystes sont invités à profiler la meilleure variante correcte de leur
arbre et à lire ses preuves natives avant de conseiller une poursuite ou un arrêt.
Une collecte réussie sur la référence n'est pas une mesure de la variante.

## Outils

| Outil | Usage |
|---|---|
| `diagnostic_capabilities(probe)` | Inventaire contextualisé ; sondes de versions, compteurs, GPU et permissions sur le nœud si autorisées |
| `diagnostic_sources(offset, limit)` | Sources admises, commits et état de correction officiel |
| `diagnostic_source(source_id, path, offset, limit, byte_offset)` | Liste des fichiers puis lignes exactes ; octets base64 pour les lignes très longues |
| `diagnostic_collect(source_id, collector, question, request_key, options)` | Collecte bornée sur une copie ; options typées, aucune commande arbitraire |
| `diagnostic_survey(source_id, question, request_key)` | Passe les dix collecteurs sur une variante évaluée, réutilise les preuves du même commit et conserve les refus/absences |
| `diagnostic_summaries(offset, limit)` | Collections, questions, statut et IDs |
| `diagnostic_read(evidence_id, artifact, offset, limit, binary)` | Manifeste, texte paginé ou octets bruts ; contrôle du SHA-256 |
| `diagnostic_table(evidence_id, artifact, table, columns, equals, order_by, descending, offset, limit)` | Tables SQLite natives, schéma et lignes filtrées ; accès en lecture seule sans SQL libre |

Les offsets sont à base zéro. Une clé de collecte identique avec les mêmes
arguments restitue le résultat antérieur, même interrompu ; elle ne relance
pas implicitement un programme. Une question différente exige une autre clé.
`summary.json` contient la synthèse, les unités, le périmètre, les limites et
les données manquantes. Les autres artefacts contiennent les preuves détaillées.
Le service conserve les données binaires natives ; il ne prétend pas convertir
tous les formats propriétaires en un modèle de compteurs universel.
Les exports SQLite de Systems sont interrogeables sans aplatir les corrélations
dans une liste de quelques fonctions. Le schéma et les unités restent ceux du
producteur. Les requêtes sont bornées en lignes, en volume et en temps ; les
cellules tronquées sont signalées, et le fichier brut demeure accessible.

## Collecteurs intégrés

| Collecteur | Exécution et preuves | Limites explicites |
|---|---|---|
| `runtime` | Build distinct, contrôle diagnostic, charge figée, temps monotone | Temps diagnostic incluant le lancement ; aucun score |
| `perf-stat` | `perf stat`, événements sélectionnés, CSV natif | PMU et permissions du noyau ; valeurs non comptées nulles, temps actif/multiplexage conservés |
| `perf-record` | `perf record`, piles DWARF, `report --stdio`, `annotate --stdio` filtrable par symbole | Skid, échantillons perdus, déroulage et symboles ; rangs distants hors portée locale |
| `hpctoolkit` | `hpcrun` après le lanceur MPI, `hpcstruct`, `hpcprof` ; profils, traces et base native | Support effectif d'OMPT, CUDA/HIP/Level Zero et événements dépendant du build ; HPCViewer pour l'exploration graphique |
| `nsys` | Chronologie CUDA/NVTX/OSRT, domaines MPI/OpenMP demandables ; `nsys stats` CSV et export SQLite par rapport | Pas d'échantillonnage CPU privilégié par défaut ; rapports par rang ; chronologie perturbée par la collecte |
| `ncu` | Filtre de noyau, métriques, saut et nombre de lancements ; rapport natif, CSV, source/SASS | Permissions GPU, replay, architecture ; replay MPI concurrent refusé ; aucune assimilation au temps bout en bout |
| `compiler` | Interception des compilateurs ; pour les noyaux CUDA, capture des appels NVRTC, options originales, journal, PTX et CUBIN | NVRTC conserve ses options exactes ; appels statiques ou symboles obtenus par `dlopen` peuvent contourner l'observateur ; couverture explicitée |
| `disassembly` | `objdump -d -S -l -C` ; pour CUDA, `cuobjdump` sur le CUBIN capturé et ressources statiques | Le lanceur JSON ne représente pas le code GPU ; association ligne/instruction dépendant des informations de debug |
| `scorep` | Rebuild séparé préfixant les compilations/liens interceptés par Score-P ; CUBE/OTF2 | Compilateur et adaptateurs MPI/OpenMP compatibles requis ; aucun remplacement de compilateur |
| `scalasca` | Build Score-P puis `scalasca -analyze -t`, archive dédiée | Gros volumes et perturbations possibles ; outils supplémentaires requis |

Les builds de symbolisation ajoutent `-g` aux familles reconnues ou `-lineinfo`
à NVCC, sans diminuer l'optimisation. Le collecteur compilateur utilise les
rapports GCC `-fopt-info-all`, `-fdump-tree-optimized`, `-save-temps=obj`, ou
Clang `-Rpass`, `-Rpass-missed`, `-Rpass-analysis`,
`-fsave-optimization-record`, `-save-temps=obj`. Les intermédiaires LLVM peuvent
être binaires ; leur présence n'est pas présentée comme une IR textuelle.
NVCC peut conserver PTX et intermédiaires ; NVHPC émet `-Minfo=all`.
Une famille inconnue ne reçoit aucun drapeau deviné.

Pour un projet importé, la charge doit être une commande directe, comme le
contrat actuel de l'application. Une commande shell composée est signalée
comme non prise en charge par cet adaptateur. Le moteur générique peut garder
un lanceur MPI figé et placer HPCToolkit/Nsight après celui-ci. Un protocole
`python protocol.py benchmark solution search` est profilé en entier, avec
ses sous-processus ; le chemin `solution` est un argument, pas une frontière
de commande. Les lanceurs `srun`, `mpirun`, `mpiexec`, `mpiexec.hydra` et
`orterun` sont reconnus avec leurs options prises en charge. Les commandes
MPI enveloppées, MPMD ou de syntaxe inconnue demandent un adaptateur explicite ;
aucun découpage n'est deviné. Nsight Compute conserve son refus du replay MPI
concurrent. L'application
ROMEO conserve le placement historique sans contrat explicite. Avec un contrat
`execution_validation`, les processus et leurs diagnostics héritent de
l'allocation CPU vérifiée, et les variables OpenMP expriment le nombre de
threads de calcul demandé. Le profilage ne change pas ces exigences figées.
Le contrôle configurable actuel porte sur un nœud CPU, sans prise en charge
implicite de MPI multi-nœuds.

## Conservation et interprétation

Les données sont dans `campaign/diagnostics/` : grants, audit de chaque appel,
sondes, collections, commandes, versions, copies de build, rapports bruts,
SHA-256 et synthèses. Un appel démarré sans résultat reste enregistré comme
tel. Une erreur de permission, un outil absent, une architecture non supportée,
un plafond atteint ou une interruption ne produit aucun score. Le contrôleur
réévalue et confirme indépendamment sans ces profileurs.

Les collectes prennent le même verrou de cible que l'évaluateur et utilisent
l'affinité du contrôleur. Elles ne chevauchent donc pas ses mesures officielles.
Les commandes figées reçoivent la phase `search` pour réutiliser les entrées de
recherche ; les données de confirmation restent réservées au contrôleur.
La provenance distingue cette sélection d'entrées de l'exécution diagnostique.
L'intégrité des fichiers protégés est vérifiée avant et après. Les exécutables
et les scripts de projet restent des programmes fournis par l'utilisateur :
la copie et les hashes ne constituent pas une isolation OS contre un programme
hostile, pas plus que l'évaluateur existant. Le service n'offre aux modèles
aucune commande arbitraire ni accès libre au système de fichiers.

Une mesure de compteur ou une décision du compilateur peut soutenir une
hypothèse. Pour affirmer une cause ou un gain, il faut une comparaison contrôlée
et les évaluations officielles. Les unités et dénominateurs de chaque outil
restent visibles ; une valeur manquante n'est jamais remplacée par zéro.

## État ROMEO constaté le 28 octobre 2026

Consultation du catalogue Spack uniquement, sans calcul ni installation :

| Architecture | Observation |
|---|---|
| `armgpu` / Neoverse V2 | `nvidia-nsight-systems@2024.6.1`, `hpctoolkit@2023.03.stable`, `hpctoolkit@2024.01.1` annoncés |
| `armgpu` | Plusieurs CUDA annoncés ; présence de `ncu` et accès aux compteurs non vérifiés |
| `x64cpu` | HPCToolkit absent du résultat du catalogue consulté |
| Les deux | Aucun paquet Score-P ou Scalasca dans les résultats consultés |

Un catalogue ne prouve ni qu'un paquet est chargé dans le profil de la mission,
ni que ses compteurs ou adaptateurs fonctionnent. `perf` peut venir du système,
donc son absence de Spack ne suffit pas à le déclarer absent. Les sondes sur le
nœud font foi pour cette allocation. Le service n'installe ni ne charge un
paquet de son propre chef.

## Approfondissement et coût des collectes

Le contrôleur relie les fenêtres de suivi aux vrais descendants du programme qui
a progressé. Mother peut ouvrir une continuation `refine`, bornée à deux essais
par défaut, dans un nouvel arbre TreeQuest amorcé par ce programme. Les appels
AB-MCTS `ask/tell` restent inchangés et aucun score n'est recopié dans l'arbre
source. Les parents de recherche, de délégation et les imports restent distincts.
Les dossiers encore en file sont rafraîchis avant publication ; une requête déjà
publiée conserve son instantané et ses preuves.

Les outils absents sont détectés avant l'attente du verrou cible. Le refus explicite
Nsight Compute `ERR_NVGPUCTRPERM` est réutilisé seulement pour les mêmes binaire,
hôte, allocation, architecture et protocole. Il reste une absence de mesure, avec
un score absent. La configuration active complète réserve une intégration puis
un réglage du programme intégré mesuré. Cette seconde étape peut profiler ses
sources autorisées pendant au plus 45 secondes, si le temps restant préserve
l'écriture, l'évaluation et la confirmation. Les autres collectes après fermeture
restent interdites ; les résultats antérieurs restent lisibles.

## Validation reproductible

Contrôles logiciels : `python -m pytest`, `python -m ruff check src tests`,
`node --test tests/test_web_frontend.mjs`. `tests/test_diagnostics.py` distingue
les vrais sous-processus et échanges MCP des captures synthétiques de commandes
de profileurs. Son test GCC POSIX compile réellement une petite fixture et
vérifie les rapports et l'assembleur produits.

Pour une validation CPU locale explicitement choisie, dans un dossier neuf :

```text
python tools/diagnostics_probe.py artifacts/diagnostics-local-NOUVEAU --local
```

Pour une future validation ROMEO **après autorisation distincte de l'allocation**,
préparer un profil chargé avec les empreintes Spack choisies et un environnement
du projet incluant l'extra `web`. Sur le nœud alloué uniquement :

```text
python tools/diagnostics_probe.py /scratch/.../diagnostics-NOUVEAU --collector runtime --collector compiler --collector disassembly --collector perf-stat --collector hpctoolkit
```

Ce programme refuse le login sans allocation, ne soumet rien, n'installe rien,
crée une campagne synthétique séparée, valide sa référence et écrit
`diagnostic-validation.json`. Le code de sortie 2 signifie qu'au moins une
collecte n'a pas réussi ; les preuves restent présentes. Cette fixture CPU ne
valide pas CUDA ou MPI. Pour ces derniers, créer une **nouvelle** campagne avec
le programme réel, son lanceur, son compilateur et sa charge figés, puis lire
les preuves via les mêmes outils. Vérifier les deux étages CUDA séparément :
chronologie Systems, puis noyau ciblé Compute. Ne pas charger un autre
compilateur ni changer le protocole pour faire passer la validation.

## Références officielles utilisées

- [HPCToolkit : compilation, mesure et corrélation](https://hpctoolkit.gitlab.io/hpctoolkit/users/quickstart.html)
- [Nsight Systems CLI](https://docs.nvidia.com/nsight-systems/UserGuide/index.html)
- [Nsight Compute CLI](https://docs.nvidia.com/nsight-compute/NsightComputeCli/index.html)
- [Nsight Compute : métriques, replay et coûts](https://docs.nvidia.com/nsight-compute/ProfilingGuide/index.html)
- [GCC : rapports et intermédiaires](https://gcc.gnu.org/onlinedocs/gcc/Developer-Options.html)
- [Clang : rapports d'optimisation](https://clang.llvm.org/docs/UsersManual.html)
- [Score-P : instrumentation et outils](https://perftools.pages.jsc.fz-juelich.de/cicd/scorep/tags/latest/html/scoreptools.html)
- [Scalasca : mesure et analyse](https://apps.fz-juelich.de/scalasca/releases/scalasca/2.6/docs/manual/start_measurement.html)

Ces références sont aussi accessibles aux modèles via le catalogue `hpc_docs`.
Leur version courante ne garantit pas les fonctionnalités des versions installées.
Pour étendre la couverture, ajouter un adaptateur dans `diagnostic_collectors`
(capacités, options typées, portée, unités, limites, collecte et preuves), ses
tests de contrat, puis une validation réelle sur la cible avant de le présenter
comme validé. HIP, SYCL, autres GPU et runtimes ne sont pas déclarés couverts
par la seule présence d'un nom d'événement.
