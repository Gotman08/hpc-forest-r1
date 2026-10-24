"""Freeze new active-architecture campaigns; never change earlier experiments."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import tarfile
import time
import uuid

R = Path(__file__).resolve().parent
ROOT = R.parents[1]
REPO = Path(r'C:\Users\nicol\Documents\Codex\2026-10-20\new-chat\outputs\hpc-forest-r1')
OLD = R.parent / 'reference-study'
LATEST = R.parent / 'reference-rerun'
SCOPE = 'active-architecture-luna-max-v5-reprise'
REQUEST = ('Implémenter complètement la nouvelle architecture Forest, puis relancer tous les tests '
           'des CSV sur ROMEO avec les mêmes entrées, comparer les résultats et les temps. '
           'GPT-6 Luna effort max pour tous les rôles, mémoire neuve par programme.')
GPU_INITIAL = {'sgemm', 'transpose', 'stencil_y'}
GPU_EXTRA = {'reduction', 's4convd', 'softmax', 'sumabs'}
RENDER = {'aobench', 'deferred', 'raytracer', 'volume'}
CASES = sorted({p.name for p in (OLD/'campaigns').iterdir() if p.is_dir()} - {'deferred_r2'})


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(path):
    return {p.relative_to(path).as_posix(): sha(p) for p in sorted(path.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def prepare(key, *, name=None, duration=None, mode='full', smoke=False):
    name = name or key
    a = R/'campaigns'/name
    if a.exists():
        raise RuntimeError('Prepared campaign already exists; never overwrite: '+str(a))
    prior = LATEST/'campaigns'/key
    if not prior.exists():
        prior = OLD/'campaigns'/key
    cfg = read(prior/'payload/settings.json')
    old_plan = read(prior/'plan.json')
    p = a/'payload'
    shutil.copytree(prior/'payload', p, ignore=shutil.ignore_patterns('project', '__pycache__', '*.pyc'))
    shutil.copytree(REPO/'src', p/'project/src', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    engine = inventory(p/'project/src')
    expected = read(R/'engine-files.json') if (R/'engine-files.json').exists() else engine
    if expected != engine:
        raise RuntimeError('Engine changed during this batch; use a new study directory')
    write(R/'engine-files.json', engine)
    session = uuid.uuid4().hex
    remote = '/scratch_p/nimarano/forest-active-'+name+'-'+session
    cfg['forest']['active'] = {'mode': mode, 'analysis_every': 1 if smoke else 3,
                              'analysis_calls': 2 if smoke else 3, 'steering_calls': 2 if smoke else 3,
                              'control_workers': 1, 'surprise_gain': 0.25}
    cfg['codex'].update(model='gpt-6-luna', reasoning_effort='max', session_id=session, mailbox_dir=remote+'/pending/mailbox')
    if duration is not None:
        cfg['budget']['wall_seconds'] = duration
    assert cfg['forest']['integration'] == 'memory-guided-v1'
    plan = copy.deepcopy(old_plan)
    plan.update(scope=SCOPE, session_id=session, remote_root=remote, created_at=time.time(),
                case_id=key, condition=name, wall_seconds=cfg['budget']['wall_seconds'],
                forest={k:v for k,v in cfg['forest'].items() if k != 'statement'}, memory=cfg['memory'],
                old_candidates_imported=False, fresh_memory=True, smoke_only=smoke,
                prior_campaign=str(prior), previous_job=read(prior/'job.json')['job_id'],
                previous_seconds=old_plan['wall_seconds'], engine_manifest_sha256=sha(R/'engine-files.json'))
    assert inventory(p/'source/src') == inventory(prior/'payload/source/src')
    assert inventory(p/'validation') == inventory(prior/'payload/validation')
    wrappers = []
    if key in GPU_INITIAL:
        case = read(p/'validation/case.json')
        if not (p/'source/Makefile').exists():
            (p/'source/Makefile').write_text('all: build/solution\nbuild/solution: src/candidate.cu\n\tmkdir -p build\n\tnvcc -std=c++17 -O3 -arch=sm_90 -shared -Xcompiler=-fPIC $< -o $@\n', encoding='utf8')
            wrappers.append('Makefile')
        if not (p/'source/run.sh').exists():
            (p/'source/run.sh').write_text('#!/usr/bin/env bash\nset -euo pipefail\nexec "${FOREST_REFERENCE_SUITE:?}/gpu_driver" '
                +str(case['kind'])+' "${FOREST_REFERENCE_SUITE:?}/references.so" ./build/solution 1 '
                +str(case['n'])+' 271 '+str(case['reps'])+' '+str(case['warmups'])+' 1\n', encoding='utf8')
            wrappers.append('run.sh')
    plan['delivery_wrappers_added'] = wrappers
    for filename, data in [('settings.json', cfg), ('plan.json', plan)]:
        write(p/filename, data)
        write(a/filename, data)
    shutil.copyfile(p/'statement.txt', a/'statement.txt')
    pilot = (p/'pilot.py').read_text(encoding='utf8')
    pilot = pilot.replace(old_plan['scope'], SCOPE)
    pilot = pilot.replace('"research_scheduler",', '"research_scheduler",\n                "active_architecture",')
    if "fresh-memory.json" not in pilot:
        anchor = 'controller.db.event("cuda_nbody_fresh_campaign", result)'
        assert anchor in pilot
        pilot = pilot.replace(anchor, '''fresh = {'session_id': plan['session_id'], 'trial_count': len(controller.db.rows('SELECT id FROM trials')),
                'document_count': len(controller.db.rows('SELECT * FROM documents')), 'previous_candidates_imported': False}
            if fresh['trial_count'] or fresh['document_count']:
                raise InfrastructureError('Fresh campaign unexpectedly contains prior research')
            atomic_json(output / 'fresh-memory.json', fresh)
            controller.db.event('active_fresh_campaign', fresh)''')
    (p/'pilot.py').write_text(pilot, encoding='utf8', newline='\n')
    write(p/'runtime-manifest.json', {name: value for name, value in inventory(p).items() if name != 'runtime-manifest.json'})
    with tarfile.open(a/'payload.tar.gz', 'w:gz') as archive:
        for f in sorted(p.rglob('*')):
            if f.is_file():
                archive.add(f, arcname=f.relative_to(p).as_posix())
    prep = {'condition': name, 'case_id': key, 'remote_root': remote, 'remote_payload': remote+'.tar.gz',
            'remote_results': remote+'.results.tar.gz', 'artifact': str(a), 'session_id': session,
            'model_mcp': False, 'payload_sha256': sha(a/'payload.tar.gz')}
    write(a/'preparation.json', prep)
    if (prior/'command.sh').exists():
        command = (prior/'command.sh').read_text().replace(old_plan['remote_root'], remote)
        command = command.replace(read(prior/'preparation.json')['payload_sha256'], prep['payload_sha256'])
    else:
        assert key in GPU_INITIAL
        driver = read(p/'validation/case.json')['suite']+'/gpu_driver'
        command = '\n'.join([
            'root='+remote, 'test ! -e "$root"',
            "echo '"+prep['payload_sha256']+'  '+remote+".tar.gz' | sha256sum -c -",
            'mkdir "$root"', 'tar -xzf "$root.tar.gz" -C "$root"',
            'export PYTHONPATH="$root/project/src" PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1',
            'export FOREST_REFERENCE_DRIVER='+driver, 'mkdir -p "$root/cache"',
            "echo '{\"architecture\":\"aarch64\",\"retained_protected_suite\":true}' > \"$root/cache/preflight.json\"",
            'lscpu > "$root/allocation-cpu.txt"', 'nvidia-smi -q > "$root/allocation-gpu.txt"',
            'cd "$root"', 'set +e',
            '/scratch_p/nimarano/hpc-forest-localmodels-20261015-r1/venv-r3/bin/python -u pilot.py --root "$root"',
            'rc=$?', 'echo "$rc" > engine-exit-code.txt',
            'tar -czf "$root.results.tar.gz" results-* allocation-cpu.txt allocation-gpu.txt engine-exit-code.txt', 'exit "$rc"', ''])
    if key in GPU_INITIAL:
        setup = '\n'.join([
            'FOREST_CUDA_PREFIX=$(spack location -i /uxlsycgnldislqswr4gcj6hlc6u2pdxp)',
            'test -f "$FOREST_CUDA_PREFIX/lib64/libcublas.so.12"',
            'export LD_LIBRARY_PATH="$FOREST_CUDA_PREFIX/lib64:${LD_LIBRARY_PATH:-}"', ''])
        command = setup + command
        command = command.replace('cd "$root"', 'sha256sum "$FOREST_CUDA_PREFIX/lib64/libcublas.so.12" > "$root/allocation-cublas.txt"\ncd "$root"')
        command = command.replace('allocation-gpu.txt engine-exit-code.txt', 'allocation-gpu.txt allocation-cublas.txt engine-exit-code.txt')
    (a/'command.sh').write_text(command, encoding='utf8', newline='\n')
    args = {'arch': plan['hardware'], 'command': command, 'cpus_per_task': plan['cpus'],
            'gpus_per_node': plan['gpus'], 'mem_gb': 16, 'name': 'forest-active-'+name,
            'time_limit': '01:00:00' if smoke else '04:00:00' if plan['wall_seconds'] >= 7200 else '02:00:00',
            'spack_packages': ['/uxlsycgnldislqswr4gcj6hlc6u2pdxp' if plan['gpus'] else '/fmrcj5jrubquulzxeqmhucxqunhodrxp'],
            'workdir': '/scratch_p/nimarano'}
    write(a/'job-arguments.json', args)
    record = {'case_id': key, 'condition': name, 'mode': mode, 'previous_job': plan['previous_job'],
              'previous_seconds': old_plan['wall_seconds'], 'new_seconds': plan['wall_seconds'],
              'smoke_only': smoke, 'cpus': plan['cpus'], 'gpus': plan['gpus'], 'session_id': session,
              'remote_root': remote, 'source_files': inventory(p/'source/src'),
              'protected_files': inventory(p/'validation'), 'delivery_wrappers_added': wrappers,
              'memory_context_characters': cfg['memory']['context_characters'],
              'payload_sha256': prep['payload_sha256']}
    index = read(R/'campaigns.json') if (R/'campaigns.json').exists() else []
    write(R/'campaigns.json', [*index, record])
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', nargs='+', choices=CASES, default=CASES)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    records = [prepare(key, name=key+'-smoke' if args.smoke else key,
                       duration=900 if args.smoke else None, smoke=args.smoke) for key in args.cases]
    write(R/'protocol.json', {'scope': SCOPE, 'user_request': REQUEST, 'model': 'gpt-6-luna', 'effort': 'max',
        'new_sessions_and_databases': True, 'operator_algorithm_hints': False, 'retained_source_and_validation': True,
        'comparison': 'Naive, published reference, previous selected/G and new selected/G, paired on the same allocation',
        'interpretation': 'One stochastic search per program; repeated timing blocks do not establish search-level statistical superiority',
        'missing_documentary_rows': read(OLD/'analysis.json')['summary']['unavailable'],
        'engine_head_before_changes': subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()})
    print(json.dumps([{k:r[k] for k in ('case_id','condition','new_seconds','cpus','gpus')} for r in records]))
