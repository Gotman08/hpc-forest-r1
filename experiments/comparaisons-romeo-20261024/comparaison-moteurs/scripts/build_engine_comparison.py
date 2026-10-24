"""Build the evidence-backed comparison after all campaigns and the common GPU replay."""
from collections import Counter,defaultdict
from itertools import combinations
import json
import math
from pathlib import Path
import statistics
from engine_study import ROOT, CONDITIONS, read, write
from engine_extract import table

OUT=ROOT/'outputs/comparaison-moteurs'
OLD=ROOT/'outputs/comparaison-historique'
SERIES=[('interrupted','S1 — relais historiques',OUT,''),
        ('shared-scp','S2 — connexion partagée',OUT/'relance-controlee','relance-controlee/'),
        ('atomic','S3 — messages atomiques',OUT/'serie-atomique','serie-atomique/')]
LABELS={'772923':'Vagues / paires','774157':'Arbres indépendants / paires','775521':'Mémoire / réserve initiale',
        '775815':'Première correction de réserve','776048':'Réserve et assemblage adaptatifs',
        '776290':'Correction d’admission','780448':'Fiabilité et critique du plan'}

def number(x,digits=3):return '—' if x is None else f'{x:.{digits}f}'.replace('.',',')
def ms(x):return number(x*1000 if x is not None else None,6)
def duration(x):return '—' if x is None else f'{int(x)//60} min {int(x)%60:02d} s'
def escape(x):return str(x).replace('|','\\|').replace('\n',' ')

