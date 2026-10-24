"""Summarize relay transport observations separately from experiment outcomes."""
from pathlib import Path
import collections
import datetime
import json

R=Path(__file__).resolve().parent
O=R.parents[1]/'outputs/comparaison-reprises'
roots=[]
for phase,folder in [('interrupted_context12000',R/'attempt-context12000/campaigns'),
                     ('superseded_output_limit',R/'attempt-output-limit'),
                     ('final_context64000',R/'campaigns')]:
    for path in folder.glob('*/plan.json'):
        plan=json.loads(path.read_text(encoding='utf8'))
        roots.append((plan['remote_root'],phase,path.parent.name))
groups=collections.defaultdict(lambda:{'operations':0,'failures':0,'tools':collections.Counter(),
                                    'seconds':0.0,'queue_seconds':0.0,'first':None,'last':None})
failed=[];successes=collections.defaultdict(list);lines=0;invalid=0
for line in (R/'broker/operations.jsonl').read_text(encoding='utf8').splitlines():
    lines+=1
    try:item=json.loads(line)
    except ValueError:
        invalid+=1
        continue
    remote=item.get('remote_path') or ''
    owner=next(((phase,case) for root,phase,case in roots
                if remote==root or remote.startswith(root+'/') or remote.startswith(root+'.')),('other','other'))
    group=groups[owner];group['operations']+=1
    group['tools'][item['tool']]+=1
    group['seconds']+=item.get('seconds',0)
    group['queue_seconds']+=item.get('queue_seconds',0)
    t=item['started'];group['first']=min(group['first'] or t,t);group['last']=max(group['last'] or t,t)
    identity=(item['tool'],remote)
    if item.get('ok') is True:
        successes[identity].append(t)
    else:
        group['failures']+=1
        failed.append({'phase':owner[0],'case_id':owner[1],'tool':item['tool'],
                       'started':t,'remote_path':remote,'error':item.get('error')})
for item in failed:
    item['later_success_for_same_tool_and_path']=any(t>item['started'] for t in successes[(item['tool'],item['remote_path'])])
rows=[{'phase':phase,'case_id':case,**value,'tools':dict(value['tools'])} for (phase,case),value in sorted(groups.items())]
assert sum(r['operations'] for r in rows)+invalid==lines
output={'scope':'Owned campaign relays only; direct MCP preparation, comparison and transfer calls are outside this log.',
        'interpretation':'An unsuccessful transport operation is not automatically a failed experiment. A later successful call for the same tool/path is reported separately and is not proof that every earlier operation was replayed identically.',
        'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'operations':lines-invalid,'invalid_log_lines':invalid,'failed_operations':len(failed),
        'campaigns':rows,'failures':failed}
(O/'AUDIT-TRANSPORT.json').write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps({k:output[k] for k in ['operations','invalid_log_lines','failed_operations']}))
