from pathlib import Path
import json,datetime,sys,collections
R=Path(__file__).resolve().parent;D=json.loads((R/'analysis.json').read_text(encoding='utf8'));O=Path(sys.argv[1]) if len(sys.argv)>1 else R/'report-preview';O.mkdir(parents=True,exist_ok=True)
rows=D['rows'];byid={r['id']:r for r in rows};engines={e['case_id']:e for e in D['engines']}
def f(x,d=2):return 'NR' if x is None else f'{x:.{d}f}'.replace('.',',')
def esc(x):return str(x or '').replace('|','\\|').replace('\n',' ')
def rowtable(items):
 s=['| Programme / variante | Publié | Référence sur ROMEO | Forest sur ROMEO | Forest / référence |','|---|---:|---:|---:|---:|']
 for r in items:s.append('| '+esc(r['label'])+' | '+' | '.join(f(r.get(k))+'×' if r.get(k) is not None else 'NR' for k in ['published_speedup','reference_speedup','forest_speedup','forest_vs_reference'])+' |')
 return '\n'.join(s)
measured=[r for r in rows if r.get('forest_speedup')]
wins=[r for r in measured if (r.get('forest_vs_reference_range') or [0])[0]>1]
losses=[r for r in measured if (r.get('forest_vs_reference_range') or [0,2])[1]<1]
mixed=[r for r in measured if r not in wins+losses]
raw=D['measurements'];fails=D['summary']['final_failures'];candidatefails=[r for r in fails if r['variant'] in ['selected','final_g']]
counts=collections.Counter(t['status'] for t in D['trials']);complete=sum(e['pipeline_complete'] for e in D['engines'])
chosen=['CPU_ARGMIN_RANDOM','CPU_ISPC_BINOMIAL_1C','CPU_ISPC_BLACKSCHOLES_4C','CPU_ISPC_MANDELBROT_4C','CPU_BOEHM_O3_FINAL','gpu_sgemm_11','gpu_sgemm_cublas','gpu_reduce_07','gpu_softmax_triton','gpu_sum_abs_fusion','gpu_s4convd_kernels']
report=f'''# Comparaison publiée → ROMEO → Forest

Mesures du 23 octobre 2026 · synthèse générée {D['summary']['generated_at']}.

**{len(measured)} des 62 observations du classeur ont été mesurées**, à partir de {len(engines)} familles de programmes. Cinq observations ne sont pas reproduites faute de source complète ou d’entrées exactes. {'Les mesures de rendu sont encore en cours ; ceci est un brouillon.' if D['summary']['pending'] else 'La campagne finale est terminée.'}

Forest obtient des gains sur certaines familles et reste derrière les références sur d’autres. On ne peut donc pas conclure que le système atteint globalement les résultats du tableau. Les comparaisons de chaque variante sur ROMEO sont directes ; le passage d’un résultat publié à ROMEO combine les effets du matériel, du compilateur, des versions de sources et parfois des données et du protocole.

[Tableau de bord interactif](TABLEAU-DE-BORD.html) · [Classeur](COMPARAISON.xlsx) · [CSV](COMPARAISON.csv) · [Historique des essais](HISTORIQUE-FOREST.md) · [Audit du contexte, de la mémoire et des arbres](DETAILS-FOREST.md) · [Preuves et codes](PREUVES-ET-CODES.zip).

## Résultats représentatifs

{rowtable([byid[x] for x in chosen])}

Chaque speedup ROMEO est calculé par **temps du même naïf / temps de la variante**. La dernière colonne vaut temps de la référence / temps de Forest : au-dessus de 1, Forest est plus rapide. Les références publiées ne sont pas réutilisées comme dénominateur ROMEO.

Sur les lignes documentaires mesurées, Forest est plus rapide à chaque bloc dans {len(wins)} cas, la référence dans {len(losses)}, et le classement varie dans {len(mixed)}. **Ces comptes ne sont pas un taux de réussite sur des problèmes indépendants** : plusieurs lignes partagent le même naïf et le même candidat Forest, notamment les étapes SGEMM, la réduction et les matériels historiques de transpose. Les étendues observées ne sont pas des intervalles de confiance ; aucune significativité statistique n’est affirmée.

## Matériel et comparabilité

| Élément | CPU ROMEO | GPU ROMEO |
|---|---|---|
| Processeur | AMD EPYC 9654, 2 × 96 cœurs ; SMT désactivé | CPU Grace ARM + NVIDIA GH200 120 Go |
| Allocation | Sous-ensemble de 1, 4, 8 ou 40 cœurs physiques | 1 GPU alloué ; 4 CPU pour les outils/hôtes |
| Logiciels | GCC 14.2 ; Clang 17.0.6 pour la ligne popcount Clang ; ISPC 1.32.0, LLVM 23.1.2 | CUDA 12.6.3 ; pilote 590.48.01 ; torch 2.9.1+cu126 ; Triton 3.5.1 |
| Compilation | C++17, -O3 -march=native ; ISPC -O2 --target=avx512skx-x16 | -O3 -arch=sm_90 ; précision FP32, pas de remplacement par TF32 |

Les nœuds CPU sont partagés ; les cœurs attribués et l’affinité sont consignés. Il ne s’agit pas de nœuds entiers réservés. Les variantes d’un même cas final sont exécutées en série dans la même allocation, avec un ordre pseudo-aléatoire par bloc. Les familles indépendantes peuvent utiliser des allocations distinctes. Fréquence, caches, NUMA et charge extérieure restent des sources de variabilité ; aucun compteur matériel ne permet ici d’en attribuer précisément l’effet. Le tableau fournit les temps absolus, la dispersion et les compilateurs au lieu d’une correction fondée sur les FLOPS théoriques.

Les lignes à 1/4/40 cœurs ne sont pas toutes une étude à taille constante : AO passe de 512² à 2048², et les options de 131 072 à 2 097 152 éléments pour les lignes à 40 cœurs. Chaque speedup utilise son propre naïf de même taille. On ne peut pas déduire directement de ces lignes une efficacité de montée en nombre de cœurs à problème constant.

Le speedup publié et le speedup ROMEO répondent à une question différente du ratio Forest/référence sur ROMEO. Un gain publié de 30× qui devient 3× sur GH200 ne prouve pas que l’optimisation est mauvaise : le naïf et l’optimisé peuvent bénéficier différemment du nouveau matériel et du nouveau compilateur. L’effet *strictement matériel* nécessiterait également le même code, les mêmes entrées et un protocole identique sur les deux anciennes et nouvelles machines, ce qui n’a pas été réalisé.

Le code du moteur est identique dans les 22 lancements, vérification SHA256 fichier par fichier à l’appui. Les 58 fichiers Python correspondent au dépôt propre pour ces sources au commit `934627c1399b48e4aa0f25630e9c4223680a3511`. L’empreinte agrégée du manifeste trié vaut `047ebea64b2e1d39249d1b6303e0bcbcf1ff92ffb548658a5c91cb2d5ab7fb4e`. Les adaptateurs changent selon la famille ; la politique du moteur reste gelée.

## Protocole suivi

1. Lire les 62 lignes et leurs conditions dans le classeur, retrouver les sources primaires, figer les commits et empreintes des fichiers.
2. Construire et tester d’abord les références naïves et optimisées sur ROMEO : jobs 781111 (GPU initial, puis répétitions supplémentaires 781153), 781157/781163 (CPU et diagnostics), 781161 (GPU complémentaire), 781186 (rendus). Le test Clang 781195 commence également par les références avant de compiler les sources Forest déjà retenues sous GCC.
3. Démarrer Forest du naïf avec le moteur gelé, sans lui fournir le code optimisé de référence. Les contrôles, tailles, drapeaux de compilation et fichiers de données sont protégés. Le seul naïf réparé avant la recherche est UTF-8, dont la version historique est objectivement incorrecte sur des séquences malformées.
4. Conserver essais corrects, incorrects, erreurs d’infrastructure et intégrations. Confirmer le meilleur candidat et G séparément. Aucune optimisation manuelle n’est ajoutée aux candidats générés.
5. Recompiler les sources sélectionnées inchangées puis remesurer naïf, référence, meilleur confirmé et G sur les mêmes entrées, après échauffement. Les valeurs du tableau viennent de cette phase indépendante, pas du meilleur temps de recherche.

### Mesures et contrôles

| Groupe | Blocs finaux | Chronométrage | Contrôles supplémentaires |
|---|---:|---|---|
| CPU | 7 | Boucle native adaptative ≥0,1 s ; 3 échauffements ; temps mural | Graines 1907 + 53×bloc, variantes de données, gardes et immutabilité ; oracles adaptés au problème |
| GPU initial | 9 | Événements CUDA ; SGEMM 20 répétitions/5 échauffements, transpose et stencil 100/10 | Sorties complètes, tailles supplémentaires, erreurs CUDA, gardes mémoire |
| GPU complémentaire | 9 | Même chronomètre pour toutes les variantes d’un cas ; kernels/wrappers complets | 79 enregistrements diagnostiques, références FP64 selon les cas |
| Rendus | 3 | C++ steady_clock ; 2 échauffements ; boucle adaptative ≥0,05 s | Autres résolutions, caméra/densités/lumières modifiées, images complètes et IDs exacts pour ray tracing |

Le rapport des médianes est retenu, avec deux exceptions documentaires : UTF-8 « BEST » utilise le minimum des temps de lots, « MEAN » leur moyenne. L’ordre varie entre blocs. Les données et graines sont identiques entre variantes d’un bloc ; sur CPU, les SHA256 d’entrée ont été comparés automatiquement. Un seul tirage Forest par famille ne permet pas d’évaluer sa variabilité entre campagnes ou modèles.

AO reste un rendu stochastique : le générateur aléatoire peut différer pour permettre le parallélisme, mais la scène, les échantillons primaires et les 8×8 rayons d’occlusion par impact sont conservés. Le contrôle combine RMSE ≤0,06, biais moyen absolu ≤0,015 et revue du code. Une tolérance image seule ne suffirait pas à justifier une baisse de qualité.

## Résultats du moteur, diagnostics et régressions

{complete}/{len(engines)} campagnes retenues ont achevé le pipeline complet. L’historique contient {len(D['trials'])} essais enregistrés : {', '.join(str(v)+' '+str(k) for k,v in sorted(counts.items()))}. Les {len(raw)} enregistrements finaux incluent les diagnostics, pas seulement les temps. Échecs finaux de candidats Forest/G : **{len(candidatefails)}**. Échecs finaux de références : {len(fails)-len(candidatefails)} (1 naïf UTF-8 sur texte malformé et 2 tests du volume ISPC hors de sa précondition de dimensions).

- **UTF-8** : l’audit indépendant teste 79 729 chaînes par version, dont toutes les séquences de 1 et 2 octets, des frontières SIMD et des mutations déterministes. Le naïf historique échoue 5 773 fois ; le naïf réparé, la référence AVX, Forest et G n’échouent pas sur cet audit. Les speedups du tableau restent limités au texte valide chronométré. Le gain de validation correcte est distingué du gain de vitesse.
- **Accès aux outils** : deux essais de recherche Base64 échouent après une tentative d’accès à un outil non autorisé par le worker. Le meilleur confirmé reste le naïf scalaire. Le même diagnostic touche certaines branches des rendus (AO, ray tracing et deferred). Les journaux indiquent exactement les essais affectés. Cela montre une limite de cette exécution du moteur, pas l’impossibilité d’optimiser ces algorithmes. G Base64 existe mais est plus lent.
- **GPU initial** : recherche, sélection et confirmation ont produit des sources valides pour SGEMM, stencil et transpose ; la fin du pipeline échoue sur l’empaquetage, car l’adaptateur initial ne fournissait pas Makefile/run.sh. Le défaut est conservé dans les résultats. Les sources ont ensuite été revalidées et chronométrées indépendamment.
- **Deferred** : le premier import dépasse la limite de lecture de source de Mother (32 000 caractères) avant tout appel au modèle. Un nouveau lancement enlève uniquement l’indentation en début de ligne ; le flux de tokens C++ est identique, commentaires de licence conservés. Le premier échec reste archivé. Les sources et protocoles expérimentaux ne sont pas optimisés à cette occasion.
- **Volume ISPC** : le noyau documente une précondition de dimensions multiples de 4. Les contrôles additionnels en 96×126 et 128×169 sortent de ce domaine et provoquent deux plantages. Un audit distinct avec une zone de garde agrandie confirme 192 et 384 écritures hors de l’image, pour les versions ISPC simple et tasks. Sur les tailles admissibles 224×296 et 336×444, les 10 contrôles des cinq variantes passent. Forest et le naïf passent aussi les deux petites tailles hors domaine ISPC. Le benchmark 896×1184 satisfait la précondition ; ses temps ne sont pas rejetés. Aucun masque ou changement du code de référence n’a été ajouté aux mesures.
- **Clang** : le premier job final ne charge pas libomp et produit des erreurs d’infrastructure, malgré un code de sortie SLURM zéro. Il est exclu des temps. Le job 781195 charge le runtime et fournit les mesures valides.
- **Intégration G** : le tableau principal utilise le meilleur confirmé par le moteur. Les colonnes détaillées conservent G même s’il régresse, en particulier sur SGEMM, GEMM CPU, Base64 et ray tracing à 40 cœurs (13,38× pour le meilleur confirmé contre 10,10× pour G). Aucun remplacement manuel après coup n’est effectué.

### Changements qui expliquent les gains observés

La revue du code relie les candidats aux transformations réelles ; elle ne remplace pas une étude d’ablation.

| Famille | Transformation observée dans le candidat retenu | Limite d’interprétation |
|---|---|---|
| Argmin | Réduction SIMD par blocs, puis récupération stable du premier indice | Deux distributions et tailles de contrôle, pas tous les usages possibles |
| GEMM CPU | Micro-noyau AVX2/FMA 4×16 et parallélisme OpenMP | Comparaison à une adaptation de l’article ; le facteur face au naïf est très dépendant du compilateur |
| Binomial | Espérance binomiale équivalente aux 63 transitions historiques, récurrence des puissances, OpenMP | Le gain à 1/4 cœurs ne garantit pas le même classement à 40 |
| Réduction GPU | Plusieurs éléments par thread, réduction par warp et deux passes | Référence moderne portée, pas exécution inchangée du code G80 |
| sum(abs) | Fusion et réduction par blocs CUB, plusieurs accumulateurs | Volume exact fixé à 1 GiB, celui du billet historique reste ambigu |
| Softmax | Noyau Triton fusionné avec regroupement de lignes | Le gain face au Triton de référence est plus petit que celui face au naïf |
| Occlusion ambiante | Calculs invariants d’intersection réutilisés et accumulation RGB commune | Nombre de rayons conservé ; le candidat reste séquentiel après l’échec de la branche de parallélisme |
| Volume | OpenMP, réutilisation des indices et pointeurs d’interpolation, intersection des ombres adaptée aux origines intérieures | Pas d’échantillonnage et rayons conservés ; domaine de la référence ISPC limité aux dimensions multiples de 4 |
| S4ConvD | Fusion du forward et d’une partie du backward, réduction du gradient poids | Ici la référence complète reste plus rapide ; pas d’extrapolation à une epoch |
| Black-Scholes / Mandelbrot | Parallélisme CPU, vectorisation restant limitée face à ISPC | La montée en nombre de cœurs ne suffit pas à combler le déficit SIMD |

Les hypothèses détaillées, les commits parents, les essais invalides et les essais d’intégration figurent dans [HISTORIQUE-FOREST.md](HISTORIQUE-FOREST.md). Les compteurs de tokens natifs peuvent additionner plusieurs fois des compteurs cumulés de conversations reprises ; aucun coût total n’est présenté comme audité.

La cible de 30 minutes est une cible d’admission, avec la politique `finish-started` : les confirmations commencées peuvent la dépasser. La feuille Moteur et l’historique donnent les durées observées et dépassements. Dans les rendus, chaque évaluation reconstruit aussi l’image oracle hors chronométrage : cette validation répétée peut dominer le temps mural de la campagne, sans faire partie du temps du noyau affiché. Les statistiques d’efficacité SLURM décrivent l’allocation entière, attentes modèle comprises ; elles ne mesurent pas l’efficacité du noyau optimisé seul.

## Observations non reproduites

'''
for r in rows:
 if r.get('case_id') is None:report+=f"- **{r['label']}** : {r['notes']} [Source]({r['source']}).\n"
