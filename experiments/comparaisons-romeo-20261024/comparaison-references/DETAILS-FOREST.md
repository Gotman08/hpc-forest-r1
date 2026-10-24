# Forest : contexte, mémoire, interventions et arbres réellement exécutés

Audit du 2026-10-23T19:53:31.645241+00:00. Les résultats de performance ne sont pas modifiés. Cet audit lit les 22 configurations, les 22 bases SQLite archivées et les 325 invocations locales du client Codex.

[Comparaison des performances](RAPPORT.md) · [Détail tabulaire CSV](DETAILS-FOREST.csv) · [Audit structuré](AUDIT-FOREST.json) · [Historique des 173 essais](HISTORIQUE-FOREST.md).

## 1. Qu’est-ce qui était réinitialisé ?

**Entre deux familles de programmes : une nouvelle campagne.** Les 22 lancements ont 22 identifiants de session et 22 répertoires ROMEO distincts. La création refuse un répertoire déjà existant. Chaque campagne recrée son dépôt Git à partir d’un instantané du naïf, sans copier son `.git`, et sa propre base `registry.sqlite3`. Aucun ancien candidat n’est importé. Le premier deferred échoue avant Mother ; le second repart lui aussi dans une nouvelle campagne.

L’audit trouve 21 conversations Mother distinctes, commencées au tour 0 sans identifiant de conversation antérieure, et **aucun identifiant de conversation ou de thread partagé entre programmes**. Les 218 threads natifs observés correspondent aux 21 conversations Mother et aux 197 invocations éphémères. Les sessions de cette discussion ne sont pas transmises aux workers. Le client ignore la configuration utilisateur et désactive les mémoires automatiques Codex, les documents de projet, les plugins et le shell. Les compétences du projet Forest restent, elles, fournies explicitement et identiques entre campagnes.

**Entre essais d’un même programme : la mémoire n’est pas effacée.** C’est un choix de cette configuration Forest. La base conserve les sources/commits, mesures, erreurs, essais de développement, leçons proposées par le modèle et états AB-MCTS. Un essai peut repartir d’un candidat précédent choisi par AB-MCTS. La mémoire continue donc de s’enrichir pendant la campagne ; les anciens codes restent archivés.

**Mother garde sa conversation**, de la planification à la revue puis à l’intégration. Les générations des arbres sont lancées dans des conversations éphémères, mais reçoivent un contexte reconstruit : code parent, mission, mesures et mémoire autorisée. « Conversation fraîche » ne veut donc pas dire « aucun retour des essais précédents ». La lecture de mémoire d’un arbre est limitée à son arbre et au naïf, dans le protocole et l’époque courants. Mother/G peut consulter les preuves de tous les arbres de cette campagne pour intégrer leurs idées. Les arbres ne redémarrent pas après la fermeture de la recherche et l’intégration G.

**Les répétitions chronométrées ne relancent pas le modèle.** Elles utilisent le candidat figé. Il n’y a pas de redémarrage du nœud ni de purge systématique des caches CPU/GPU entre répétitions : les pilotes font leurs échauffements et appliquent le même protocole aux variantes. Les entrées et sorties sont contrôlées ; réutiliser une réponse calculée pour une ancienne entrée est interdit. Cette expérience n’est pas un benchmark matériel « caches froids ».

Aucun entraînement ou ajustement des poids du modèle n’a été effectué. L’isolation vérifiée porte sur l’état de l’application et les conversations ; elle ne signifie pas que le modèle perd ses connaissances préentraînées.

## 2. L’assistant a-t-il aidé ?

**Oui, pour préparer et conduire l’expérience.** L’assistant a choisi avec le contexte de la demande le modèle, le budget et le protocole, retrouvé les sources, préparé/porté les références et naïfs, écrit les adaptateurs, tests et chronomètres, lancé les allocations, transporté les messages, diagnostiqué les incidents et analysé les résultats. Les contrats décrivent explicitement le problème, les tailles, la précision, le matériel, les opérations autorisées et les contraintes de correction. L’expérience n’est donc pas la résolution autonome d’un classeur brut par Forest.

**Les optimisations retenues ont été produites par Forest.** Les thèmes d’arbres viennent de Mother ; l’assistant n’a pas fourni la recette de fusion G, modifié manuellement les candidats retenus, ou remplacé le vainqueur après les mesures finales. Les 42 fichiers retenus/G remesurés ont été vérifiés par SHA256. Les programmes optimisés de comparaison n’ont pas été donnés au modèle dans son espace source. Le modèle disposait de documentation technique officielle et des compétences figées du projet, ainsi que des retours automatiques de compilation et de correction.

Interventions à garder visibles :

- **UTF-8, avant recherche** : le naïf historique est incorrect sur certaines chaînes malformées. Un naïf scalaire réparé a été préparé pour le départ Forest. Ce n’est pas une amélioration générée par Forest. La comparaison temporelle au naïf historique ne porte que sur les entrées valides.
- **Deferred, après le premier échec d’import** : le fichier dépassait les 32 000 caractères lus par Mother. Seule l’indentation en début de ligne a été retirée ; les tokens C++ sont inchangés. Une nouvelle session a été lancée. Le premier lancement avait fait zéro appel modèle et reste dans le tableau.
- **Trois premières campagnes GPU** : l’adaptateur ne fournissait pas les fichiers attendus pour l’empaquetage final. Les recherches et confirmations ont eu lieu, mais la fin du pipeline a échoué. Les sources confirmées ont ensuite été extraites et remesurées séparément, sans correction de leurs optimisations.
- **Clang/popcount** : le chargement de libomp a été corrigé dans un nouveau job de mesure. Le candidat déjà choisi sous GCC a été recompilé inchangé ; il n’y a pas eu une deuxième recherche Forest sous Clang.
- **Volume** : après deux plantages de la référence sur des tailles incompatibles avec son domaine, un diagnostic distinct avec gardes a confirmé la précondition « dimensions multiples de 4 ». Ce diagnostic n’a pas modifié le code chronométré ni le candidat Forest.

Les erreurs d’outils rencontrées par les recherches Base64, AO, ray tracing et deferred n’ont pas été réparées en donnant un meilleur candidat au modèle. Elles restent comptées. Les réparations automatiques éventuelles d’un essai appartiennent au harness Forest (maximum de trois tentatives de développement), avec retours mesurés et journal conservé.

## 3. Qu’est-ce qui tournait sur ROMEO ?

| Étape | Lieu réel |
|---|---|
| Contrôleur Forest, ordonnanceur des arbres, base de campagne et sélection AB-MCTS-A | Nœud de calcul ROMEO dans le job SLURM indiqué |
| Compilation, contrôles de correction, évaluations de développement, recherche, confirmations et benchmarks finaux | ROMEO ; EPYC 9654 pour CPU, GH200 pour GPU |
| Relais des requêtes et processus client Codex | PC local Windows |
| Inférence gpt-6-luna, effort max | Service hébergé appelé par Codex ; pas un modèle chargé sur ROMEO |
| Extraction, audit, CSV, Excel, rapports | PC local |

Dire « tout le système tournait sur ROMEO » aurait donc été imprécis. **Tous les temps de programmes comparés proviennent de ROMEO**, mais l’architecture de recherche était hybride. Les 325 invocations vérifiées déclarent une inférence hébergée, sans exécution locale du code candidat et sans accès ROMEO direct du modèle. Les expériences distantes sont exécutées par le contrôleur via le protocole protégé. L’outil de documentation officielle est autorisé en lecture.

## 4. Configuration commune et fonctionnement des arbres

