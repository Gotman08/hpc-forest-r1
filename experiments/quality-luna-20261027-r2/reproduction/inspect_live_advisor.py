"""Read-only pilot diagnostics; no feedback to the active searches."""
import json
import sqlite3
from collections import Counter
from pathlib import Path

BASE = Path('/scratch_p/nimarano/forest-romeo-oauth-20261025-51ab9260')
ARMS = [
    ('gemm_cpu', 'quality-luna-20261027-gemm_cpu-corrected-1c309656', '42102f76204848619c967253ce63cda1'),
    ('blackscholes', 'quality-luna-20261027-blackscholes-corrected-e834d2fe', 'db46b75c7094463b9b9da23c0980dd8e'),
]

for case, block, arm in ARMS:
    path = BASE / block / ('forest-app-' + arm) / 'campaign/registry.sqlite3'
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=10)
    try:
        connection.execute('PRAGMA query_only=ON')
        rows = [json.loads(row[0]) for row in connection.execute(
            "SELECT payload FROM events WHERE kind='advisor_decision' ORDER BY id")]
    finally:
        connection.close()
    slim = [{key: row.get(key) for key in
             ('id', 'tree_id', 'status', 'called', 'reordered', 'validation', 'seconds')}
            | {'context_count': len(row.get('context_ids', []))} for row in rows]
    print(json.dumps({'case': case, 'decisions': len(rows),
                      'statuses': dict(Counter(row['status'] for row in rows)),
                      'reasons': dict(Counter(row.get('validation', {}).get('reason') for row in rows
                                              if row.get('validation', {}).get('reason'))),
                      'latest': slim[-8:]}, ensure_ascii=False))
