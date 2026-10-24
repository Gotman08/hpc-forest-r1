from pathlib import Path
import subprocess,json,os,random,time
R=Path(__file__).resolve().parent;out=R/('reference-'+os.environ['SLURM_JOB_ID']);out.mkdir();cases=json.loads((R/'cases.json').read_text());rows=[];order=[];rng=random.Random(23)
for c in cases:
    for n,t in c['performance']:
        for v in ['naive','optimized' if t==1 or c['id']=='deferred' else 'tasks']:order.append((c,n,t,v))
(out/'environment.json').write_text(json.dumps({'cpu':subprocess.check_output(['lscpu'],text=True),'compiler':subprocess.check_output(['g++','--version'],text=True),'affinity':sorted(os.sched_getaffinity(0)),'job':os.environ['SLURM_JOB_ID']},indent=2))
for block in range(3):
    rng.shuffle(order)
    for c,n,t,v in order:
        cmd=[str(R/'render_driver'),str(R),c['id'],str(R/'cases'/c['id']/(v+'.so')),str(n),'23',str(t),'bench']
        try:
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=600)
            try:d=json.loads(p.stdout)
            except Exception:d={'error':(p.stdout+p.stderr)[-2000:]}
            row={'case_id':c['id'],'variant':v,'block':block,'exit_code':p.returncode,'measurement':d}
        except subprocess.TimeoutExpired:row={'case_id':c['id'],'variant':v,'block':block,'error':'timeout 600s'}
        rows.append(row);(out/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
(out/'complete.json').write_text(json.dumps({'time':time.time(),'records':len(rows)}));print('RENDER_REFERENCES_DONE',out,flush=True)