- Moteur hpc-forest-r1 gelé, sources Python au commit `934627c1399b48e4aa0f25630e9c4223680a3511`, méthode H, TreeQuest 0.3.2 / **AB-MCTS-A**, graine 23.
- Modèle **gpt-6-luna**, effort **max**. Une campagne retenue par famille ; aucun balayage de modèles ou de graines.
- Mother choisit le nombre et les sujets des arbres. Les entrées historiques `roles=A/B/C` et `max_workers=1` de la configuration ne fixent pas le nombre effectif en mode Mother : le plan observé et l’ordonnanceur indépendant font foi.
- **2 à 4 arbres de recherche** selon le programme. Les premiers nœuds de chaque campagne ont été soumis dans une fenêtre inférieure à 0,007 seconde. Cela prouve l’envoi concurrent ; cela ne garantit pas une simultanéité parfaite du calcul chez le fournisseur du modèle.
- Un essai au plus en attente par arbre. Dès qu’un essai est évalué, l’arbre peut proposer le suivant si le budget d’admission le permet. La génération peut se chevaucher entre arbres ; les mesures sur une allocation cible sont sérialisées et protégées par verrou.
- Cible **1 800 s**, admission adaptative, `finish-started`. Ce n’est pas une coupure stricte à 30 minutes. La planification, les échanges modèle, les contrôles et la finalisation consomment du temps. Des travaux déjà admis peuvent dépasser la cible. Les arrêts anticipés et erreurs d’infrastructure existent aussi.
- Pas de quota configuré de tokens, de nœuds ou de profondeur pour AB-MCTS ; les compteurs de tokens sont en observation seule. Cela ne supprime pas les limites du fournisseur. Aucun coût en tokens n’est déduit des compteurs cumulés de conversations reprises.
- Recherche : **3 mesures par évaluation** ; confirmation : **5**. Les échauffements sont dans les pilotes, même si le champ `protocol.warmups` externe vaut zéro. Les séries finales indépendantes restent à 7 blocs CPU, 9 GPU et 3 rendus.
- Mémoire active : contexte de lecture jusqu’à 12 000 caractères, pages de 6 éléments, 3 lectures par mission ; intégration configurée jusqu’à 16 tours, 4 appels de sélection par tour et 3 sources par intégration. Ce sont des limites configurées, pas des comptes d’actions réellement atteints.
- Le code **G** est produit après la recherche par Mother qui reprend sa conversation. G n’est pas un arbre de recherche supplémentaire lancé en parallèle. La base comporte aussi des états `G` / `G-merge-*` pour tracer les intégrations ; ils ne sont pas inclus dans les 58 arbres de recherche.

## Vue d’ensemble par campagne

**58 arbres, 148 essais de recherche + 25 essais G = 173 essais enregistrés.** Bilan : 162 valides, 2 incorrects, 2 échecs de génération et 7 erreurs d’infrastructure. « Valide » signifie que les contrôles ont passé, pas que le candidat est plus rapide.

**325 invocations natives du client Codex** : 128 dans les conversations Mother persistantes et 197 éphémères. Ce ne sont ni 325 essais, ni un total de requêtes internes du fournisseur : les échanges d’outils peuvent déclencher d’autres tours. Trente arbres n’ont enregistré qu’un essai ; 33 essais de recherche ont eu pour parent un candidat antérieur ; la profondeur maximale observée est 3. Cette campagne n’établit pas le plafond d’une recherche plus longue.

Durée = durée totale du job de recherche selon SLURM, incluant installation du contexte, attentes et finalisation. Elle exclut les jobs de référence précédents et de mesure finale suivants. Les minutes sont arrondies. `E` = erreur d’infrastructure, `Gén.` = génération échouée, `I` = résultat incorrect.

| Programme | Job | Arbres | Essais T1/T2/T3/T4 | Essais G | Valides / total | Échecs | Durée (min) |
|---|---:|---:|---|---:|---:|---|---:|
| AOBench | 781191 | 3 | 1/1/1 | 1 | 3 / 4 | 1 E | 63,1 |
| Argmin | 781166 | 2 | 3/4 | 1 | 8 / 8 | — | 34,0 |
| Base64 | 781167 | 2 | 1/1 | 1 | 1 / 3 | 2 E | 40,5 |
| Options binomiales | 781168 | 3 | 3/3/2 | 1 | 9 / 9 | — | 30,0 |
| Black–Scholes | 781169 | 2 | 5/1 | 1 | 6 / 7 | 1 Gén. | 31,8 |
| Deferred shading (import initial) | 781194 | 0 | — | 0 | 0 / 0 | import | 0,7 |
| Deferred shading (reprise neuve) | 781198 | 3 | 1/1/1 | 3 | 3 / 6 | 3 E | 25,1 |
| GEMM CPU | 781170 | 3 | 2/2/1 | 1 | 6 / 6 | — | 31,3 |
| Mandelbrot | 781171 | 3 | 1/1/2 | 1 | 5 / 5 | — | 25,5 |
| Bruit Perlin | 781172 | 3 | 4/3/3 | 1 | 11 / 11 | — | 29,2 |
| Popcount | 781173 | 3 | 3/4/4 | 1 | 12 / 12 | — | 32,6 |
| Ray tracing | 781193 | 3 | 4/3/1 | 3 | 10 / 11 | 1 E | 22,2 |
| Réduction GPU | 781178 | 3 | 1/1/1 | 1 | 4 / 4 | — | 33,7 |
| S4ConvD | 781179 | 4 | 1/1/1/1 | 1 | 5 / 5 | — | 31,1 |
| SGEMM CUDA | 781115 | 2 | 10/4 | 1 | 14 / 15 | 1 Gén. | 25,1 |
| Softmax | 781180 | 2 | 1/1 | 1 | 3 / 3 | — | 26,0 |
| Stencil 3D CPU | 781174 | 3 | 1/1/1 | 1 | 4 / 4 | — | 28,3 |
| Stencil Y CUDA | 781116 | 3 | 4/9/9 | 1 | 21 / 23 | 2 I | 24,3 |
| Somme des valeurs absolues | 781181 | 2 | 1/2 | 1 | 4 / 4 | — | 28,2 |
| Transpose CUDA | 781117 | 3 | 8/5/8 | 1 | 22 / 22 | — | 24,0 |
| UTF-8 | 781175 | 3 | 2/3/1 | 1 | 7 / 7 | — | 30,1 |
| Rendu volumique | 781192 | 3 | 1/1/1 | 1 | 4 / 4 | — | 41,4 |

La recherche s’arrête sur une erreur d’infrastructure pour Base64, AOBench, ray tracing et deferred_r2. Les autres arbres déjà admis sont drainés et l’intégration peut encore avoir lieu. Cela explique notamment le faible nombre d’essais de certaines familles. Une longue durée totale ne signifie donc pas une recherche profonde : AO prend environ 63 minutes, dont environ 30,5 minutes de confirmation.

## Objectifs, mémoire et diagnostic pour chaque campagne

Les sujets et objectifs ci-dessous sont les sorties exactes de Mother, en anglais, après sa revue. Ils ne sont pas des suggestions ajoutées après coup par l’assistant. Les profondeurs comptent la première proposition au niveau 1. Les compteurs mémoire sont des fiches conservées, distinctes des essais et des appels modèle.

### AOBench — aobench / job 781191

40 CPU alloués, EPYC 9654. Session `2f3347c7faed418cb33de843a52eff90`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **7**, dont 3 Mother persistantes et 4 éphémères. Mémoire finale : 4 fiches de développement, 5 fiches d’expérience, 2 leçons.

