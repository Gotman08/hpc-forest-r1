"""Read-only timing decomposition of the completed campaign."""
import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
with sqlite3.connect((HERE / 'evidence/registry.sqlite3').as_uri() + '?mode=ro&immutable=1', uri=True) as con:
    meta = {k: json.loads(v) for k, v in con.execute('SELECT key,value FROM metadata')}
    events = [{'kind': k, 'payload': json.loads(p), 'at': t} for k, p, t in con.execute(
        "SELECT kind,payload,created FROM events WHERE kind LIKE '%budget%' OR kind LIKE '%admission%' ORDER BY id")]
result = json.loads((HERE / 'evidence/results.json').read_text())
started = meta['started']
closed = meta['search_closed:1']
assembly = meta['mother_assembly_started:1']
finished = result['timing']['finished_at']
summary = {'target_seconds': meta['config']['budget']['wall_seconds'],
           'actual_seconds': finished - started, 'unused_seconds': meta['deadline'] - finished,
           'research_closure_seconds': closed - started, 'assembly_started_seconds': assembly - started,
           'postprocess_seconds': result['timing']['samples']['postprocess'][-1],
           'confirmation_seconds': result['timing']['samples']['confirmation'][-1],
           'archive_seconds': result['timing']['samples']['archive'][-1],
           'remaining_at_closure': meta['deadline'] - closed, 'events': events}
(HERE / 'timing-audit.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf8')
print(json.dumps({k: v for k, v in summary.items() if k != 'events'}))
print(json.dumps({'last_budget_events': events[-5:]}))
