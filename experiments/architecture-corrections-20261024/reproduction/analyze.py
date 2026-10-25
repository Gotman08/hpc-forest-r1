"""Three-generation comparison, using the existing frozen measurement aggregation."""
from pathlib import Path
import collections
import csv
import json
import statistics

from legacy_analysis import aggregate, engine_details, paired_range, samples

R = Path(__file__).resolve().parent
O = R.parents[1]/'outputs/forest-corrections-20261024'
PREVIOUS = R.parent/'active-architecture-20261024-v5-reprise'
CASES = ['sgemm','utf8','mandelbrot']


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')


def csv_file(name, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (O/name).open('w',encoding='utf-8-sig',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})


def excluded_attempts(selection):
    attempts=[]
    for study in [R.parent/'forest-corrections-20261024',R]:
        for job_file in sorted((study/'campaigns').glob('*/job.json')):
            directory=job_file.parent
            if study==R and directory.name in selection.values():
                continue
            job=read(job_file)
            plan=read(directory/'plan.json')
            info=read(directory/'efficiency.json') if (directory/'efficiency.json').exists() else {}
            incident=next((read(directory/f) for f in ['network-incident.json','interrupted.json']
                if (directory/f).exists()),{})
            paths=list((directory/'results').glob('results-*/results.json'))
            result=read(paths[0]) if paths else {}
            attempts.append({'job_id':str(job['job_id']),'case_id':plan.get('case_id'),
                'condition':directory.name,'study':study.name,'excluded_from_performance':True,
                'scheduler_state':info.get('state'),'elapsed_seconds':info.get('elapsed_seconds'),
                'pipeline_complete':result.get('pipeline_complete',False),
                'trial_count':len(result.get('trials',[])) if result else None,
                'error':result.get('error'),'incident':incident})
    return attempts


def input_comparability(found):
    blocks=collections.defaultdict(list)
    for name,values in found.items():
        for value in values:
            blocks[value['job_id'],value['block']].append((name,value))
    checks=[]
    for (job,block),items in sorted(blocks.items()):
        assert {name for name,_ in items}==set(found), (job,block)
        values=[value for _,value in items]
        hashes=[v['input_sha256'] for v in values if v.get('input_sha256')]
        if hashes:
            assert len(hashes)==len(values) and len(set(hashes))==1, (job,block,hashes)
            check={'method':'runtime_content_hash','input_sha256':hashes[0]}
        else:
            seeds=[v.get('seed') for v in values]
            assert all(seed is not None for seed in seeds) and len(set(seeds))==1, (job,block,seeds)
            check={'method':'seed_and_dimensions_with_hash_verified_protected_driver','seed':seeds[0]}
        checks.append({'job_id':job,'block':block,**check})
    methods={check['method'] for check in checks}
    return {'input_comparability_verified':True,'input_identity_methods':sorted(methods),
            'input_hashes_match':True if methods=={'runtime_content_hash'} else None,
            'input_checks_by_block':checks}