État de recherche : `infrastructure_error`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — Race-free OpenMP rendering and independent sampling** : 1 essai(s), 1 infrastructure_error ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Own OpenMP work distribution and random-number handling. Parallelize disjoint scanlines or pixels while treating threads as a strict maximum and preserving a serial path. Replace shared mutable random state with race-free per-work-unit streams that generate uniform independent samples. Preserve nsubsamples squared primary rays and all 64 ambient rays per hit, shade every ray, and fully overwrite output. Measure scheduling and RNG variants on the official workloads; do not change intersection math or pixel accumulation.

- **T2 — Ambient-ray intersection kernel** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Own the ambient-ray intersection path. Reduce scalar per-ray overhead in the sphere and plane tests while preserving the source geometry, testing all three spheres and the plane, and retaining nearest-positive-hit, normal, and epsilon semantics. Do not prune intersections or change sample generation, ray counts, threading, or primary-ray/output dataflow. Validate correctness and measure the official workloads.

- **T3 — Primary-ray and pixel-output dataflow** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Own primary-ray construction and per-pixel output accumulation only. Explore safe invariant hoisting and avoiding redundant RGB accumulation, such as accumulating one visibility value per pixel and writing it to all three channels once. Preserve every primary sample, its shading, output dimensions and channels, and the existing sampling order. Do not alter ambient-ray generation, intersection logic, or threading; test all valid inputs rather than specializing to benchmark values.

Essais d’intégration G : 1. Commit retenu : `55803576af51607645a2efb3f3c2aea1a9ba8376`. Commit G : `55803576af51607645a2efb3f3c2aea1a9ba8376`.

### Argmin — argmin / job 781166

1 CPU alloués, EPYC 9654. Session `f4514c52bc614ef3a6ec29c797fc2970`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **15**, dont 6 Mother persistantes et 9 éphémères. Mémoire finale : 10 fiches de développement, 9 fiches d’expérience, 6 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — SIMD argmin with stable first-index recovery** : 3 essai(s), 3 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explore target-compatible packed int32 reductions in src/candidate.cpp, focusing on SIMD throughput and index recovery. Contrast one-pass vector argmin approaches with vector minimum reduction followed by earliest-match recovery, and measure the extra read traffic of any second pass rather than assuming it is negligible for the 32 KiB input. Treat ISA/build compatibility as something to establish on the frozen target, not assume. Compare against the supplied baseline on random and decreasing inputs; validate first-index ties, signed extrema, all valid n, the stated patterns, full output writes, and the threads budget. SIMD is the primary hypothesis, not a restriction on correctness-preserving alternatives or combinations.

- **T2 — Scalar multi-accumulator argmin** : 4 essai(s), 4 valid ; profondeur maximale 3, 2 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Test whether several independent scalar (minimum value, index) accumulators, merged by signed value and then lowest index, improve the baseline; compare conditional and branchless updates where useful. Measure this standalone form to isolate the scalar instruction-level-parallelism and branch hypothesis, but do not make scalar-only a search restriction: retain and separately measure any promising structure that could combine with T1 or compiler vectorization. Compare against the supplied baseline on random and decreasing inputs; validate first-index ties, signed extrema, all valid n, the stated patterns, full output writes, and the threads budget.

Essais d’intégration G : 1. Commit retenu : `638e4486d8c08c3315b7ec012a527697ad15741f`. Commit G : `638e4486d8c08c3315b7ec012a527697ad15741f`.

### Base64 — base64 / job 781167

1 CPU alloués, EPYC 9654. Session `9efde8ec50f04b9ba0699ff3134f924c`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **16**, dont 7 Mother persistantes et 9 éphémères. Mémoire finale : 2 fiches de développement, 4 fiches d’expérience, 0 leçons.

État de recherche : `infrastructure_error`. Pipeline complet : **oui**. G : `confirmed`.

**Le naïf a été conservé comme meilleur confirmé.**

- **T1 — Décodage Base64 SIMD sur EPYC : comparaison AVX2 et AVX-512** : 1 essai(s), 1 infrastructure_error ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explorer un décodeur SIMD mono-cœur, en gardant AVX2 comme référence et en comparant une variante AVX-512 sur l’EPYC 9654 si elle se compile avec la configuration gelée. Ne pas changer compilateur, options ni cible, et ne pas supposer que la largeur supérieure gagne. Traiter correctement blocs, reliquat et padding ; respecter ABI, budget threads, limites mémoire et sortie définie par l’oracle. Vérifier des données valides aléatoires et plusieurs longueurs, puis comparer le temps de l’appel complet au baseline selon le protocole officiel et consigner les échecs.

- **T2 — Décodeur scalaire direct et helper réutilisable pour queue ou repli** : 1 essai(s), 1 infrastructure_error ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Étudier une alternative sans SIMD utilisant conversion arithmétique ou table compacte et décodage groupé. Comparer les écritures exactes aux écritures groupées seulement si elles restent dans les limites autorisées ; ne pas imposer une stratégie de stockage qui pourrait écarter une optimisation correcte. Vérifier padding, petites longueurs, exactitude et budget threads, puis mesurer le chemin scalaire complet sous le protocole officiel. Conserver aussi un helper scalaire réutilisable comme queue ou repli potentiel pour T1 : une performance globale inférieure n’écarte pas cette utilité pour une intégration ultérieure.

Essais d’intégration G : 1. Commit retenu : `28657d0677be5dfe6a44b7fb09de8f4dc2d5230e`. Commit G : `5d028ec0c8c79bf5aac78b33c9dfb91de78bff2f`.

### Options binomiales — binomial / job 781168

40 CPU alloués, EPYC 9654. Session `34a3999b9ac2420aadbaa278e6820923`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **13**, dont 4 Mother persistantes et 9 éphémères. Mémoire finale : 9 fiches de développement, 10 fiches d’expérience, 8 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — OpenMP parallelization across independent contracts** : 3 essai(s), 3 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Isolate outer-loop parallelism: parallelize work across input elements using the threads argument as the CPU-thread budget, with per-thread scratch and an appropriate schedule. Keep each element's baseline arithmetic and reduction order unchanged. Measure scaling and any small-n overhead; validate every output and varied inputs.

- **T2 — Recurrence-based terminal power generation** : 3 essai(s), 3 valid ; profondeur maximale 2, 1 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Replace repeated terminal powf evaluation with a tested multiplicative recurrence (for example, one initial power followed by multiplication by u squared). Preserve all 64 payoffs and their exact endpoint exponents, and leave the backward reduction unchanged to isolate the effect. Check numerical error across varied valid inputs and measure runtime.

- **T3 — Collapse the triangular backward induction** : 2 essai(s), 2 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Derive and test an equivalent binomial-weighted sum over the baseline's 64 terminal payoffs and 63 active transitions, preserving its unusual endpoint convention. Generate weights robustly, including probability endpoints, without fragile division by zero; compare against the oracle within tolerance across varied inputs and measure runtime. Do not substitute a different pricing algorithm.

Essais d’intégration G : 1. Commit retenu : `5ed8a5d1214ccbad796bf4f4c47e60942c104d1d`. Commit G : `5ed8a5d1214ccbad796bf4f4c47e60942c104d1d`.

### Black–Scholes — blackscholes / job 781169

40 CPU alloués, EPYC 9654. Session `f7cb9fffcd6241909510599734f0cdb9`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **14**, dont 6 Mother persistantes et 8 éphémères. Mémoire finale : 9 fiches de développement, 8 fiches d’expérience, 6 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — OpenMP thread-level parallelism and scheduling for the currently serial kernel** : 5 essai(s), 5 valid ; profondeur maximale 2, 1 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explore thread-level parallelism over independent elements, honoring threads as a strict CPU budget and writing every output. Use the original scalar kernel as a control to isolate scaling; treat contiguous static worksharing and a serial small-n path as starting hypotheses, and compare other reasonable partition/chunk choices if measurements warrant them. Preserve correctness for varied inputs. Report correctness and comparable native wall-clock results across relevant thread budgets and workload sizes; do not assume the best schedule in advance.

