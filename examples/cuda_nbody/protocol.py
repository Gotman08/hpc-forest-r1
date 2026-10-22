"""Frozen N-body CUDA protocol. Candidate device code never controls timing/checks."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import uuid
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from use_harness import BufferArgument, HarnessRuner, KernelRequest, ScalarArgument

SPECS = [(1,.01,'single'), (2,.01,'coincident'), (31,.01,'tail'),
         (127,0.,'zero_dt'), (257,-.005,'negative_dt'), (257,.01,'mixed_masses'),
         (4095,.01,'tail_large'), (4096,.01,'original_size'),
         (8192,.01,'double_size'), (16384,.01,'quadruple_size'),
         (1,.01,'single_large_mass')]
PERFORMANCE = (7, 8, 9)


def write(path, value):
    Path(path).write_text(json.dumps(value, allow_nan=False, indent=2)+'\n', encoding='utf8')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def launch_settings(value):
    if not isinstance(value, dict) or set(value) != {'block','items_per_block','shared_memory_bytes'}:
        raise ValueError('launch.json requires exactly block, items_per_block, shared_memory_bytes')
    for key, maximum, minimum in [('block',1024,1),('items_per_block',1048576,1),
                                  ('shared_memory_bytes',49152,0)]:
        if type(value[key]) is not int or not minimum <= value[key] <= maximum:
            raise ValueError('Invalid launch setting: '+key)
    return value


def make_inputs(directory, seed):
    directory.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(seed)
    cases = []
    for index, (n, dt, label) in enumerate(SPECS):
        particles = np.empty((n,7),dtype='<f4')
        particles[:,:3] = rng.uniform(0,10,(n,3))
        particles[:,3:6] = rng.uniform(-.05,.05,(n,3))
        particles[:,6] = rng.uniform(1,10.9,n)
        if label == 'coincident':
            particles[1,:3] = particles[0,:3]
        if label == 'mixed_masses':
            particles[:,6] = np.geomspace(.001,1000,n)
            particles[10:13,:3] = particles[0,:3]
        if label == 'single_large_mass':
            particles[:,6] = np.float32(1e30)
        path = directory / f'{index:02}.bin'
        particles.tofile(path)
        cases.append({'n':n,'dt':dt,'label':label,'input':str(path), 'input_sha256':sha(path)})
    return cases


def cpu_expected(particles, dt):
    n = len(particles)
    rows = np.arange(n) if n <= 257 else np.linspace(0,n-1,32,dtype=int)
    values = particles.astype(np.float64)
    expected = values[rows].copy()
    dt = float(np.float32(dt))
    for k, row in enumerate(rows):
        delta = values[:,:3] - values[row,:3]
        d2 = np.sum(delta*delta,axis=1) + float(np.float32(.001))
        factor = values[:,6] / (d2*np.sqrt(d2))
        factor[row] = 0
        expected[k,3:6] += np.sum(delta*factor[:,None],axis=0)*dt
        expected[k,:3] += expected[k,3:6]*dt
    return rows, expected


def run_kernel(source, settings, case, output, *, benchmark=False):
    output.mkdir(parents=True, exist_ok=True)
    runner = HarnessRuner(Path(os.environ['FOREST_CUDA_HARNESS']), output)
    n = case['n']
    args = [BufferArgument(n*28,case['input'],'input'),
            BufferArgument(n*28,None,'output'), ScalarArgument('int32',n),
            ScalarArgument('float32',case['dt'])]
    request = KernelRequest(str(source.resolve()),'nbody_step_naive',
        'benchmark' if benchmark else 'run',0,
        [(n+settings['items_per_block']-1)//settings['items_per_block'],1,1],
        [settings['block'],1,1],settings['shared_memory_bytes'],
        10 if benchmark else 0,100 if benchmark else 1,args)
    report = runner.run(uuid.uuid4().hex, request)
    if not report.get('ok'):
        stage = report.get('stage','unknown')
        if stage in {'context','record','source','request','harness/execute'} or report.get('persistence_error'):
            raise RuntimeError('CUDA infrastructure failure: '+json.dumps(report))
        raise ValueError('Candidate CUDA failure: '+json.dumps(report))
    raw = Path(report['outputs'][0]['path']).read_bytes()
    if len(raw) != n*28:
        raise RuntimeError('Harness output size mismatch')
    return np.frombuffer(raw,dtype='<f4').reshape(n,7), report


def compare(actual, reference, inputs):
    if actual.shape != reference.shape or not np.isfinite(actual).all():
        return {'ok':False,'reason':'shape or nonfinite values'}
    matches = np.isclose(actual,reference,atol=5e-5,rtol=2e-4)
    masses = np.array_equal(actual[:,6],inputs[:,6])
    return {'ok':bool(matches.all() and masses),'mismatches':int((~matches).sum()),
            'mass_exact':bool(masses),'max_absolute_error':float(np.max(np.abs(actual-reference)))}


def preflight(trusted, cache):
    cache.mkdir(parents=True, exist_ok=False)
    device = HarnessRuner(Path(os.environ['FOREST_CUDA_HARNESS']),cache/'device').get_device_properties(0)
    write(cache/'device.json',device)
    settings = {'block':256,'items_per_block':256,'shared_memory_bytes':0}
    all_phases = {}
    for phase, seed in [('search',20261021),('confirmation',20261022)]:
        cases = make_inputs(cache/phase/'inputs',seed)
        for index,case in enumerate(cases):
            actual, report = run_kernel(trusted/'reference.cu',settings,case,cache/phase/'reference-runs')
            inputs = np.fromfile(case['input'],dtype='<f4').reshape(-1,7)
            rows, expected = cpu_expected(inputs,case['dt'])
            ok = bool(np.isfinite(actual).all() and
                      np.isclose(actual[rows],expected,atol=5e-5,rtol=5e-4).all() and
                      np.array_equal(actual[:,6],inputs[:,6]))
            if not ok:
                raise RuntimeError(f'Original kernel failed independent CPU oracle: {phase}/{index}')
            reference = cache/phase/f'reference-{index:02}.bin'
            actual.tofile(reference)
            case.update(reference=str(reference),reference_sha256=sha(reference),
                        cpu_rows=len(rows),cpu_oracle_passed=True)
        write(cache/f'{phase}.json',cases)
        all_phases[phase] = {'cases':len(cases),'seed':seed,'manifest_sha256':sha(cache/f'{phase}.json')}
    write(cache/'preflight.json',{'passed':True,'phases':all_phases,'device':device})
    print(json.dumps({'gpu_preflight':'passed','cases':sum(p['cases'] for p in all_phases.values()),'phases':all_phases}))


def load_cases(phase):
    if phase not in {'search','confirmation'}:
        raise ValueError('Unknown evaluation phase')
    cache = Path(os.environ['FOREST_CUDA_CACHE'])
    path = cache/f'{phase}.json'
    frozen = json.loads((cache/'preflight.json').read_text())
    if sha(path) != frozen['phases'][phase]['manifest_sha256']:
        raise RuntimeError('Reference manifest changed')
    cases = json.loads(path.read_text())
    for case in cases:
        if sha(case['input']) != case['input_sha256'] or sha(case['reference']) != case['reference_sha256']:
            raise RuntimeError('Frozen input/reference changed')
    return cases


def bundle(worktree, build):
    source = worktree/'src/nbody_kernel.cu'
    launch = worktree/'src/launch.json'
    if source.is_symlink() or launch.is_symlink():
        raise ValueError('Candidate symlinks are forbidden')
    text = source.read_text(encoding='utf8')
    if len(text.encode()) > 1000000 or 'nbody_step_naive' not in text:
        raise ValueError('Missing or oversized CUDA kernel')
    settings = launch_settings(json.loads(launch.read_text()))
    build.mkdir(parents=True,exist_ok=True)
    write(build/'solution',{'format':'nbody-cuda-bundle-v1','source':text,'launch':settings})
    print(json.dumps({'built':True,'bundle_sha256':sha(build/'solution')}))


def evaluate(binary, phase, benchmark):
    value = json.loads(binary.read_text())
    if value.get('format') != 'nbody-cuda-bundle-v1':
        raise ValueError('Invalid candidate bundle')
    settings = launch_settings(value['launch'])
    run = binary.parent/'cuda-runs'/uuid.uuid4().hex
    run.mkdir(parents=True)
    source = run/'kernel.cu'
    source.write_text(value['source'],encoding='utf8')
    cases = load_cases(phase)
    results = []
    for index in (PERFORMANCE if benchmark else range(len(cases))):
        case = cases[index]
        actual, report = run_kernel(source,settings,case,run,benchmark=benchmark)
        reference = np.fromfile(case['reference'],dtype='<f4').reshape(-1,7)
        inputs = np.fromfile(case['input'],dtype='<f4').reshape(-1,7)
        checked = compare(actual,reference,inputs)
        results.append({'n':case['n'],'label':case['label'],**checked,
                        'latency_ms':report.get('latency_ms'),'report_path':report.get('result_path')})
        if not checked['ok']:
            print(json.dumps({'correct':False,'cases':len(results),'details':results}))
            return 1
    result = {'correct':True,'cases':len(results),'details':results,'phase':phase}
    if benchmark:
        latencies = [r['latency_ms'] for r in results]
        if any(type(v) not in (int,float) or not math.isfinite(v) or v <= 0 for v in latencies):
            raise RuntimeError('Nonpositive or invalid CUDA event metric')
        result.update(metric='geomean_cuda_event_seconds',
            seconds=math.exp(sum(math.log(v/1000) for v in latencies)/len(latencies)),
            warmup_launches=10,timed_launches_per_size=100)
    print(json.dumps(result,allow_nan=False))
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=['preflight','build','check','benchmark'])
    parser.add_argument('first',type=Path)
    parser.add_argument('second')
    args = parser.parse_args()
    try:
        if args.action == 'preflight':
            preflight(args.first.resolve(),Path(args.second).resolve())
        elif args.action == 'build':
            bundle(args.first,Path(args.second))
        else:
            return evaluate(args.first,args.second,args.action=='benchmark')
        return 0
    except (ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'correct':False,'error':str(exc)}))
        return 1
    except Exception as exc:
        print(json.dumps({'infrastructure_error':type(exc).__name__+': '+str(exc)}))
        return 70


if __name__ == '__main__':
    raise SystemExit(main())
