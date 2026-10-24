"""Export every recorded old/new trial without deserializing TreeQuest pickle states."""
from pathlib import Path
import csv
import datetime
import json
import sqlite3

R = Path(__file__).resolve().parent
O = R.parents[1]/'outputs/comparaison-reprises'
plans = json.loads((R/'campaigns.json').read_text(encoding='utf8'))
rows = []


def utc(t):
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).isoformat() if t is not None else None


for plan in plans:
    key = plan['case_id']
    for period, folder in [('Ancien', R.parent/'reference-study/campaigns'/('deferred_r2' if key == 'deferred' else key)),
                           ('Nouveau', R/'campaigns'/key)]:
        result = next(folder.glob('results/results-*/results.json'))
        job = json.loads(result.read_text(encoding='utf8'))['job_id']
        db = next(result.parent.glob('reference-*/registry.sqlite3')).resolve()
        c = sqlite3.connect(db.as_uri()+'?mode=ro', uri=True)
        c.row_factory = sqlite3.Row
        start = json.loads(c.execute('SELECT value FROM metadata WHERE key=?', ('started',)).fetchone()[0])
        baseline = json.loads(c.execute('SELECT payload FROM evaluations WHERE experiment_id=? ORDER BY created LIMIT 1', ('baseline-e1',)).fetchone()[0])
        baseline_seconds = baseline['mean_seconds']
        settled = {}
        for e in c.execute('SELECT payload FROM events WHERE kind=?', ('research_node_settled',)):
            event = json.loads(e['payload'])
            settled[event['experiment_id']] = event['settled_at']
        for ordinal, trial in enumerate(c.execute('SELECT id,role,state,mission,result,created FROM trials ORDER BY created,id'), 1):
            mission = json.loads(trial['mission'])
            outcome = json.loads(trial['result'] or '{}')
            valid = outcome.get('status') == 'valid' and outcome.get('correct') is True
            ended = settled.get(trial['id'])
            if ended is None:
                found = c.execute('SELECT MAX(created) FROM evaluations WHERE experiment_id=?', (trial['id'],)).fetchone()[0]
                ended = found
            row = {'case_id': key, 'period': period, 'job': job, 'ordinal': ordinal,
                   'role': trial['role'], 'id': trial['id'], 'depth': mission['depth'],
                   'parent_id': mission['parent_id'], 'phase': mission['budget_phase'],
                   'status': outcome.get('status', trial['state']), 'correct': outcome.get('correct'),
                   'mean_seconds': outcome.get('mean_seconds') if valid else None,
                   'baseline_seconds': baseline_seconds,
                   'search_speedup': baseline_seconds/outcome['mean_seconds'] if valid else None,
                   'score': outcome.get('score'), 'commit': outcome.get('commit'),
                   'submitted_utc': utc(trial['created']), 'settled_utc': utc(ended),
                   'submitted_minute': (trial['created']-start)/60,
                   'settled_minute': (ended-start)/60 if ended is not None else None,
                   'hypothesis': mission['hypothesis'], 'transformations': mission['transformations'],
                   'reason': outcome.get('reason'), 'source_commits': mission['source_commits']}
            rows.append(row)
        c.close()
output = {'note': 'Search objective speedups use each campaign baseline and its protected multiconfiguration objective. They are diagnostics, not the final paired documentary speedups.', 'trials': rows}
(O/'ESSAIS-FOREST.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf8')
with (O/'ESSAIS-FOREST.csv').open('w', encoding='utf-8-sig', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in r.items()} for r in rows)
print(json.dumps({'trials': len(rows), 'new': sum(r['period'] == 'Nouveau' for r in rows)}))
