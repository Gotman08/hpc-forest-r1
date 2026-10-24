"""Read-only audit of fresh campaigns, model contexts, trees and execution sites."""
from pathlib import Path
import json, sqlite3, collections, hashlib, csv, datetime
R=Path(__file__).resolve().parent
O=R.parent.parent/'outputs/comparaison-reprises'
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
eff={}
for p in R.glob('job-efficiency*.json'):
    d=read(p)
    for v in d if isinstance(d,list) else d.values():
        if isinstance(v,dict) and v.get('job_id'):eff[v['job_id']]=v
rows=[];seen_threads=collections.defaultdict(set);seen_conversations=collections.defaultdict(set)
for root in sorted((R/'campaigns').iterdir()):
    result_path=next(root.glob('results/results-*/results.json'))
    d=read(result_path);plan=read(root/'plan.json');settings=read(root/'settings.json')
    assert settings['memory']['context_characters']==64000
    assert d['session_id']==plan['session_id']==settings['codex']['session_id']
    assert d['old_candidates_imported'] is False and plan['old_candidates_imported'] is False
    db_path=next(result_path.parent.glob('reference-*/registry.sqlite3'))
    con=sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
    meta={r['key']:json.loads(r['value']) for r in con.execute('SELECT * FROM metadata')}
    fp=d.get('forest_plan') or meta.get('forest_plan:1') or {}
    trials=[{**t,'mission':json.loads(t['mission']),'result':json.loads(t['result'] or '{}')} for t in d.get('trials',[])]
    statuses=collections.Counter(t['result'].get('status') for t in trials)
    counts=collections.Counter(t['role'] for t in trials)
    trees=[dict(r) for r in con.execute('SELECT id,role,version FROM trees ORDER BY role')]
    facts=[dict(r) for r in con.execute('SELECT kind,count(*) AS n FROM memory_facts GROUP BY kind')]
    scopes=[dict(r) for r in con.execute('SELECT DISTINCT epoch,protocol_id FROM memory_facts')]
    assert all(s['epoch']==1 and s['protocol_id']==meta['protocol_id'] for s in scopes)
    events=[dict(r) for r in con.execute('SELECT kind,payload,created FROM events ORDER BY id')]
    assert events[0]['kind']=='workspace_created'
    assert len([e for e in events if e['kind']=='workspace_created'])==1
    memory_first=con.execute('SELECT min(created) FROM memory_facts').fetchone()[0]
    # Baseline memory uses the epoch creation time, slightly before the
    # workspace_created event; it does not use the later ingestion time.
    epoch_start=con.execute('SELECT min(created) FROM epochs').fetchone()[0]
    assert memory_first is None or memory_first>=epoch_start
    scheduler=meta.get('research_scheduler:1') or {}
    assert set(counts)-{'G'}=={child['role'] for child in fp.get('children',[])}
    submitted=[json.loads(e['payload']) for e in events if e['kind']=='research_node_submitted']
    assert len(submitted)==sum(v for k,v in counts.items() if k!='G')
    calls=[];initial_mother=[];native_threads=set();method_conversations=set()
    for p in sorted((root/'worker').glob('*/invocation.json')):
        inv=read(p);req=read(p.parent/'request.json');argv=inv['argv']
        assert req['session_id']==plan['session_id']
        assert inv['hosted_inference'] is True and inv['local_source_execution_allowed'] is False
        assert inv.get('remote_experiments_allowed') is False and inv.get('model_mcp') is None
        for flag in ['--ignore-user-config','--strict-config','features.memories=false','features.apps=false','features.shell_tool=false','project_doc_max_bytes=0']:
            assert flag in argv,(root.name,flag)
        cv=inv.get('conversation');persistent=cv is not None
        if persistent:
            method_conversations.add(cv['id']);seen_conversations[cv['id']].add(root.name)
            if cv['turn']==0:
                assert cv['thread_id'] is None and 'resume' not in argv
                initial_mother.append({'id':cv['id'],'turn':0,'thread_id':None})
            else:assert 'resume' in argv and cv['thread_id'] in argv
        else:assert '--ephemeral' in argv and 'resume' not in argv
        tids=set();completed=0;native_failures=[]
        for line in (p.parent/'codex.jsonl').read_text(encoding='utf8',errors='replace').splitlines():
            try:event=json.loads(line)
            except ValueError:continue
            if event.get('type')=='thread.started' and event.get('thread_id'):tids.add(event['thread_id'])
            if event.get('type')=='turn.completed':completed+=1
            if event.get('type')=='error' and event.get('message'):native_failures.append(event['message'])
            if event.get('type')=='turn.failed' and (event.get('error') or {}).get('message'):
                native_failures.append(event['error']['message'])
        native_threads.update(tids)
        for tid in tids:seen_threads[tid].add(root.name)
        response=read(p.parent/'response.json') if (p.parent/'response.json').exists() else {}
        source_context={}
        for message in req.get('messages',[]):
            content=message.get('content','')
            marker='\n\nCURRENT SOURCE AS DATA:\n'
            if message.get('role')=='user' and isinstance(content,str) and marker in content:
                prefix,source=content.split(marker,1)
                source_data=json.loads(prefix)
                memory=source_data.get('context_as_data',{}).get('memory',{})
                source_context={'source_paged':bool(memory.get('source_read_required')),
                                'context_limit_characters':memory.get('max_result_characters'),
                                'inline_source_paths':source_data.get('current_source_paths',[]),
                                'inline_source_section_characters':len(source)}
        calls.append({'nonce':req['nonce'],'mission_id':req['mission_id'],'meta_role':req.get('meta_role'),'budget_phase':req.get('budget_phase'),'persistent_mother':persistent,'conversation':cv,'native_thread_ids':sorted(tids),'observed_turn_completed_events':completed,'request_sha256':inv['request_sha256'],'invocation_sha256':sha(p),'ephemeral_flag':'--ephemeral' in argv,'hosted_inference':True,'documentation_enabled':bool(inv.get('documentation_mcp')),'error':response.get('error'),'infrastructure_error':response.get('infrastructure_error'),'native_failure_messages':list(dict.fromkeys(native_failures)),'source_context':source_context})
    assert len(initial_mother)==(1 if fp else 0)
    assert len(method_conversations)==(1 if fp else 0)
    first_by_role={}
    for event in submitted:first_by_role.setdefault(event['role'],event['submitted_at'])
    spread=max(first_by_role.values())-min(first_by_role.values()) if first_by_role else None
    node_stats=[]
    for child in fp.get('children',[]):
        ts=[t for t in trials if t['role']==child['role']]
        node_stats.append({**child,'attempts':len(ts),'statuses':dict(collections.Counter(t['result'].get('status') for t in ts)),'max_mission_depth':max((t['mission']['depth'] for t in ts),default=0),'nonbaseline_parent_attempts':sum(bool(t['mission']['parent_id']) for t in ts)})
    alloc_path=result_path.parent/'allocation.json';alloc=read(alloc_path) if alloc_path.exists() else None
    if alloc:assert alloc['job_id']==d['job_id'] and alloc['treequest']=='0.3.2'
    end=(d.get('timing') or {}).get('finished_at') or meta.get('pipeline_finished:1') or meta.get('confirmation_finished:1')
    start=meta.get('started');elapsed=end-start if start and end else None
    selected=d.get('best_confirmed') or {};g=d.get('final_g_confirmation') or {}
    rows.append({'case_id':d['subject'].removeprefix('reference-'),'campaign':root.name,'job_id':d['job_id'],'session_id':plan['session_id'],'remote_root':plan['remote_root'],'fresh_workspace_created':True,'old_candidates_imported':False,'initial_mother':initial_mother,'native_thread_ids':sorted(native_threads),'source_sha256':plan['source_sha256'],'result_sha256':sha(result_path),'registry_sha256':sha(db_path),'settings_sha256':sha(root/'settings.json'),'model':d['model'],'effort':d['effort'],'trees_selected':len(node_stats),'tree_details':node_stats,'trial_counts':dict(counts),'trial_statuses':dict(statuses),'registered_trees':trees,'scheduler':scheduler,'initial_dispatch_spread_seconds':spread,'memory_records':{r['kind']:r['n'] for r in facts},'memory_protocol_scopes':scopes,'mother_last_turn':(meta.get('mother_conversation:1') or {}).get('turn'),'invocation_count':len(calls),'persistent_invocations':sum(c['persistent_mother'] for c in calls),'ephemeral_invocations':sum(not c['persistent_mother'] for c in calls),'calls':calls,'settings':{k:settings[k] for k in ['forest','completion','budget','schedule','memory','protocol','harness']},'allocation':alloc,'requested_cpus':plan.get('cpus'),'requested_gpus':plan.get('gpus'),'target_seconds':d['target_seconds'],'elapsed_to_final_or_confirmation_seconds':elapsed,'elapsed_end_is_pipeline_finished':bool((d.get('timing') or {}).get('finished_at')),'slurm_elapsed_seconds':eff.get(d['job_id'],{}).get('elapsed_seconds'),'slurm_state':eff.get(d['job_id'],{}).get('state'),'pipeline_complete':d.get('pipeline_complete',False),'pipeline_error':d.get('error'),'selected_commit':selected.get('commit'),'selected_is_baseline':selected.get('is_baseline',False),'final_g_commit':(g.get('outcome') or {}).get('commit'),'final_g_status':g.get('status')})
    fresh=read(result_path.parent/'fresh-memory.json')
    assert fresh['session_id']==plan['session_id']
    assert fresh['epoch']==1 and fresh['trial_count']==fresh['document_count']==0
    rows[-1]['initial_empty_memory_receipt']=fresh
    rows[-1]['costs']=d.get('costs')
    rows[-1]['phase_costs']=d.get('phase_costs')
    rows[-1]['timing']=d.get('timing')
    rows[-1]['engine_manifest_sha256']=plan['engine_manifest_sha256']
    rows[-1]['output_limit_classification_fixed']=plan.get('output_limit_classified_as_generation_failure',False)
    con.close()