- **T2 — Per-element FP32 math-kernel optimization: scalar simplification and SIMD** : 1 essai(s), 1 generation_failed ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Investigate per-element kernel cost separately from thread-scheduling improvements. First test whether source-level reductions—such as reusing sqrtf(T) and Horner evaluation of the CND polynomial—survive compiler optimization and improve measured time. Then contrast compiler-supported SIMD with target-supported x86 vector math; do not assume a specific ISA or vector math ABI from x86_64 alone. Operation reassociation or approximations may be explored as hypotheses, but every candidate must meet the stated tolerance on varied inputs, handle tails, overwrite all outputs, and avoid test-specific values or external libraries. Use a comparable thread policy when measuring SIMD effects, respect the threads budget, and record failed attempts as well as correctness and timings.

Essais d’intégration G : 1. Commit retenu : `043d577e5ff2678bf02c0c7111340a8cbbd096b4`. Commit G : `c9c4ff6a62f21474936e832eec812b7bca2c7c69`.

### Deferred shading — deferred / job 781194

4 CPU alloués, EPYC 9654. Session `16bd32ab4e094f199021967ce02096f7`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **0**, dont 0 Mother persistantes et 0 éphémères. Mémoire finale : 0 fiches de développement, 0 fiches d’expérience, 0 leçons.

État de recherche : `non commencée`. Pipeline complet : **non**. G : `absent`.

Diagnostic de pipeline : InfrastructureError: Mother did not produce a valid research forest: not_invoked_source_limit

Essais d’intégration G : 0. Commit retenu : `aucun`. Commit G : `aucun`.

### Deferred shading — deferred_r2 / job 781198

4 CPU alloués, EPYC 9654. Session `11b642a5459447db894e178b4a06ba70`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **28**, dont 16 Mother persistantes et 12 éphémères. Mémoire finale : 3 fiches de développement, 7 fiches d’expérience, 0 leçons.

État de recherche : `infrastructure_error`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — Parallelize root-tile shading and test load balance** : 1 essai(s), 1 infrastructure_error ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explore OpenMP parallelization of the independent root-tile shading work, bounded by `threads`. Contrast static scheduling with dynamic or guided scheduling because root subtrees may have uneven shading work. Measure this change in isolation against the matching 1- and 4-core baselines; validate full output and altered-light-color cases. The tree is read-only during shading and root subtrees write disjoint framebuffer regions.

- **T2 — Parallelize current-frame depth-bounds construction** : 1 essai(s), 1 infrastructure_error ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explore parallelizing `MinMaxZTree::Update` while preserving the current-frame depth scan and validity bounds. Contrast parallelizing only independent base-tile scans with also parallelizing upper levels, where level dependencies require completion between levels; compare useful tile or row granularity. Bound workers by `threads`, measure in isolation against matching 1- and 4-core baselines, and validate output.

- **T3 — Improve per-pixel shading throughput with exact and approximate alternatives** : 1 essai(s), 1 infrastructure_error ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explore reducing `ShadeTileC` per-pixel cost. Contrast exact-preserving loop transformations or vectorization with measured approximate alternatives for normalization, specular, or gamma math; report which changes matter rather than assuming `powf` or SIMD is dominant. Check compiler/ISA availability before using target-specific code. Preserve the one-level-per-component tolerance and altered-light-color checks, avoid specializing to fixed colors, and measure against matching 1- and 4-core baselines.

Essais d’intégration G : 3. Commit retenu : `5820ee9ced976b03b4f2a20f32ec3df7f962e60f`. Commit G : `5820ee9ced976b03b4f2a20f32ec3df7f962e60f`.

### GEMM CPU — gemm_cpu / job 781170

8 CPU alloués, EPYC 9654. Session `c96c215142b84969af9f4afe032f452a`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **10**, dont 4 Mother persistantes et 6 éphémères. Mémoire finale : 6 fiches de développement, 7 fiches d’expérience, 5 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — Contiguous streaming and row-parallel GEMM** : 2 essai(s), 2 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : In src/candidate.cpp, explore a simple row-major streaming loop order (such as r-k-c) with disjoint row ownership across at most threads workers. Initialize output on every call, handle generic dimensions safely, and keep the inner contiguous-column loop suitable for compiler vectorization. Keep this path focused on loop order and threading rather than explicit intrinsics or cache-panel packing. Record failed attempts and compare correctness and repeated n=1024 wall-clock measurements under the official protocol.

- **T2 — Cache-tiled GEMM** : 2 essai(s), 2 valid ; profondeur maximale 2, 1 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : In src/candidate.cpp, explore cache-blocked FP32 GEMM with output-tile ownership and tuned loop/tile order to increase reuse across A, B, and C. Handle tile fringes and ensure each output region is race-free and completely overwritten per call. Keep the investigation focused on cache tiling with ordinary compiler-generated code, not explicit x86 intrinsics or packed-panel transformations. Record failed attempts and compare correctness and repeated n=1024 wall-clock measurements under the official protocol.

- **T3 — SIMD FMA register microkernel** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : In src/candidate.cpp, explore an explicit SIMD FMA register microkernel for FP32 GEMM, with row/column reuse and safe handling of generic dimensions and tails. Respect the supplied thread budget and overwrite all output on every call. Check that the chosen intrinsics compile and execute safely with the frozen GCC 14.2 build and target; do not assume unspecified compiler ISA flags. Keep the focus on the register-level kernel rather than broad tile-size or packing searches. Record failed attempts and compare correctness and repeated n=1024 wall-clock measurements under the official protocol.

Essais d’intégration G : 1. Commit retenu : `0ecb5936ff627da58938a56d56a8dec416f2c2b2`. Commit G : `cbe7a14fbdebb39504379334337f6fa487b061a2`.

### Mandelbrot — mandelbrot / job 781171

4 CPU alloués, EPYC 9654. Session `a13469c830fb4f288bad1737b276e61e`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **9**, dont 5 Mother persistantes et 4 éphémères. Mémoire finale : 5 fiches de développement, 6 fiches d’expérience, 2 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — OpenMP parallelization: schedule and granularity contrast** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : In src/candidate.cpp, use no more than the threads budget and compare a contiguous static row partition against tiled dynamic or guided scheduling to test load-balance benefits from variable per-pixel iteration counts. Keep a low-overhead one-thread path. Preserve each pixel’s baseline coordinate and recurrence calculations and full output writes; validate smaller checks and shifted bounds, and measure correctness and native wall time at one and four cores.

- **T2 — Exact SIMD across independent pixels** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Restrict this tree to pixel-lane SIMD mapping, lane masks/termination, and handling vector tails; do not pursue a general scalar-loop rewrite or thread scheduling. Compare the scalar baseline with lane widths and divergence strategies supported by the fixed target build—do not infer a usable ISA from x86_64 alone. Preserve coordinate generation, per-operation float semantics, the strict escape test, and max-count behavior. Validate exact counts for all required sizes and shifted bounds, then measure one- and four-core performance.

- **T3 — Scalar recurrence and arithmetic reuse** : 2 essai(s), 2 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Restrict this tree to a scalar recurrence rewrite, separate from SIMD and threading. Compare the baseline scalar loop with explicit reuse of real/imaginary squares in the escape test and update, without changing coordinate generation, operation order, per-operation float semantics, strict escape comparison, or iteration limits. Treat compiler reuse as an untested hypothesis: measure any benefit and record if the rewrite is redundant or slower. Validate exact counts for smaller checks and shifted bounds.

