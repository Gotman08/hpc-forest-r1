"""Keep the prematurely stopped Base64 campaign distinct from final comparisons."""
import collections
import json
import tarfile
from pathlib import Path

from prepare import R, read, write, sha

root=R/'attempt-output-limit/base64'
if not (root/'results').exists():
    with tarfile.open(root/'results.tar.gz') as archive:
        archive.extractall(root/'results',filter='data')
p=next(root.glob('results/results-*/results.json'));d=read(p)
trials=[{**t,'mission':json.loads(t['mission']),'result':json.loads(t['result'] or '{}')} for t in d['trials']]
failures=[{'id':t['id'],'role':t['role'],'status':t['result'].get('status'),
           'reason':t['result'].get('reason')} for t in trials if t['result'].get('status')!='valid']
out={'campaign':'base64','job_id':d['job_id'],'session_id':d['session_id'],
     'used_as_final_speedup':False,'pipeline_complete':d['pipeline_complete'],
     'reason_superseded':'A native max_output_tokens failure was misclassified as infrastructure and ended research early. A new empty-memory campaign uses the corrected classification.',
     'context_characters':64000,'target_seconds':d['target_seconds'],
     'timing':d.get('timing'),'search_status':d.get('search',{}).get('status'),
     'research_scheduler':d.get('research_scheduler'),'forest_plan':d.get('forest_plan'),
     'trial_count':len(trials),'trial_statuses':dict(collections.Counter(t['result'].get('status') for t in trials)),
     'failures':failures,'results_sha256':sha(p),'archive_sha256':sha(root/'results.tar.gz'),
     'historical_statuses_unchanged':True}
write(R.parents[1]/'outputs/comparaison-reprises/TENTATIVE-BASE64-LIMITE.json',out)
print(json.dumps({k:out[k] for k in ['job_id','pipeline_complete','trial_count','trial_statuses','search_status']}))
