from pathlib import Path
import json, subprocess, os, platform, time, hashlib
R=Path(__file__).resolve().parent
os.chdir(R)
logs=R/'preflight';logs.mkdir(exist_ok=True)
def command(args,name,timeout=300):
    p=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
    (logs/(name+'.log')).write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError(f'{name}: {p.returncode}: '+p.stderr[-1500:])
    return p.stdout
device=command(['nvidia-smi','-q'],'gpu')
command(['lscpu'],'cpu')
command(['nvcc','--version'],'compiler')
command(['nvcc','-std=c++17','-O3','-arch=sm_90','-shared','-Xcompiler=-fPIC','references.cu','-lcublas','-o','references.so'],'reference-build')
command(['nvcc','-std=c++17','-O3','-arch=sm_90','gpu_driver.cu','-ldl','-o','gpu_driver'],'driver-build')
results=[]
for case in json.loads((R/'cases.json').read_text()):
    name=case['id'];src=R/'cases'/name/'src/candidate.cu';lib=R/'cases'/name/'baseline.so'
    command(['nvcc','-std=c++17','-O3','-arch=sm_90','-shared','-Xcompiler=-fPIC',str(src),'-o',str(lib)],name+'-build')
    for variant in case['reference_variants']+['candidate']:
        args=[str(R/'gpu_driver'),str(case['kind']),str(R/'references.so'),str(lib) if variant=='candidate' else 'REF',str(1 if variant=='candidate' else variant),str(case['n']),'23',str(case['reps']),str(case['warmups']),'1']
        p=subprocess.run(args,capture_output=True,text=True,timeout=300)
        (logs/(name+'-'+str(variant)+'.log')).write_text(p.stdout+p.stderr)
        row={'case_id':name,'variant':variant,'exit_code':p.returncode,'command':args}
        try:row['measurement']=json.loads(p.stdout)
        except Exception:row['error']=(p.stdout+p.stderr)[-1000:]
        results.append(row)
        (logs/'results.json').write_text(json.dumps(results,indent=2))
        print(json.dumps(row),flush=True)
(logs/'environment.json').write_text(json.dumps({'job_id':os.environ['SLURM_JOB_ID'],'machine':platform.machine(),'time':time.time(),'files':{x:hashlib.sha256((R/x).read_bytes()).hexdigest() for x in ['gpu_driver','references.so','gpu_driver.cu','references.cu']}},indent=2))
print('GPU_PREFLIGHT_DONE',flush=True)
