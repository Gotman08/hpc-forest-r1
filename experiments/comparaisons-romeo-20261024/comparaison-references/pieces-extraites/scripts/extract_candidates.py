from pathlib import Path
import json,subprocess,hashlib,tarfile
R=Path(__file__).resolve().parent;P=R/'gpu-final';P.mkdir(exist_ok=True);manifest=[]
for a in (R/'campaigns').iterdir():
    found=list(a.glob('results/results-*/results.json'))
    if not found:continue
    result=json.loads(found[0].read_text());campaign=found[0].parent/('reference-'+a.name);repo=campaign/'repo'
    for variant,commit in [('selected',result['best_confirmed']['commit']),('final_g',result['final_g_confirmation']['outcome']['commit'])]:
        d=P/a.name/variant;d.mkdir(parents=True,exist_ok=True)
        p=subprocess.run(['git','-C',str(repo),'show',commit+':src/candidate.cu'],capture_output=True,check=True)
        (d/'candidate.cu').write_bytes(p.stdout)
        manifest.append({'case_id':a.name,'variant':variant,'commit':commit,'sha256':hashlib.sha256(p.stdout).hexdigest(),'engine_job':result['job_id'],'engine_packaging_error':result.get('error'),'confirmation_status':result['final_g_confirmation']['status']})
(P/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))
with tarfile.open(R/'gpu-final.tar.gz','w:gz') as t:
    for p in P.iterdir():t.add(p,arcname=p.name)
