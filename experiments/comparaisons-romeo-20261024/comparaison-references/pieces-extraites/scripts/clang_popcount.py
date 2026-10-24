from pathlib import Path
import os,sys,json,subprocess,random,time,hashlib
S=Path('/scratch_p/nimarano/forest-reference-cpu-suite-20261023');F=Path('/scratch_p/nimarano/forest-reference-cpu-final-20261023');R=Path('/scratch_p/nimarano/forest-reference-clang-20261023');R.mkdir(exist_ok=True);out=R/('measurements-'+os.environ['SLURM_JOB_ID']);out.mkdir();rows=[]
sources={'naive':S/'cases/popcount/src/candidate.cpp','optimized':S/'cases/popcount/optimized.cpp','selected':F/'popcount/selected/candidate.cpp','final_g':F/'popcount/final_g/candidate.cpp'}
order=[]
def build(label):
    src=sources[label];p=subprocess.run(['clang++','-std=c++17','-O3','-march=native','-fPIC','-shared','-fopenmp','-Wl,-Bsymbolic',str(src),'-o',str(out/(label+'.so'))],capture_output=True,text=True)
    (out/(label+'-build.log')).write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError(p.stderr[-2500:])
def measure(label,block):
    cmd=[sys.executable,str(S/'cpu_driver.py'),'popcount',str(out/(label+'.so')),'1000',str(1907+53*block),'1','bench','0'];p=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
    try:d=json.loads(p.stdout)
    except Exception:d={'error':p.stdout+p.stderr}
    row={'case_id':'popcount','variant':label,'block':block,'exit_code':p.returncode,'measurement':d};rows.append(row);(out/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
env={'job':os.environ['SLURM_JOB_ID'],'cpu':subprocess.check_output(['lscpu'],text=True),'compiler':subprocess.check_output(['clang++','--version'],text=True),'affinity':sorted(os.sched_getaffinity(0)),'time':time.time(),'source_hashes':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in sources.items()},'note':'Forest sources were selected under GCC 14.2; same unchanged sources recompiled with Clang 17.0.6.'};(out/'environment.json').write_text(json.dumps(env,indent=2))
# Establish the reference pair on Clang before measuring the Forest candidates.
for v in ['naive','optimized']:build(v);measure(v,0)
for v in ['selected','final_g']:build(v)
rng=random.Random(1907);order=list(sources)
for block in range(1,8):
    rng.shuffle(order)
    for v in order:measure(v,block)
(out/'complete.json').write_text(json.dumps({'records':len(rows),'time':time.time()}));print('CLANG_DONE',out,flush=True)