report+='''
## Adaptations et sources, par famille

Les lignes « remesurées » incluent des ports ou reconstructions explicités ci-dessous. Ce sont des comparaisons reproductibles sur ROMEO, pas des reproductions exactes de toutes les conditions historiques.

'''
for key in sorted({r['case_id'] for r in rows if r.get('case_id')}):
 rs=[r for r in rows if r.get('case_id')==key];urls=list(dict.fromkeys(r['source'] for r in rs));report+=f"- **{key}** — {rs[0]['notes']} "+' · '.join(f'[Source {i+1}]({u})' for i,u in enumerate(urls))+'\n'
report+='\n## Tableau complet des 62 observations\n\n'+rowtable(rows)+'\n\n## Fichiers et traçabilité\n\n'
report+='''Le classeur source est conservé intact dans les preuves. Les feuilles du nouveau classeur distinguent les ratios calculés, les conditions, les mesures brutes, les essais et l’état du moteur. Le dashboard expose les temps, étendues par paire, diagnostics et commits au clic sur une ligne.

L’archive contient les résultats bruts, les captures d’environnement, les scripts, les sources des références et les archives natives des campagnes. MANIFEST-SHA256.json permet de contrôler les fichiers inclus. Les détails d’authentification du relais ne sont pas exportés. Les calculs ont été exécutés dans des jobs SLURM, pas sur le nœud de login.

L’étude historique antérieure est conservée séparément : [comparaison des anciens codes](../comparaison-historique/TABLEAU-DE-BORD.html) et [bilan historique](../BILAN-COMPLET.md). Cette nouvelle campagne compare le moteur gelé courant aux programmes du classeur ; elle ne rejoue pas une nouvelle fois toutes les anciennes versions du moteur sur chaque nouvelle famille.
'''
(O/'RAPPORT.md').write_text(report,encoding='utf8')
history=['# Historique des recherches Forest','',f"{len(D['trials'])} essais enregistrés ; ordre d’enregistrement dans le journal, pas nécessairement ordre de fin entre arbres parallèles.",'','Les temps « objectif » sont ceux des évaluations natives : moyenne des répétitions de l’objectif, parfois une moyenne géométrique de plusieurs tailles/nombres de cœurs. Ils ne remplacent pas les temps par entrée de la comparaison finale. Les hypothèses et transformations ci-dessous sont les déclarations du générateur, conservées comme données expérimentales.','', 'Moteur gelé hpc-forest-r1 ; méthode H, AB-MCTS-A, Mother persistante, memory-guided-v1, gpt-6-luna/max, graine 23, cible 1800 s, finish-started.','']
for e in D['attempts']:
 key=e['case_id'];history += [f"## {key} — job {e['job']}",'',f"Campagne `{e['campaign_directory']}`. Pipeline achevé : **{e['pipeline_complete']}**. Essais : {e['trial_count']}. Commit retenu : `{e['selected_commit'] or 'aucun'}`. Commit G : `{e['final_g_commit'] or 'aucun'}`. G confirmé : {e['final_g_confirmed']}.",'',f"Objectif naïf de recherche : {f(e.get('reference_seconds'),9)} s ; retenu : {f(e.get('selected_objective_seconds'),9)} s ; G : {f(e.get('final_g_objective_seconds'),9)} s.",'']
 if e.get('error'):history += ['Erreur de pipeline : '+str(e['error']),'']
 if e.get('naive_retained'):history += ['**Le moteur a conservé le naïf.**','']
 timing=e.get('timing') or {};started=timing.get('started_at');finished=timing.get('finished_at')
 if started:history += [f"Début UTC : {datetime.datetime.fromtimestamp(started,datetime.timezone.utc).isoformat()} ; durée murale : {f(finished-started if finished else None,1)} s ; dépassement cible déclaré : {f(timing.get('overrun_seconds'),1)} s.",'']
 history += ['| Ordre | Rôle | ID essai | Statut | Objectif (s) | Commit |','|---:|---|---|---|---:|---|']
 ts=[t for t in D['trials'] if t['campaign_directory']==e['campaign_directory']]
 for t in ts:history.append(f"| {t['ordinal']} | {t['role']} | {t['id']} | {t['status']} | {f(t['seconds'],9)} | {t['commit'] or '—'} |")
 history.append('')
 for t in ts:
  history += [f"### Essai {t['ordinal']} · {t['role']} · {t['id']}",'',f"Parent : `{t['parent']}`. Statut mesuré : **{t['status']}**.",'']
  if t['hypothesis']:history += ['Hypothèse déclarée : '+t['hypothesis'],'']
  trans=t['transformations'] or {}
  if trans:history+=['Transformations déclarées :','', '```json',json.dumps(trans,ensure_ascii=False,indent=2),'```','']
  if t['reason']:history+=['Diagnostic : '+t['reason'],'']
history += ['## Limites de ce journal','','Les résultats indépendants du tableau principal priment sur le classement de recherche. Un essai invalide n’est pas un gain de performance. Une erreur d’infrastructure n’est pas traitée comme un algorithme incorrect. Les références optimisées n’ont pas été transmises au modèle. Les compteurs cumulés de tokens ne sont pas additionnés ici.','']
(O/'HISTORIQUE-FOREST.md').write_text('\n'.join(history),encoding='utf8')
print(json.dumps({'report':str(O/'RAPPORT.md'),'history_trials':len(D['trials']),'measured':len(measured),'wins_documentary_rows':len(wins),'losses_documentary_rows':len(losses),'mixed_documentary_rows':len(mixed),'candidate_failures':len(candidatefails)},ensure_ascii=False))
