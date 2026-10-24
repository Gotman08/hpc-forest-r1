from pathlib import Path
import json
R=Path(__file__).resolve().parent;rows=[];env=[]
for key in ['aobench','volume','raytracer','deferred']:
    p=R/f'render-{key}-final-results.json'
    if not p.exists():continue
    complete=json.loads((R/f'render-{key}-final-complete.json').read_text())
    records=json.loads(p.read_text());assert len(records)==complete['records']
    assert all(r['case_id']==key for r in records)
    rows+=records;env.append(json.loads((R/f'render-{key}-final-environment.json').read_text()))
(R/'render-final-results.json').write_text(json.dumps(rows,indent=2))
(R/'render-final-environment.json').write_text(json.dumps(env,indent=2))
print(json.dumps({'cases':[e['cases'] for e in env],'records':len(rows),'failures':sum(r.get('measurement',{}).get('correct') is not True for r in rows)}))
