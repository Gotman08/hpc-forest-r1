from pathlib import Path
import json,collections
R=Path(__file__).resolve().parent;O=R.parent.parent/'outputs/comparaison-references'
D=json.loads((O/'AUDIT-FOREST.json').read_text(encoding='utf8'));rows=D['campaigns'];s=D['summary']
def fmt(x):return '—' if x is None else f'{x:.1f}'.replace('.',',')
def yn(x):return 'oui' if x else 'non'
def clean(x):return str(x or '—').replace('|','\\|').replace('\n',' ')
labels={'aobench':'AOBench','argmin':'Argmin','base64':'Base64','binomial':'Options binomiales','blackscholes':'Black–Scholes','deferred':'Deferred shading','gemm_cpu':'GEMM CPU','mandelbrot':'Mandelbrot','noise':'Bruit Perlin','popcount':'Popcount','raytracer':'Ray tracing','reduction':'Réduction GPU','s4convd':'S4ConvD','sgemm':'SGEMM CUDA','softmax':'Softmax','stencil3d':'Stencil 3D CPU','stencil_y':'Stencil Y CUDA','sumabs':'Somme des valeurs absolues','transpose':'Transpose CUDA','utf8':'UTF-8','volume':'Rendu volumique'}
text=f'''# Forest : contexte, mémoire, interventions et arbres réellement exécutés

Audit du {s['audit_utc']}. Les résultats de performance ne sont pas modifiés. Cet audit lit les 22 configurations, les 22 bases SQLite archivées et les 325 invocations locales du client Codex.

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
'''
for r in rows:
    name=labels[r['case_id']]+(' (import initial)' if r['campaign']=='deferred' else ' (reprise neuve)' if r['campaign']=='deferred_r2' else '')
    counts='/'.join(str(t['attempts']) for t in r['tree_details']) or '—'
    errs=', '.join(f'{r["trial_statuses"][k]} {label}' for k,label in [('infrastructure_error','E'),('generation_failed','Gén.'),('incorrect','I')] if r['trial_statuses'].get(k)) or ('import' if not r['trees_selected'] else '—')
    text+=f"| {name} | {r['job_id']} | {r['trees_selected']} | {counts} | {r['trial_counts'].get('G',0)} | {r['trial_statuses'].get('valid',0)} / {sum(r['trial_counts'].values())} | {errs} | {fmt(r['slurm_elapsed_seconds']/60 if r['slurm_elapsed_seconds'] is not None else None)} |\n"
text+='''
La recherche s’arrête sur une erreur d’infrastructure pour Base64, AOBench, ray tracing et deferred_r2. Les autres arbres déjà admis sont drainés et l’intégration peut encore avoir lieu. Cela explique notamment le faible nombre d’essais de certaines familles. Une longue durée totale ne signifie donc pas une recherche profonde : AO prend environ 63 minutes, dont environ 30,5 minutes de confirmation.

## Objectifs, mémoire et diagnostic pour chaque campagne

Les sujets et objectifs ci-dessous sont les sorties exactes de Mother, en anglais, après sa revue. Ils ne sont pas des suggestions ajoutées après coup par l’assistant. Les profondeurs comptent la première proposition au niveau 1. Les compteurs mémoire sont des fiches conservées, distinctes des essais et des appels modèle.

'''
for r in rows:
    text+=f"### {labels[r['case_id']]} — {r['campaign']} / job {r['job_id']}\n\n"
    alloc=f"{r['requested_cpus']} CPU alloués"+(f", {r['requested_gpus']} GPU GH200" if r['requested_gpus'] else ', EPYC 9654')
    text+=f"{alloc}. Session `{r['session_id']}`. Nouveau répertoire et nouvelle base de mémoire.\n\n"
    text+=f"Invocations Codex : **{r['invocation_count']}**, dont {r['persistent_invocations']} Mother persistantes et {r['ephemeral_invocations']} éphémères. Mémoire finale : {r['memory_records'].get('development',0)} fiches de développement, {r['memory_records'].get('experiment',0)} fiches d’expérience, {r['memory_records'].get('lesson',0)} leçons.\n\n"
    text+=f"État de recherche : `{r['scheduler'].get('status','non commencée')}`. Pipeline complet : **{yn(r['pipeline_complete'])}**. G : `{r['final_g_status'] or 'absent'}`.\n\n"
    if r['pipeline_error']:text+='Diagnostic de pipeline : '+r['pipeline_error']+'\n\n'
    if r['selected_is_baseline']:text+='**Le naïf a été conservé comme meilleur confirmé.**\n\n'
    for t in r['tree_details']:
        status=', '.join(f'{v} {k}' for k,v in t['statuses'].items())
        text+=f"- **{t['role']} — {t['subject']}** : {t['attempts']} essai(s), {status} ; profondeur maximale {t['max_mission_depth']}, {t['nonbaseline_parent_attempts']} essai(s) repartant d’un candidat antérieur.\n\n  Objectif déclaré : {t['objective']}\n\n"
    text+=f"Essais d’intégration G : {r['trial_counts'].get('G',0)}. Commit retenu : `{r['selected_commit'] or 'aucun'}`. Commit G : `{r['final_g_commit'] or 'aucun'}`.\n\n"
text+='''## Traçabilité de cet audit

Le script `audit_forest_execution.py` lit les bases SQLite en mode lecture seule, vérifie les sessions des requêtes, les scopes des fiches mémoire, les démarrages Mother et les options réellement passées au client Codex. Il relève les threads dans les événements `thread.started` et contrôle leur non-réutilisation entre campagnes. Les empreintes des bases, résultats, configurations et invocations sont dans AUDIT-FOREST.json. Les invocations complètes restent dans les dossiers de travail locaux ; l’export fournit les champs utiles à l’audit sans exporter la configuration de connexion du relais.

Le moteur figé inclus dans PREUVES-ET-CODES.zip permet de relire les règles : `controller.py:create_workspace`, `gitops.py:initialize_source`, `codex_process.py:command_for`, `codex_conversation.py`, `forest_scheduler.py:run_research`, `memory_retrieval.py:MemoryReader`, `node_harness.py:NodeHarness` et `evaluator.py:_target`. Les bases de chaque campagne et les plans sont dans les archives natives déjà fournies. Les interventions de préparation sont décrites séparément des preuves automatiques ; un journal d’exécution seul n’est pas une preuve exhaustive de toute action opérateur.
'''
(O/'DETAILS-FOREST.md').write_text(text,encoding='utf8')
print(json.dumps({'report':str(O/'DETAILS-FOREST.md'),'campaigns':len(rows),'research_trees':s['research_trees'],'characters':len(text)},ensure_ascii=False))