Essais d’intégration G : 1. Commit retenu : `6a17decffee591711d0406ef41be1641aa462bca`. Commit G : `6a17decffee591711d0406ef41be1641aa462bca`.

### Bruit Perlin — noise / job 781172

1 CPU alloués, EPYC 9654. Session `deabd09ca183432d9b991fb021231134`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **15**, dont 5 Mother persistantes et 10 éphémères. Mémoire finale : 11 fiches de développement, 12 fiches d’expérience, 8 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — Factor and measure scalar Perlin corner hashing** : 4 essai(s), 4 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Use AB-MCTS to test scalar factoring of the eight Perlin corner hashes, comparing the existing per-corner Grad lookups with explicit shared first- and second-level permutation results. Where available, check whether the compiler already coalesces those loads; treat that as an observation, not a reason to skip measurement. Preserve the existing floating-point expressions while isolating lookup changes, then try compatible combinations if results justify them. Validate the full output across performance and smaller sizes and shifted bounds; record failed attempts. Preserve the ABI, full output overwrite, general inputs, and threads budget.

- **T2 — Measure scalar fade and interpolation alternatives** : 3 essai(s), 3 valid ; profondeur maximale 2, 1 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Use AB-MCTS to compare the original NoiseWeight and Lerp forms with alternatives such as Horner evaluation and low + t*(high-low). Measure each change separately first, without changing compiler flags or removing octaves; validate every candidate against the fixed tolerance on varied inputs. Since effects may interact, also test correctness-preserving combinations when useful and judge them by their own measurements, not by summed individual gains. Preserve the ABI, full output overwrite, general inputs, and threads budget.

- **T3 — Contrast row-invariant reuse with SIMD pixel batching** : 3 essai(s), 3 valid ; profondeur maximale 2, 1 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Use AB-MCTS to compare two row-oriented opportunities while keeping the scalar hash and arithmetic forms at baseline initially: hoist reusable octave-scaled y setup across columns (and investigate the image-constant z setup), versus batching contiguous pixels with target-supported SIMD for x-varying work. The purpose is to test reuse against SIMD on this lookup-heavy kernel, not assume either wins. Attribute gains with isolated variants first, then allow compatible combinations. Do not change compiler flags or add runtime hardware probing. Validate all outputs, tails, sizes, and shifted bounds against tolerance; include setup/gather costs, preserve the ABI and full overwrite, and honor the threads budget.

Essais d’intégration G : 1. Commit retenu : `5d7dc3713d9a28c3a1d90d7ea9c461ec7b605ccd`. Commit G : `5d7dc3713d9a28c3a1d90d7ea9c461ec7b605ccd`.

### Popcount — popcount / job 781173

1 CPU alloués, EPYC 9654. Session `5bfdb00d1f884b97b3ae9b0d10f7f1dd`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **18**, dont 6 Mother persistantes et 12 éphémères. Mémoire finale : 14 fiches de développement, 13 fiches d’expérience, 5 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — Hardware/compiler popcount lowering** : 3 essai(s), 3 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explore a compiler-recognized or x86 hardware-popcount implementation for each uint32_t XOR value. Verify that it builds with the frozen GCC 14.2 configuration and that its actual lowering is suitable for EPYC 9654; compare correctness and official latency against baseline. Preserve input order, the dependent result update, unsigned 32-bit wraparound, generic valid inputs, and the thread budget.

- **T2 — Scalar SWAR popcount alternative** : 4 essai(s), 4 valid ; profondeur maximale 3, 2 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Independently explore an inline scalar arithmetic popcount alternative, such as a 32-bit SWAR reduction, for the dependent update. Measure it against baseline and the hardware-popcount path, and establish whether the compiler canonicalizes it to the same implementation. Preserve exact uint32_t popcount and recurrence semantics for all valid inputs; do not rely on benchmark values.

- **T3 — Recurrent loop traversal and control overhead** : 4 essai(s), 4 valid ; profondeur maximale 2, 1 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explore sequential loop-control improvements—such as pointer traversal and modest ordered unrolling—to reduce index and branch overhead. Compare loop-only variants against the original baseline and report the change separately from any popcount change. Do not dismiss a correctness-preserving loop variant solely because its standalone gain is small with the naive popcount; retain compatible variants for integration to test alongside the selected fast-popcount implementation, comparing the merged result with both isolated candidates. Preserve exact pass/element order and the dependency, handle valid dimensions without unsafe flattened-count arithmetic, overwrite output every call, and do not parallelize the recurrence or exceed the threads budget.

Essais d’intégration G : 1. Commit retenu : `b0ee7ba58f17ad6800b7fa68ed8ef6dbbf3d7ae5`. Commit G : `99192ffccaf41980855989103266f9a866838867`.

### Ray tracing — raytracer / job 781193

40 CPU alloués, EPYC 9654. Session `7ca5c3544fff4475b27aef10e3f8c6a6`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **22**, dont 12 Mother persistantes et 10 éphémères. Mémoire finale : 10 fiches de développement, 12 fiches d’expérience, 7 leçons.

État de recherche : `infrastructure_error`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — Use the requested CPU thread budget for image parallelism** : 4 essai(s), 4 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explore OpenMP parallelization of the pixel or row loop using the threads argument as the maximum thread budget. Compare suitable work schedules while keeping each pixel's ray generation and traversal order unchanged, writing every output exactly once, and preserving the ABI. Validate hit IDs and depth tolerance across the required thread counts and changed cameras and resolutions; report measured performance at 1, 4, and 40 threads.

- **T2 — Reduce scalar BVH bounding-box and node traversal cost** : 3 essai(s), 3 valid ; profondeur maximale 2, 1 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Optimize the scalar BBoxIntersect and BVH node-walk hot path. Preserve the existing bounds acceptance rules, split-axis traversal order, primitive visitation behavior, and stack safety; do not cache hits or change input data. Verify correctness for boundary and varied-camera cases, and report measured performance at the required thread counts.

- **T3 — Explore SIMD packet tracing across pixel rays** : 1 essai(s), 1 infrastructure_error ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explore SIMD packet tracing across independent, spatially adjacent pixel rays, contrasting it with the scalar single-ray path. Verify the active target/compiler ISA and matching documentation before selecting an implementation; do not change compiler flags or the target. Handle traversal divergence with lane masks and/or scalar fallback as appropriate. Preserve per-ray intersection rules and hit identifiers, depth tolerance, full output writes, and the no-cached-hits constraint. Validate changed cameras and resolutions, measure at 1, 4, and 40 threads, and record infeasible or slower trials. Keep this distinct from T1's thread-level parallelism and T2's scalar BVH micro-optimization.

Essais d’intégration G : 3. Commit retenu : `9566a6000f050a2489c4baa16ad2f0533be686db`. Commit G : `fc387887531dd17a80ece6235826a6d5c6ebb078`.

### Réduction GPU — reduction / job 781178

4 CPU alloués, 1 GPU GH200. Session `a987e665bcbb4df2b15f8e8ddb5affa0`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **8**, dont 5 Mother persistantes et 3 éphémères. Mémoire finale : 4 fiches de développement, 5 fiches d’expérience, 4 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — Réduction hiérarchique à deux passes : comparaison des primitives warp/bloc et débit des CTA** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Dans src/candidate.cu, remplacer la chaîne de réductions pour les grandes entrées par une réduction hiérarchique à deux passes : des CTA traitent des tuiles coalescées, écrivent leurs partiels dans scratch, puis un kernel final écrit directement dans out. Comparer explicitement une réduction personnalisée warp/shuffle (notamment le helper `warpReduceSum` existant) à CUB `BlockReduce`, autorisé par le contrat ; explorer tailles de tuile et éléments par thread. Gérer les queues, petits n et sommes intermédiaires sans lecture hors limites ni dépendance à l’initialisation de scratch. Mesurer le temps complet et valider tous les cas de contrôle ainsi que n=4194304.

