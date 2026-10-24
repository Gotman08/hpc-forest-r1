from pathlib import Path
import json,subprocess,random,os,hashlib,time
R=Path(__file__).resolve().parent;S=Path('/scratch_p/nimarano/forest-reference-gpu-suite-20261023')
out=R/('measurements-'+os.environ['SLURM_JOB_ID']);out.mkdir();manifest=json.loads((R/'manifest.json').read_text());rows=[]
for m in manifest:
    d=R/m['case_id']/m['variant'];assert hashlib.sha256((d/'candidate.cu').read_bytes()).hexdigest()==m['sha256']
    p=subprocess.run(['nvcc','-std=c++17','-O3','-arch=sm_90','-shared','-Xcompiler=-fPIC',str(d/'candidate.cu'),'-o',str(d/'candidate.so')],capture_output=True,text=True)
    (out/(m['case_id']+'-'+m['variant']+'-build.log')).write_text(p.stdout+p.stderr);assert p.returncode==0
cases=json.loads((S/'cases.json').read_text());order=[]
for c in cases:
    for v in c['reference_variants']:order.append((c,'ref-'+str(v),'REF',v))
    for v in ['selected','final_g']:order.append((c,v,str(R/c['id']/v/'candidate.so'),1))
rng=random.Random(271)
(out/'environment.json').write_text(json.dumps({'job':os.environ['SLURM_JOB_ID'],'gpu':subprocess.check_output(['nvidia-smi','-q'],text=True),'cpu':subprocess.check_output(['lscpu'],text=True),'compiler':subprocess.check_output(['nvcc','--version'],text=True),'start':time.time()},indent=2))
for block in range(9):
    rng.shuffle(order)
    for c,label,binary,v in order:
        args=[str(S/'gpu_driver'),str(c['kind']),str(S/'references.so'),binary,str(v),str(c['n']),str(271+37*block),str(c['reps']),str(c['warmups']),'1']
        p=subprocess.run(args,capture_output=True,text=True,timeout=240)
        try:data=json.loads(p.stdout)
        except Exception:data={'error':p.stdout+p.stderr}
        row={'case_id':c['id'],'variant':label,'block':block,'exit_code':p.returncode,'measurement':data};rows.append(row)
        (out/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
(out/'complete.json').write_text(json.dumps({'time':time.time(),'records':len(rows)}));print('FINAL_COMPARISON_DONE',out,flush=True)
