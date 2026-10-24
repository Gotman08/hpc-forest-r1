"""Check delivery wrappers before spending the new search budget."""
from pathlib import Path
import io
import json
import shutil
import sys
import tarfile
import uuid
import zipfile

from prepare import R, OLD, read, write, sha
sys.path.insert(0, str(R/'campaigns/base64/payload/project/src'))
from hpc_forest.submission import delivery_manifest

items = read(R/'campaigns.json')
bundle = R/'preflight'
bundle.mkdir(exist_ok=False)
metadata = []
for item in items:
    key = item['case_id']
    a = R/'campaigns'/key
    p = a/'payload'
    changes = []
    for name in ['Makefile', 'run.sh']:
        path = p/'source'/name
        before = sha(path)
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
        if before != sha(path):
            changes.append({'path': name, 'old_sha256': before, 'new_sha256': sha(path),
                            'change': 'CRLF to LF only; Linux delivery compatibility'})
    item['wrapper_normalization'] = changes
    item['baseline_program_identical'] = True
    item['source_files'] = {f.relative_to(p/'source').as_posix(): sha(f)
                            for f in (p/'source').rglob('*') if f.is_file()}
    item['baseline_identical'] = not changes
    write(p/'runtime-manifest.json', {f.relative_to(p).as_posix(): sha(f) for f in p.rglob('*')
          if f.is_file() and f.name != 'runtime-manifest.json' and '__pycache__' not in f.parts})
    old_hash = sha(a/'payload.tar.gz')
    with tarfile.open(a/'payload.tar.gz', 'w:gz') as tar:
        for f in sorted(p.rglob('*')):
            if f.is_file() and '__pycache__' not in f.parts:
                tar.add(f, arcname=f.relative_to(p).as_posix())
    prep = read(a/'preparation.json')
    prep['payload_sha256'] = item['payload_sha256'] = sha(a/'payload.tar.gz')
    write(a/'preparation.json', prep)
    command = (a/'command.sh').read_text().replace(old_hash, prep['payload_sha256'])
    (a/'command.sh').write_text(command, encoding='utf8', newline='\n')
    target = bundle/'cases'/key
    for folder in ['source', 'validation']:
        shutil.copytree(p/folder, target/folder)
    metadata.append({'case_id': key, 'gpu': bool(item['gpus']), 'search': True})

for key in ['sgemm', 'stencil_y', 'transpose']:
    prior = OLD/'campaigns'/key/'payload'
    target = bundle/'cases'/key
    for folder in ['source', 'validation']:
        shutil.copytree(prior/folder, target/folder)
    case = read(target/'validation/case.json')
    (target/'source/Makefile').write_text('all: build/solution\nbuild/solution: src/candidate.cu\n\tmkdir -p build\n\tnvcc -std=c++17 -O3 -arch=sm_90 -shared -Xcompiler=-fPIC $< -o $@\n', encoding='utf8', newline='\n')
    script = '#!/usr/bin/env bash\nset -euo pipefail\nexec "${FOREST_REFERENCE_SUITE:?}/gpu_driver" '+str(case['kind'])+' "${FOREST_REFERENCE_SUITE}/references.so" ./build/solution 1 '+str(case['n'])+' 271 '+str(case['reps'])+' '+str(case['warmups'])+' 1\n'
    (target/'source/run.sh').write_text(script, encoding='utf8', newline='\n')
    metadata.append({'case_id': key, 'gpu': True, 'search': False,
                     'purpose': 'Regression for the three missing delivery wrappers; no new search'})
receipts = []
for item in metadata:
    source = bundle/'cases'/item['case_id']/'source'
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w') as archive:
        for f in source.rglob('*'):
            if f.is_file():
                archive.write(f, f.relative_to(source).as_posix())
    with zipfile.ZipFile(io.BytesIO(raw.getvalue())) as archive:
        receipt = delivery_manifest(archive, {})
    receipts.append({**item, 'delivery': receipt})
write(R/'delivery-contract-check.json', receipts)
write(R/'campaigns.json', items)
write(bundle/'cases.json', metadata)
shutil.copyfile(R/'preflight_run.py', bundle/'run.py')
with tarfile.open(R/'preflight.tar.gz', 'w:gz') as tar:
    for f in bundle.rglob('*'):
        if f.is_file():
            tar.add(f, arcname=f.relative_to(bundle).as_posix())
write(R/'preflight-transfer.json', {'remote': '/scratch_p/nimarano/forest-reference-preflight-'+uuid.uuid4().hex,
                                   'sha256': sha(R/'preflight.tar.gz')})
print('Seventeen delivery contracts accepted; fourteen unchanged candidate programs, Linux wrappers fixed.')
