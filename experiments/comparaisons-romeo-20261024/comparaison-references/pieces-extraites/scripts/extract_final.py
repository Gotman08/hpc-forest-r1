from pathlib import Path
import json,subprocess,hashlib,tarfile,sys,re
R=Path(__file__).resolve().parent;group=sys.argv[1]
cpu=[x['id'] for x in json.loads((R/'cpu-suite/cases.json').read_text())]
extra=['reduction','s4convd','softmax','sumabs'];render=['aobench','volume','raytracer','deferred']
keys={'cpu':cpu,'extra':extra,'render':render}[group]
single=sys.argv[2] if len(sys.argv)>2 else None
if single:
    assert group=='render' and single in keys
    keys=[single]
stem=group+'-final'+('-'+single if single else '')
P=R/stem;P.mkdir(exist_ok=True);manifest=[]
if group=='render':
    import shutil
    shutil.copyfile(R/'render_final_compare.py',P/'render_final_compare.py')
    shutil.copyfile(R/'render-final/render_final_driver.cpp',P/'render_final_driver.cpp')
for key in keys:
    a=R/'campaigns'/('deferred_r2' if key=='deferred' and (R/'campaigns/deferred_r2').exists() else key)
    if not (a/'results.tar.gz').exists():raise RuntimeError('Missing results for '+key)
    if not (a/'results').exists():
        with tarfile.open(a/'results.tar.gz') as t:t.extractall(a/'results',filter='data')
    result_file=next(a.glob('results/results-*/results.json'));result=json.loads(result_file.read_text());repo=result_file.parent/('reference-'+key)/'repo'
    selected=result.get('best_confirmed') or {};final=(result.get('final_g_confirmation') or {}).get('outcome') or {}
    suffix='.py' if key=='softmax' else '.cu' if group=='extra' else '.cpp'
    for variant,ev in [('selected',selected),('final_g',final)]:
        commit=ev.get('commit')
        if not commit:manifest.append({'case_id':key,'variant':variant,'missing':True,'engine_error':result.get('error')});continue
        assert re.fullmatch('[0-9a-f]{40}',commit)
        d=P/key/variant;d.mkdir(parents=True,exist_ok=True)
        src=subprocess.check_output(['git','-C',str(repo),'show',commit+':src/candidate'+suffix])
        (d/('candidate'+suffix)).write_bytes(src)
        manifest.append({'case_id':key,'variant':variant,'commit':commit,'sha256':hashlib.sha256(src).hexdigest(),'engine_job':result['job_id'],'engine_error':result.get('error'),'pipeline_complete':result['pipeline_complete'],'confirmation_status':(result.get('final_g_confirmation') or {}).get('status'),'reported_seconds':ev.get('mean_seconds'),'suffix':suffix})
    print(key,result['pipeline_complete'],len(result.get('trials',[])),flush=True)
(P/'manifest.json').write_text(json.dumps(manifest,indent=2))
with tarfile.open(R/(stem+'.tar.gz'),'w:gz') as t:
    for f in P.iterdir():t.add(f,arcname=f.name)