def engine(case, period, directory):
    info, trials, trees, calls, decisions, chronology = engine_details(directory,period)
    assert info is not None
    root = Path(info['result_path']).parent/('reference-'+case)
    active_path = root/'report/active-architecture.json'
    active = read(active_path) if active_path.exists() else {}
    jobs = active.get('jobs',[])
    state = active.get('state',{})
    analyst_jobs = [j for j in jobs if j['kind']=='analyst']
    info.update(analyst_calls=sum(len(j['calls']) for j in analyst_jobs),
        completed_analyses=sum(j['status']=='complete' for j in analyst_jobs),
        analyses_with_code=sum(j['status']=='complete' and bool(j.get('report',{}).get('code_findings')) for j in analyst_jobs),
        provided_source_excerpts=sum(len(j['coverage'].get('provided_sources',[])) for j in analyst_jobs),
        explicit_source_reads=sum(r['operation']=='source' for j in analyst_jobs for r in j['coverage']['reads']),
        verified_source_citations=sum(len(j['coverage'].get('cited_sources',[])) for j in analyst_jobs),
        unavailable_analyses=sum(j['status']=='unavailable' for j in analyst_jobs),
        analyst_call_wall_sum=sum(call.get('elapsed_seconds',0) for j in analyst_jobs for call in j['calls']),
        mother_call_wall_sum=sum(call.get('elapsed_seconds',0) for j in jobs if j['kind']=='mother' for call in j['calls']),
        unavailable_mother_jobs=sum(j['kind']=='mother' and j['status']=='unavailable' for j in jobs),
        mother_errors=dict(collections.Counter(j.get('error','unspecified') for j in jobs
            if j['kind']=='mother' and j['status']=='unavailable')),
        lifecycle=state.get('lifecycle'))
    result = read(Path(info['result_path']))
    info['stop_reason'] = result.get('research_scheduler',{}).get('stop_reason')
    origin = info['timing'].get('started_at')
    stops = []
    by_id = {j['id']:j for j in jobs}
    for job_id, batch in sorted(state.get('decisions',{}).items(),key=lambda pair:pair[1]['applied_at']):
        payload = json.loads(by_id[job_id]['calls'][-1]['request']['messages'][1]['content'])
        for item in batch['actions']:
            if item['action']['kind'] in {'close','suspend'}:
                stops.append({'case_id':case,'period':period,'job_id':info['job_id'],
                    'since_start_seconds':batch['applied_at']-origin if origin else None,
                    'decision_id':item['id'],'budget_at_snapshot':payload['budget'],
                    'newer_evidence_ids':batch.get('newer_evidence_ids',[]),**item})
    info['stop_decisions'] = stops
    info['first_close_proposal_seconds'] = next((s['since_start_seconds'] for s in stops
        if s['action']['kind']=='close'),None)
    info['rejected_close_count'] = sum(s['action']['kind']=='close' and s.get('status')=='rejected'
        for s in stops)
    info['rejected_suspend_count'] = sum(s['action']['kind']=='suspend' and s.get('status')=='rejected'
        for s in stops)
    info['stop_rejection_reasons'] = dict(collections.Counter(s.get('reason','unspecified')
        for s in stops if s.get('status')=='rejected'))
    info['lifecycle_events'] = dict(collections.Counter(e['event'] for e in chronology
        if e['event'].startswith(('active_progress','active_protected','active_unprotected','active_late','active_idle'))))
    info['idle_review_seconds'] = [e.get('since_start_seconds') for e in chronology
        if e['event']=='active_idle_review']
    info['first_close_request_seconds'] = next((s['since_start_seconds'] for s in stops
        if s['action']['kind']=='close' and s.get('status')=='applied'),None)
    info['confirmed_close_seconds'] = next((s['since_start_seconds'] for s in stops
        if s.get('closure_confirmed')),None)
    cutoff=info['first_close_request_seconds']
    measured=[e for e in chronology if e['event']=='evaluation_search' and e.get('correct') is True
              and e.get('seconds') and e.get('since_start_seconds') is not None
              and not e.get('experiment_id','').startswith('baseline-e')]
    before=[e for e in measured if cutoff is not None and e['since_start_seconds']<=cutoff]
    after=[e for e in measured if cutoff is not None and e['since_start_seconds']>cutoff]
    info['research_best_at_first_close_seconds']=min((e['seconds'] for e in before),default=None)
    info['research_best_after_first_close_seconds']=min((e['seconds'] for e in after),default=None)
    info['correct_research_evaluations_after_first_close']=len(after)
    reports = [{'case_id':case,'period':period,'tree':j['role'],'job_id':j['id'],
        'trigger':j.get('trigger'),'status':j['status'],'coverage':j['coverage'],'report':j.get('report'),
        'calls':len(j['calls']),'elapsed_seconds_sum':sum(c.get('elapsed_seconds',0) for c in j['calls']),
        'error':j.get('error')} for j in analyst_jobs]
    for job,report in zip(analyst_jobs,reports):
        payload=json.loads(job['calls'][0]['request']['messages'][1]['content']) if job['calls'] else {}
        own_ids=payload.get('trees',{}).get(job['role'],{}).get('completed_ids',[])
        latest=own_ids[-1] if own_ids else None
        report['latest_own_trial_id']=latest
        report['latest_own_source_provided']=bool(latest and any(
            page['evidence_id']==latest for page in payload.get('code_packet',{}).get('sources',[])))
        report['latest_own_source_cited']=bool(latest and any(
            citation['evidence_id']==latest for citation in job['coverage'].get('cited_sources',[])))
        latest_contents={(page['path'],page['sha256'])
            for page in payload.get('code_packet',{}).get('sources',[])
            if page['evidence_id']==latest}
        report['latest_own_code_cited']=bool(latest_contents.intersection(
            (citation['path'],citation['sha256'])
            for citation in job['coverage'].get('cited_sources',[])))
    info['analyses_citing_latest_own_source']=sum(report['status']=='complete'
        and report['latest_own_source_cited'] for report in reports)
    info['analyses_with_latest_own_source_provided']=sum(report['status']=='complete'
        and report['latest_own_source_provided'] for report in reports)
    info['analyses_citing_latest_own_code']=sum(report['status']=='complete'
        and report['latest_own_code_cited'] for report in reports)
    # Every native invocation must retain the requested runtime identity.
    identities = collections.Counter()
    for path in (directory/'worker').glob('*/request.json'):
        request = read(path)
        identities[(request.get('model'),request.get('reasoning_effort'))] += 1
    info['native_model_identities'] = [{'model':m,'effort':e,'requests':n} for (m,e),n in identities.items()]
    if period=='corrected':
        assert identities and set(identities)=={('gpt-6-luna','max')}, identities
        fresh=info['fresh_memory']
        assert fresh['trial_count']==fresh['document_count']==0 and not fresh['previous_candidates_imported']
    return info,trials,trees,calls,decisions,chronology,reports,stops


