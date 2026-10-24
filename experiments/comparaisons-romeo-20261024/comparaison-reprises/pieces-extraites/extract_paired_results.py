"""Validate completed comparison receipts and copy raw measurement records."""
from pathlib import Path
import json
import shutil
import sys
import tarfile

R = Path(__file__).resolve().parent
stem = sys.argv[1]
root = R/(stem+'-results')
root.mkdir(exist_ok=False)
with tarfile.open(R/(stem+'-results.tar.gz')) as archive:
    archive.extractall(root, filter='data')
exit_code = (root/'comparison-exit-code.txt').read_text().strip()
assert exit_code == '0', (stem, exit_code)
measurements = list(root.glob('measurements-*'))
assert len(measurements) == 1
folder = measurements[0]
complete = json.loads((folder/'complete.json').read_text())
records = json.loads((folder/'results.json').read_text())
assert complete['records'] == len(records) and records
for name in ['results', 'environment', 'complete']:
    shutil.copyfile(folder/(name+'.json'), R/(stem+'-'+name+'.json'))
if (folder/'utf8-audit.json').exists():
    shutil.copyfile(folder/'utf8-audit.json', R/(stem+'-utf8-audit.json'))
print(stem, len(records), 'completed raw measurement records')
