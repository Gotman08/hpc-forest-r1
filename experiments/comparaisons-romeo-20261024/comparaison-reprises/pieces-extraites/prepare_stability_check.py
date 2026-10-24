"""Freeze an additional Black-Scholes check after observing unstable 40-core timings."""
import hashlib
import json
import shutil
import tarfile
import uuid
from pathlib import Path

R = Path(__file__).resolve().parent
stem = 'paired-cpu-blackscholes-stability'
src, dest = R / 'paired-cpu', R / stem
dest.mkdir(exist_ok=False)
manifest = [r for r in json.loads((src / 'manifest.json').read_text()) if r['case_id'] == 'blackscholes']
assert len(manifest) == 4
shutil.copytree(src / 'blackscholes', dest / 'blackscholes')
shutil.copyfile(src / 'suite-snapshot.json', dest / 'suite-snapshot.json')
script = (src / 'compare.py').read_text(encoding='utf8')
assert script.count('for block in range(7):') == 1
script = script.replace('for block in range(7):', 'for block in range(21):')
(dest / 'compare.py').write_text(script, encoding='utf8', newline='\n')
(dest / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
note = {'purpose': 'Additional stability check triggered by wide old/new ratios at 40 cores in primary job 781608.',
        'primary_results_preserved': True, 'candidate_changes': False,
        'changes_from_primary': ['Only Black-Scholes', '21 blocks instead of 7; same input-size configurations, compiler, protected drivers and seed rule'],
        'selection_rule': 'Do not replace the primary comparison or select a different winner from these measurements.'}
(dest / 'stability-protocol.json').write_text(json.dumps(note, indent=2), encoding='utf8')
archive_path = R / (stem + '.tar.gz')
with tarfile.open(archive_path, 'w:gz') as archive:
    for p in dest.rglob('*'):
        if p.is_file():
            archive.add(p, arcname=p.relative_to(dest).as_posix())
transfer = {'group': 'cpu', 'keys': ['blackscholes'], 'artifact': str(archive_path),
            'remote': '/scratch_p/nimarano/forest-reference-' + stem + '-' + uuid.uuid4().hex,
            'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest()}
(R / (stem + '-transfer.json')).write_text(json.dumps(transfer, indent=2), encoding='utf8')
print(json.dumps(transfer))