assert len({r['session_id'] for r in rows})==len(rows)==14
assert len({r['remote_root'] for r in rows})==14
assert all(len(c)==1 for c in seen_threads.values())
assert all(len(c)==1 for c in seen_conversations.values())
previous=read(R.parent.parent/'outputs/comparaison-references/AUDIT-FOREST.json')
old_sessions={r['session_id'] for r in previous['campaigns']}
old_threads={t for r in previous['campaigns'] for t in r['native_thread_ids']}
old_conversations={c['id'] for r in previous['campaigns'] for c in r['initial_mother']}
interrupted=read(O/'TENTATIVE-INTERROMPUE.json')
old_sessions.update(r['session_id'] for r in interrupted['campaigns'])
old_conversations.update((r['tree_plan'].get('conversation') or {}).get('id') for r in interrupted['campaigns'])
for log in (R/'attempt-context12000/campaigns').glob('*/worker/*/codex.jsonl'):
    for line in log.read_text(encoding='utf8', errors='replace').splitlines():
        try:event=json.loads(line)
        except ValueError:continue
        if event.get('type')=='thread.started' and event.get('thread_id'):
            old_threads.add(event['thread_id'])
assert not old_sessions.intersection(r['session_id'] for r in rows)
if (R/'attempt-output-limit/base64/plan.json').exists():
    superseded=R/'attempt-output-limit/base64'
    old_sessions.add(read(superseded/'plan.json')['session_id'])
    for p in (superseded/'worker').glob('*/invocation.json'):
        cv=read(p).get('conversation')
        if cv:old_conversations.add(cv['id'])
        for line in (p.parent/'codex.jsonl').read_text(encoding='utf8',errors='replace').splitlines():
            try:event=json.loads(line)
            except ValueError:continue
            if event.get('type')=='thread.started' and event.get('thread_id'):old_threads.add(event['thread_id'])
