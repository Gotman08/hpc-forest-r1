from pathlib import Path
import sys,os,json,subprocess,hashlib
T=Path(__file__).resolve().parent
C=json.loads((T/'case.json').read_text())
R=Path(C['suite'])
for name,expected in C.get('trusted_binaries',{}).items():
    if hashlib.sha256((R/name).read_bytes()).hexdigest()!=expected:
        print(json.dumps({'infrastructure_error':'Protected reference binary changed: '+name}));sys.exit(70)

def build(source,dest):
    src=Path(source)/'src/candidate.cu';dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    if not src.is_file() or src.is_symlink():return 1
    # The model receives this single editable translation unit. The driver,
    # comparison implementations, inputs and compiler switches stay protected.
    args=['nvcc','-std=c++17','-O3','-arch=sm_90','-shared','-Xcompiler=-fPIC',str(src),'-o',str(dest/'solution')]
    p=subprocess.run(args,capture_output=True,text=True)
    print(p.stdout+p.stderr,end='')
    return p.returncode

def invoke(binary,n,seed,reps,warm):
    args=[str(R/'gpu_driver'),str(C['kind']),str(R/'references.so'),str(Path(binary).resolve()),'1',str(n),str(seed),str(reps),str(warm),'1']
    p=subprocess.run(args,capture_output=True,text=True,timeout=230)
    try:d=json.loads(p.stdout)
    except Exception:d={'correct':False,'error':(p.stdout+p.stderr)[-3000:]}
    if p.returncode==70:raise RuntimeError(d)
    return d,p.returncode

def main():
    action=sys.argv[1]
    if action=='build':return build(sys.argv[2],sys.argv[3])
    binary=sys.argv[2];phase=sys.argv[3]
    seed=271 if phase=='confirmation' else 23
    rows=[];code=0
    for n in (C['checks']+[C['n']] if action=='check' else [C['n']]):
        for actual_seed in ([seed,seed+37] if action=='check' else [seed+101]):
            row,rc=invoke(binary,n,actual_seed,0 if action=='check' else C['reps'],0 if action=='check' else C['warmups'])
            rows.append(row);code=max(code,rc)
            if rc:break
        if code:break
    result={'correct':code==0,'cases':len(rows),'details':rows}
    if action=='benchmark' and not code:result.update(metric='protected_kernel_seconds',seconds=rows[0]['latency_ms']/1000)
    print(json.dumps(result))
    return code

if __name__=='__main__':
    try:raise SystemExit(main())
    except (RuntimeError,subprocess.TimeoutExpired) as e:
        print(json.dumps({'correct':False,'infrastructure_error':str(e)}));raise SystemExit(70)
