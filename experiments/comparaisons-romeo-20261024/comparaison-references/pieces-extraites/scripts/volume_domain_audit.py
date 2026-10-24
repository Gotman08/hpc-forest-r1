from pathlib import Path
import subprocess,json,os,hashlib
R=Path(__file__).resolve().parent;S=Path('/scratch_p/nimarano/forest-reference-render-20261023');F=Path('/scratch_p/nimarano/forest-reference-render-final-volume-20261023')
source=(F/'render_final_driver.cpp').read_text()
old='image(count+32,0),expected(count+32,0)'
assert source.count(old)==1
# Preserve the numerical oracle and checks; extra output guards make the
# reference's known out-of-domain tile writes observable without heap damage.
source=source.replace(old,'image(count+4*ctx.width+32,0),expected(count+4*ctx.width+32,0)')
(R/'guarded_driver.cpp').write_text(source)
cmd=['g++','-std=c++17','-O3','-march=native','-fopenmp','-I'+str(S/'include'),str(R/'guarded_driver.cpp'),str(S/'common-adapted.cpp'),'-ldl','-o',str(R/'guarded_driver')]
p=subprocess.run(cmd,capture_output=True,text=True);(R/'build.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr
variants=[('naive',S/'cases/volume/naive.so'),('optimized',S/'cases/volume/optimized.so'),('tasks',S/'cases/volume/tasks.so'),('selected',F/'volume/selected/candidate.so'),('final_g',F/'volume/final_g/candidate.so')]
rows=[]
for n in [224,336,96,128]:
    height=int(n*1184/896);supported=n%4==0 and height%4==0
    for name,library in variants:
        if not supported and name not in ['optimized','tasks']:continue
        command=[str(R/'guarded_driver'),str(S),'volume',str(library),str(n),'1009','4','check']
        q=subprocess.run(command,capture_output=True,text=True,timeout=120)
        try:m=json.loads(q.stdout)
        except Exception:m={'error':(q.stdout+q.stderr)[-2000:]}
        rows.append({'variant':name,'n':n,'width':n,'height':height,'reference_supported_domain':supported,'exit_code':q.returncode,'measurement':m,'command':command});print(json.dumps(rows[-1]),flush=True)
result={'job':os.environ['SLURM_JOB_ID'],'source_precondition':'volume_tile requires both tile extents divisible by 4; original ISPC comment lines 243-245','guard_change':'Only output padding was extended by 4 image rows; immutable numerical oracle and checks; not used for performance measurements','source_sha256':hashlib.sha256((S/'reference/volume_rendering/volume.ispc').read_bytes()).hexdigest(),'driver_sha256':hashlib.sha256((R/'guarded_driver.cpp').read_bytes()).hexdigest(),'records':rows}
(R/'audit.json').write_text(json.dumps(result,indent=2))
assert all(r['measurement'].get('correct') is True for r in rows if r['reference_supported_domain'])
assert all(r['measurement'].get('correct') is False for r in rows if not r['reference_supported_domain'])
print('VOLUME_DOMAIN_AUDIT_DONE')