- **T2 — Réduction en un kernel avec synchronisation coopérative de grille** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Dans src/candidate.cu, évaluer un kernel de réduction à lancement coopératif : les CTA calculent des partiels, synchronisent la grille avec Cooperative Groups, puis un CTA produit out. Choisir une grille compatible avec les contraintes de lancement coopératif et l’occupation ; vérifier explicitement que le lancement fonctionne sur la cible et conserver une voie de repli correcte si nécessaire. Respecter les limites des buffers, les entrées de queue et les sommes intermédiaires exactes. Mesurer le temps total et valider tous les cas de contrôle ainsi que n=4194304 ; une réduction du nombre de lancements ne suffit pas à conclure à un gain.

- **T3 — Accumulation atomique : coût de contention et exactitude malgré les dépassements intermédiaires** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Dans src/candidate.cu, évaluer une réduction par CTA suivie d’une accumulation atomique, en initialisant explicitement l’accumulateur à chaque appel dans le flux par défaut. Ne pas supposer que des partiels ou leur somme temporaire tiennent en int32 simplement parce que le résultat final y tient : accumuler les partiels en int64 et comparer une accumulation atomique unsigned modulo 2^32 dans out à un accumulateur int64 en scratch avec conversion finale. Inclure initialisation et éventuelle finalisation dans la mesure ; ne pas utiliser d’allocation supplémentaire. Valider l’exactitude pour tous les cas de contrôle et n=4194304.

Essais d’intégration G : 1. Commit retenu : `bc06b33364947603b1dd1de4e586350d914e2a16`. Commit G : `bc06b33364947603b1dd1de4e586350d914e2a16`.

### S4ConvD — s4convd / job 781179

4 CPU alloués, 1 GPU GH200. Session `3f9eaa71294f48248f831e6ba7be02c1`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **10**, dont 5 Mother persistantes et 5 éphémères. Mémoire finale : 5 fiches de développement, 6 fiches d’expérience, 1 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — Forward/gx launch mapping and fusion contrast** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Keep gk unchanged. Compare separate forward/gx launches with a fused per-row launch, and compare generic flattened-output versus grouped-row mappings. Keep direct per-output tap loads as the control so launch/mapping effects are distinguishable from stencil input reuse. Preserve runtime dimensions, padding, gx tap reversal, full FP32, and fresh writes; measure correctness and official full-call timing.

- **T2 — Forward/gx stencil input reuse** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Keep gk and launch/fusion strategy unchanged. Compare the direct-load stencil with a shared-memory or warp-neighbor tile that reuses x for forward and gy for gx across taps. Control mapping where practical and report necessary mapping changes separately. Preserve row boundaries, zero padding, runtime K, gx reversal, and full FP32; judge by correctness and full-call timing.

- **T3 — gk reduction topology: single-CTA versus split partials** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Keep forward/gx unchanged. Contrast a no-scratch, one-CTA-per-(h,j) reduction parallelized over batch/time with chunked per-coefficient partials plus a final reduction in scratch. For the partial variant, write every value before reading it and respect scratch capacity; neither variant may depend on initialized memory or accumulate across calls. Preserve FP32 and validate correctness and full-call timing.

- **T4 — gk multi-tap tiled data reuse** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Keep forward/gx unchanged. Explore a distinct gk approach that computes several tap coefficients from a cooperatively loaded x/gy tile, thereby reusing row data across taps. Compare it with a per-coefficient direct-load reduction control; keep the reduction/writeback design explicit, use scratch only within capacity, and fully overwrite gk on every call. Preserve runtime dimensions, boundaries, and FP32; measure correctness and full-call timing.

Essais d’intégration G : 1. Commit retenu : `c72ee5545644b220d0e779756c27a952d8b9f857`. Commit G : `c72ee5545644b220d0e779756c27a952d8b9f857`.

### SGEMM CUDA — sgemm / job 781115

4 CPU alloués, 1 GPU GH200. Session `c8cd0409047941f380f50a399e4580d8`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **26**, dont 6 Mother persistantes et 20 éphémères. Mémoire finale : 16 fiches de développement, 16 fiches d’expérience, 8 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **non**. G : `confirmed`.

Diagnostic de pipeline : ForestError: Submission requires a Makefile and run.sh in the imported repository

- **T1 — Mapping coalescé, puis réutilisation et tuilage SIMT FP32** : 10 essai(s), 10 valid ; profondeur maximale 2, 4 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Construire des variantes SIMT FP32 en séparant d’abord l’effet du mapping de celui de la réutilisation : comparer le kernel naïf à un kernel direct sans mémoire partagée, mais avec les colonnes row-major contiguës affectées aux lanes, puis à un kernel synchrone à tuiles partagées. Après ce contrôle, explorer réutilisation A/B, accumulateurs en registres et dimensions de tuiles, seuls ou combinés. Appliquer alpha et beta une seule fois, préserver l’exactitude FP32 et les bords, ne pas ajouter d’allocation et produire C pour toutes les tailles. Rapporter correction et temps répétés pour chaque variante sur le cas 4096.

- **T2 — Comparaison contrôlée du chargement TMA asynchrone sur Hopper** : 4 essai(s), 3 valid, 1 generation_failed ; profondeur maximale 2, 1 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Pour isoler le mécanisme de chargement, comparer d’abord un kernel SIMT FP32 synchrone et sa variante TMA avec le même mapping de sortie, les mêmes tuiles et le même calcul; mesurer l’effet de TMA et de la profondeur du pipeline avant de modifier ces autres paramètres. Vérifier la faisabilité cible/CUDA 12.6.3, la synchronisation, les alignements et les bords; conserver alpha/beta et le calcul FP32 complet sans allocation supplémentaire. Ensuite, explorer le réglage ou la combinaison des variantes si les mesures le justifient. Rapporter correction et temps répétés sur le cas 4096, ainsi que tout obstacle de compatibilité.

Essais d’intégration G : 1. Commit retenu : `333cfd136707d8ec68b4f134f90a5a24f6b2be25`. Commit G : `7c0c0c85e7fb6452fefbb195e643987fbf72086e`.

### Softmax — softmax / job 781180

4 CPU alloués, 1 GPU GH200. Session `02dd873bedb4448ba9a082e5f0ccd1ea`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **7**, dont 5 Mother persistantes et 2 éphémères. Mémoire finale : 3 fiches de développement, 4 fiches d’expérience, 1 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — Fused Triton softmax: one CTA per row** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Develop and measure a general fused Triton softmax using one program/CTA per row. Compute the row maximum, exponentials, and normalization in FP32 in one kernel; handle arbitrary row/column tails with masks and tune the row reduction layout/warp count. Change only src/candidate.py in this research branch. Preserve input immutability, fresh same-shape CUDA FP32 output, numerical tolerance, and correctness on all required and independent inputs; use only the official evaluation protocol.

- **T2 — Fused Triton softmax: multiple rows per CTA** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Develop and measure a general fused Triton softmax that processes a tunable group of rows per program/CTA, with a row-wise reduction layout (for example, warp cooperation per row). Tune grouping and layout for throughput while handling both row and column tails. Change only src/candidate.py in this research branch. Preserve input immutability, fresh same-shape CUDA FP32 output, numerical tolerance, and correctness on all required and independent inputs; use only the official evaluation protocol.

