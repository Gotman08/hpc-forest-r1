from pathlib import Path
import json,sys,subprocess,hashlib,math
T=Path(__file__).resolve().parent;C=json.loads((T/'case.json').read_text());R=Path(C['suite'])
for name,expected in C.get('trusted_files',{}).items():
    if hashlib.sha256((R/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Protected file changed: '+name)
def main():
    action=sys.argv[1]
    if action=='build':
        source=Path(sys.argv[2])/'src/candidate.cpp';dest=Path(sys.argv[3]);dest.mkdir(parents=True,exist_ok=True)
        p=subprocess.run(['g++','-std=c++17','-O3','-march=native','-fPIC','-shared','-fopenmp','-Wl,-Bsymbolic',str(source),'-o',str(dest/'solution')],capture_output=True,text=True)
        print(p.stdout+p.stderr,end='');return p.returncode
    binary=str(Path(sys.argv[2]).resolve());phase=sys.argv[3];seed=271 if phase=='confirmation' else 23
    perf=C.get('performance',[[C['n'],C['threads']]])
    specs=[(n,t,seed+101,0) for n,t in perf] if action=='benchmark' else [(n,C['threads'],s,p) for n in sorted(set(C['checks']+[C['n']])) for s,p in [(seed,0),(seed+37,1)]]
    if action=='check' and C['id']=='utf8':specs.extend((n,1,seed,p) for n in [1,16,1024] for p in [2,3])
    if action=='check' and C['id']=='argmin':specs.extend((8192,1,seed,p) for p in [2,3,4])
    rows=[];rc=0
    for n,t,s,p in specs:
        cmd=[sys.executable,str(R/'cpu_driver.py'),C['id'],binary,str(n),str(s),str(t),'bench' if action=='benchmark' else 'check',str(p)]
        run=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        try:d=json.loads(run.stdout)
        except Exception:d={'correct':False,'error':(run.stdout+run.stderr)[-2000:]}
        rows.append(d)
        if run.returncode:rc=1;break
    result={'correct':rc==0,'cases':len(rows),'details':rows}
    if action=='benchmark' and rc==0:result.update(metric='protected_kernel_seconds',seconds=math.exp(sum(math.log(x['seconds']) for x in rows)/len(rows)))
    print(json.dumps(result));return rc
if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,RuntimeError,subprocess.TimeoutExpired) as e:print(json.dumps({'infrastructure_error':str(e)}));sys.exit(70)
