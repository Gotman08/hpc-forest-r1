from pathlib import Path
import json
import os
import platform
import subprocess
import sys
import time

R = Path(__file__).resolve().parent
gpu = sys.argv[1] == 'gpu'
assert platform.machine() == ('aarch64' if gpu else 'x86_64')
rows = []
out = R/('receipts-'+os.environ['SLURM_JOB_ID'])
out.mkdir()
for item in json.loads((R/'cases.json').read_text()):
    if item['gpu'] != gpu:
        continue
    key = item['case_id']
    folder = R/'cases'/key
    config = json.loads((folder/'validation/case.json').read_text())
    env = {**os.environ, 'FOREST_REFERENCE_SUITE': config['suite'],
           'FOREST_PYTHON': sys.executable,
           'FOREST_TORCH_PYTHON': '/scratch_p/nimarano/forest-reference-torch-20261023/bin/python',
           'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': str(config.get('threads', 4))}
    commands = [('make', ['make']), ('delivery', ['bash', 'run.sh']),
                ('protected-build', [sys.executable, str(folder/'validation/protocol.py'),
                                     'build', str(folder/'source'), str(folder/'build')]),
                ('protected-check', [sys.executable, str(folder/'validation/protocol.py'),
                                     'check', str(folder/'build/solution'), 'confirmation'])]
    for stage, command in commands:
        started = time.time()
        result = subprocess.run(command, cwd=folder/'source', env=env, capture_output=True,
                                text=True, timeout=1200)
        (out/(key+'-'+stage+'.log')).write_text(result.stdout+result.stderr)
        row = {'case': key, 'stage': stage, 'exit_code': result.returncode,
               'seconds': time.time()-started}
        rows.append(row)
        (out/'results.json').write_text(json.dumps(rows, indent=2))
        print(json.dumps(row), flush=True)
        if result.returncode:
            raise RuntimeError((key, stage, (result.stdout+result.stderr)[-2000:]))
(out/'complete.json').write_text(json.dumps({'ok': True, 'stages': len(rows)}))
