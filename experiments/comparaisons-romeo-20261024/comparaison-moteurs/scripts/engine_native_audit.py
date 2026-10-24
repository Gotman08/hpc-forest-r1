"""Audit final native calls, provenance, tool use and Mother continuity."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
from engine_study import ROOT, STUDY, OUT, CONDITIONS, read, write, sha
from engine_extract import table

def audit():
    all_calls=[]
    summaries=[]
    for key in CONDITIONS:
        artifact=STUDY/key
        auth=read(artifact/'authorization.json')
        calls=[]
        for request_path in sorted((artifact/'worker').glob('*/downloaded-request.json')):
            folder=request_path.parent
            req=read(request_path)
            assert req['session_id']==auth['session_id'] and req['model']=='gpt-6-luna' and req['reasoning_effort']=='max'
            claim=read(folder/'generation-claimed.json') if (folder/'generation-claimed.json').exists() else {}
            delivered=read(folder/'delivered.json') if (folder/'delivered.json').exists() else {}
            response=read(folder/'response.json') if (folder/'response.json').exists() else {}
            metrics=read(folder/'codex.jsonl.json') if (folder/'codex.jsonl.json').exists() else {}
            if response:
                assert response['request_sha256']==sha(request_path)
                assert response['session_id']==auth['session_id']
            if delivered:
                assert delivered['request_sha256']==sha(request_path)
                assert delivered['response_sha256']==sha(folder/'response.json')
            usage=response.get('usage',{})
            events=usage.get('events',[])
            token_names=['input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens']
            token_sum={'reported_'+name:sum(e.get(name,0) or 0 for e in events) for name in token_names}
            counter={name:events[-1].get(name,0) or 0 for name in token_names} if events else None
            native_thread_id=None
            if (folder/'codex.jsonl').exists():
                for line in (folder/'codex.jsonl').read_text(encoding='utf8',errors='replace').splitlines():
                    try:event=json.loads(line)
                    except ValueError:continue
                    if event.get('type')=='thread.started':native_thread_id=event.get('thread_id')
            convo=req.get('conversation') or {}
            skill=usage.get('model_skills') or {}
            role=skill.get('manifest',{}).get('role') or req.get('meta_role') or 'research'
            phase=convo.get('phase') or req.get('budget_phase')
            row={'condition':key,'job_id':auth['job_id'],'nonce':folder.name,'mission_id':req.get('mission_id'),
                'role':role,'phase':phase,'budget_phase':req.get('budget_phase'),'model':req['model'],'effort':req['reasoning_effort'],
                'started':claim.get('claimed_at'),'delivered':delivered.get('delivered_at'),
                'native_seconds':metrics.get('seconds'),'returncode':metrics.get('returncode'),'timed_out':metrics.get('timed_out'),
                'received':bool(response),'delivery_verified':bool(delivered),'infrastructure_error':response.get('infrastructure_error'),
                'error':response.get('error'),'usage_status':usage.get('status'),**token_sum,
                'native_thread_id':native_thread_id,'native_cumulative_usage':counter,
                'mcp_calls':len(usage.get('mcp_tool_calls',[])),'mcp_tools':dict(Counter(c['server']+'.'+c['tool'] for c in usage.get('mcp_tool_calls',[]))),
                'forbidden_tool_events':usage.get('forbidden_tool_events',[]),
                'conversation_id':convo.get('id'),'conversation_phase':convo.get('phase'),'conversation_turn':convo.get('turn'),
                'response_thread_id':(response.get('conversation') or {}).get('thread_id'),
                'request_sha256':sha(request_path),'response_sha256':sha(folder/'response.json') if response else None,
                'effective_instructions_sha256':skill.get('effective_instructions_sha256'),
                'project_skills':skill.get('manifest',{}).get('bundle_sha256')}
            calls.append(row)
        calls.sort(key=lambda r:r['started'] or 0)
        # Native turn.completed reports total_token_usage for the thread,
        # including earlier invocations after `exec resume`. Do not sum it twice.
        counters={}
        for row in calls:
            counter=row['native_cumulative_usage'];thread=row['native_thread_id'] or row['nonce']
            prior=counters.get(thread,{name:0 for name in token_names})
            if counter is None:
                row.update({name:0 for name in token_names})
                row['token_accounting']='unavailable'
                continue
            assert all(counter[name]>=prior[name] for name in token_names), 'Native token counter decreased: '+row['nonce']
            row.update({name:counter[name]-prior[name] for name in token_names})
            row['token_accounting']='difference_of_thread_totals' if thread in counters else 'first_observed_thread_total'
            counters[thread]=counter
        all_calls+=calls
        mother=[r for r in calls if r['conversation_id']]
        thread_ids=sorted(set(r['response_thread_id'] for r in mother if r['response_thread_id']))
        phases=Counter(r['phase'] for r in calls)
        summary={'condition':key,'job_id':auth['job_id'],'native_calls':len(calls),'phases':dict(phases),
            'native_seconds_sum_not_wall_time':sum(r['native_seconds'] or 0 for r in calls),
            'input_tokens':sum(r['input_tokens'] for r in calls),'cached_input_tokens':sum(r['cached_input_tokens'] for r in calls),
            'output_tokens':sum(r['output_tokens'] for r in calls),'reasoning_output_tokens':sum(r['reasoning_output_tokens'] for r in calls),
            'reported_input_tokens_sum':sum(r['reported_input_tokens'] for r in calls),
            'reported_output_tokens_sum':sum(r['reported_output_tokens'] for r in calls),
            'token_accounting':'Differences of native cumulative thread counters; raw reported values preserved separately',
            'calls_without_token_usage':sum(r['token_accounting']=='unavailable' for r in calls),
            'infrastructure_errors':sum(r['infrastructure_error'] is True for r in calls),
            'undelivered':sum(not r['delivery_verified'] for r in calls),'mcp_calls':sum(r['mcp_calls'] for r in calls),
            'mother_thread_ids':thread_ids,'one_mother_thread':len(thread_ids)==1,
            'forbidden_tools_observed':any(r['forbidden_tool_events'] for r in calls)}
        write(OUT/'data'/key/'native-calls.json',calls)
        write(OUT/'data'/key/'native-summary.json',summary)
        summaries.append(summary)
        # Full requests, public model outputs and transport diagnostics stay in
        # the evidence archive; report tables use only the measured fields above.
        dest=OUT/'native'/key
        shutil.copytree(artifact/'worker',dest,dirs_exist_ok=True,ignore=shutil.ignore_patterns('heartbeat-snapshots','worker.lock'))
        for name in ['relay.stdout.log','relay.stderr.log','relay-failure.json','relay-transfer-errors.jsonl','worker-finished.json','relay-exit.json']:
            if (artifact/name).exists():shutil.copyfile(artifact/name,dest/name)
    write(OUT/'data/native-calls.json',all_calls)
    write(OUT/'data/native-summary.json',summaries)
    table(OUT/'tables/native-calls.csv',all_calls)
    table(OUT/'tables/native-summary.csv',summaries)
    print(json.dumps(summaries,ensure_ascii=True))

if __name__=='__main__':audit()
