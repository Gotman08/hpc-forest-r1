"""Flatten numeric diagnostics and preserve links to the exact original logs."""
from collections import Counter
import json
from engine_study import ROOT,CONDITIONS,read,write
from engine_extract import table

def main():
    base=ROOT/'outputs/comparaison-moteurs'
    suites=[('interrupted',base),('shared-scp',base/'relance-controlee'),('atomic',base/'serie-atomique')]
    log_rows=[];case_rows=[];evaluations=[];selections=[];harness_rows=[];harness_missions=[]
    for series,folder in suites:
        for key in CONDITIONS:
            d=folder/'data'/key
            if not (d/'summary.json').exists():continue
            summary=read(d/'summary.json')
            for e in read(d/'evaluations.json'):
                p=e['payload']
                row={'series':series,'condition':key,'evaluation_id':e['id'],'experiment_id':e['experiment_id'],'phase':e['phase'],
                    'status':p.get('status'),'correct':p.get('correct'),'reason':p.get('reason'),'mean_seconds':p.get('mean_seconds'),
                    'created':e['created'],'elapsed_seconds':e['created']-summary['started'],'commit':p.get('commit'),'logs':p.get('logs')}
                evaluations.append(row)
            for selection in (summary.get('postprocess') or {}).get('selections',[]):
                selections.append({'series':series,'condition':key,**selection})
            for journal in sorted((folder/'evidence'/key/'logs').rglob('node-harness.json')):
                h=read(journal);attempts=h.get('attempts',[])
                common={'series':series,'condition':key,'mission_id':h['mission_id'],
                    'tree_id':h.get('tree_id'),'path':journal.relative_to(base).as_posix()}
                states=[a.get('state') for a in attempts]
                harness_missions.append({**common,'state':h.get('state'),'attempts':len(attempts),
                    'development_checks':h.get('development_checks'),
                    'outer_tree_reward_assigned':h.get('outer_tree_reward_assigned'),
                    'holdout_access':h.get('holdout_access'),
                    'development_passed':any(s=='development_passed' for s in states),
                    'passed_after_development_failure':'development_passed' in states and 'development_failed' in states,
                    'states':states})
                for a in attempts:
                    outcome=a.get('development_outcome') or {};proposal=a.get('proposal') or {}
                    harness_rows.append({**common,'attempt':a.get('attempt'),'generation_id':a.get('generation_id'),
                        'state':a.get('state'),'llm_calls':a.get('llm_calls'),'generation_error':a.get('generation_error'),
                        'source_digest_before_call':a.get('source_digest_before_call'),'source_digest':a.get('source_digest'),
                        'development_status':outcome.get('status'),'development_correct':outcome.get('correct'),
                        'development_reason':outcome.get('reason'),'development_commit':outcome.get('commit'),
                        'hypothesis':proposal.get('hypothesis'),'transformations':proposal.get('transformations'),
                        'diagnostics':a.get('measured_diagnostics')})
            for log in (folder/'evidence'/key/'logs').rglob('*.log'):
                payload=None
                for line in reversed(log.read_text(encoding='utf8',errors='replace').splitlines()):
                    try:payload=json.loads(line)
                    except ValueError:continue
                    if isinstance(payload,dict):break
                    payload=None
                if payload is None:continue
                rel=log.relative_to(base).as_posix()
                info={'series':series,'condition':key,'path':rel,'stage':log.stem,
                    'correct':payload.get('correct'),'case_count':payload.get('cases'),'seconds':payload.get('seconds'),
                    'error':payload.get('error') or payload.get('infrastructure_error'),'reason':payload.get('reason')}
                log_rows.append(info)
                for detail in payload.get('details',[]):
                    if isinstance(detail,dict):case_rows.append({'series':series,'condition':key,'path':rel,'stage':log.stem,**detail})
    for name,rows in [('diagnostics-evaluations',evaluations),('diagnostics-journaux',log_rows),('diagnostics-cas',case_rows),('diagnostics-selections',selections),('diagnostics-tentatives-locales',harness_rows),('diagnostics-missions-locales',harness_missions)]:
        write(base/'data'/(name+'.json'),rows)
        table(base/'tables'/(name+'.csv'),rows)
    summary={'evaluations':len(evaluations),'json_logs':len(log_rows),'numeric_case_results':len(case_rows),'selection_decisions':len(selections),
        'local_harness_missions':len(harness_missions),'local_harness_attempts':len(harness_rows),
        'local_attempt_states':{s:dict(Counter(r['state'] for r in harness_rows if r['series']==s)) for s,_ in suites},
        'local_missions_passed_after_failure':{s:sum(r['passed_after_development_failure'] for r in harness_missions if r['series']==s) for s,_ in suites},
        'failed_cases':[r for r in case_rows if r.get('ok') is False],
        'evaluation_statuses':{s:dict(Counter(r['status'] for r in evaluations if r['series']==s)) for s,_ in suites}}
    write(base/'data/diagnostics-summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='failed_cases'},ensure_ascii=True))

if __name__=='__main__':main()
