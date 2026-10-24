"""Prepare readable SLURM arguments; submission still uses ROMEO prepare/review/submit."""
import json
from pathlib import Path
import re
import shlex
import sys

R = Path(__file__).resolve().parent
stem = sys.argv[1]
assert re.fullmatch(r'paired-(cpu(?:-base64|-blackscholes-stability)?|extra|render-(aobench|deferred|raytracer|volume))', stem)
record = json.loads((R/(stem+'-transfer.json')).read_text(encoding='utf8'))
root = record['remote']
gpu = record['group'] == 'extra'
python = ('/scratch_p/nimarano/forest-reference-torch-20261023/bin/python' if gpu else
          '/scratch_p/nimarano/forest-reference-study-20261023-x64env/bin/python')
cuda = '/uxlsycgnldislqswr4gcj6hlc6u2pdxp'
compiler = cuda if gpu else '/fmrcj5jrubquulzxeqmhucxqunhodrxp'
lines = [
    'root='+shlex.quote(root),
    'test ! -e "$root"',
    'echo '+shlex.quote(record['sha256']+'  '+root+'.tar.gz')+' | sha256sum -c -',
    'mkdir "$root"',
    'tar -xzf "$root.tar.gz" -C "$root"',
    'export OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1',
]
if gpu:
    lines += ['cuda_prefix=$(spack location -i '+cuda+')',
              'export LD_LIBRARY_PATH="$cuda_prefix/lib64:$cuda_prefix/targets/sbsa-linux/lib:${LD_LIBRARY_PATH:-}"']
lines += ['cd "$root"', 'set +e', shlex.quote(python)+' -u compare.py', 'rc=$?']
if 'utf8' in record['keys']:
    lines += ['if [ "$rc" -eq 0 ]; then',
              '  '+shlex.quote(python)+' -u utf8_audit.py', '  rc=$?', 'fi']
lines += ['echo "$rc" > comparison-exit-code.txt',
          'tar -czf "$root.results.tar.gz" -C "$root" .', 'exit "$rc"']
args = {'arch': 'armgpu' if gpu else 'x64cpu', 'command': '\n'.join(lines),
        'cpus_per_task': 1 if record['keys'] == ['base64'] else 4 if gpu or record['keys'] == ['deferred'] else 40,
        'gpus_per_node': int(gpu), 'mem_gb': 16,
        'name': 'forest-'+stem, 'time_limit': '02:00:00',
        'spack_packages': [compiler], 'workdir': '/scratch_p/nimarano'}
(R/(stem+'-job-arguments.json')).write_text(json.dumps(args, indent=2), encoding='utf8')
print(json.dumps(args))
