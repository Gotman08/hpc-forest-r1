"""Render the verified comparison and forest evidence without recomputing scores."""
from pathlib import Path
import json
import collections

R=Path(__file__).resolve().parent
O=R.parents[1]/'outputs/architecture-active'


def num(value):
    return f'{value:.4g}' if isinstance(value,(int,float)) else '—'


def main():
    data=json.loads((O/'RESULTATS.json').read_text(encoding='utf8'))
    summary=data['summary']
    engines={(e['period'],e['case_id']):e for e in data['engines']}
    rows=data['rows']
    finished=summary['new_finished']==21 and summary['measured_rows']==57
    title='Forest actif — résultats ROMEO' if finished else 'Forest actif — suivi des validations en cours'
    software=json.loads((R/'software-validation.json').read_text(encoding='utf8')) if (R/'software-validation.json').exists() else None
    lines=[f'# {title}','',
        f"{summary['new_finished']} / 21 nouvelles campagnes terminées ; {summary['measured_rows']} / 57 lignes documentaires remesurées ; 5 observations du tableau restent non exécutables faute de source ou de données exactes.",'',
        'Les speedups de cette campagne emploient un même naïf, dans une même allocation ROMEO, pour la référence publiée remesurée, l’ancien programme Forest et le nouveau. Les speedups publiés restent affichés séparément : ils proviennent d’autres matériels et parfois d’autres versions de compilateur ou d’exemple. Aucun facteur théorique de puissance matérielle n’est appliqué.','',
        *( [f"Moteur testé : `{software['engine_commit']}` ; **{software['pytest']['passed']} tests réussis**, aucun échec ni test ignoré, Ruff et contrôle du diff validés. Les fichiers exécutés sur ROMEO correspondent octet pour octet au moteur figé.",''] if software else []),
        '[Diagnostic détaillé par programme](ANALYSE.md) : décisions, coûts, combinaisons et lecture des sources.','',
        '[Classeur Excel filtrable](COMPARAISON-ROMEO.xlsx) : speedups calculés par formules, temps, arbres, décisions, chronologie et ressources. Les CSV et JSON restent les données complètes.','',
        '## Protocole et portée','',
        '- GPT-6 Luna, effort max, pour tous les rôles. Mêmes sources initiales, entrées et tests protégés que les campagnes précédentes.','- Mémoire, registre et session neufs par programme ; aucun ancien candidat injecté dans la recherche. Les anciens candidats servent uniquement à la remesure après sélection.','- 14 programmes conservent le budget précédent de 7 200 s ; les 7 autres conservent 1 800 s. La réserve finale et la règle de fin des travaux déjà admis restent applicables.','- Les appels au modèle passent par le relais local et le service Codex ; les poids de Luna ne sont pas hébergés sur ROMEO. La recherche, la compilation, les contrôles et les mesures des programmes s’exécutent sur ROMEO.','- GPU GH200 pour CUDA/Triton ; CPU AMD EPYC 9654 pour les codes CPU. Les sources old/new sont remesurées dans le même job, avec les mêmes entrées et un ordre alterné déterministe.','- 9 blocs de mesure pour les cas GPU, 7 pour les cas CPU et de rendu. Les contrôles supplémentaires sont conservés séparément des temps.','- Une recherche complète retenue par programme : les répétitions de chronométrage mesurent le bruit temporel, pas la variabilité de la recherche. N est choisi par Mother ; un résultat ne démontre pas à lui seul un effet causal de l’architecture.','',
        '## Comparaison','',
        '![Gains et régressions mesurés](GAINS-REGRESSIONS.png)','',
        '[Graphique vectoriel](GAINS-REGRESSIONS.svg) · [PDF](GAINS-REGRESSIONS.pdf). Une ligne par comparaison distincte ; les barres montrent la plage des blocs.', '',
        f"Les {summary['measured_rows']} lignes remesurées correspondent à {summary['distinct_old_new_comparisons']} comparaisons ancien/nouveau distinctes. Plusieurs références documentaires peuvent partager le même couple de candidats et les mêmes entrées ; leurs lignes ne constituent pas des réplications indépendantes.",'',
        '| Observation | Publié | Référence sur ROMEO | Ancien Forest, remesuré | Forest actif | Actif / ancien | Conclusion |','|---|---:|---:|---:|---:|---:|---|']
    applied = [d for d in data['decisions'] if d['period']=='new' and d['status']=='applied']
    counts = collections.Counter(d['kind'] for d in applied)
    capabilities = ['## Boucle active observée', '',
        'Ces décisions ont été appliquées pendant les recherches retenues, avec des appels Luna réels. Les tests logiciels vérifient aussi les conditions de rejet et de reprise. Une décision appliquée ne démontre pas un gain : ses descendants doivent encore être mesurés.', '',
        '| Action | Occurrences appliquées | Programmes concernés |', '|---|---:|---:|']
    for kind in ['continue','suspend','resume','branch','share','integrate','close']:
        cases={d['case_id'] for d in applied if d['kind']==kind}
        capabilities.append(f'| {kind} | {counts[kind]} | {len(cases)} |')
    capabilities.append('')
    position = lines.index('## Comparaison')
    lines[position:position] = ['## Interventions et indépendance des recherches', '',
        'L’opérateur a préparé les contrats et lanceurs, corrigé les défauts révélés par les pilotes et relancé les échecs techniques documentés. Le moteur des campagnes comparées est ensuite resté figé. Aucun ancien candidat optimisé, conseil algorithmique issu des comparaisons ou correction manuelle d’un candidat n’a été fourni aux modèles pendant ces recherches. La lecture comparative des sources a été faite après la livraison de chaque programme.', '',
        'Les relances après échec technique augmentent le coût total. Le budget nominal identique concerne chaque tentative ; une comparaison à coût total strictement égal devrait également déduire le coût de ces échecs. Ce dossier conserve les deux comptes et retient la première tentative complète, sans choisir selon son speedup.', '']
    position = lines.index('## Comparaison')
    lines[position:position] = capabilities
    position = lines.index('## Comparaison')
    lines[position:position] = ['## Ce qui est réinitialisé', '',
        'Chaque tentative de recherche crée une session et un registre vides. À l’intérieur d’une même recherche, Mother conserve sa conversation et les arbres conservent leur historique : cette continuité fait partie du système. Les analystes reçoivent des instantanés bornés de leur arbre, dans des appels isolés. Les reprises documentées repartent du code initial et ne récupèrent aucun candidat de la tentative échouée.', '',
        'Dans les remesures appariées, chaque combinaison variante / entrée / bloc lance un nouveau processus pilote. Ses appels de correction, d’échauffement et de chronométrage réutilisent ensuite ce processus et ses allocations. Les répétitions chronométrées ne correspondent donc pas à des démarrages à froid indépendants. Softmax emploie le protocole triton.testing.do_bench ; les autres suites GPU utilisent des événements CUDA avec synchronisation, et les pilotes CPU chronomètrent leurs répétitions après échauffement.', '',
        'Il n’y a pas de redémarrage du nœud, de remise à zéro globale du GPU ou de purge globale des caches système entre deux variantes. Les caches de fichiers ou de compilation, les fréquences et la température peuvent persister. L’ordre alterné, les répétitions et les mesures dans la même allocation limitent certains biais, sans supprimer ces effets matériels. Les timings ne mesurent pas le coût complet de démarrage ou de compilation à froid.', '']
    position = lines.index('## Comparaison')
    lines[position:position] = ['[Durées par phase](DUREES-PHASES.csv) : compilation, contrôle, benchmark, attente de verrou et appels modèle, avec tous les échantillons disponibles. Ces phases se chevauchent ou sont imbriquées ; leurs totaux ne sont pas additifs.', '']
    lines[position:position] = ['Les cœurs sont limités par l’affinité de l’allocation SLURM, mais les nœuds CPU ne sont pas réservés exclusivement. D’autres jobs peuvent partager mémoire, alimentation et fréquences. L’ordre alterné et les blocs répétés réduisent certains biais ; ils ne garantissent pas une isolation physique parfaite.', '']
    lines[position:position] = ['Les tailles d’entrée sont conservées ligne par ligne. Pour AOBench, Binomial et Black-Scholes, les lignes historiques à 40 threads emploient une taille plus grande que celles à 1 ou 4 threads. Leurs temps bruts ne mesurent donc pas une mise à l’échelle à problème constant. Le diagnostic indique les tailles et ne calcule cette mise à l’échelle que pour les entrées identiques.', '']
    reference_counts=summary['strongest_reference_verdict_counts']
    reference_lines=['## Niveau atteint face aux références du tableau', '',
        'Pour chaque entrée et chaque allocation, on retient la référence remesurée la plus rapide parmi les lignes documentaires comparables, avec le même agrégat temporel. Cette comparaison évite de compter comme une réussite le seul dépassement d’une référence intermédiaire plus lente. Elle ne prétend pas couvrir toutes les implémentations existantes.', '',
        '| Constat face à cette référence | Configurations mesurées |', '|---|---:|']
    for label in ['Forest dépasse la référence dans chaque bloc','Référence plus rapide dans chaque bloc','Écart dans la variabilité observée']:
        reference_lines.append(f'| {label} | {reference_counts.get(label,0)} |')
    reference_lines += ['', '[Détail par entrée, matériel et référence](REFERENCES-LES-PLUS-RAPIDES.csv). Les répétitions ne sont pas des recherches indépendantes ; les agrégats suivent le protocole, dont le minimum pour la ligne UTF-8 BEST.', '']
    position=lines.index('## Comparaison')
    lines[position:position]=reference_lines
    verdicts=summary['distinct_verdict_counts']
    position=next(i for i,line in enumerate(lines) if line.startswith('| Observation | Publié |'))
    lines[position:position]=[
        f"Sur ces configurations distinctes : **{verdicts.get('Nouveau plus rapide dans chaque bloc',0)} gains dans chaque bloc**, **{verdicts.get('Ancien plus rapide dans chaque bloc',0)} régressions dans chaque bloc**, {verdicts.get('Écart dans la variabilité observée',0)} résultats mixtes et {verdicts.get('Code ou binaire identique : variation de mesure',0)} cas avec le même code ou binaire. Il n’y a donc pas d’amélioration systématique. Les tailles d’entrée et nombres de threads d’un même programme restent liés ; ces comptes ne sont pas des recherches indépendantes.", '']
    for row in rows:
        values=[row['id'],*[num(row.get(k)) for k in ['published_speedup','reference_speedup','old_selected_speedup','new_selected_speedup','new_vs_old']],row['verdict']]
        lines.append('| '+' | '.join(str(v).replace('|',' / ') for v in values)+' |')
    lines += ['', 'Le rapport entre le temps ancien et le temps nouveau est supérieur à 1 lorsque le nouveau programme est plus rapide. Si les sources ou les binaires sont identiques, la différence est classée comme variation de mesure. Les plages par bloc et coefficients de variation sont dans le CSV.', '',
        '## Détail des campagnes', '', '| Programme | Arbres initiaux → créés | Essais corrects / total | Analyse + pilotage | Durée réelle / budget (s) | G confirmé |', '|---|---:|---:|---:|---:|---|']
    for key in sorted({r['case_id'] for r in rows if r.get('case_id')}):
        e=engines.get(('new',key))
        if not e:
            lines.append(f'| {key} | En cours | — | — | — | — |')
            continue
        active=e.get('active_summary') or {}
        lines.append(f"| {key} | {e['initial_trees']} → +{e['created_trees']} | {e['correct_trials']} / {e['total_trials']} | {active.get('control_calls',0)} appels ; {active.get('applied_actions',0)} actions | {num(e['elapsed_seconds'])} / {e['target_seconds']} | {e['final_g_confirmed']} |")
    lines += ['', '## Ancienne et nouvelle recherche, côte à côte', '',
        '| Programme | Arbres initiaux ancien → actif | Essais corrects / total, ancien → actif | Durée réelle ancien → actif (s) | Combinaisons Gm | Essais avec avis |',
        '|---|---:|---|---:|---:|---:|']
    for key in sorted({r['case_id'] for r in rows if r.get('case_id')}):
        old,new=engines.get(('old',key)),engines.get(('new',key))
        if not old or not new:
            continue
        lines.append(f"| {key} | {old['initial_trees']} → {new['initial_trees']} | {old['correct_trials']} / {old['total_trials']} → {new['correct_trials']} / {new['total_trials']} | {num(old['elapsed_seconds'])} → {num(new['elapsed_seconds'])} | {new['intermediate_integrations']} | {new['trials_with_analyst_or_mother_advice']} |")
    lines += ['', '## Coût et décisions observées', '',
        '| Programme | Tokens vérifiables ancien → actif | Appels sans usage connu ancien → actif | Tokens analystes et pilotage | Gm améliorant le meilleur connu / Gm mesurées | Fin de recherche |',
        '|---|---:|---:|---:|---:|---|']
    for key in sorted({r['case_id'] for r in rows if r.get('case_id')}):
        old,new=engines.get(('old',key)),engines.get(('new',key))
        if not old or not new:
            continue
        ou,nu=old['native_usage_normalized'],new['native_usage_normalized']
        stop=('Fermeture explicite' if new['explicit_research_closure'] else
              'Tous les arbres de recherche suspendus' if new['all_research_trees_suspended_at_end'] else
              new.get('scheduler_status') or 'Voir chronologie')
        lines.append(f"| {key} | {ou['known_tokens_normalized']:,} → {nu['known_tokens_normalized']:,} | {ou['unknown_invocation_usage']} → {nu['unknown_invocation_usage']} | {(new.get('active_summary') or {}).get('known_tokens',0):,} | {new['intermediate_integrations_improving_incumbent']} / {new['intermediate_integrations']} | {stop} |")
    lines += ['', 'Ces tokens décrivent le travail connu, pas un prix en euros. Les appels inconnus ne valent pas zéro. Le bilan des tentatives échouées ci-dessous s’ajoute au coût de la tentative retenue. Une combinaison peut améliorer ses propres sources tout en restant moins rapide que le meilleur code trouvé entre-temps ; le décompte Gm emploie ce meilleur connu au moment de la mesure.', '',
        'Quand Mother suspend tous les arbres, la boucle termine les travaux admis puis passe à la confirmation. Dans cette version, le champ brut `budget_exhausted` peut aussi couvrir cet arrêt sans travail admissible : il ne démontre donc pas que toute la durée autorisée a été consommée. Le tableau conserve la cause observée et les durées réelles.', '',
        'La somme des durées des appels modèle se chevauche avec la recherche et ne doit pas être ajoutée à la durée murale. Les compteurs historiques cumulés de Mother sont recalculés par différence dans `native_usage_normalized` ; les journaux d’origine restent intacts. Un appel sans consommation vérifiable reste inconnu.', '',
        '## Fichiers de preuve','',
        '- [Comparaison complète](COMPARAISON.csv) : 62 lignes documentaires, temps, speedups, matériel, compilateur, répétitions, variabilité et limites de reproduction.','- [Campagnes](CAMPAGNES.csv), [arbres](ARBRES.csv) et [essais](ESSAIS.csv) : sujets, parents, bases, états, diagnostics et résultats.','- [Chronologie](CHRONOLOGIE.csv) : admissions, décisions et évaluations, horodatées en UTC et en secondes depuis le début de chaque recherche.','- [Appels des analystes et de Mother](APPELS-ANALYSTES-MOTHER.csv), [décisions](DECISIONS.csv) : coût, couverture, raisons, actions appliquées ou rejetées et descendants mesurés.','- [Mesures brutes](MESURES-BRUTES.csv) et [dossier JSON](RESULTATS.json) : identités, environnement et blocs de mesure.','',
        '## Essais de mise au point conservés','',
        'Les pilotes préalables ont révélé un alias dans le schéma JSON final, une priorité injuste entre analystes, un double comptage des compteurs cumulés de Mother et des champs de décision ambigus pour le modèle. Ces défauts ont été corrigés et couverts par des tests. Les pilotes touchés par les coupures SSH ou l’erreur 503 du service modèle restent des échecs d’infrastructure ; leurs résultats ne sont pas substitués aux campagnes comparées.','',
        'Windows est aussi entré en veille sur batterie le 24 octobre à 10:51:23 UTC, puis a repris à 11:58:30 UTC. Huit allocations ont perdu leur relais local. Les six campagnes principales concernées ont été relancées avec le même moteur, des sessions neuves et sans reprise des candidats. Les deux autres étaient des pilotes.','',
        f"Le [registre des tentatives préalables](TENTATIVES-PREALABLES.csv) conserve {summary['setup_attempts']} allocations exclues de la comparaison : {num(summary['setup_allocation_seconds_sum'])} secondes d’allocation cumulées et {summary['setup_known_tokens_normalized']:,} tokens vérifiables. La consommation de {summary['setup_unknown_invocation_usage']} appels reste inconnue. Les durées d’allocations parallèles ne représentent pas un temps mural total.",'',
        '| Job | Tentative | État | Allocation (s) | Appels modèle | Tokens connus | Usages inconnus | Veille batterie |',
        '|---|---|---|---:|---:|---:|---:|---|']
    for attempt in data['setup_attempts']:
        values=[attempt['job_id'],attempt['condition'],attempt.get('state'),num(attempt.get('allocation_elapsed_seconds')),
                attempt['native_invocations'],attempt['known_tokens_normalized'],attempt['unknown_invocation_usage'],
                'Oui' if attempt['local_battery_sleep_affected'] else 'Non']
        lines.append('| '+' | '.join(str(v).replace('|',' / ') for v in values)+' |')
    lines += ['', 'Les temps exploratoires des pilotes, y compris la combinaison intermédiaire Gm1, restent dans les preuves et ne sont pas présentés comme des résultats confirmés de la matrice finale.',
        'Une nouvelle tentative complète est autorisée après un échec technique, avec une session neuve et le même moteur. La première tentative complète est retenue, sans sélection entre tentatives selon leur speedup. Les échecs et leur consommation restent comptés séparément. Le registre de reprise documente notamment la limite de sortie native atteinte par Mother sur GEMM CPU, binomial et Base64.', '',
        '## Reproduction', '',
        'Le dossier publié conserve le moteur exact, les sources initiales, les tests protégés, les sources candidates, les plans SLURM, les mesures et leurs empreintes SHA-256. Les scripts de `reproduction/` décrivent les opérations exécutées ; leurs chemins locaux et distants correspondent à cette étude et doivent être adaptés pour une nouvelle machine ou un autre compte ROMEO. Les sessions, clés et fichiers privés du relais ne sont pas publiés.', '',
        'Pour une nouvelle recherche, utiliser une nouvelle session, le même protocole protégé, le modèle et les budgets enregistrés. Pour remesurer les résultats, compiler les sources anciennes et nouvelles dans la même allocation avec le compilateur déclaré, conserver les entrées et graines, puis vérifier chaque mesure avant de calculer les rapports. Les fichiers d’historique ne doivent pas être écrasés.', '']
    retry_cases = [r['case_id'] for r in json.loads((R/'infrastructure-retries.json').read_text(encoding='utf-8-sig')) if not r.get('environment_changed')]
    lines = [line.replace('sur GEMM CPU, binomial et Base64.', 'sur les programmes suivants : '+', '.join(retry_cases)+'.') for line in lines]
    lines += ['Le lanceur des trois cas de la suite GPU (SGEMM, Stencil Y, Transpose) omettait le chemin de chargement de `libcublas.so.12`. Ils ont échoué avant tout appel au modèle. Le lanceur ajoute maintenant le `lib64` de la même installation CUDA 12.6.3. Un job de vérification indépendant a repassé leurs 20 contrôles protégés ; les trois campagnes ont été relancées avec des sessions neuves, sans changer le moteur, le compilateur, les sources ou les tests. La preuve et l’empreinte de la bibliothèque sont conservées dans `validation/runtime-library-fix.json`.', '',
        '## Limites des références et contrôles négatifs', '',
        'Cinq lignes documentaires restent sans remesure exacte : les deux exemples NVIDIA BVH, une epoch complète de S4ConvD et les deux speedups de la démonstration MIT GEMM. Les scènes, données ou versions complètes nécessaires manquent. Leurs valeurs publiées restent visibles, sans leur substituer des nombres provenant d’un autre problème.', '',
        'Le naïf UTF-8 historique est défectueux : il échoue sur 5 773 des 79 729 chaînes de contrôle. Il est conservé comme contrôle négatif. Les programmes ancien et nouveau, la référence et le naïf réparé passent ce contrôle. Les timings affichés portent sur les chaînes valides définies par le protocole ; ce constat ne transforme pas le naïf historique en validateur correct.', '',
        'Pour Volume, la référence ISPC exige des dimensions divisibles par 4. Les 14 contrôles à 224×296 et 336×444 réussissent pour les sept variantes. À 96×126 et 128×169, les deux diagnostics initiaux de la référence optimisée s’arrêtent avec « free(): invalid pointer ». L’audit séparé, qui ajoute uniquement du padding de sortie pour observer les débordements, détecte les quatre échecs attendus des deux références ISPC hors domaine. Les anciens et nouveaux candidats passent leurs contrôles. Ces échecs restent dans les mesures brutes comme contrôles négatifs ; les chronométrages et speedups emploient les dimensions valides 896×1184. Les dimensions des processus arrêtés sont reconstituées à partir de l’ordre du lanceur figé, pas présentées comme une sortie de ces processus.', '',
        'Une mémoire neuve désigne le registre, les candidats et les conversations de cette campagne. À l’intérieur d’un programme, Mother conserve son contexte et les imports explicitement décidés permettent le partage entre arbres. Les caches physiques du nœud et les connaissances préalables du modèle ne sont pas effacés.', '']
    lines += ['[Environnements des mesures](ENVIRONNEMENTS.csv) : modèle CPU/GPU, compilateur, affinité CPU lorsqu’elle a été enregistrée, version du pilote et état matériel au moment de la capture. Ces captures ne sont pas un suivi continu des fréquences ou températures. La version CUDA annoncée par le pilote indique sa compatibilité et ne remplace pas la version du toolkit de compilation, CUDA 12.6.3 dans cette étude.','']
    resource_path=O/'RESSOURCES-SLURM.json'
    if resource_path.exists():
        resources=json.loads(resource_path.read_text(encoding='utf8'))
        labels={'historical_search':'Anciennes recherches retenues','active_search_selected':'Nouvelles recherches retenues',
            'active_search_failed':'Nouvelles tentatives échouées','pilot_or_interrupted':'Pilotes et interruptions préalables',
            'paired_measurements':'Remesures appariées','runtime_validation':'Vérification du chargement CUDA',
            'paired_measurement_validation':'Validation préalable du protocole de remesure'}
        lines += ['## Ressources réservées sur ROMEO','',
            '![Durées des campagnes et tentatives échouées](DUREES-CAMPAGNES.png)', '',
            '[Graphique vectoriel](DUREES-CAMPAGNES.svg) · [PDF](DUREES-CAMPAGNES.pdf). Les allocations incluent la préparation, les attentes modèle et la confirmation. Le budget nominal est indiqué par tentative ; les échecs ajoutent un coût. Les pilotes et interruptions préalables sont comptabilisés dans le tableau ci-dessous.', '',
            '| Périmètre | Jobs comptabilisés | Heures CPU réservées | Heures CPU utilisées | Heures GPU réservées |',
            '|---|---:|---:|---:|---:|']
        for scope,stats in resources['scopes'].items():
            lines.append('| '+' | '.join([labels.get(scope,scope),str(stats['jobs']),
                num(stats['cpu_seconds_reserved_known_sum']/3600),num(stats['cpu_seconds_used_known_sum']/3600),
                num(stats['gpu_seconds_reserved_known_sum']/3600)])+' |')
        lines += ['', '[Détail SLURM en CSV](RESSOURCES-SLURM.csv) et [preuves agrégées en JSON](RESSOURCES-SLURM.json). Ces totaux additionnent les ressources d’allocations qui peuvent se chevaucher ; ils ne mesurent pas la durée murale de l’étude. Les heures GPU sont réservées, pas une mesure d’activité effective du GPU. Une faible utilisation CPU ne signifie pas à elle seule une faible utilisation du GPU. Les totaux portent sur les valeurs connues ; toute télémétrie manquante reste signalée dans le JSON.','']
        old=resources['scopes']['historical_search']['elapsed_seconds_known_sum']/3600
        selected=resources['scopes']['active_search_selected']['elapsed_seconds_known_sum']/3600
        failed=resources['scopes']['active_search_failed']['elapsed_seconds_known_sum']/3600
        lines += [f"Les durées d’allocations cumulées représentent {num(old)} h pour les anciennes recherches retenues, {num(selected)} h pour les nouvelles retenues et {num(failed)} h supplémentaires pour leurs tentatives échouées. Les pilotes et remesures sont séparés. Ce constat ne suffit pas à conclure à une meilleure efficacité : les recherches actives livrent aussi des régressions, et les éventuels échecs des anciennes séries ne sont pas ajoutés aux 21 anciennes campagnes retenues.", '']
    (O/'RAPPORT.md').write_text('\n'.join(lines),encoding='utf8')
    landing=['# Architecture active : campagne ROMEO du 24 octobre 2026','',
        f"{summary['new_finished']} / 21 programmes ont terminé leur recherche. {summary['measured_rows']} / 57 lignes exécutables du tableau ont été remesurées ; les 5 lignes sans source ou données exactes restent explicitement indisponibles.",'',
        'La campagne emploie le mode `full`, GPT-6 Luna avec l’effort `max`, une mémoire neuve par programme et les mêmes budgets nominaux que les essais précédents. Les anciens et nouveaux candidats sont ensuite comparés au naïf et à la référence dans une même allocation.','',
        '- [Rapport de comparaison](RAPPORT.md) : protocole, speedups publiés et remesurés, coûts, incidents et limites.',
        '- [Diagnostic détaillé](ANALYSE.md) : chaque programme, chaque arbre, décisions de Mother et lecture des sources.',
        '- [Classeur Excel](COMPARAISON-ROMEO.xlsx) : comparaison par formules et onglets de données filtrables.',
        '- [Niveau face aux références les plus rapides du tableau](REFERENCES-LES-PLUS-RAPIDES.csv), pour chaque entrée remesurée.',
        '- [CSV principal](COMPARAISON.csv) et [données JSON](RESULTATS.json) : toutes les valeurs et leur provenance.',
        '- [Tableau de bord HTML](TABLEAU-DE-BORD.html) : filtres par programme et résultat ; ouvrir le fichier téléchargé dans un navigateur.',
        '- [Graphique des gains et régressions](GAINS-REGRESSIONS.png), [SVG](GAINS-REGRESSIONS.svg) et [PDF](GAINS-REGRESSIONS.pdf).',
        '- [Durées des campagnes et coût des échecs](DUREES-CAMPAGNES.png), [SVG](DUREES-CAMPAGNES.svg) et [PDF](DUREES-CAMPAGNES.pdf).',
        '- [Matériel enregistré](ENVIRONNEMENTS.csv), [durées par phase](DUREES-PHASES.csv) et [tentatives préalables](TENTATIVES-PREALABLES.csv).','',
        '[Ressources SLURM](RESSOURCES-SLURM.csv) : allocations, heures CPU utilisées ou réservées et heures GPU réservées, séparées par périmètre.','',
        'Le dossier publié contient `campagnes/` pour les recherches retenues, `mesures/` pour les comparaisons appariées, `validation/` pour les contrôles, `moteur/` pour le code exact exécuté et `reproduction/` pour les scripts de cette étude. Les pilotes et tentatives interrompues restent conservés séparément. `MANIFESTE-PUBLICATION.json` recense les empreintes des fichiers et les exclusions.','',
        'Les gains et régressions sont tous conservés. Une recherche terminée par programme ne démontre pas une supériorité causale de l’architecture ; les répétitions de chronométrage mesurent la variabilité temporelle. Les échecs et relances ne sont pas gratuits : leur coût est publié séparément.','']
    (O/'README.md').write_text('\n'.join(landing),encoding='utf8')
    payload=json.dumps({k:data[k] for k in ['summary','rows','engines']},ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Forest actif — comparaison ROMEO</title><style>
body{font:16px system-ui,sans-serif;background:#f4f6f9;color:#182239;margin:0;padding:32px}main{max-width:1700px;margin:auto}h1{font-size:32px;margin-bottom:8px}p{max-width:1100px;line-height:1.6}a{color:#204fa8}.cards{display:flex;flex-wrap:wrap;gap:14px;margin:25px 0}.card{background:white;padding:18px 25px;border:1px solid #dde3eb;border-radius:10px;min-width:180px}.card b{font-size:28px;display:block}.controls{display:flex;gap:12px;align-items:center;margin:20px 0}input,select{font:inherit;padding:9px;border:1px solid #b2c1d7;border-radius:6px}.scroll{overflow:auto;max-height:70vh;background:white;border:1px solid #dde3eb}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:12px;text-align:left;border-bottom:1px solid #e3e8f0}th{position:sticky;top:0;background:#e9eef5;white-space:nowrap}td.number{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}tr.good{background:#e8f5ee}tr.bad{background:#fff0e9}details{max-width:750px}summary{cursor:pointer}small{display:block;color:#516078;max-width:400px}footer{margin-top:28px;color:#516078}h2{margin-top:36px}.warning{padding:14px;background:#fff4d5;border-left:4px solid #c28a19}
</style><main><h1>Forest actif : comparaison sur ROMEO</h1><p id="state"></p>
<div class="cards" id="cards"></div><p>Chaque comparaison oppose les anciens et nouveaux programmes, le naïf et la référence dans une même allocation. Un rapport « actif / ancien » supérieur à 1 signifie un nouveau programme plus rapide. Les nombres publiés proviennent d’autres matériels.</p>
<p class="warning">Une recherche retenue par programme. Les blocs répétés quantifient le bruit de mesure ; ils ne prouvent pas que la nouvelle architecture gagne à chaque recherche. Une mémoire neuve ne signifie pas une purge des caches physiques du nœud.</p>
<p><a href="RAPPORT.md">Rapport</a> · <a href="ANALYSE.md">Diagnostic par programme</a> · <a href="COMPARAISON.csv">CSV complet</a> · <a href="RESULTATS.json">Dossier JSON</a> · <a href="ARBRES.csv">Arbres</a> · <a href="DECISIONS.csv">Décisions</a> · <a href="TENTATIVES-PREALABLES.csv">Pilotes et interruptions</a></p>
<p><a href="GAINS-REGRESSIONS.png">Graphique des gains et régressions</a> · <a href="GAINS-REGRESSIONS.svg">SVG</a> · <a href="GAINS-REGRESSIONS.pdf">PDF</a></p>
<p><a href="DUREES-CAMPAGNES.png">Durées des campagnes et coût des échecs</a> · <a href="RESSOURCES-SLURM.csv">Ressources réservées et utilisées</a> · <a href="REFERENCES-LES-PLUS-RAPIDES.csv">Niveau face aux références les plus rapides du tableau</a></p>
<p><a href="COMPARAISON-ROMEO.xlsx">Classeur Excel : speedups, temps et détails de Forest</a></p>
<p><a href="ENVIRONNEMENTS.csv">Matériel et environnements enregistrés</a> · <a href="DUREES-PHASES.csv">Durées par phase</a></p>
<div class="controls"><input id="filter" type="search" placeholder="Programme, matériel, observation…" aria-label="Filtrer les observations"><select id="verdict" aria-label="Filtrer le résultat"><option value="">Tous les résultats</option><option>Nouveau plus rapide dans chaque bloc</option><option>Ancien plus rapide dans chaque bloc</option><option>Écart dans la variabilité observée</option><option>Code ou binaire identique : variation de mesure</option></select><span id="count"></span></div>
<div class="scroll"><table><thead><tr><th>Observation</th><th>Publié ×</th><th>Référence ROMEO ×</th><th>Ancien Forest ×</th><th>Forest actif ×</th><th>Actif / ancien</th><th>Conclusion et protocole</th></tr></thead><tbody id="rows"></tbody></table></div>
<h2>Ce que la forêt a réellement exploré</h2><p>Le nombre d’arbres, les appels de contrôle, les essais corrects, les décisions et les durées sont conservés pour chaque programme. Les sommes des durées modèle peuvent se chevaucher.</p><div class="scroll"><table><thead><tr><th>Programme</th><th>Arbres initiaux + créés</th><th>Essais corrects / total</th><th>Appels de contrôle</th><th>Actions appliquées</th><th>Temps / budget (s)</th><th>G confirmé</th></tr></thead><tbody id="engines"></tbody></table></div><footer id="stamp"></footer></main>
<script>const data=PAYLOAD;
const esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const fmt=x=>Number.isFinite(x)?x.toLocaleString('fr-FR',{maximumSignificantDigits:4}):'—';
const s=data.summary;document.querySelector('#state').textContent=`${s.new_finished} / 21 campagnes terminées · ${s.measured_rows} / 57 lignes documentaires remesurées · 5 observations non exécutables`;
document.querySelector('#cards').innerHTML=[['Programmes',21],['Points documentaires',62],['Lignes remesurées',s.measured_rows],['Comparaisons distinctes',s.distinct_old_new_comparisons],['Mesures brutes',s.records]].map(([name,n])=>`<div class="card"><b>${n}</b>${name}</div>`).join('');
function render(){const q=document.querySelector('#filter').value.toLocaleLowerCase(),v=document.querySelector('#verdict').value;const rows=data.rows.filter(r=>(!v||r.verdict===v)&&JSON.stringify([r.id,r.label,r.hardware,r.published_hardware,r.case_id]).toLocaleLowerCase().includes(q));document.querySelector('#count').textContent=rows.length+' lignes';document.querySelector('#rows').innerHTML=rows.map(r=>{const cls=r.verdict.startsWith('Nouveau plus')?'good':r.verdict.startsWith('Ancien plus')?'bad':'';const n=x=>`<td class="number">${fmt(x)}</td>`;return `<tr class="${cls}"><td>${esc(r.id)}<small>${esc(r.label)}</small></td>${['published_speedup','reference_speedup','old_selected_speedup','new_selected_speedup','new_vs_old'].map(k=>n(r[k])).join('')}<td><details><summary>${esc(r.verdict)}</summary><p>${esc(r.notes)}</p><p>Publié : ${esc(r.published_hardware)}<br>ROMEO : ${esc(r.hardware)}<br>${esc(r.compiler)}<br>Entrée : ${esc(r.n)} ; threads : ${esc(r.threads)} ; job : ${esc(r.comparison_job)}</p><p>Temps ancien : ${fmt((r.old_selected?.seconds??NaN)*1000)} ms ; actif : ${fmt((r.new_selected?.seconds??NaN)*1000)} ms.<br>Rapports par bloc : ${fmt(r.new_vs_old_min)} à ${fmt(r.new_vs_old_max)}.</p></details></td></tr>`}).join('')}
document.querySelector('#filter').addEventListener('input',render);document.querySelector('#verdict').addEventListener('change',render);render();
document.querySelector('#engines').innerHTML=data.engines.filter(e=>e.period==='new').map(e=>`<tr><td>${esc(e.case_id)}<small>Job ${esc(e.job_id)}</small></td><td>${e.initial_trees} + ${e.created_trees}</td><td>${e.correct_trials} / ${e.total_trials}</td><td>${e.active_summary?.control_calls??0}</td><td>${e.active_summary?.applied_actions??0}</td><td>${fmt(e.elapsed_seconds)} / ${e.target_seconds}</td><td>${e.final_g_confirmed?'Oui':'Non'}</td></tr>`).join('');document.querySelector('#stamp').textContent='Dossier généré le '+new Date(s.generated_at).toLocaleString('fr-FR')+'. Les résultats incomplets restent indiqués comme tels.';
</script></html>'''.replace('PAYLOAD',payload)
    (O/'TABLEAU-DE-BORD.html').write_text(page,encoding='utf8')
    print(title,summary['measured_rows'],'rows measured')


if __name__=='__main__':
    main()