Essais d’intégration G : 1. Commit retenu : `4cd8282d9f32637ec22ad20f64c9dd360a599b31`. Commit G : `4cd8282d9f32637ec22ad20f64c9dd360a599b31`.

### Stencil 3D CPU — stencil3d / job 781174

4 CPU alloués, EPYC 9654. Session `71716815d6684de2856c5861cd66df7f`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **9**, dont 6 Mother persistantes et 3 éphémères. Mémoire finale : 4 fiches de développement, 5 fiches d’expérience, 1 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — Comparaison du cycle de vie OpenMP et du découpage des cellules** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Comparer explicitement une équipe OpenMP conservée pour les six pas (avec barrière entre les pas) à une région parallèle relancée pour chaque pas. Comparer aussi un découpage statique en plans z à un découpage statique aplati sur z/y. Utiliser le budget `threads`, conserver le noyau arithmétique et l’alternance des buffers, sans tuilage temporel. Valider les petits cas et les frontières, puis mesurer à 1 et 4 threads sur n=256. Rapporter séparément les effets du cycle de vie de l’équipe et du découpage.

- **T2 — Vectorisation SIMD et génération du code du noyau** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Optimiser le noyau d’un pas autour de l’axe x contigu : rendre les offsets et coefficients propices à la vectorisation GCC/OpenMP SIMD et examiner des chargements ou déroulages sûrs. Ne pas changer le découpage entre threads ni fusionner des pas; éviter les lectures hors limites et n’utiliser des intrinsics que si compatibles avec le build figé. Valider la tolérance sur les cas officiels et comparer à 1 et 4 threads.

- **T3 — Réduction du trafic mémoire : initialisation et tuilage spatial/temporel** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explorer la réduction du trafic mémoire en séparant trois variantes : (1) éviter les copies/initialisations des cellules intérieures qui seront réécrites, en lisant input1 directement au premier pas et en écrivant exactement toutes les cellules hors de [4,n-4)^3 dans les deux sorties; (2) tuilage spatial sans fusion temporelle comme contrôle; (3) tuilage temporel à différentes profondeurs, avec halos couvrant les dépendances de rayon 3 par pas. Pour les petits n sans intérieur, préserver le comportement complet d’initialisation. Écrire l’intégralité des sorties à chaque appel, respecter les frontières, le budget de threads et inclure l’allocation scratch dans les mesures. Ne pas explorer ici les stratégies de scheduling (T1) ou SIMD (T2). Valider et mesurer chaque variante séparément à 1 et 4 threads sur n=256; conserver les versions correctes même plus lentes si elles sont utiles à une combinaison ultérieure.

Essais d’intégration G : 1. Commit retenu : `589fb88b8ecb46d37e9f73624a3a48fd3b2be89b`. Commit G : `589fb88b8ecb46d37e9f73624a3a48fd3b2be89b`.

### Stencil Y CUDA — stencil_y / job 781116

4 CPU alloués, 1 GPU GH200. Session `149c16f3f04f476eb03863fbc559f27f`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **34**, dont 7 Mother persistantes et 27 éphémères. Mémoire finale : 27 fiches de développement, 24 fiches d’expérience, 12 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **non**. G : `confirmed`.

Diagnostic de pipeline : ForestError: Submission requires a Makefile and run.sh in the imported repository

- **T1 — Coalesced scalar direct-global y stencil** : 4 essai(s), 2 valid, 2 incorrect ; profondeur maximale 2, 1 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : In src/candidate.cu, test a single-launch direct-global stencil with one output per thread and warp lanes mapped to contiguous x positions. Load the eight y-neighbors directly, apply the specified coefficients, and implement the period-63 wrapping correctly at both endpoints. Avoid shared-memory staging and barriers. Compare complete-run latency with the baseline while validating all outputs on varied signed inputs against the oracle.

- **T2 — Coalesced shared-memory y tiling** : 9 essai(s), 9 valid ; profondeur maximale 3, 6 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : In src/candidate.cu, test a single-launch shared-memory design with x-contiguous warp accesses and cooperative loading of a multi-row y tile plus the required halos. Explore tile height and block mapping to balance sample reuse, barriers, and occupancy. Preserve the exact period-63 neighbor mapping and produce every output; compare complete-run latency and oracle correctness.

- **T3 — Arithmetic specialization with baseline dataflow** : 9 essai(s), 9 valid ; profondeur maximale 2, 1 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Preserve the baseline's one-launch thread mapping and shared-memory dataflow while testing whether arithmetic changes help: specialize the fixed y coefficients from the specified FP32 expressions and compare equivalent accumulation/FMA forms. Do not alter neighbors, endpoint handling, buffer behavior, or output coverage. Check the stated tolerance on varied signed inputs, including cancellation cases, and compare full-run latency. Keep changes separable so a validated arithmetic improvement can later be combined with a faster layout from another tree.

Essais d’intégration G : 1. Commit retenu : `6e67b2e7565d8fe16129bac260683b0f124ef141`. Commit G : `6e67b2e7565d8fe16129bac260683b0f124ef141`.

### Somme des valeurs absolues — sumabs / job 781181

4 CPU alloués, 1 GPU GH200. Session `9ac3c829d76f47ca880c399789c188d5`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **9**, dont 6 Mother persistantes et 3 éphémères. Mémoire finale : 5 fiches de développement, 5 fiches d’expérience, 3 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — Single-pass fused block reduction with atomic output** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Test a single-kernel path that reads x directly, computes abs values, reduces within each block, and atomically adds each block total to output. Include output initialization and launch cost in end-to-end measurements. Vary work per block and grid size to assess whether reduced launch/traffic costs outweigh atomic contention, across small and large valid n. Compare with the supplied baseline and the non-atomic partial-reduction alternative; preserve the run signature, default-stream ordering, bounds safety, and correctness for every valid input. Do not specialize to listed test sizes.

- **T2 — Direct-input two-stage hierarchical reduction** : 2 essai(s), 2 valid ; profondeur maximale 2, 1 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Test a two-stage path whose first kernel reads x directly, computes abs values, and writes one partial per block to scratch; the second reduces only the written partials and overwrites output. Tune first-stage work and grid size to balance input throughput against the final partial-reduction cost. Include both launches in end-to-end measurements and compare against the atomic single-kernel alternative and supplied baseline. Do not rely on initialized scratch; write every partial consumed, preserve the run signature, default-stream ordering, bounds safety, and correctness for every valid input. Do not specialize to listed test sizes.

Essais d’intégration G : 1. Commit retenu : `858fba34d62836a6fe907b3d372251f77a6062dd`. Commit G : `858fba34d62836a6fe907b3d372251f77a6062dd`.

### Transpose CUDA — transpose / job 781117

4 CPU alloués, 1 GPU GH200. Session `4dfe419e7637426aa0225f0798d840b7`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **33**, dont 6 Mother persistantes et 27 éphémères. Mémoire finale : 23 fiches de développement, 23 fiches d’expérience, 15 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **non**. G : `confirmed`.

Diagnostic de pipeline : ForestError: Submission requires a Makefile and run.sh in the imported repository

- **T1 — Transposition tuilée et coalesçage des accès globaux** : 8 essai(s), 8 valid ; profondeur maximale 2, 3 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explorer principalement une transposition tuilée qui transforme les accès stridés du baseline en lectures et écritures globales coalescées. Prendre une tuile partagée conflict-free, par exemple 32x33, comme hypothèse de départ plutôt que comme obligation ; comparer si utile des géométries CTA et du travail scalaire ou vectorisé par thread. Préserver l’API, le flux par défaut, l’absence d’allocation et la copie bit-exacte de toutes les valeurs. Vérifier la correction à n=32,64,256,1024 et comparer des temps répétés de l’exécution complète à n=1024 sur la cible fixée, sans présumer qu’un accès nominalement coalescé sera plus rapide.

