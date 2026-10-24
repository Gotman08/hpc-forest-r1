from pathlib import Path
import json,subprocess,random,os,hashlib,time
R=Path(__file__).resolve().parent;S=Path('/scratch_p/nimarano/forest-reference-render-20261023');out=R/('measurements-'+os.environ['SLURM_JOB_ID']);out.mkdir();rows=[]
manifest=json.loads((R/'manifest.json').read_text());cases=json.loads((S/'cases.json').read_text())
selected_cases={m['case_id'] for m in manifest};cases=[c for c in cases if c['id'] in selected_cases]
flags=['g++','-std=c++17','-O3','-march=native','-fopenmp','-I'+str(S/'include')]
p=subprocess.run(flags+[str(R/'render_final_driver.cpp'),str(S/'common-adapted.cpp'),'-ldl','-o',str(R/'render_final_driver')],capture_output=True,text=True);(out/'driver-build.log').write_text(p.stdout+p.stderr)
if p.returncode:raise RuntimeError(p.stderr)
for name, expected in json.loads((R/'suite-snapshot.json').read_text()).items():
    assert hashlib.sha256((S/name).read_bytes()).hexdigest()==expected, ('frozen suite',name)
for key in {m['case_id'] for m in manifest}:
    protected=json.loads((R/key/'protected.json').read_text())
    for name,expected in protected.get('trusted_files',protected.get('trusted_binaries',{})).items():
        assert hashlib.sha256((Path(protected['suite'])/name).read_bytes()).hexdigest()==expected, (key,name)
for m in manifest:
    if m.get('missing'):continue
    d=R/m['case_id']/m['variant'];src=d/'candidate.cpp';assert hashlib.sha256(src.read_bytes()).hexdigest()==m['sha256']
    p=subprocess.run(flags+['-shared','-fPIC','-Wl,-Bsymbolic',str(src),'-o',str(d/'candidate.so')],capture_output=True,text=True);(out/(m['case_id']+'-'+m['variant']+'-build.log')).write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError(p.stderr)
order=[];checks=[]
for c in cases:
    key=c['id']
    for n,t in c['performance']:
        variants=[('naive',S/'cases'/key/'naive.so'),('optimized' if t==1 or key=='deferred' else 'tasks',S/'cases'/key/('optimized.so' if t==1 or key=='deferred' else 'tasks.so'))]
        variants +=[(v,R/key/v/'candidate.so') for v in ['old_selected','new_selected','old_g','new_g'] if (R/key/v/'candidate.so').exists()]
        for label,p in variants:order.append((c,label,p,n,t))
    variants=[('naive',S/'cases'/key/'naive.so'),('optimized',S/'cases'/key/'optimized.so')]+[(v,R/key/v/'candidate.so') for v in ['old_selected','new_selected','old_g','new_g'] if (R/key/v/'candidate.so').exists()]
    for label,p in variants:
        for n in ([1280] if key=='deferred' else [96,128]):checks.append((c,label,p,n,c['threads']))
scene_files=[p for p in (S/'data').rglob('*') if p.is_file() and p.suffix in {'.bin','.bvh','.camera','.dat','.vol'}]
env={'job':os.environ['SLURM_JOB_ID'],'cases':sorted(selected_cases),'cpu':subprocess.check_output(['lscpu'],text=True),'compiler':subprocess.check_output(['g++','--version'],text=True),'affinity':sorted(os.sched_getaffinity(0)),'start':time.time(),'timing_driver_sha256':hashlib.sha256((S/'render_driver').read_bytes()).hexdigest(),'additional_check_driver_sha256':hashlib.sha256((R/'render_final_driver').read_bytes()).hexdigest(),'scene_sha256':{str(p.relative_to(S/'data')):hashlib.sha256(p.read_bytes()).hexdigest() for p in scene_files}}
env['candidate_artifact_sha256']={p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob('*/*/candidate.*') if p.is_file()}
(out/'environment.json').write_text(json.dumps(env,indent=2));rng=random.Random(1907)
def run(c,label,p,n,t,block,check=False):
    driver=R/'render_final_driver' if check else S/'render_driver';seed=1009 if check else 23
    cmd=[str(driver),str(S),c['id'],str(p),str(n),str(seed),str(t),'check' if check else 'bench']
    try:
        q=subprocess.run(cmd,capture_output=True,text=True,timeout=600)
        try:d=json.loads(q.stdout)
        except Exception:d={'error':(q.stdout+q.stderr)[-2500:]}
        row={'case_id':c['id'],'variant':label,'block':block,'diagnostic':check,'exit_code':q.returncode,'measurement':d}
    except subprocess.TimeoutExpired:row={'case_id':c['id'],'variant':label,'block':block,'diagnostic':check,'error':'timeout 600s'}
    row['job']=os.environ['SLURM_JOB_ID'];rows.append(row);(out/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
for block in range(3):
    rng.shuffle(order)
    for spec in order:run(*spec,block)
for spec in checks:run(*spec,-1,True)
(out/'complete.json').write_text(json.dumps({'records':len(rows),'time':time.time()}));print('RENDER_FINAL_DONE',out,flush=True)
