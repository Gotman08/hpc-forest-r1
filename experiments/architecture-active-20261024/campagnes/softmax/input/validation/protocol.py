from pathlib import Path
import json,sys,subprocess,hashlib,shutil,py_compile
T=Path(__file__).resolve().parent;C=json.loads((T/'case.json').read_text());R=Path(C['suite'])
for name,expected in C['trusted_files'].items():
    if hashlib.sha256((R/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Protected file changed: '+name)
def main():
    action=sys.argv[1]
    if action=='build':
        src=Path(sys.argv[2])/'src'/('candidate.py' if C['id']=='softmax' else 'candidate.cu');dest=Path(sys.argv[3]);dest.mkdir(parents=True,exist_ok=True)
        if C['id']=='softmax':
            try:compile(src.read_text(),str(src),'exec')
            except SyntaxError as e:print(e);return 1
            shutil.copyfile(src,dest/'solution');return 0
        p=subprocess.run(['nvcc','-std=c++17','-O3','-arch=sm_90','-shared','-Xcompiler=-fPIC',str(src),'-o',str(dest/'solution')],capture_output=True,text=True);print(p.stdout+p.stderr,end='');return p.returncode
    binary=str(Path(sys.argv[2]).resolve());phase=sys.argv[3];seed=271 if phase=='confirmation' else 23
    specs=[(C['n'],seed+101)] if action=='benchmark' else [(n,s) for n in C['checks']+[C['n']] for s in [seed,seed+37]]
    rows=[];rc=0
    for n,s in specs:
        p=subprocess.run(['/scratch_p/nimarano/forest-reference-torch-20261023/bin/python',str(R/'gpu_extra_driver.py'),C['id'],binary,str(n),str(s),'bench' if action=='benchmark' else 'check'],capture_output=True,text=True,timeout=240)
        try:d=json.loads(p.stdout)
        except Exception:d={'correct':False,'error':(p.stdout+p.stderr)[-3000:]}
        rows.append(d)
        if p.returncode:rc=1;break
    result={'correct':rc==0,'cases':len(rows),'details':rows}
    if action=='benchmark' and rc==0:result.update(metric='protected_kernel_seconds',seconds=rows[0]['seconds'])
    print(json.dumps(result));return rc
if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,RuntimeError,subprocess.TimeoutExpired) as e:print(json.dumps({'infrastructure_error':str(e)}));sys.exit(70)