- **T2 — Échange des données par registres et lanes : voie alternative ou hybride** : 5 essai(s), 5 valid ; profondeur maximale 3, 3 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Évaluer comme approche alternative un échange de valeurs par registres et lanes, avec les shuffles comme une possibilité, afin de voir si les accès globaux peuvent être coalescés à moindre coût de synchronisation ou de mémoire partagée. Ne pas exiger une solution exclusivement intra-warp : tester une variante hybride si l’échange entre warps ou une permutation différente est nécessaire. Préserver les bits FP32, valider la participation et les masques des lanes, tester toutes les dimensions de correction et mesurer à n=1024 avec des répétitions comparables. Rapporter aussi un résultat négatif si le coût des échanges ou des transferts annule le bénéfice attendu.

- **T3 — Ordre des blocs : expérience contrôlée sur une transposition tuilée** : 8 essai(s), 8 valid ; profondeur maximale 2, 1 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Isoler l’effet de l’ordre des blocs sur une transposition tuilée correcte à accès coalescés. Dans cette branche indépendante, établir un contrôle row-major, puis garder fixes son code intra-CTA, sa géométrie et son mapping de données pendant la comparaison avec un remappage diagonal ou une autre permutation bijective des CTAs. Comparer sur les grilles correspondant aux dimensions valides. Traiter un effet éventuel sur la localité, le cache ou les partitions mémoire comme une hypothèse à mesurer, pas comme un fait ; conserver le changement seulement s’il passe les tests exacts et améliore les mesures répétées de l’exécution complète à n=1024.

Essais d’intégration G : 1. Commit retenu : `63e81efb0ef64c0f37e55a8f1a7b5333da58e83b`. Commit G : `63e81efb0ef64c0f37e55a8f1a7b5333da58e83b`.

### UTF-8 — utf8 / job 781175

1 CPU alloués, EPYC 9654. Session `ccf9c4524fab484ab8840569ffee1089`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **16**, dont 5 Mother persistantes et 11 éphémères. Mémoire finale : 10 fiches de développement, 8 fiches d’expérience, 5 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — Full SIMD validation of UTF-8 blocks** : 2 essai(s), 2 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explore a direct block-wise SIMD UTF-8 validator: classify bytes and validate continuation structure plus overlong, surrogate, and Unicode upper-bound restrictions using masks, correctly carrying boundary conditions between blocks and validating the tail without out-of-bounds reads. Use only intrinsics compatible with the frozen target and build; do not change compiler flags, target, or thread budget. Preserve correctness for every input and record candidate measurements and failed variants.

- **T2 — Word-at-a-time ASCII-span skipping with scalar fallback** : 3 essai(s), 3 valid ; profondeur maximale 2, 1 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explore word-at-a-time detection of ASCII spans using ordinary scalar operations, then validate non-ASCII bytes with an exact scalar UTF-8 parser. Use safe loads (for example, memcpy-based word reads where needed), and handle alignment, boundaries, short inputs, and tails without out-of-bounds access or aliasing assumptions. Preserve all UTF-8 validity rules, the ABI, full output overwrite, and the thread budget. Compare against the byte-at-a-time baseline path on the official valid mixed-width workload; record correctness, timings, and failed variants. This is an alternative bulk-scan mechanism, not a restriction on other correctness-preserving experiments.

- **T3 — Table-driven scalar UTF-8 DFA** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Explore a serial, branch-reduced scalar UTF-8 DFA using byte classes and compact state transitions instead of the baseline's per-codepoint branch structure. Encode all continuation, overlong, surrogate, truncation, and maximum-code-point constraints; avoid per-call table construction and any assumptions about input contents. Preserve the ABI and output behavior, respect the threads budget, and record correctness, timing, and failed variants.

Essais d’intégration G : 1. Commit retenu : `ad28ccd027ca3adf78cf7293b0aa7ff37e72a855`. Commit G : `ad28ccd027ca3adf78cf7293b0aa7ff37e72a855`.

### Rendu volumique — volume / job 781192

40 CPU alloués, EPYC 9654. Session `4730a16c8e54415faaccecb2b31c1881`. Nouveau répertoire et nouvelle base de mémoire.

Invocations Codex : **6**, dont 3 Mother persistantes et 3 éphémères. Mémoire finale : 4 fiches de développement, 5 fiches d’expérience, 3 leçons.

État de recherche : `budget_exhausted`. Pipeline complet : **oui**. G : `confirmed`.

- **T1 — Parallélisme OpenMP du rendu par pixels** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Dans `src/candidate.cpp`, paralléliser le parcours indépendant des lignes ou pixels de `volume_serial` avec OpenMP, en respectant `threads` comme plafond pour les budgets valides et en conservant un chemin sériel pour un seul thread. Éviter tout état mutable partagé. Ne modifier ni les calculs par rayon, ni les interpolations, ni les pas d’échantillonnage. Vérifier le remplissage complet de l’image et la correction, puis mesurer à 1, 4 et 40 cœurs.

- **T2 — Réduction du coût d’interpolation de densité** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Dans `src/candidate.cpp`, optimiser exclusivement `D` et `Density` : réduire les calculs répétés d’indices, de clamps et d’adresses pour l’interpolation trilineaire. Préserver le test de volume, le calcul des coordonnées, la conversion flottant-entier et son comportement aux limites, les clamps et les valeurs pour toute dimension d’entrée valide. Ne pas modifier le parcours des rayons ou introduire de cache d’answers. Valider les caméras redimensionnées et densités modifiées, puis comparer les performances.

- **T3 — Optimisation du parcours de transmittance des rayons d’ombre** : 1 essai(s), 1 valid ; profondeur maximale 1, 0 essai(s) repartant d’un candidat antérieur.

  Objectif déclaré : Dans `src/candidate.cpp`, cibler uniquement la mise en place et le parcours des rayons d’ombre dans `transmittance` et ses aides dédiées. Réduire le coût de l’intersection avec le volume ou du calcul des incréments sans toucher à `Density` ni au parcours primaire. Conserver les extrémités, le pas de 0,2, les échantillons effectivement visités, l’accumulation de `tau` et le calcul final de transmittance. Valider tous les cas prévus et mesurer séparément la performance.

Essais d’intégration G : 1. Commit retenu : `9fbb1576cf62e5f738c85df1d8067012723ffc29`. Commit G : `9fbb1576cf62e5f738c85df1d8067012723ffc29`.

## Traçabilité de cet audit

Le script `audit_forest_execution.py` lit les bases SQLite en mode lecture seule, vérifie les sessions des requêtes, les scopes des fiches mémoire, les démarrages Mother et les options réellement passées au client Codex. Il relève les threads dans les événements `thread.started` et contrôle leur non-réutilisation entre campagnes. Les empreintes des bases, résultats, configurations et invocations sont dans AUDIT-FOREST.json. Les invocations complètes restent dans les dossiers de travail locaux ; l’export fournit les champs utiles à l’audit sans exporter la configuration de connexion du relais.

Le moteur figé inclus dans PREUVES-ET-CODES.zip permet de relire les règles : `controller.py:create_workspace`, `gitops.py:initialize_source`, `codex_process.py:command_for`, `codex_conversation.py`, `forest_scheduler.py:run_research`, `memory_retrieval.py:MemoryReader`, `node_harness.py:NodeHarness` et `evaluator.py:_target`. Les bases de chaque campagne et les plans sont dans les archives natives déjà fournies. Les interventions de préparation sont décrites séparément des preuves automatiques ; un journal d’exécution seul n’est pas une preuve exhaustive de toute action opérateur.
