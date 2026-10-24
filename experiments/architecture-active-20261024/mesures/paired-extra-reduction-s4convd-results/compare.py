from pathlib import Path
import json,subprocess,random,os,hashlib,time,sys
R=Path(__file__).resolve().parent;S=Path('/scratch_p/nimarano/forest-reference-gpu-extra-20261023');out=R/('measurements-'+os.environ['SLURM_JOB_ID']);out.mkdir()
manifest=json.loads((R/'manifest.json').read_text());cases=json.loads((S/'cases.json').read_text());rows=[]
cases=[c for c in cases if c['id'] in {m['case_id'] for m in manifest}]
for name, expected in json.loads((R/'suite-snapshot.json').read_text()).items():
    assert hashlib.sha256((S/name).read_bytes()).hexdigest()==expected, ('frozen suite',name)
for key in {m['case_id'] for m in manifest}:
    protected=json.loads((R/key/'protected.json').read_text())
    for name,expected in protected.get('trusted_files',protected.get('trusted_binaries',{})).items():
        assert hashlib.sha256((Path(protected['suite'])/name).read_bytes()).hexdigest()==expected, (key,name)
for m in manifest:
    if m.get('missing'):continue
    d=R/m['case_id']/m['variant'];src=d/('candidate'+m['suffix']);assert hashlib.sha256(src.read_bytes()).hexdigest()==m['sha256']
    if m['case_id']=='softmax':continue
    p=subprocess.run(['nvcc','-std=c++17','-O3','-arch=sm_90','-shared','-Xcompiler=-fPIC',str(src),'-o',str(d/'candidate.so')],capture_output=True,text=True)
    (out/(m['case_id']+'-'+m['variant']+'-build.log')).write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError('Candidate build failed '+m['case_id'])
order=[];checks=[]
for c in cases:
    key=c['id'];variants=[('ref-'+str(v),str(v) if key=='softmax' else str(S/(key+'-'+str(v)+'.so'))) for v in c['variants']]
    variants +=[(v,str(R/key/v/('candidate.py' if key=='softmax' else 'candidate.so'))) for v in ['old_selected','new_selected','old_g','new_g'] if (R/key/v/('candidate.py' if key=='softmax' else 'candidate.so')).exists()]
    for label,p in variants:
        order.append((c,label,p,c['n']))
        for n in c['checks']:checks.append((c,label,p,n))
env={'job':os.environ['SLURM_JOB_ID'],'gpu':subprocess.check_output(['nvidia-smi','-q'],text=True),'cpu':subprocess.check_output(['lscpu'],text=True),'compiler':subprocess.check_output(['nvcc','--version'],text=True),'start':time.time(),'driver_sha256':hashlib.sha256((S/'gpu_extra_driver.py').read_bytes()).hexdigest()}
env['candidate_artifact_sha256']={p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob('*/*/candidate.*') if p.is_file()}
(out/'environment.json').write_text(json.dumps(env,indent=2));rng=random.Random(1907)
def run(c,label,p,n,block,check=False):
    cmd=[sys.executable,str(S/'gpu_extra_driver.py'),c['id'],p,str(n),str(1907+53*max(block,0)),'check' if check else 'bench']
    try:
        q=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
        try:d=json.loads(q.stdout)
        except Exception:d={'error':(q.stdout+q.stderr)[-2500:]}
        row={'case_id':c['id'],'variant':label,'block':block,'diagnostic':check,'exit_code':q.returncode,'measurement':d}
    except subprocess.TimeoutExpired:row={'case_id':c['id'],'variant':label,'block':block,'diagnostic':check,'error':'timeout 300s'}
    rows.append(row);(out/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
for block in range(9):
    rng.shuffle(order)
    for spec in order:run(*spec,block)
for spec in checks:run(*spec,-1,True)
(out/'complete.json').write_text(json.dumps({'records':len(rows),'time':time.time()}));print('EXTRA_FINAL_DONE',out,flush=True)
