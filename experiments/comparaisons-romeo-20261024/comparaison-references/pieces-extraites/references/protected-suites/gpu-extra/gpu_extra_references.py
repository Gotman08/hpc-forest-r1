from pathlib import Path
import subprocess,json,os,sys,random,hashlib,time
R=Path(__file__).resolve().parent;out=R/('reference-'+os.environ['SLURM_JOB_ID']);out.mkdir();cases=json.loads((R/'cases.json').read_text());rows=[]
for c in cases:
    if c['id']=='softmax':continue
    for v in c['variants']:
        p=R/(c['id']+'-'+str(v));cmd=['nvcc','-std=c++17','-O3','-arch=sm_90','-shared','-Xcompiler=-fPIC',str(p)+'.cu','-o',str(p)+'.so']
        r=subprocess.run(cmd,capture_output=True,text=True);(out/(p.name+'-build.log')).write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError(r.stderr[-2000:])
(out/'environment.json').write_text(json.dumps({'gpu':subprocess.check_output(['nvidia-smi','-q'],text=True),'compiler':subprocess.check_output(['nvcc','--version'],text=True),'job':os.environ['SLURM_JOB_ID'],'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob('*.so')}},indent=2))
order=[(c,v) for c in cases for v in c['variants']];rng=random.Random(23)
for block in range(5):
    rng.shuffle(order)
    for c,v in order:
        name=c['id'];binary=str(v) if name=='softmax' else str(R/(name+'-'+str(v)+'.so'))
        cmd=[sys.executable,str(R/'gpu_extra_driver.py'),name,binary,str(c['n']),str(23+37*block),'bench']
        try:
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
            try:d=json.loads(p.stdout)
            except Exception:d={'error':(p.stdout+p.stderr)[-3000:]}
            row={'case_id':name,'variant':v,'block':block,'exit_code':p.returncode,'measurement':d}
        except subprocess.TimeoutExpired:row={'case_id':name,'variant':v,'block':block,'error':'timeout 300s'}
        rows.append(row);(out/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
(out/'complete.json').write_text(json.dumps({'time':time.time(),'records':len(rows)}));print('EXTRA_REFERENCES_DONE',out,flush=True)
