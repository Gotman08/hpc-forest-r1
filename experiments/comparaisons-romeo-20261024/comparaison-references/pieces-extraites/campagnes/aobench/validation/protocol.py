from pathlib import Path
import json,sys,subprocess,hashlib,math
T=Path(__file__).resolve().parent;C=json.loads((T/'case.json').read_text());R=Path(C['suite'])
for name,expected in C['trusted_files'].items():
    if hashlib.sha256((R/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Protected file changed: '+name)
def main():
    action=sys.argv[1]
    if action=='build':
        source=Path(sys.argv[2])/'src/candidate.cpp';dest=Path(sys.argv[3]);dest.mkdir(parents=True,exist_ok=True)
        p=subprocess.run(['g++','-std=c++17','-O3','-march=native','-fPIC','-shared','-fopenmp','-Wl,-Bsymbolic','-I'+str(R/'include'),str(source),'-o',str(dest/'solution')],capture_output=True,text=True)
        print(p.stdout+p.stderr,end='');return p.returncode
    binary=str(Path(sys.argv[2]).resolve());seed=271 if sys.argv[3]=='confirmation' else 23
    specs=[(n,t,seed) for n,t in C['performance']] if action=='benchmark' else [(n,C['threads'],s) for n in sorted(set(C['checks']+[C['n']])) for s in [seed,308]]
    rows=[];rc=0
    for n,t,s in specs:
        p=subprocess.run([str(R/'render_driver'),str(R),C['id'],binary,str(n),str(s),str(t),'bench' if action=='benchmark' else 'check'],capture_output=True,text=True,timeout=600)
        try:d=json.loads(p.stdout)
        except Exception:d={'correct':False,'error':(p.stdout+p.stderr)[-2500:]}
        rows.append(d)
        if p.returncode:rc=70 if p.returncode==70 else 1;break
    result={'correct':rc==0,'cases':len(rows),'details':rows}
    if action=='benchmark' and not rc:result.update(metric='protected_kernel_seconds',seconds=math.exp(sum(math.log(x['seconds']) for x in rows)/len(rows)))
    print(json.dumps(result));return rc
if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,RuntimeError,subprocess.TimeoutExpired) as e:print(json.dumps({'infrastructure_error':str(e)}));sys.exit(70)
