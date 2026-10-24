from pathlib import Path
import json,subprocess,random,os,hashlib,time,sys
R=Path(__file__).resolve().parent;S=Path('/scratch_p/nimarano/forest-reference-cpu-suite-20261023');out=R/('measurements-'+os.environ['SLURM_JOB_ID']);out.mkdir()
manifest=json.loads((R/'manifest.json').read_text());cases=json.loads((S/'cases.json').read_text());rows=[]
for m in manifest:
    if m.get('missing'):continue
    d=R/m['case_id']/m['variant'];src=d/'candidate.cpp';assert hashlib.sha256(src.read_bytes()).hexdigest()==m['sha256']
    p=subprocess.run(['g++','-std=c++17','-O3','-march=native','-fPIC','-shared','-fopenmp','-Wl,-Bsymbolic',str(src),'-o',str(d/'candidate.so')],capture_output=True,text=True)
    (out/(m['case_id']+'-'+m['variant']+'-build.log')).write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError('Candidate build failed '+m['case_id'])
order=[];checks=[]
for c in cases:
    key=c['id'];variants=[(p.stem,p) for p in (S/'cases'/key).glob('*.so')]+[(v,R/key/v/'candidate.so') for v in ['selected','final_g'] if (R/key/v/'candidate.so').exists()]
    configs=[(c['n'],c['threads'])]
    if c.get('ispc') and key!='noise':configs=[(c['n'],1),(c['n'],4)]+([(2097152,40)] if c.get('max_threads') else [])
    for n,threads in configs:
        for label,p in variants:
            if label=='tasks' and threads==1:continue
            if label=='optimized' and threads!=1 and c.get('ispc_tasks'):continue
            for pattern in ([0,1] if key=='argmin' else [0]):order.append((c,label,p,n,threads,pattern))
    for label,p in variants:
        for pattern in ([1,2,3] if key=='utf8' else [2,3,4] if key=='argmin' else [1]):checks.append((c,label,p,c['checks'][-1],c['threads'],pattern))
env={'job':os.environ['SLURM_JOB_ID'],'cpu':subprocess.check_output(['lscpu'],text=True),'compiler':subprocess.check_output(['g++','--version'],text=True),'affinity':sorted(os.sched_getaffinity(0)),'start':time.time(),'files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [S/'cpu_driver.py',S/'build/timing.so',*list(R.glob('*/*/candidate.so'))]}}
(out/'environment.json').write_text(json.dumps(env,indent=2));rng=random.Random(1907)
def run(c,label,p,n,threads,pattern,block,check=False):
    cmd=[sys.executable,str(S/'cpu_driver.py'),c['id'],str(p),str(n),str(1907+53*max(block,0)),str(threads),'check' if check else 'bench',str(pattern)]
    try:
        q=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
        try:d=json.loads(q.stdout)
        except Exception:d={'error':(q.stdout+q.stderr)[-2500:]}
        row={'case_id':c['id'],'variant':label,'block':block,'diagnostic':check,'exit_code':q.returncode,'measurement':d}
    except subprocess.TimeoutExpired:row={'case_id':c['id'],'variant':label,'block':block,'diagnostic':check,'error':'timeout 300s'}
    rows.append(row);(out/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
for block in range(7):
    rng.shuffle(order)
    for spec in order:run(*spec,block)
for spec in checks:run(*spec,-1,True)
(out/'complete.json').write_text(json.dumps({'records':len(rows),'time':time.time()}));print('CPU_FINAL_DONE',out,flush=True)
