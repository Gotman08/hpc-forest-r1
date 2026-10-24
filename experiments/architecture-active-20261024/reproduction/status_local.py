"""Read bounded local transport metadata; never expose native prompts or tokens."""
import collections
import json
from pathlib import Path

R = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


for directory in sorted((R/'campaigns').iterdir()):
    if not (directory/'job.json').exists():
        continue
    counts = collections.Counter()
    errors = []
    for path in (directory/'worker').glob('*/request.json'):
        request = read(path)
        role = request.get('role') or (request.get('active_control') or {}).get('kind') or 'planning_or_memory'
        completed = path.with_name('response.json').exists()
        counts[role+(':returned' if completed else ':pending')] += 1
        if completed:
            response = read(path.with_name('response.json'))
            if response.get('error'):
                errors.append(str(response['error'])[:300])
    print(json.dumps({'case':directory.name, 'job':read(directory/'job.json')['job_id'],
                      'calls':dict(counts), 'errors':errors[-3:]},ensure_ascii=False),flush=True)
