"""Compact, read-only relay observations; no execution-speed claims."""
from pathlib import Path
import collections
import datetime
import json
import time

R=Path(__file__).resolve().parent
def read(p):
    try:return json.loads(p.read_text(encoding='utf8'))
    except (OSError,ValueError):return {}

rows=[]
for root in sorted((R/'campaigns').iterdir()):
    job=read(root/'job.json')
    if not job:continue
    reqs=[read(p) for p in (root/'worker').glob('*/request.json')]
    res=[read(p) for p in (root/'worker').glob('*/response.json')]
    trees=read(root/'worker/forest-plan.json').get('children',[])
    done=read(root/'worker-finished.json')
    rows.append({'case':root.name,'minutes':round((time.time()-job['started'])/60,1),
      'requests':len(reqs),'responses':len(res),
      'proposals':sum(bool((r.get('data') or {}).get('files')) for r in res),
      'trees':len(trees),'phases':dict(collections.Counter(str(r.get('budget_phase')) for r in reqs)),
      'errors':[{'error':r.get('error'),'infrastructure':r.get('infrastructure_error')} for r in res if r.get('error')],
      'relay_failure':read(root/'relay-failure.json'),'finished':done})
snapshot={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'rows':rows}
with (R/'relay-observations.jsonl').open('a',encoding='utf8') as out:
    out.write(json.dumps(snapshot,ensure_ascii=False)+'\n')
print(json.dumps({'utc':snapshot['utc'],'elapsed_min':[min(r['minutes'] for r in rows),max(r['minutes'] for r in rows)],
  'requests':sum(r['requests'] for r in rows),'responses':sum(r['responses'] for r in rows),
  'proposals':sum(r['proposals'] for r in rows),'trees':sum(r['trees'] for r in rows),
  'finished':[r['case'] for r in rows if r['finished']],
  'errors':{r['case']:r['errors'] for r in rows if r['errors']},
  'relay_failures':{r['case']:r['relay_failure'] for r in rows if r['relay_failure']},
  'phases':{r['case']:r['phases'] for r in rows if set(r['phases'])-{'search'}}},ensure_ascii=False))
