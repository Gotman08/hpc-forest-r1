"""Describe improvements over elapsed search time; never replace paired speedups."""
import collections
import datetime
import json
import sqlite3
import sys
from pathlib import Path

R = Path(__file__).resolve().parent
O = R.parents[1] / 'outputs/comparaison-reprises'
partial = '--partial' in sys.argv
rows = []
for folder in sorted((R / 'campaigns').iterdir()):
    paths = list(folder.glob('results/results-*/results.json'))
    if not paths:
        assert partial, folder.name
        continue
    d = json.loads(paths[0].read_text(encoding='utf8'))
    db = next(paths[0].parent.glob('reference-*/registry.sqlite3')).resolve()
    con = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    started = json.loads(con.execute('SELECT value FROM metadata WHERE key=?', ('started',)).fetchone()[0])
    baseline = json.loads(con.execute('SELECT payload FROM evaluations WHERE experiment_id=? ORDER BY created LIMIT 1', ('baseline-e1',)).fetchone()[0])['mean_seconds']
    settled = {}
    for e in con.execute('SELECT payload FROM events WHERE kind=?', ('research_node_settled',)):
        v = json.loads(e['payload'])
        settled[v['experiment_id']] = v['settled_at']
    trials = []
    for t in con.execute('SELECT id,role,mission,result,created FROM trials ORDER BY created,id'):
        if t['role'] == 'G':
            continue
        m, v = json.loads(t['mission']), json.loads(t['result'] or '{}')
        end = settled.get(t['id'])
        assert end is not None, (folder.name, t['id'])
        valid = v.get('correct') is True and v.get('status') == 'valid'
        trials.append({'id': t['id'], 'role': t['role'], 'depth': m['depth'],
                       'submitted_minute': (t['created'] - started) / 60,
                       'settled_minute': (end - started) / 60,
                       'status': v.get('status'), 'commit': v.get('commit'),
                       'search_speedup': baseline / v['mean_seconds'] if valid else None})
    trials.sort(key=lambda t: t['settled_minute'])
    best, records = 1.0, []
    for t in trials:
        value = t['search_speedup']
        if value is not None and value > best:
            best = value
            records.append(t)
    valid_trials = [t for t in trials if t['search_speedup'] is not None]
    first30 = [t for t in trials if t['settled_minute'] <= 30]
    best30 = max([1.0] + [t['search_speedup'] for t in first30 if t['search_speedup'] is not None])
    selected = d.get('best_confirmed') or {}
    matches = [t for t in trials if t['commit'] and t['commit'] == selected.get('commit')]
    g = d.get('final_g_confirmation') or {}
    rows.append({'case_id': folder.name, 'job_id': d['job_id'],
                 'search_trials': len(trials), 'search_statuses': dict(collections.Counter(t['status'] for t in trials)),
                 'completed_trials_at_30_min': len(first30),
                 'valid_trials_at_30_min': sum(t['search_speedup'] is not None for t in first30),
                 'first_valid_minute': valid_trials[0]['settled_minute'] if valid_trials else None,
                 'last_search_settled_minute': trials[-1]['settled_minute'] if trials else None,
                 'best_search_speedup_at_30_min': best30,
                 'best_search_speedup_final': best,
                 'late_best_search_ratio': best / best30,
                 'improvement_events': records,
                 'selected_first_submitted_minute': min((t['submitted_minute'] for t in matches), default=None),
                 'selected_search_trial_ids': [t['id'] for t in matches],
                 'selected_commit': selected.get('commit'),
                 'confirmed_speedup': selected.get('reference_seconds', 0) / selected['mean_seconds'] if selected.get('mean_seconds') else None,
                 'G_commit_identical_to_selected': (g.get('outcome') or {}).get('commit') == selected.get('commit'),
                 'trials_by_settlement': trials})
    con.close()

assert partial or len(rows) == 14
out = {'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'note': 'These are the same new campaigns observed at 30 minutes and at the end, not independent equal-budget searches. Search speedups use the campaign objective and baseline, may be noisy, and are not the final paired documentary speedups. The baseline (speedup 1) is included when no improvement is observed. G is excluded from the search curve and remains separately confirmed.',
       'campaigns': rows}
dest = R / 'search-progress-preview.json' if partial else O / 'PROGRESSION-RECHERCHE.json'
dest.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf8')
print(json.dumps([{k: v for k, v in r.items() if k not in {'trials_by_settlement', 'improvement_events'}} for r in rows], ensure_ascii=False))
