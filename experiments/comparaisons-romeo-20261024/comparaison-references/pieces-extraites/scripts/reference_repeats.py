"""Phase 1: references only; the binaries under test are never rebuilt here."""
from pathlib import Path
import os, sys, json, subprocess, time, random, hashlib
R=Path(__file__).resolve().parent
mode=sys.argv[1]
out=R/('reference-repeats-'+mode+'-'+os.environ['SLURM_JOB_ID'])
out.mkdir()
def save(name, data): (out/name).write_text(json.dumps(data,indent=2))
def capture(args):
    p=subprocess.run(args,capture_output=True,text=True)
    return {'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
save('environment.json',{'job_id':os.environ['SLURM_JOB_ID'],'time':time.time(),'affinity':sorted(os.sched_getaffinity(0)),'cpu':capture(['lscpu']),'gpu':capture(['nvidia-smi','-q']) if mode=='gpu' else None,'compiler':capture(['nvcc','--version'] if mode=='gpu' else ['g++','--version'])})
records=[];rng=random.Random(20261023)
if mode=='gpu':
    suite=Path('/scratch_p/nimarano/forest-reference-gpu-suite-20261023')
    cases=json.loads((suite/'cases.json').read_text())
    save('binaries.json',{x:hashlib.sha256((suite/x).read_bytes()).hexdigest() for x in ['gpu_driver','references.so']})
    for block in range(7):
        order=[(c,v) for c in cases for v in c['reference_variants']];rng.shuffle(order)
        for c,v in order:
            args=[str(suite/'gpu_driver'),str(c['kind']),str(suite/'references.so'),'REF',str(v),str(c['n']),str(23+37*block),str(c['reps']),str(c['warmups']),'1']
            p=subprocess.run(args,text=True,capture_output=True,timeout=240)
            row={'case_id':c['id'],'variant':v,'block':block,'seed':23+37*block,'command':args,'exit_code':p.returncode}
            try:row['measurement']=json.loads(p.stdout)
            except Exception:row['error']=p.stdout+p.stderr
            records.append(row);save('results.json',records);print(json.dumps(row),flush=True)
else:
    suite=Path('/scratch_p/nimarano/forest-reference-cpu-preflight-20261023')
    e=suite/'examples/cpu';b=suite/'build';cpus=sorted(os.sched_getaffinity(0))
    specs=[('aobench','aobench',['512','512','3','3','3'],[1,4]),('aobench','aobench',['2048','2048','3','3','3'],[40]),('options','options',['--count=131072'],[1,4]),('options','options',['--count=2097152'],[40]),('deferred','deferred_shading',[str(e/'deferred/data/pp1280x720.bin'),'3','3','20'],[1,4]),('mandelbrot_tasks','mandelbrot_tasks',['3','3'],[1,4]),('noise','noise',['3','3'],[1]),('rt','rt',[str(e/'rt/sponza'),'3','3','3'],[1,4,40]),('stencil','stencil',['3','3','3'],[1,4]),('volume_rendering','volume_rendering',[str(e/'volume_rendering/camera.dat'),str(e/'volume_rendering/density_lowres.vol'),'3','3','3'],[1,4,40])]
    tasks=[(folder,binary,args,t) for folder,binary,args,ts in specs for t in ts]
    save('protocol.json',{'specs':specs,'blocks':3,'inner_repetitions':3,'statistic':'median of block minima','units':'upstream TSC ticks / 2^20; ratios within the same process only'})
    for block in range(3):
        rng.shuffle(tasks)
        for folder,binary,args,t in tasks:
            trial=out/(f'{folder}-{t}-{block}-'+str(len(records)));trial.mkdir()
            command=['taskset','-c',','.join(map(str,cpus[:t])),str(b/folder/binary),*args]
            start=time.monotonic()
            try:
                p=subprocess.run(command,text=True,capture_output=True,cwd=trial,timeout=600)
                row={'case_id':folder,'threads':t,'block':block,'command':command,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'wall_seconds':time.monotonic()-start}
            except subprocess.TimeoutExpired as ex:row={'case_id':folder,'threads':t,'block':block,'command':command,'error':'timeout 600s','stdout':str(ex.stdout),'wall_seconds':time.monotonic()-start}
            records.append(row);save('results.json',records);print(json.dumps(row),flush=True)
save('complete.json',{'completed':time.time(),'records':len(records)})
print('REFERENCE_REPEATS_DONE',out,flush=True)