def main():
    O.mkdir(parents=True,exist_ok=True)
    tables = {k:[] for k in ['engines','trials','trees','calls','decisions','chronology','analyst_reports','stops']}
    selection = read(PREVIOUS/'main-selections.json')
    corrected_selection = read(R/'main-selections.json') if (R/'main-selections.json').exists() else {}
    for case in CASES:
        old=R.parent/'reference-rerun/campaigns'/case
        if not old.exists(): old=R.parent/'reference-study/campaigns'/case
        for period,directory in [('historical',old),('previous',PREVIOUS/'campaigns'/selection.get(case,case)),
                                 ('corrected',R/'campaigns'/corrected_selection.get(case,case))]:
            values=engine(case,period,directory)
            for key,value in zip(tables,values):
                tables[key].extend(value if isinstance(value,list) else [value])
    measurements=[];environments={};audits={};binary_audits={}
    for case in CASES:
        folder=R/('paired-'+case+'-results')
        files=list(folder.glob('measurements-*/results.json'))
        assert len(files)==1, (case,files)
        job=files[0].parent.name.removeprefix('measurements-')
        measurements.extend({**row,'job_id':job} for row in read(files[0]))
        environments[case]=read(files[0].with_name('environment.json'))
        audit=files[0].with_name('utf8-audit.json')
        if audit.exists(): audits[case]=read(audit)
        extended=files[0].with_name('utf8-extended-audit.json')
        if extended.exists(): audits[case+'_extended']=read(extended)
        binary_audit=files[0].parent/'binary-audit/manifest.json'
        if binary_audit.exists(): binary_audits[case]=read(binary_audit)
    timed=[item for item in measurements if not item.get('diagnostic')]
    assert all(item.get('exit_code')==0 and item.get('measurement',{}).get('correct') is True
               for item in timed), 'A failed timed variant must not disappear from the comparison'
    rows=[]
    variants={'baseline':None,'reference':None,'historical':'old_selected','previous':'previous_selected','corrected':'new_selected'}
    for old in read(R.parent/'reference-study/analysis.json')['rows']:
        if old.get('case_id') not in CASES: continue
        row={k:old.get(k) for k in ['id','label','case_id','n','threads','pattern','aggregation','baseline_variant',
            'reference_variant','published_speedup','published_hardware','hardware','compiler','notes']}
        found={name:samples(measurements,row,variant or row[name+'_variant']) for name,variant in variants.items()}
        assert all(found.values()), (row['id'],{k:len(v) for k,v in found.items()})
        expected_blocks=9 if row['case_id']=='sgemm' else 7
        assert all(len(values)==expected_blocks for values in found.values()), (row['id'],expected_blocks)
        for name,values in found.items(): row[name]=aggregate(values,row['aggregation'])
        for name in variants:
            if name!='baseline': row[name+'_speedup']=row['baseline']['seconds']/row[name]['seconds']
        row['corrected_vs_previous']=row['previous']['seconds']/row['corrected']['seconds']
        row['corrected_vs_historical']=row['historical']['seconds']/row['corrected']['seconds']
        row['corrected_vs_previous_block_range']=paired_range(found['previous'],found['corrected'])
        row.update(input_comparability(found))
        row['comparison_jobs']=sorted({v['job_id'] for values in found.values() for v in values})
        if row['case_id']=='utf8':
            repaired=samples(measurements,row,'repaired')
            row['repaired_baseline']=aggregate(repaired,row['aggregation'])
            row['corrected_vs_repaired']=row['repaired_baseline']['seconds']/row['corrected']['seconds']
        rows.append(row)
    durations=[]
    for entry in tables['engines']:
        for phase,values in entry['timing'].get('samples',{}).items():
            assert isinstance(values,list) and all(isinstance(v,(int,float)) and v>=0 for v in values)
            if values:
                durations.append({'period':entry['period'],'case_id':entry['case_id'],'job_id':entry['job_id'],
                    'phase':phase,'count':len(values),'sum_seconds':sum(values),
                    'min_seconds':min(values),'median_seconds':statistics.median(values),
                    'max_seconds':max(values),'samples_seconds':values,
                    'not_additive_across_phases':True})
    excluded=excluded_attempts({case:corrected_selection.get(case,case) for case in CASES})
    result={**tables,'rows':rows,'measurements':measurements,'environments':environments,'audits':audits,
        'binary_audits':binary_audits,
        'durations':durations,'excluded_attempts':excluded,'software_validation':read(R/'software-validation.json'),
        'protocol':read(R/'protocol.json'),'implementation':read(R/'implementation.json'),
        'limitation':'One completed stochastic search selected per case and architecture; interrupted attempts are retained separately and never selected by speedup. Repeated timing blocks are not independent search replicates.'}
    write(O/'RESULTATS.json',result)
    flat=[]
    for row in rows:
        item={k:v for k,v in row.items() if not isinstance(v,dict)}
        for name in ['baseline','reference','historical','previous','corrected','repaired_baseline']:
            stats=row.get(name) or {}
            item[name+'_seconds']=stats.get('seconds')
            item[name+'_repetitions']=stats.get('count')
            item[name+'_cv_pct']=stats.get('cv_pct')
        flat.append(item)
    for name,values in {**tables,'comparaison':flat,'mesures':measurements,'durees':durations,
                        'tentatives-interrompues':excluded}.items(): csv_file(name+'.csv',values)
    print(json.dumps({'engines':len(tables['engines']),'comparisons':len(rows),'measurements':len(measurements)}))


if __name__=='__main__':
    main()
