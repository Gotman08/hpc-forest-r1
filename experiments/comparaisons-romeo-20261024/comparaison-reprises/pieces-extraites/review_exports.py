"""Read-only provenance and diffs of the winners selected before paired timings."""
from pathlib import Path
import hashlib
import json
import subprocess

R = Path(__file__).resolve().parent
D = R / 'source-review'
D.mkdir(exist_ok=True)
rows = []
for root in sorted(R.glob('paired-*')):
    if not root.is_dir() or root.name.endswith(('-results', '-stability')) or not (root / 'manifest.json').exists():
        continue
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf8'))
    for key in sorted({m['case_id'] for m in manifest}):
        selected = {m['variant']: m for m in manifest if m['case_id'] == key}
        a = selected['old_selected']
        b = selected['new_selected']
        old = root / key / 'old_selected' / ('candidate' + a['suffix'])
        new = root / key / 'new_selected' / ('candidate' + b['suffix'])
        assert hashlib.sha256(old.read_bytes()).hexdigest() == a['sha256']
        assert hashlib.sha256(new.read_bytes()).hexdigest() == b['sha256']
        p = subprocess.run(['git', '-c', 'core.autocrlf=false', 'diff', '--no-index', '--', str(old), str(new)], capture_output=True)
        assert p.returncode in (0, 1), p.stderr.decode(errors='replace')
        (D / (key + '.diff')).write_bytes(p.stdout)
        row = {'case_id': key, 'old_commit': a['commit'], 'new_commit': b['commit'],
               'old_sha256': a['sha256'], 'new_sha256': b['sha256'],
               'identical_source': a['sha256'] == b['sha256'],
               'old_lines': len(old.read_bytes().splitlines()), 'new_lines': len(new.read_bytes().splitlines()),
               'diff': str((D / (key + '.diff')).relative_to(R)),
               'diff_sha256': hashlib.sha256(p.stdout).hexdigest(),
               'old_G_equals_selected': selected.get('old_g', {}).get('sha256') == a['sha256'],
               'new_G_equals_selected': selected.get('new_g', {}).get('sha256') == b['sha256']}
        rows.append(row)
(D / 'manifest.json').write_text(json.dumps(rows, indent=2), encoding='utf8')
print(json.dumps(rows, ensure_ascii=False))
