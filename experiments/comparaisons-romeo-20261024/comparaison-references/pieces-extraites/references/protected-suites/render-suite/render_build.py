from pathlib import Path
import json,os,subprocess,hashlib,shutil
R=Path(__file__).resolve().parent;os.chdir(R);logs=[]
def build(args):
    p=subprocess.run(args,capture_output=True,text=True);logs.append({'command':args,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr});(R/'build-log.json').write_text(json.dumps(logs,indent=2));
    if p.returncode:raise RuntimeError(p.stderr[-3000:])
cases=json.loads((R/'cases.json').read_text());ispc=next(Path('/scratch_p/nimarano/forest-reference-cpu-preflight-20261023').glob('ispc*/bin/ispc'))
for c in cases:
    folder=R/'reference'/c['folder'];stem=c['ispc_file']
    build([str(ispc),str(folder/(stem+'.ispc')),'--pic','-O2','--target=avx512skx-x16','-o',str(folder/'ref.o'),'-h',str(R/'include'/(stem+'_ispc.h'))])
shutil.copyfile(R/'reference/deferred/deferred.h',R/'include/deferred.h')
common=(R/'reference/deferred/common.cpp').read_text().replace('#include "../../common/timing.h"','').replace('lAlignedMalloc(nPixels, ALIGNMENT_BYTES)','lAlignedMalloc(nPixels+64, ALIGNMENT_BYTES)')
(R/'common-adapted.cpp').write_text(common)
flags=['g++','-std=c++17','-O3','-march=native','-fopenmp','-I'+str(R/'include')]
build(flags+['render_driver.cpp','common-adapted.cpp','-ldl','-o','render_driver'])
for c in cases:
    d=R/'cases'/c['id'];extra=[str(R/'reference'/c['folder']/'ref.o'),str(R/'reference/tasksys.cpp')]
    build(flags+['-shared','-fPIC','-Wl,-Bsymbolic',str(d/'src/candidate.cpp'),'-o',str(d/'naive.so')])
    for v in ['optimized','tasks']:
        if not (d/(v+'.cpp')).exists():continue
        build(flags+['-shared','-fPIC','-Wl,-Bsymbolic',str(d/(v+'.cpp')),*extra,'-o',str(d/(v+'.so'))])
    print(c['id'],'BUILT',flush=True)
data=R/'data'
if not data.exists():data.symlink_to(Path('/scratch_p/nimarano/forest-reference-cpu-preflight-20261023/examples/cpu'),target_is_directory=True)
(R/'trusted-files.json').write_text(json.dumps({p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [R/'render_driver',R/'cases.json',*list((R/'include').glob('*')),*list((R/'cases').glob('*/naive.so'))]},indent=2))
