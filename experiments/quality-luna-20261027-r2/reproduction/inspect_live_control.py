"""Read-only control diagnostics; never provide feedback to active jobs."""
import json
import sqlite3
from collections import Counter
from pathlib import Path

BASE = Path('/scratch_p/nimarano/forest-romeo-oauth-20261025-51ab9260')
ROOT = BASE / 'quality-luna-20261027-gemm_cpu-off-5a207162/forest-app-334781e225e44132b43031f93d8f8d36'
db = sqlite3.connect((ROOT / 'campaign/registry.sqlite3').resolve().as_uri() + '?mode=ro', uri=True, timeout=10)
try:
    db.execute('PRAGMA query_only=ON')
    meta = {k: json.loads(v) for k, v in db.execute(
        "SELECT key, value FROM metadata WHERE key LIKE 'active_%' OR key LIKE 'research_scheduler:%'")}
    events = [{'id': i, 'kind': k, 'payload': json.loads(p), 'created': t} for i,k,p,t in db.execute(
        "SELECT id,kind,payload,created FROM events WHERE kind LIKE 'active_%' ORDER BY id DESC LIMIT 12")]
finally:
    db.close()
active = meta.get('active_forest:1', {})
jobs = [v for k,v in meta.items() if k.startswith('active_control:')]
latest = [{k:j.get(k) for k in ('id','kind','role','status','error','trigger')}
          | {'calls': len(j.get('calls', []))} for j in jobs[-10:]]
print(json.dumps({'jobs': dict(Counter((j['kind'] + ':' + j['status']) for j in jobs)),
                  'latest_jobs': latest, 'scheduler': meta.get('research_scheduler:1'),
                  'active_keys': list(active), 'suspended': active.get('suspended'),
                  'closed': active.get('closed'), 'events': events}, ensure_ascii=False))
