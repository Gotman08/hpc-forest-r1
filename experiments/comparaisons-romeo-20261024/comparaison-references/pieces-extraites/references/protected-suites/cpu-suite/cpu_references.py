from pathlib import Path
import json,subprocess,sys,random,os,time
R=Path(__file__).resolve().parent;out=R/('reference-'+os.environ['SLURM_JOB_ID']);out.mkdir()
rows=[];rng=random.Random(23)
cases=json.loads((R/'cases.json').read_text());order=[]
for c in cases:
    name=c['id'];variants=[p for p in (R/'cases'/name).glob('*.so')]
    configs=[(c['n'],c['threads'])]
    if c.get('ispc') and name!='noise':configs=[(c['n'],1),(c['n'],4)]+([(2097152,40)] if c.get('max_threads') else [])
    for n,threads in configs:
        for p in variants:
            if p.stem=='tasks' and threads==1:continue
            if p.stem=='optimized' and threads!=1 and c.get('ispc_tasks'):continue
            for pattern in ([0,1] if name=='argmin' else [0]):order.append((c,p,n,threads,pattern))
for block in range(5):
    rng.shuffle(order)
    for c,p,n,threads,pattern in order:
        args=[sys.executable,str(R/'cpu_driver.py'),c['id'],str(p),str(n),str(23+37*block),str(threads),'bench',str(pattern)]
        try:
            run=subprocess.run(args,text=True,capture_output=True,timeout=180)
            try:d=json.loads(run.stdout)
            except Exception:d={'error':(run.stdout+run.stderr)[-3000:]}
            row={'block':block,'variant':p.stem,'exit_code':run.returncode,'case_id':c['id'],'measurement':d}
        except subprocess.TimeoutExpired:row={'block':block,'case_id':c['id'],'variant':p.stem,'error':'timeout 180s'}
        rows.append(row);(out/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
# Validation diagnostics use inputs outside the timed workload as well.
for c in cases:
    for pattern in ([1,2,3] if c['id']=='utf8' else [2,3,4] if c['id']=='argmin' else [1]):
        for p in (R/'cases'/c['id']).glob('*.so'):
            n=c['checks'][-1]
            args=[sys.executable,str(R/'cpu_driver.py'),c['id'],str(p),str(n),'271',str(c['threads']),'check',str(pattern)]
            run=subprocess.run(args,capture_output=True,text=True,timeout=180)
            rows.append({'diagnostic':True,'case_id':c['id'],'variant':p.stem,'exit_code':run.returncode,'stdout':run.stdout,'stderr':run.stderr})
(out/'results.json').write_text(json.dumps(rows,indent=2));(out/'complete.json').write_text(json.dumps({'records':len(rows),'time':time.time()}))
print('CPU_REFERENCES_DONE',out,flush=True)
