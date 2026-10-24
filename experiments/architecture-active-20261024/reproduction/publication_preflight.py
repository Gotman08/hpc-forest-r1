"""Estimate public archive sizes without copying private runtime directories."""
import json
import tarfile
from pathlib import Path, PurePosixPath
from archive import policy, R, ROOT

rows = []
for path in (ROOT / 'outputs/architecture-active').glob('*'):
    if path.is_file():
        rows.append({'source': str(path), 'bytes': path.stat().st_size})
for version in [R, *[R.parent / name for name in
    ['active-architecture-20261024', 'active-architecture-20261024-v2',
     'active-architecture-20261024-v3', 'active-architecture-20261024-v4',
     'active-architecture-20261024-v5']]]:
    for folder in (version / 'campaigns').glob('*'):
        bundle = folder / 'results.tar.gz'
        if not bundle.exists():
            continue
        with tarfile.open(bundle) as archive:
            for member in archive:
                if not member.isfile() or policy.path_reason(member.name):
                    continue
                if {'repo', 'worktrees', 'mailbox', 'deliverables'} & set(PurePosixPath(member.name).parts):
                    continue
                rows.append({'source': str(bundle) + '!' + member.name, 'bytes': member.size})
result = {'scope': 'Output files and eligible archive members; Git source history and comparison directories are additional.',
          'files': len(rows), 'bytes': sum(r['bytes'] for r in rows),
          'largest': sorted(rows, key=lambda r: r['bytes'], reverse=True)[:10],
          'over_50_mib': [r for r in rows if r['bytes'] > 50 * 1024**2]}
(R / 'publication-preflight.json').write_text(json.dumps(result, indent=2), encoding='utf8')
print(json.dumps(result))