assert not old_sessions.intersection(r['session_id'] for r in rows)
assert not old_threads.intersection(seen_threads)
assert not old_conversations.intersection(seen_conversations)
summary={'campaigns':14,'program_families':14,'campaigns_reaching_mother':sum(bool(r['initial_mother']) for r in rows),'research_trees':sum(r['trees_selected'] for r in rows),'trials':sum(sum(r['trial_counts'].values()) for r in rows),'G_trials':sum(r['trial_counts'].get('G',0) for r in rows),'native_invocations':sum(r['invocation_count'] for r in rows),'persistent_mother_invocations':sum(r['persistent_invocations'] for r in rows),'ephemeral_invocations':sum(r['ephemeral_invocations'] for r in rows),'unique_native_threads':len(seen_threads),'cross_campaign_reused_threads':0,'cross_campaign_reused_conversations':0,'unique_sessions':14,'all_protocol_scopes_local':True,'prior_study_sessions_reused':0,'prior_study_threads_reused':0,'prior_study_conversations_reused':0,'all_initial_memory_receipts_empty':True,'all_automatic_codex_memories_disabled':True,'all_model_inference_hosted':True,'all_model_local_source_execution_disabled':True,'audit_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
out={'summary':summary,'campaigns':rows,'evidence_scope':'Observed application contexts, archived controller databases and native CLI invocations; no claim about erasing model training or provider internals.'}
summary.update({'interrupted_attempt_campaigns_excluded':14,'memory_context_characters':64000,'interrupted_attempt_context_characters':12000})
summary['source_paged_calls']=sum(bool(c['source_context'].get('source_paged')) for r in rows for c in r['calls'])
summary['reported_tokens_used']=sum((r['costs'] or {}).get('tokens_used',0) for r in rows)
summary['superseded_output_limit_campaigns']=int((R/'attempt-output-limit/base64/plan.json').exists())
summary['engine_manifest_sha256_values']=sorted({r['engine_manifest_sha256'] for r in rows})
(O/'AUDIT-FOREST.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf8')
fields=['programme','campagne','job','arbres_recherche','essais_par_arbre','essais_G','essais_total','valides','incorrects','generation_echouee','infrastructure','appels_natifs','appels_Mother_persistants','appels_ephemeres','memoires_developpement','memoires_experience','memoires_lecon','duree_slurm_min','pipeline_acheve','erreur_pipeline','tous_statuts_essais']
with (O/'DETAILS-FOREST.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for r in rows:
        w.writerow(dict(zip(fields,[r['case_id'],r['campaign'],r['job_id'],r['trees_selected'],'; '.join(f"{k}={v}" for k,v in r['trial_counts'].items() if k!='G'),r['trial_counts'].get('G',0),sum(r['trial_counts'].values()),r['trial_statuses'].get('valid',0),r['trial_statuses'].get('incorrect',0),r['trial_statuses'].get('generation_failed',0),r['trial_statuses'].get('infrastructure_error',0),r['invocation_count'],r['persistent_invocations'],r['ephemeral_invocations'],r['memory_records'].get('development',0),r['memory_records'].get('experiment',0),r['memory_records'].get('lesson',0),r['slurm_elapsed_seconds']/60 if r['slurm_elapsed_seconds'] is not None else None,r['pipeline_complete'],r['pipeline_error'],json.dumps(r['trial_statuses'],ensure_ascii=False)])))
print(json.dumps(summary,ensure_ascii=False))
for r in rows:print(r['campaign'],r['trees_selected'],dict(r['trial_counts']),'calls',r['invocation_count'],'memory',sum(r['memory_records'].values()),'minutes',round(r['slurm_elapsed_seconds']/60,1) if r['slurm_elapsed_seconds'] else None)
