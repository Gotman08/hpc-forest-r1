import json,time
from pathlib import Path
r=Path(r'C:\Users\nicol\Documents\Codex\2026-10-23\ce-que-je-voudrais-que-tu\work\active-architecture-20261024-v5-reprise')
for case in ['volume','stencil_y_retry2']:
 pending=[]
 for p in (r/'campaigns'/case/'worker').glob('*/request.json'):
  if p.with_name('response.json').exists():continue
  q=json.loads(p.read_text(encoding='utf8'))
  pending.append({'age_seconds':round(time.time()-p.stat().st_mtime),'role':(q.get('active_control') or {}).get('kind') or q.get('role') or (q.get('conversation') or {}).get('phase') or 'research_or_memory','claimed':p.with_name('generation-claimed.json').exists()})
 print(json.dumps({'case':case,'pending':pending}))
