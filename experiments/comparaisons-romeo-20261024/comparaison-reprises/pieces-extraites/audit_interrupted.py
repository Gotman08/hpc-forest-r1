"""Audit the preserved attempt stopped for insufficient source context."""
from pathlib import Path
import collections
import json
import sqlite3
import tarfile
from prepare import R, read, write, sha

attempt = R/'attempt-context12000'
efficiency = {r['job_id']: r for r in read(attempt/'job-efficiency.json')}
rows = []
for folder in sorted((attempt/'campaigns').iterdir()):
    if not folder.is_dir():
        continue
    selected = folder/'snapshot'
    selected.mkdir(exist_ok=True)
    wanted = {'registry.sqlite3', 'registry.sqlite3-wal', 'registry.sqlite3-shm',
              'progress.json', 'fresh-memory.json', 'allocation.json', 'results.json'}
    with tarfile.open(folder/'interrupted.tar.gz') as archive:
        members = [m for m in archive.getmembers() if m.isfile() and Path(m.name).name in wanted]
        archive.extractall(selected, members=members, filter='data')
    db = next(selected.glob('results-*/reference-*/registry.sqlite3')).resolve()
    c = sqlite3.connect(db.as_uri()+'?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    meta = {r['key']: json.loads(r['value']) for r in c.execute('SELECT * FROM metadata')}
    plan = read(folder/'plan.json')
    job = read(folder/'job.json')['job_id']
    trials = []
    for t in c.execute('SELECT id,role,state,mission,result,created FROM trials ORDER BY created,id'):
        m = json.loads(t['mission'])
        outcome = json.loads(t['result'] or '{}')
        trials.append({'id': t['id'], 'role': t['role'], 'state': t['state'],
                       'status': outcome.get('status', 'interrupted_pending'),
                       'depth': m['depth'], 'parent_id': m['parent_id'], 'created': t['created'],
                       'mean_seconds': outcome.get('mean_seconds'), 'reason': outcome.get('reason')})
    fp = meta.get('forest_plan:1') or {}
    rows.append({'case_id': folder.name, 'job_id': job, 'session_id': plan['session_id'],
                 'status': 'operator_interrupted_for_context_configuration',
                 'context_characters': 12000, 'elapsed_seconds': efficiency[job]['elapsed_seconds'],
                 'tree_count': len(fp.get('children', [])), 'tree_plan': fp,
                 'trials': trials, 'trial_statuses': dict(collections.Counter(t['status'] for t in trials)),
                 'trial_counts': dict(collections.Counter(t['role'] for t in trials)),
                 'archive_sha256': sha(folder/'interrupted.tar.gz'),
                 'initial_memory': read(next(selected.glob('results-*/fresh-memory.json'))),
                 'used_as_final_speedup': False})
    c.close()
assert len(rows) == 14
output = {'reason': 'Uniform restart after source paging exceeded the ephemeral-call history window. Current-source capacity increased from 12000 to 64000 characters, without importing optimized code or past memory.',
          'campaigns': rows, 'final_results': False}
write(R.parents[1]/'outputs/comparaison-reprises/TENTATIVE-INTERROMPUE.json', output)
print(json.dumps({'campaigns': len(rows), 'registered_trials': sum(len(r['trials']) for r in rows),
                  'statuses': dict(sum((collections.Counter(r['trial_statuses']) for r in rows), collections.Counter()))}))
