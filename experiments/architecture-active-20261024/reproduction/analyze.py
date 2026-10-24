"""Compare frozen old/new sources against reference codes in paired ROMEO jobs."""
from pathlib import Path
import argparse
import collections
import csv
import datetime
import json
import math
import re
import statistics as st
import tarfile

R = Path(__file__).resolve().parent
O = R.parents[1]/'outputs/architecture-active'


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else default


def csv_file(name, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (O/name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)


def samples(records, row, variant):
    result = []
    for item in records:
        m = item.get('measurement', {})
        if (item['case_id'] != row['case_id'] or str(item['variant']) != variant
                or item.get('diagnostic') or item.get('exit_code') != 0 or m.get('correct') is not True
                or m.get('n') != row['n'] or row['threads'] is not None and m.get('threads') != row['threads']
                or m.get('pattern', 0) != row.get('pattern', 0)):
            continue
        seconds = m.get('seconds', m.get('latency_ms', 0)/1000)
        if seconds > 0 and math.isfinite(seconds):
            result.append({**m, 'seconds':seconds, 'block':item['block'], 'job_id':item['job_id']})
    return result


def aggregate(records, method):
    if not records:
        return None
    x = [r['seconds'] for r in records]
    return {'seconds':{'median':st.median,'mean':st.mean,'min':min}[method](x),
            'count':len(x),'min':min(x),'max':max(x),'cv_pct':100*st.stdev(x)/st.mean(x) if len(x)>1 else 0}


def paired_range(a, b):
    by_block = {(r['job_id'],r['block']):r['seconds'] for r in b}
    ratios = [r['seconds']/by_block[(r['job_id'],r['block'])] for r in a if (r['job_id'],r['block']) in by_block]
    return [min(ratios),max(ratios)] if ratios else None


def native_usage(directory):
    """Normalize historical cumulative Mother counters without changing old files."""
    requests = []
    for path in (directory/'worker').glob('*/request.json'):
        if not path.with_name('generation-claimed.json').exists():
            continue
        request = read(path)
        response = read(path.with_name('response.json'),{})
        requests.append((request,response))
    previous = {}
    known,unknown,count = 0,0,0
    def order(pair):
        conversation=pair[0].get('conversation') or {}
        return conversation.get('id',''),conversation.get('turn',0)
    for request,response in sorted(requests,key=order):
        count += 1
        usage=response.get('usage') or {}
        tokens=usage.get('tokens') if usage.get('token_accounting')=='exact' else None
        conversation=request.get('conversation')
        if conversation and usage.get('accounting_scope')!='native_conversation_delta':
            raw=(usage.get('events') or [None])[-1]
            current={k:raw[k] for k in ['input_tokens','output_tokens']} if isinstance(raw,dict) and all(type(raw.get(k)) is int and raw[k]>=0 for k in ['input_tokens','output_tokens']) else None
            before={'input_tokens':0,'output_tokens':0} if conversation['turn']==0 else previous.get((conversation['id'],conversation['turn']-1))
            tokens=sum(current[k]-before[k] for k in current) if current and before and all(current[k]>=before[k] for k in current) else None
            previous[(conversation['id'],conversation['turn'])]=current
        if type(tokens) is int and tokens>=0:
            known+=tokens
        else:
            unknown+=1
    return {'native_invocations':count,'known_tokens_normalized':known,'unknown_invocation_usage':unknown,
            'method':'Mother cumulative counters differenced within each persisted conversation; raw original files retained',
            'available':bool(requests)}


def engine_details(directory, period):
    paths = list(directory.glob('results/results-*/results.json'))
    if not paths:
        return None, [], [], [], [], []
    assert len(paths)==1, paths
    result = read(paths[0])
    key = result['subject'].removeprefix('reference-')
    root = paths[0].parent/('reference-'+key)
    plan = result.get('forest_plan') or {}
    active = read(root/'report/active-architecture.json', {})
    current = active.get('state', {})
    evidence = read(root/'report/experiments.json', {})
    timing = result.get('timing') or {}
    metrics = timing.get('samples') or {}
    winner = result.get('best_confirmed') or {}
    final = result.get('final_g_confirmation') or {}
    calls, decisions, trials, trees = [], [], [], []
    for filename, target in [('active-control.csv',calls),('active-decisions.csv',decisions)]:
        file = root/'report'/filename
        if file.exists():
            with file.open(encoding='utf-8-sig',newline='') as stream:
                target.extend({'period':period,'case_id':key,'slurm_job':result['job_id'],**row} for row in csv.DictReader(stream))
    for trial in result.get('trials', []):
        mission, outcome = json.loads(trial['mission']), json.loads(trial.get('result') or '{}')
        trials.append({'period':period,'case_id':key,'job_id':result['job_id'],'id':trial['id'],'role':trial['role'],
            'state':trial['state'],'kind':'final_integration' if trial['role']=='G' else mission.get('kind','research'),
            'correct':outcome.get('correct'),'status':outcome.get('status'),'seconds':outcome.get('mean_seconds'),
            'score':outcome.get('score'),'reason':outcome.get('reason'),'commit':outcome.get('commit'),
            'base_commit':mission.get('base_commit'),'parent_id':mission.get('parent_id'),'source_ids':mission.get('sources'),
            'base_source_id':mission.get('base_source_id'),'decision_id':mission.get('control_decision_id'),
            'advice_ids':mission.get('advice_ids'),'import_ids':mission.get('import_ids'),
            'hypothesis':mission.get('hypothesis'),'transformations':mission.get('transformations'),
            'measurement_samples_seconds':outcome.get('times'), 'logs':outcome.get('logs')})
    measured_sources = {v['experiment_id']:v['outcome']['mean_seconds'] for v in evidence.get('evaluations', [])
                        if v['phase']=='search' and v['outcome'].get('correct') is True and v['outcome'].get('mean_seconds')}
    for item in trials:
        sources = item.get('source_ids') or []
        if item['correct'] is True and item['seconds'] and sources and all(s in measured_sources for s in sources):
            item['best_declared_source_seconds'] = min(measured_sources[s] for s in sources)
            item['speedup_over_best_declared_source'] = item['best_declared_source_seconds']/item['seconds']
    by_id = {item['id']:item for item in trials}
    incumbent = None
    for evaluation in sorted(evidence.get('evaluations', []),key=lambda e:e['created']):
        identity,outcome = evaluation['experiment_id'],evaluation['outcome']
        if evaluation['phase']!='search' or identity not in by_id and not identity.startswith('baseline-e'):
            continue
        seconds = outcome.get('mean_seconds') if outcome.get('correct') is True else None
        if identity in by_id and incumbent:
            by_id[identity].update(incumbent_before_id=incumbent[0],incumbent_before_seconds=incumbent[1],
                speedup_over_incumbent_before_measurement=incumbent[1]/seconds if seconds else None,
                improves_incumbent=bool(seconds and seconds<incumbent[1]))
        if seconds and (incumbent is None or seconds<incumbent[1]):
            incumbent=(identity,seconds)
    chronology = []
    origin = {'period':period,'case_id':key,'job_id':result['job_id']}
    safe_fields = {'experiment_id','role','ordinal','control_decision_id','job_id','kind','call',
                   'snapshot_id','closed','resulting_revision','actions','reason','can_admit',
                   'remaining_seconds','reserve_seconds','next_work_seconds'}
    for event in evidence.get('events', []):
        if event['kind'].startswith(('research_', 'active_')) or event['kind'] in {'adaptive_admission','budget_stop','search_exhausted','mother_forest_selected'}:
            payload = json.loads(event['payload'])
            chronology.append({**origin,'timestamp_unix':event['created'],'event':event['kind'],
                               'details':{k:v for k,v in payload.items() if k in safe_fields}})
    for evaluation in evidence.get('evaluations', []):
        outcome = evaluation['outcome']
        chronology.append({**origin,'timestamp_unix':evaluation['created'],'event':'evaluation_'+evaluation['phase'],
            'experiment_id':evaluation['experiment_id'],'correct':outcome.get('correct'),
            'status':outcome.get('status'),'seconds':outcome.get('mean_seconds'),'score':outcome.get('score'),
            'measurement_samples_seconds':outcome.get('times'),'reason':outcome.get('reason')})
    chronology.sort(key=lambda e:(e['timestamp_unix'],e['event']))
    for event in chronology:
        event['utc'] = datetime.datetime.fromtimestamp(event['timestamp_unix'],datetime.timezone.utc).isoformat()
        event['since_start_seconds'] = event['timestamp_unix']-timing['started_at'] if timing.get('started_at') else None
    for child in [*plan.get('children',[]),*current.get('children',[])]:
        role = child['role']
        own = [t for t in trials if t['role']==role]
        control = [c for c in calls if c['tree']==role]
        analyst = current.get('analysts',{}).get(role,{})
        trees.append({'period':period,'case_id':key,'job_id':result['job_id'],**child,
            'trials':len(own),'correct_trials':sum(t['correct'] is True for t in own),
            'status_counts':dict(collections.Counter(t['status'] for t in own)),
            'best_search_seconds':min((t['seconds'] for t in own if t['correct'] and t['seconds']),default=None),
            'analyst_calls':len(control),'analyst_report_id':analyst.get('report_id'),
            'analyst_status':analyst.get('status'),'analyst_coverage':analyst.get('coverage'),
            'generation_wall_sum':sum(metrics.get('generation:'+role,[])),
            'compilation_wall_sum':sum(metrics.get('evaluation_build:'+role,[])),
            'correctness_wall_sum':sum(metrics.get('evaluation_check:'+role,[])),
            'measurement_wall_sum':sum(metrics.get('evaluation_benchmark:'+role,[]))})
    elapsed = timing['finished_at']-timing['started_at'] if timing.get('finished_at') and timing.get('started_at') else None
    research_roles = {child['role'] for child in [*plan.get('children',[]),*current.get('children',[])]
                      if child.get('kind') != 'intermediate_integration'}
    all_suspended = bool(research_roles) and research_roles.issubset(set(current.get('suspended',[])))
    info = {'period':period,'case_id':key,'job_id':result['job_id'],'pipeline_complete':result.get('pipeline_complete'),
        'error':result.get('error'),'model':result.get('model'),'effort':result.get('effort'),
        'target_seconds':result.get('target_seconds'),'elapsed_seconds':elapsed,'overrun_seconds':timing.get('overrun_seconds'),
        'initial_trees':len(plan.get('children',[])),'created_trees':len(current.get('children',[])),
        'research_parallelism':(result.get('research_scheduler') or {}).get('research_workers'),
        'control_parallelism':(result.get('research_scheduler') or {}).get('control_workers',0),
        'total_trials':len(trials),'correct_trials':sum(t['correct'] is True for t in trials),
        'trials_with_analyst_or_mother_advice':sum(bool(t.get('advice_ids')) for t in trials),
        'trials_with_explicit_imports':sum(bool(t.get('import_ids')) for t in trials),
        'intermediate_integrations':sum(t['kind']=='intermediate_integration' for t in trials),
        'scheduler_status':(result.get('research_scheduler') or {}).get('status'),
        'all_research_trees_suspended_at_end':all_suspended,
        'explicit_research_closure':current.get('closed',False),
        'intermediate_integrations_improving_incumbent':sum(t['kind']=='intermediate_integration' and t.get('improves_incumbent') is True for t in trials),
        'status_counts':dict(collections.Counter(t['status'] for t in trials)),
        'active_summary':result.get('active_architecture'),'phase_costs':result.get('phase_costs'),
        'native_usage_normalized':native_usage(directory),
        'winner_id':winner.get('experiment_id'),'winner_commit':winner.get('commit'),
        'winner_objective_seconds':winner.get('mean_seconds'),'naive_retained':winner.get('is_baseline'),
        'final_g_confirmed':final.get('status')=='confirmed','verification':result.get('verification'),
        'fresh_memory':read(paths[0].parent/'fresh-memory.json'),
        'timing':timing,'result_path':str(paths[0])}
    return info, trials, trees, calls, decisions, chronology


def setup_attempts():
    """Keep all submitted development/interrupted runs outside the comparison."""
    power = read(R.parent/'active-architecture-20261024-v5/power-interruption.json', {})
    affected = set(power.get('affected_jobs', []))
    attempts = []
    seen = set()
    selected = set(read(R/'main-selections.json', {}).values())
    for study in sorted(R.parent.glob('active-architecture-20261024*')):
        for job_path in sorted(study.glob('campaigns/*/job.json')):
            directory = job_path.parent
            if study == R and directory.name in selected:
                continue
            job = str(read(job_path)['job_id'])
            assert job not in seen, job
            seen.add(job)
            plan = read(directory/'plan.json', {})
            efficiency = read(directory/'efficiency.json', {})
            result = None
            paths = list(directory.glob('results/results-*/results.json'))
            if paths:
                assert len(paths) == 1, paths
                result = read(paths[0])
            elif (directory/'results.tar.gz').exists():
                with tarfile.open(directory/'results.tar.gz') as archive:
                    names = [m for m in archive if m.isfile() and m.name.removeprefix('./') == f'results-{job}/results.json']
                    assert len(names) == 1, (job, names)
                    result = json.load(archive.extractfile(names[0]))
            result = result or {}
            active = result.get('active_architecture') or result.get('search', {}).get('active_architecture') or {}
            usage = native_usage(directory)
            attempts.append({'job_id':job, 'study':study.name, 'condition':directory.name,
                'case_id':plan.get('case_id', result.get('subject', '').removeprefix('reference-')),
                'category':'interrupted_main_attempt' if not plan.get('smoke_only', True) else 'development_pilot',
                'excluded_from_performance_comparison':True, 'state':efficiency.get('state'),
                'pipeline_complete':result.get('pipeline_complete', False), 'error':result.get('error'),
                'budget_seconds':plan.get('wall_seconds'), 'allocation_elapsed_seconds':efficiency.get('elapsed_seconds'),
                'allocated_cpus':efficiency.get('alloc_cpus'), 'allocated_gpus':efficiency.get('alloc_gpus'),
                'cpu_seconds_reserved':efficiency.get('cpu_seconds_reserved'),
                'gpu_seconds_reserved':efficiency.get('elapsed_seconds',0)*efficiency.get('alloc_gpus',0),
                'native_invocations':usage['native_invocations'], 'known_tokens_normalized':usage['known_tokens_normalized'],
                'unknown_invocation_usage':usage['unknown_invocation_usage'],
                'active_control_calls':active.get('control_calls',0), 'applied_actions':active.get('applied_actions',0),
                'local_battery_sleep_affected':job in affected,
                'final_g_confirmed':(result.get('final_g_confirmation') or {}).get('status')=='confirmed',
                'result_available':bool(result)})
    validation = R.parent/'comparison-validation-20261024'
    for job_path in sorted(validation.glob('paired-*-job.json')):
        stem = job_path.name.removesuffix('-job.json')
        job = str(read(job_path)['job_id'])
        assert job not in seen, job
        efficiency = read(validation/(stem+'-efficiency.json'), {})
        attempts.append({'job_id':job, 'study':validation.name, 'condition':stem,
            'category':'paired_measurement_validation', 'excluded_from_performance_comparison':True,
            'state':efficiency.get('state'), 'allocation_elapsed_seconds':efficiency.get('elapsed_seconds'),
            'allocated_cpus':efficiency.get('alloc_cpus'), 'allocated_gpus':efficiency.get('alloc_gpus'),
            'cpu_seconds_reserved':efficiency.get('cpu_seconds_reserved'),
            'gpu_seconds_reserved':efficiency.get('elapsed_seconds',0)*efficiency.get('alloc_gpus',0),
            'native_invocations':0, 'known_tokens_normalized':0, 'unknown_invocation_usage':0,
            'local_battery_sleep_affected':False})
    if (R/'cuda-runtime-check-job.json').exists():
        job = str(read(R/'cuda-runtime-check-job.json')['job_id'])
        efficiency = read(R/'cuda-runtime-check-efficiency.json', {})
        assert job not in seen, job
        attempts.append({'job_id':job,'study':R.name,'condition':'cuda-runtime-check',
            'category':'infrastructure_validation','excluded_from_performance_comparison':True,
            'state':efficiency.get('state'),'allocation_elapsed_seconds':efficiency.get('elapsed_seconds'),
            'allocated_cpus':efficiency.get('alloc_cpus'),'allocated_gpus':efficiency.get('alloc_gpus'),
            'cpu_seconds_reserved':efficiency.get('cpu_seconds_reserved'),
            'gpu_seconds_reserved':efficiency.get('elapsed_seconds',0)*efficiency.get('alloc_gpus',0),
            'native_invocations':0,'known_tokens_normalized':0,'unknown_invocation_usage':0,
            'local_battery_sleep_affected':False,'result_available':(R/'cuda-runtime-check.log').exists()})
    return attempts, power


def main(require_complete=False):
    O.mkdir(parents=True,exist_ok=True)
    original = read(R.parent/'reference-study/analysis.json')
    latest = {r['id']:r for r in read(R.parent/'reference-rerun/analysis.json')['rows']}
    groups = collections.defaultdict(list)
    manifests, environments, identities, audits = {}, {}, {}, {}
    for transfer in sorted(R.glob('paired-*-transfer.json')):
        meta = read(transfer)
        stem = transfer.name.removesuffix('-transfer.json')
        files = list((R/(stem+'-results')).glob('measurements-*/results.json'))
        if not files:
            continue
        assert len(files)==1, files
        environment = read(files[0].with_name('environment.json'))
        assert files[0].with_name('complete.json').exists(), stem
        records = read(files[0])
        if require_complete:
            verification = read(R/(stem+'-verification.json'))
            assert verification, stem
            if 'unexpected_failed_checks' in verification:
                assert verification['unexpected_failed_checks']==0, stem
            else:
                # First three receipts used an all-correct schema, without exceptions.
                assert verification['all_recorded_checks_correct'] is True, stem
                assert all(r.get('exit_code')==0 and r.get('measurement',{}).get('correct') is True for r in records), stem
            assert verification['source_hashes_verified'] is True, stem
            assert str(verification['job_id'])==str(environment['job']), stem
            assert verification['records']==len(records), stem
        for record in records:
            groups[meta['group']].append({**record,'job_id':str(environment['job'])})
        manifest = read(R/stem/'manifest.json')
        manifests[stem], environments[stem] = manifest, environment
        for label,relative in [('utf8','utf8-audit.json'),('volume','volume-domain/audit.json')]:
            path=files[0].parent/relative
            if path.exists():audits[label]=read(path)
        for key in meta['keys']:
            pair = {m['variant']:m for m in manifest if m['case_id']==key and not m.get('missing')}
            if not all(k in pair for k in ('old_selected','new_selected')):
                continue
            artifacts = environment.get('candidate_artifact_sha256',{})
            old_binary,new_binary = (artifacts.get(key+'/'+name+'/candidate.so') for name in ['old_selected','new_selected'])
            if meta['group']=='clang':
                old_binary,new_binary = (environment.get('binary_sha256',{}).get(name) for name in ['old_selected','new_selected'])
            identities[(meta['group'],key)] = {'old_source_sha256':pair['old_selected']['sha256'],
                'new_source_sha256':pair['new_selected']['sha256'],
                'source_identical_old_new':pair['old_selected']['sha256']==pair['new_selected']['sha256'],
                'binary_identical_old_new':old_binary==new_binary if old_binary and new_binary else None}
    rows = []
    for previous in original['rows']:
        row = {k:previous.get(k) for k in ['id','label','case_id','group','n','threads','pattern','aggregation',
            'baseline_variant','reference_variant','published_speedup','published_hardware','hardware','compiler',
            'published_input','source','notes']}
        if not row['case_id']:
            row['verdict'] = 'Non exécutable : source ou données exactes manquantes'
            rows.append(row)
            continue
        recent = latest.get(row['id'],previous)
        row.update(previous_forest_speedup=recent.get('new_selected_speedup',recent.get('forest_speedup')),
            previous_reference_speedup=recent.get('reference_speedup'))
        row.update(identities.get((row['group'],row['case_id']),{}))
        if row['case_id']=='base64':
            row['notes']=row['notes'].split('Deux erreurs')[0].strip()
        variants = [('baseline',row['baseline_variant']),('reference',row['reference_variant'])]+[(v,v) for v in ['old_selected','new_selected','old_g','new_g']]
        ss = {name:samples(groups[row['group']],row,variant) for name,variant in variants}
        expected = 9 if row['group'] in {'gpu','extra'} else 7
        complete = all(len(ss[name])==expected for name in ['baseline','reference','old_selected','new_selected'])
        if not complete:
            row['verdict']='Mesures appariées non terminées ou invalides'
            rows.append(row)
            continue
        jobs = {r['job_id'] for values in ss.values() for r in values}
        assert len(jobs)==1,(row['id'],jobs)
        row['comparison_job']=jobs.pop()
        for name,value in ss.items():
            assert len({r['block'] for r in value})==len(value),(row['id'],name,'duplicate block')
            row[name]=aggregate(value,row['aggregation'])
        times={name:row[name]['seconds'] for name in ss if row.get(name)}
        for name in ['reference','old_selected','new_selected','old_g','new_g']:
            row[name+'_speedup']=times['baseline']/times[name] if name in times else None
        row['new_vs_old']=times['old_selected']/times['new_selected']
        row['new_vs_reference']=times['reference']/times['new_selected']
        row['time_reduction_percent']=100*(1-times['new_selected']/times['old_selected'])
        row['new_vs_old_min'],row['new_vs_old_max']=paired_range(ss['old_selected'],ss['new_selected'])
        row['new_vs_reference_min'],row['new_vs_reference_max']=paired_range(ss['reference'],ss['new_selected'])
        row['verdict']=('Code ou binaire identique : variation de mesure' if row.get('source_identical_old_new') or row.get('binary_identical_old_new') else
            'Nouveau plus rapide dans chaque bloc' if row['new_vs_old_min']>1 else
            'Ancien plus rapide dans chaque bloc' if row['new_vs_old_max']<1 else 'Écart dans la variabilité observée')
        row['reference_verdict']=('Forest dépasse la référence dans chaque bloc' if row['new_vs_reference_min']>1 else
            'Référence plus rapide dans chaque bloc' if row['new_vs_reference_max']<1 else 'Écart dans la variabilité observée')
        hashes={r['block']:r.get('input_sha256') for r in ss['baseline']}
        row['input_hashes_verified']=bool(hashes) and all(hashes.values())
        if row['input_hashes_verified']:
            for name,values in ss.items():
                assert all(hashes[r['block']]==r.get('input_sha256') for r in values),(row['id'],name,'input mismatch')
        rows.append(row)
    engines,trials,trees,calls,decisions,chronology=[],[],[],[],[],[]
    keys=sorted({r['case_id'] for r in original['rows'] if r.get('case_id')})
    selected=read(R/'main-selections.json', {key:key for key in keys})
    assert set(selected)==set(keys), selected
    for key in keys:
        prior=R.parent/'reference-rerun/campaigns'/key
        if not prior.exists():prior=R.parent/'reference-study/campaigns'/key
        for period,directory in [('old',prior),('new',R/'campaigns'/selected[key])]:
            info,*details=engine_details(directory,period)
            if info:engines.append(info)
            for target,items in zip([trials,trees,calls,decisions,chronology],details):target.extend(items)
    raw=[]
    for group,records in groups.items():
        for record in records:
            measurement=record.get('measurement',{})
            raw.append({'group':group,**{k:v for k,v in record.items() if k!='measurement'},**measurement})
    failures=[r for r in raw if r.get('correct') is not True or r.get('exit_code')!=0]
    distinct = {}
    for row in rows:
        if 'new_vs_old' in row:
            identity=tuple(row.get(k) for k in ['comparison_job','case_id','n','threads','pattern'])
            if identity in distinct:
                # Different documentary aggregations can reuse the same blocks.
                assert all(row[k]==distinct[identity][k] for k in ['new_vs_old_min','new_vs_old_max','verdict']),identity
            else:
                distinct[identity]=row
    strongest_references=[]
    for identity, anchor in distinct.items():
        options=[r for r in rows if 'new_vs_old' in r
                 and tuple(r.get(k) for k in ['comparison_job','case_id','n','threads','pattern'])==identity
                 and r['aggregation']==anchor['aggregation']]
        best=min(options,key=lambda r:(r['reference']['seconds'],r['id']))
        strongest_references.append({**{k:best[k] for k in
            ['case_id','comparison_job','n','threads','pattern','aggregation','hardware','compiler',
             'reference_variant','source','new_vs_reference','new_vs_reference_min','new_vs_reference_max','reference_verdict']},
            'reference_documentary_id':best['id'], 'documentary_reference_options':sorted({r['reference_variant'] for r in options}),
            'reference_ms':best['reference']['seconds']*1000,
            'new_selected_ms':best['new_selected']['seconds']*1000,
            'note':'Fastest observed reference among documentary rows for this same input, job and aggregation; not a claim about all existing implementations.'})
    summary={'documentary_rows':len(rows),'measured_rows':sum('new_vs_old' in r for r in rows),'unavailable_rows':sum(not r.get('case_id') for r in rows),
        'distinct_old_new_comparisons':len(distinct),
        'strongest_reference_verdict_counts':dict(collections.Counter(r['reference_verdict'] for r in strongest_references)),
        'distinct_verdict_counts':dict(collections.Counter(r['verdict'] for r in distinct.values())),
        'programs':len(keys),'new_finished':sum(e['period']=='new' and e['pipeline_complete'] for e in engines),
        'verdict_counts':dict(collections.Counter(r['verdict'] for r in rows)),
        'records':len(raw),'failures':failures,'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    if require_complete:
        assert summary['documentary_rows']==62 and summary['measured_rows']==57 and summary['new_finished']==21,summary
        assert all(r['variant'] not in {'old_selected','new_selected'} for r in failures),failures
        assert len(failures)==3, failures
        assert collections.Counter((r['case_id'],r['variant'],r['diagnostic'],r['block']) for r in failures)=={
            ('utf8','naive',True,-1):1,('volume','optimized',True,-1):2}, failures
        assert 'utf8' in audits and 'volume' in audits, audits.keys()
        assert all(r['cases']==79729 for r in audits['utf8']['records'])
        assert all(r['failed']==0 for r in audits['utf8']['records'] if r['variant']!='historical'),audits['utf8']
        assert all(r['measurement'].get('correct') is True for r in audits['volume']['records'] if r['reference_supported_domain']),audits['volume']
    attempts, power = setup_attempts()
    summary['setup_attempts'] = len(attempts)
    summary['setup_allocation_seconds_sum'] = sum(a.get('allocation_elapsed_seconds') or 0 for a in attempts)
    summary['setup_known_tokens_normalized'] = sum(a['known_tokens_normalized'] for a in attempts)
    summary['setup_unknown_invocation_usage'] = sum(a['unknown_invocation_usage'] for a in attempts)
    data={'summary':summary,'rows':rows,'engines':engines,'trees':trees,'trials':trials,'calls':calls,'decisions':decisions,
        'setup_attempts':attempts, 'power_interruption':power, 'chronology':chronology,'strongest_references':strongest_references,
        'measurements':raw,'environments':environments,'manifests':manifests,'audits':audits,'protocol':read(R/'protocol.json')}
    (O/'RESULTATS.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    flat=[]
    for row in rows:
        out={k:v for k,v in row.items() if not isinstance(v,dict)}
        for name in ['baseline','reference','old_selected','new_selected','old_g','new_g']:
            stats=row.get(name) or {}
            out[name+'_ms']=stats['seconds']*1000 if stats.get('seconds') else None
            out[name+'_repetitions']=stats.get('count')
            out[name+'_cv_pct']=stats.get('cv_pct')
        flat.append(out)
    durations=[]
    for engine in engines:
        for label,values in (engine.get('timing') or {}).get('samples',{}).items():
            assert isinstance(values,list) and all(isinstance(v,(int,float)) and v>=0 for v in values),(engine['case_id'],label)
            if not values:
                continue
            durations.append({'period':engine['period'],'case_id':engine['case_id'],'job_id':engine['job_id'],
                'phase':label,'count':len(values),'sum_seconds':sum(values),
                'min_seconds':min(values),'median_seconds':st.median(values),'max_seconds':max(values),
                'samples_seconds':values,'not_additive_across_phases':True,
                'warning':'Overlapping work and nested timing scopes; do not sum phase totals as campaign elapsed time'})
    hardware=[]
    for stem,environment in sorted(environments.items()):
        def field(text,key):
            match=re.search(r'^\s*'+re.escape(key)+r'\s*:\s*(.+)$',text,re.M)
            return match.group(1).strip() if match else None
        cpu,gpu=environment.get('cpu',''),environment.get('gpu','')
        affinity=environment.get('affinity')
        hardware.append({'comparison':stem,'job_id':environment['job'],
            'cpu_model':field(cpu,'Model name'),'architecture':field(cpu,'Architecture'),
            'threads_per_core':field(cpu,'Thread(s) per core'),'cores_per_socket':field(cpu,'Core(s) per socket'),
            'sockets':field(cpu,'Socket(s)'),'numa_nodes_on_host':field(cpu,'NUMA node(s)'),
            'cpu_scaling_snapshot':field(cpu,'CPU(s) scaling MHz'),
            'allowed_cpu_count':len(affinity) if affinity is not None else None,'allowed_cpus':affinity,
            'gpu_model':field(gpu,'Product Name'),'gpu_driver':field(gpu,'Driver Version'),
            'cuda_version_reported_by_driver':field(gpu,'CUDA Version'),
            'gpu_performance_state_snapshot':field(gpu,'Performance State'),
            'gpu_temperature_snapshot':field(gpu,'GPU Current Temp'),
            'gpu_average_power_snapshot':field(gpu,'Average Power Draw'),
            'compiler_output':environment.get('compiler'),
            'recorded_at_epoch':environment.get('start',environment.get('time')),
            'warning':'Hardware state is a snapshot, not monitoring throughout the benchmarks. Driver CUDA support is not the toolkit version. Missing fields are unknown.'})
    csv_file('ENVIRONNEMENTS.csv',hardware)
    csv_file('REFERENCES-LES-PLUS-RAPIDES.csv',strongest_references)
    for name,values in [('COMPARAISON.csv',flat),('CAMPAGNES.csv',engines),('ARBRES.csv',trees),('ESSAIS.csv',trials),
                        ('APPELS-ANALYSTES-MOTHER.csv',calls),('DECISIONS.csv',decisions),('MESURES-BRUTES.csv',raw),
                        ('TENTATIVES-PREALABLES.csv',attempts),('CHRONOLOGIE.csv',chronology),('DUREES-PHASES.csv',durations)]:
        csv_file(name,values)
    print(json.dumps({k:v for k,v in summary.items() if k!='failures'},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--require-complete',action='store_true')
    main(parser.parse_args().require_complete)
