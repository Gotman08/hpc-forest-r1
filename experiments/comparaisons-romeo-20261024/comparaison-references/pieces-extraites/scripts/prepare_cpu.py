from pathlib import Path
import json, shutil, tarfile, hashlib
ROOT=Path(__file__).resolve().parent
P=ROOT/'cpu-preflight'
P.mkdir(exist_ok=True)
U=ROOT/'upstream'
for name in ['examples','popcount','fastbase64','fastvalidate-utf-8','amh-code']:
    dest=P/name
    if not dest.exists(): shutil.copytree(U/name,dest,ignore=shutil.ignore_patterns('.git','__pycache__'))
# An explicit local portability adapter: respect Slurm/taskset affinity.
tasks=P/'examples/common/tasksys.cpp'
s=tasks.read_text()
s=s.replace('sysconf(_SC_NPROCESSORS_ONLN)', 'forest_allocated_cores()')
s='#include <sched.h>\nstatic long forest_allocated_cores() { cpu_set_t c; CPU_ZERO(&c); if (sched_getaffinity(0,sizeof(c),&c)) return 1; return CPU_COUNT(&c); }\n'+s
tasks.write_text(s)
cm=P/'examples/cpu/CMakeLists.txt'
s=cm.read_text()
names={'aobench','deferred','mandelbrot_tasks','noise','options','rt','stencil','volume_rendering'}
import re
s=re.sub(r'^add_subdirectory\(([^)]+)\)',lambda m:m[0] if m[1] in names else '# excluded unrelated '+m[0],s,flags=re.M)
cm.write_text(s)
shutil.copyfile(U/'ispc-v1.32.0-linux.tar.gz',P/'ispc-v1.32.0-linux.tar.gz')
with tarfile.open(ROOT/'cpu-preflight.tar.gz','w:gz') as t:
    for p in sorted(P.iterdir()):t.add(p,arcname=p.name)
print(json.dumps({'archive':str(ROOT/'cpu-preflight.tar.gz'),'sha256':hashlib.sha256((ROOT/'cpu-preflight.tar.gz').read_bytes()).hexdigest()}))
