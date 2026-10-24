"""Frozen Popcount sources, all compiled with the same Clang on this allocation."""
from pathlib import Path
import os, sys, json, subprocess, random, time, hashlib

R = Path(__file__).resolve().parent
S = Path('/scratch_p/nimarano/forest-reference-cpu-suite-20261023')
out = R/('measurements-'+os.environ['SLURM_JOB_ID'])
out.mkdir()
manifest = json.loads((R/'manifest.json').read_text())
for name, expected in json.loads((R/'suite-snapshot.json').read_text()).items():
    assert hashlib.sha256((S/name).read_bytes()).hexdigest() == expected, name
sources = {'naive':S/'cases/popcount/src/candidate.cpp', 'optimized':S/'cases/popcount/optimized.cpp'}
for item in manifest:
    if item.get('missing'):
        continue
    path = R/'popcount'/item['variant']/'candidate.cpp'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']
    sources[item['variant']] = path
rows = []
for label, source in sources.items():
    command = ['clang++','-std=c++17','-O3','-march=native','-fPIC','-shared','-fopenmp','-Wl,-Bsymbolic',str(source),'-o',str(out/(label+'.so'))]
    p = subprocess.run(command,capture_output=True,text=True)
    (out/(label+'-build.log')).write_text(p.stdout+p.stderr)
    assert p.returncode == 0, (label,p.stderr[-2500:])
env = {'job':os.environ['SLURM_JOB_ID'],'cpu':subprocess.check_output(['lscpu'],text=True),
       'compiler':subprocess.check_output(['clang++','--version'],text=True),
       'affinity':sorted(os.sched_getaffinity(0)),'time':time.time(),
       'candidate_artifact_sha256':{p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob('*/*/candidate.*')},
       'binary_sha256':{label:hashlib.sha256((out/(label+'.so')).read_bytes()).hexdigest() for label in sources},
       'source_hashes':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in sources.items()},
       'note':'Old and new Forest searches used GCC 14.2; retained sources recompiled unchanged with Clang 17.0.6.'}
(out/'environment.json').write_text(json.dumps(env,indent=2))
rng = random.Random(1907)
order = list(sources)
for block in range(1,8):
    rng.shuffle(order)
    for label in order:
        command = [sys.executable,str(S/'cpu_driver.py'),'popcount',str(out/(label+'.so')),'1000',str(1907+53*block),'1','bench','0']
        p = subprocess.run(command,capture_output=True,text=True,timeout=120)
        try:
            measurement = json.loads(p.stdout)
        except ValueError:
            measurement = {'error':p.stdout+p.stderr}
        row = {'case_id':'popcount','variant':label,'block':block,'exit_code':p.returncode,'measurement':measurement}
        rows.append(row)
        (out/'results.json').write_text(json.dumps(rows,indent=2))
        print(json.dumps(row),flush=True)
(out/'complete.json').write_text(json.dumps({'records':len(rows),'time':time.time()}))
print('CLANG_DONE',out,flush=True)
