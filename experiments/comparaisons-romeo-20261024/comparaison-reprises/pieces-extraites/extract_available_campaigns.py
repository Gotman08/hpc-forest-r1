"""Extract verified completed archives and summarize controller outcomes without altering them."""
from pathlib import Path
import collections
import hashlib
import json
import tarfile

R = Path(__file__).resolve().parent
rows = []
for root in sorted((R/'campaigns').iterdir()):
    archive = root/'results.tar.gz'
    if not archive.exists():
        continue
    receipts = [root/'final-transfer.json', root/'transfer-result.json']
    receipt_file = next((p for p in receipts if p.exists()), None)
    if receipt_file:
        receipt = json.loads(receipt_file.read_text(encoding='utf8'))
        expected = receipt.get('remote_sha256',receipt.get('empreinte_distante'))
        if expected:
            assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected, root.name
    if not (root/'results').exists():
        with tarfile.open(archive) as stream:
            stream.extractall(root/'results', filter='data')
    files = list(root.glob('results/results-*/results.json'))
    assert len(files) == 1, (root.name, files)
    d = json.loads(files[0].read_text(encoding='utf8'))
    trials = d.get('trials',[])
    statuses = collections.Counter(json.loads(t.get('result') or '{}').get('status',t.get('state')) for t in trials)
    roles = collections.Counter(t['role'] for t in trials)
    row = {'case': root.name, 'job': d['job_id'], 'pipeline_complete': d.get('pipeline_complete'),
           'pipeline_error': d.get('error'), 'final_G_status': (d.get('final_g_confirmation') or {}).get('status'),
           'trials': len(trials), 'per_tree': dict(roles), 'statuses': dict(statuses),
           'selected_commit': (d.get('best_confirmed') or {}).get('commit')}
    rows.append(row)
    print(json.dumps(row), flush=True)
(R/'completed-campaign-summary.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