def build():
    replay_root=OUT/'gpu-comparaison'
    replay=read(replay_root/'results/summary.json')
    variants=read(replay_root/'variants.json')
    measured={p['id']:p for p in replay['programs']}
    origin_map={}
    for variant in variants:
        for origin in variant['origins']:
            if origin.get('commit'):
                origin_map[(origin['series'],origin['condition'],origin['commit'])]=variant['id']
    rows=[];all_trials=[];all_events=[];details={};all_calls=[]
    for series,label,folder,prefix in SERIES:
        for key in CONDITIONS:
            d=folder/'data'/key
            summary=read(d/'summary.json');native=read(d/'native-summary.json');calls=read(d/'native-calls.json')
            lineage=read(d/'lineage.json');events=read(d/'events.json');meta=read(d/'metadata.json')
            old=read(OLD/'data/campaigns'/key/'summary.json')
            assert summary['engine_identity']==old['engine_identity'], 'Historical engine identity mismatch'
            best=summary.get('best_confirmed') or {}
            selected=origin_map.get((series,key,best.get('commit')))
            fresh=measured.get(selected,{})
            old_variant=origin_map.get(('historical-winner',key,old['best_confirmed']['commit']))
            old_fresh=measured.get(old_variant,{})
            research=summary['research_counts'];g=summary['integration_counts']
            admissions=[e for e in events if e['kind']=='adaptive_admission']
            stops=[e for e in events if e['kind']=='budget_stop']
            initial_reserve=admissions[0]['payload'] if admissions else {}
            last_reserve=admissions[-1]['payload'] if admissions else {}
            selections=(summary.get('postprocess') or {}).get('selections',[])
            phase_seconds={phase:sum(c.get('native_seconds') or 0 for c in calls if c['phase']==phase) for phase in {c['phase'] for c in calls}}
            row={'series':series,'series_label':label,'condition':key,'label':LABELS[key],'job_id':summary['job_id'],
                'forest_width':summary['forest_width'],'research_trials':sum(research.values()),'research_valid':research.get('valid',0),
                'research_incorrect':research.get('incorrect',0),'research_infrastructure':research.get('infrastructure_error',0),
                'research_other':sum(v for k,v in research.items() if k not in {'valid','incorrect','infrastructure_error'}),
                'integration_trials':sum(g.values()),'integration_valid':g.get('valid',0),
                'pipeline_complete':summary['pipeline_complete'],'pipeline_error':summary.get('pipeline_error'),
                'search_status':summary.get('search_status'),'final_g_status':summary['final_g_confirmation'].get('status'),
                'final_g_reason':(summary['final_g_confirmation'].get('outcome') or {}).get('reason'),
                'selected_id':best.get('experiment_id'),'selected_is_baseline':best.get('is_baseline'),'selected_variant':selected,
                'selected_confirmed_seconds':best.get('mean_seconds'),'selected_common_gpu_seconds':fresh.get('mean_seconds'),
                'selected_common_gpu_speedup':fresh.get('speedup'),'historical_common_gpu_seconds':old_fresh.get('mean_seconds'),
                'historical_common_gpu_speedup':old_fresh.get('speedup'),'historical_variant':old_variant,
                'search_elapsed_seconds':summary['search_elapsed_seconds'],'total_elapsed_seconds':summary['total_elapsed_seconds'],
                'native_calls':native['native_calls'],'native_phases':native['phases'],'native_phase_seconds':phase_seconds,
                'planning_native_seconds':phase_seconds.get('planning',0),'review_native_seconds':phase_seconds.get('plan-review',0),
                'input_tokens':native['input_tokens'],'cached_input_tokens':native['cached_input_tokens'],'output_tokens':native['output_tokens'],
                'one_mother_thread':native['one_mother_thread'],'undelivered_calls':native['undelivered'],
                'native_infrastructure_errors':native['infrastructure_errors'],
                'forbidden_tools_observed':native['forbidden_tools_observed'],
                'raw_reported_input_tokens_sum':native['reported_input_tokens_sum'],
                'raw_reported_output_tokens_sum':native['reported_output_tokens_sum'],
                'initial_reserve_seconds':initial_reserve.get('reserve_seconds'),
                'initial_remaining_seconds':initial_reserve.get('remaining_seconds'),
                'last_reserve_seconds':last_reserve.get('reserve_seconds'),
                'last_remaining_seconds':last_reserve.get('remaining_seconds'),
                'first_budget_stop_seconds':stops[0]['created']-summary['started'] if stops else None,
                'budget_stop_reasons':[e['payload'].get('reason') for e in stops],
                'memory_selection_count':len(selections),
                'memory_selection_rejected':sum(s.get('status')=='rejected' for s in selections),
                'evidence_prefix':prefix,'started':summary['started'],'finished':summary['finished']}
            rows.append(row)
            by_commit={t['commit']:t for t in lineage if t.get('commit')}
            for trial in lineage:
                trial={'series':series,**trial}
                trial['evidence_prefix']=prefix
                if trial.get('patch'):trial['patch']=prefix+trial['patch']
                variant_id=origin_map.get((series,key,trial.get('commit')))
                if variant_id is None and trial.get('variant_id') in measured:
                    variant_id=trial['variant_id']
                baseline_id=origin_map.get((series,key,trial.get('base_commit')))
                now=measured.get(variant_id,{});base=measured.get(baseline_id,{})
                trial.update(common_variant=variant_id,common_gpu_seconds=now.get('mean_seconds'),common_gpu_speedup=now.get('speedup'),
                    common_gpu_status=now.get('status'),common_gpu_correct=now.get('correct'),common_gpu_fully_measured=now.get('fully_measured'),
                    base_common_variant=baseline_id,base_common_gpu_seconds=base.get('mean_seconds'))
                trial['common_gain_vs_base_pct']=100*(1-now['mean_seconds']/base['mean_seconds']) if now.get('mean_seconds') and base.get('mean_seconds') else None
                trial['winning_blocks_vs_base']=sum(a<b for a,b in zip(now.get('samples',[]),base.get('samples',[]))) if now.get('fully_measured') and base.get('fully_measured') else None
                all_trials.append(trial)
            all_events.extend({'series':series,'condition':key,'job_id':summary['job_id'],'elapsed_seconds':e['created']-summary['started'],**e} for e in events)
            all_calls.extend({'series':series,**c} for c in calls)
            details[series+':'+key]={'summary':summary,'native':native,'metadata':meta,'calls':calls,'lineage':lineage}
    write(OUT/'data/comparison.json',rows)
    write(OUT/'data/comparison-trials.json',all_trials)
    write(OUT/'data/comparison-events.json',all_events)
    write(OUT/'data/comparison-native-calls.json',all_calls)
    table(OUT/'tables/comparaison-campagnes.csv',rows)
    table(OUT/'tables/comparaison-essais.csv',all_trials)
    table(OUT/'tables/comparaison-evenements.csv',all_events)
    table(OUT/'tables/comparaison-appels.csv',all_calls)
    primary=[r for r in rows if r['series']=='atomic']
    winners=sorted([r for r in primary if r['selected_common_gpu_seconds']],key=lambda r:r['selected_common_gpu_seconds'])
    assert len(primary)==7 and winners
    winner=winners[0]
    text=['# Historique et nouvelles comparaisons : moteurs et CUDA','',
        f"Les sept états du moteur ont été relancés depuis le même programme initial. Trois séries sont conservées : deux séries de diagnostic du transport, puis une série commune avec messages atomiques. Le rejeu final compare **{len(replay['programs'])-1} programmes distincts et points de comparaison**, plus une référence de contrôle, sur un seul GPU.",
        '',f"Dans la troisième série, le meilleur programme sélectionné vient de l’état **{winner['condition']}** : **{ms(winner['selected_common_gpu_seconds'])} ms**, soit **{number(winner['selected_common_gpu_speedup'],2)}×** la référence dans le rejeu commun. Ce classement est celui d’une nouvelle campagne par état ; il ne mesure pas la probabilité qu’un moteur retrouve ce résultat.",
        '', '[Tableau de bord interactif](TABLEAU-DE-BORD.html) · [Comportements et diagnostics expliqués](COMPORTEMENTS.md) · [Méthode et limites](METHODE.md) · [Historique initial : 19 commits, 12 révisions testées, 124 programmes rejoués](../comparaison-historique/RAPPORT.md)',
        '', '## Comparaison principale : troisième série', '',
        '| État du moteur | Arbres | Essais recherche / valides | G valides / essais | G confirmé | Pipeline | Programme sélectionné, rejeu commun | Accélération | Durée observée |',
        '|---|---:|---:|---:|---|---|---:|---:|---:|']
    for r in primary:
        text.append(f"| {r['condition']} — {r['label']} | {r['forest_width']} | {r['research_trials']} / {r['research_valid']} | {r['integration_valid']} / {r['integration_trials']} | {r['final_g_status'] or '—'} | {'complet' if r['pipeline_complete'] else 'incomplet'} | {ms(r['selected_common_gpu_seconds'])} ms | {number(r['selected_common_gpu_speedup'],2)}× | {duration(r['total_elapsed_seconds'])} |")
    text+=['','Les durées comprennent les phases observées jusqu’à la fin de confirmation ou de préparation de l’archive. Une terminaison anticipée, une erreur d’export et un arrêt normal de recherche ne sont pas assimilés. Le budget de 30 minutes est un budget d’admission avec achèvement du travail déjà engagé.',
        '', '## Historique et nouvelle recherche : même GPU pour les gagnants','',
        '| État | Gagnant historique remesuré | Gagnant de S3 remesuré | Variation de latence |','|---|---:|---:|---:|']
    for r in primary:
        delta=100*(r['selected_common_gpu_seconds']/r['historical_common_gpu_seconds']-1) if r['historical_common_gpu_seconds'] and r['selected_common_gpu_seconds'] else None
        text.append(f"| {r['condition']} | {ms(r['historical_common_gpu_seconds'])} ms | {ms(r['selected_common_gpu_seconds'])} ms | {number(delta,2)} % |")
    text+=['','Une variation négative indique une latence plus faible. Cette comparaison porte sur les programmes effectivement trouvés ; une modification du moteur n’est pas à elle seule une explication causale de cet écart.']
    verification=read(OUT/'protocol/new-replay-verification.json')
    text+=['','## Contrôles et dispersion du rejeu commun','',
        f"Le rejeu examine **{verification['programs']} programmes**, référence comprise : **{verification['correct_programs']}** réussissent les contrôles de correction et **{verification['fully_measured_programs']}** ont une mesure complète. Les **{verification['timing_samples_recomputed']} échantillons** et **{verification['per_size_latencies_recomputed']} temps par taille** sont recalculés depuis les journaux.",
        '',f"La référence varie sur une étendue de **{number(verification['baseline_range_pct'],3)} %** de sa moyenne. Le coefficient de variation médian des programmes est **{number(verification['median_program_cv_pct'],3)} %**, et le maximum **{number(verification['max_program_cv_pct'],3)} %**. Ce sont des dispersions de chronométrage ; elles ne mesurent pas la variabilité d’une recherche avec le modèle.",
        '', '[Vérification indépendante](protocol/new-replay-verification.json) · [Mesures par taille](tables/rejeu-temps-par-taille.csv) · [Cas numériques du rejeu](tables/rejeu-correction-par-cas.csv)']
    failed=[p for p in replay['programs'] if not p['fully_measured']]
    if failed:
        text+=['','### Programmes exclus du classement','']
        for p in failed:
            record=read(replay_root/'results/records'/(p['id']+'.json'))
            causes=[]
            for phase,check in record.get('checks',{}).items():
                payload=check.get('payload') or {}
                for case in payload.get('details',[]):
                    if not case.get('ok'):causes.append(f"{phase}, N={case.get('n')} ({case.get('label')}), {case.get('mismatches')} composante(s) hors tolérance")
                if payload.get('error'):causes.append(phase+': '+str(payload['error'])[:250])
            text.append(f"- `{p['id']}` : `{p['status']}`. {' ; '.join(causes) or 'Voir le dossier de mesures.'} [Enregistrement](gpu-comparaison/results/records/{p['id']}.json).")
        text+=['','L’admission au rejeu exigeait une évaluation valide dans au moins une phase historique. Le classement final exige les deux jeux de correction et toutes les mesures. Un échec déjà présent dans une campagne n’est pas présenté comme une nouvelle régression due au rejeu.']
    text+=[
        '', '## Programmes les plus rapides, toutes origines confondues', '',
        '| Rang | Programme | Origines | Moyenne | Min–max | Accélération |', '|---:|---|---|---:|---:|---:|']
    ranking=sorted([p for p in replay['programs'] if p['fully_measured'] and p['id']!='baseline-control'],key=lambda p:p['mean_seconds'])
    kernel_groups=defaultdict(list)
    for v in variants:
        if v['id']!='baseline-control':kernel_groups[v['source_sha256']].append(v)
    launch_pairs=[];launch_groups=[]
    for source_sha,group in kernel_groups.items():
        if len(group)<2:continue
        valid=[v for v in group if measured[v['id']]['fully_measured']]
        if len(valid)<2:continue
        ordered=sorted(valid,key=lambda v:measured[v['id']]['mean_seconds'])
        fast,slow=ordered[0],ordered[-1]
        fast_seconds=measured[fast['id']]['mean_seconds'];slow_seconds=measured[slow['id']]['mean_seconds']
        launch_groups.append({'source_sha256':source_sha,'programs':len(group),'measured_programs':len(valid),
            'fastest_id':fast['id'],'fastest_launch':fast['launch'],'fastest_seconds':fast_seconds,
            'slowest_id':slow['id'],'slowest_launch':slow['launch'],'slowest_seconds':slow_seconds,
            'fastest_gain_vs_slowest_pct':100*(1-fast_seconds/slow_seconds)})
        for a,b in combinations(valid,2):
            ma,mb=measured[a['id']],measured[b['id']]
            launch_pairs.append({'source_sha256':source_sha,'program_a':a['id'],'program_b':b['id'],
                'launch_a':a['launch'],'launch_b':b['launch'],'same_parsed_launch':a['launch']==b['launch'],
                'seconds_a':ma['mean_seconds'],'seconds_b':mb['mean_seconds'],
                'b_latency_change_pct':100*(mb['mean_seconds']/ma['mean_seconds']-1),
                'b_faster_blocks':sum(y<x for x,y in zip(ma['samples'],mb['samples']))})
    table(OUT/'tables/comparaisons-lancements.csv',launch_pairs)
    table(OUT/'tables/familles-lancements.csv',launch_groups)
    write(OUT/'data/launch-comparisons.json',{'groups':launch_groups,'pairs':launch_pairs})
    for rank,p in enumerate(ranking[:15],1):
        variant=next(v for v in variants if v['id']==p['id'])
        origins=sorted(set(o['series']+' / '+o.get('condition','') for o in variant['origins']))
        text.append(f"| {rank} | [{p['id']}](gpu-comparaison/sources/{p['id']}/src/nbody_kernel.cu) | {', '.join(origins)} | {ms(p['mean_seconds'])} ms | {ms(p['min_seconds'])}–{ms(p['max_seconds'])} ms | {number(p['speedup'],2)}× |")
    text+=['','Ce classement rétrospectif inclut les programmes intermédiaires. Il ne remplace pas le gagnant choisi et confirmé par chaque moteur. Les sources identiques sont dédupliquées et leurs origines restent toutes conservées.',
        '', '## Réglages de lancement avec un noyau inchangé', '',
        f"Les {len(variants)-1} programmes hors contrôle utilisent {len(kernel_groups)} sources CUDA distinctes octet pour octet. {len(launch_groups)} groupes permettent de comparer plusieurs lancements avec une même source ; leurs {len(launch_pairs)} comparaisons sont conservées. Les configurations identiques après lecture du JSON sont signalées, même si les octets du fichier diffèrent.",
        '', '| Source commune | Programmes mesurés | Lancement le plus rapide | Temps | Lancement le plus lent | Temps |',
        '|---|---:|---|---:|---|---:|']
    for group in launch_groups:
        fast=group['fastest_launch'];slow=group['slowest_launch']
        def launch_label(v):return '/'.join(str(v.get(k,'—')) for k in ['block','items_per_block','shared_memory_bytes'])
        text.append(f"| `{group['source_sha256'][:12]}` | {group['measured_programs']} | [{launch_label(fast)}](gpu-comparaison/sources/{group['fastest_id']}/src/launch.json) | {ms(group['fastest_seconds'])} ms | [{launch_label(slow)}](gpu-comparaison/sources/{group['slowest_id']}/src/launch.json) | {ms(group['slowest_seconds'])} ms |")
    text+=['', 'Les triplets indiquent threads par bloc / cibles par bloc / octets de mémoire partagée dynamique. Le choix rétrospectif du plus rapide ne remplace pas le choix fait pendant la campagne. Les paires ne sont pas ordonnées comme des transitions chronologiques et les petits écarts restent à lire avec la dispersion des blocs.',
        '', '[Toutes les paires de lancements](tables/comparaisons-lancements.csv) · [Résumé par source identique](tables/familles-lancements.csv)',
        '', '## Planification, critique et volume de recherche','',
        '| État | Plan initial : temps natif | Critique : temps natif | Appels natifs | Essais incorrects | Erreurs d’infrastructure | Autres échecs de recherche |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in primary:
        text.append(f"| {r['condition']} | {duration(r['planning_native_seconds'])} | {duration(r['review_native_seconds'])} | {r['native_calls']} | {r['research_incorrect']} | {r['research_infrastructure']} | {r['research_other']} |")
    text+=['','Les appels natifs ne sont pas les essais : une réparation du candidat peut consommer plusieurs appels. Les temps natifs parallèles ne doivent pas être additionnés pour obtenir la durée murale. [Détail des appels et des jetons](tables/comparaison-appels.csv).',
        '', '## Réserve de temps et décisions de sélection', '',
        '| État | Réserve initiale estimée | Temps restant au même instant | Fin de recherche observée | Sélections mémoire / rejetées |',
        '|---|---:|---:|---:|---:|']
    for r in primary:
        text.append(f"| {r['condition']} | {duration(r['initial_reserve_seconds'])} | {duration(r['initial_remaining_seconds'])} | {duration(r['search_elapsed_seconds'])} | {r['memory_selection_count']} / {r['memory_selection_rejected']} |")
    text+=['','La réserve est l’estimation du moteur pour les étapes restantes, pas une durée réellement consommée. Une réserve initiale supérieure au temps disponible explique un arrêt anticipé d’admission après la première vague. Les sélections rejetées désignent les décisions refusées par le protocole mémoire ; elles ne sont pas des échecs numériques CUDA.',
        '', '## Les séries précédentes restent visibles','',
        '| Série | État | Job | Recherche valide / totale | Recherche : arrêt | G confirmé | Pipeline | Meilleur candidat confirmé pendant la campagne |',
        '|---|---|---|---:|---|---|---|---:|']
    for r in rows:
        text.append(f"| {r['series_label']} | {r['condition']} | {r['job_id']} | {r['research_valid']} / {r['research_trials']} | {r['search_status']} | {r['final_g_status'] or '—'} | {'complet' if r['pipeline_complete'] else 'incomplet'} | {ms(r['selected_confirmed_seconds'])} ms |")
    text+=['','S1 et S2 documentent les incidents et les attentes de transfert. Elles ne sont pas fusionnées avec S3 pour calculer une moyenne de performance des moteurs. Les programmes validés de ces séries restent inclus dans le rejeu commun.',
        '', '## Ce que l’assemblage a réellement changé','',
        '| Série / état / essai G | Modification | Gain contre son parent, même GPU | Blocs gagnés |','|---|---|---:|---:|']
    for t in all_trials:
        if t['role']=='G':
            link=f"[{t['id']}]({t['patch']})" if t.get('patch') else t['id']
            text.append(f"| {t['series']} / {t['condition']} / {link} | {t['change_kind']} ; {t['status']} | {number(t['common_gain_vs_base_pct'],2)} % | {str(t['winning_blocks_vs_base'])+'/5' if t['winning_blocks_vs_base'] is not None else '—'} |")
    text+=['','Le parent est le `base_commit` enregistré pour l’essai. Une intégration peut mobiliser plusieurs sources ; le tableau ne prétend pas attribuer un effet individuel à chacune. Les variations petites devant la dispersion des cinq blocs restent incertaines.',
        '', '## Reconstitution par moteur']
    for key in CONDITIONS:
        r=next(r for r in primary if r['condition']==key);d=details['atomic:'+key]
        text+=['',f"### {key} — {LABELS[key]}",'',f"Job **{r['job_id']}**. Recherche : `{r['search_status']}`. G : `{r['final_g_status']}`. Pipeline complet : **{'oui' if r['pipeline_complete'] else 'non'}**.",'']
        if r['pipeline_error']:text.append('Diagnostic final : `'+r['pipeline_error'].replace('`',"'")+'`.\n')
        for child in d['summary']['forest_plan'].get('children',[]):
            text.append(f"- **{child['role']} — {escape(child.get('subject',''))}** : {escape(child.get('objective',''))}")
        text+=['',f"[Métadonnées et décisions](serie-atomique/data/{key}/metadata.json) · [Événements](serie-atomique/tables/{key}-events.csv) · [Appels du modèle](serie-atomique/data/{key}/native-calls.json)",'',
            '| Ordre | Rôle / essai | État | Modification | Temps de recherche | Temps du rejeu commun | Gain contre parent, même GPU |',
            '|---:|---|---|---|---:|---:|---:|']
        for t in [t for t in all_trials if t['series']=='atomic' and t['condition']==key]:
            label=f"[{t['id']}]({t['patch']})" if t.get('patch') else t['id']
            text.append(f"| {t['ordinal']} | {t['role']} / {label} | {t['status']} | {t['change_kind']} | {ms(t['seconds'])} ms | {ms(t['common_gpu_seconds'])} ms | {number(t['common_gain_vs_base_pct'],2)} % |")
    text+=['','## Pièces de preuve','',
        '- [Table complète des campagnes](tables/comparaison-campagnes.csv), [essais](tables/comparaison-essais.csv), [événements](tables/comparaison-evenements.csv) et [appels natifs](tables/comparaison-appels.csv).',
        '- Les sources et leurs empreintes sont conservées dans chaque série ; les différences de code sont dans `diffs/`.',
        '- Les bases SQLite, résultats, journaux de compilation, contrôles numériques et mesures sont dans `evidence/`.',
        '- Les messages et réponses publics des modèles ainsi que les reçus de transfert sont dans `native/` et `protocol/`.',
        '- [Diagnostics par cas numérique](tables/diagnostics-cas.csv), [évaluations](tables/diagnostics-evaluations.csv), [sélections mémoire](tables/diagnostics-selections.csv).',
        '- [Étapes et réparations internes aux essais](tables/diagnostics-tentatives-locales.csv), avec les hypothèses, les refus et les journaux exacts.',
        '- Le rejeu commun conserve son ordre aléatoire, ses cinq blocs, les dix contrôles de référence et les résultats par taille dans `gpu-comparaison/`.',
        '', 'Les tests de douze révisions du moteur et les comparaisons avant/après des régressions restent détaillés dans le rapport historique. Aucun fichier du dépôt étudié n’a été modifié par cette comparaison.', '']
    (OUT/'RAPPORT.md').write_text('\n'.join(text),encoding='utf8')
    variant_by_id={v['id']:v for v in variants}
    dashboard={'campaigns':rows,'trials':all_trials,'events':all_events,'native_calls':all_calls,
        'programs':[{**p,'origins':variant_by_id[p['id']]['origins']} for p in replay['programs']],
        'baseline_seconds':replay['baseline_mean_seconds'],'labels':LABELS}
    write(OUT/'data/dashboard.json',dashboard)
    print(json.dumps({'campaigns':len(rows),'trials':len(all_trials),'events':len(all_events),'native_calls':len(all_calls),'replay_programs':len(replay['programs']),'winner':winner},ensure_ascii=True))

if __name__=='__main__':build()
