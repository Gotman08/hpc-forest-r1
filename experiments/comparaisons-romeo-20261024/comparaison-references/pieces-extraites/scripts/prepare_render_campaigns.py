from pathlib import Path
import json,shutil,uuid,time,hashlib,tarfile
R=Path(__file__).resolve().parent;TEMPLATE=R/'campaigns/argmin/payload'
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
cases=json.loads((R/'render-suite/cases.json').read_text());trusted=json.loads((R/'render-trusted-files.json').read_text())
headers=R/'render-headers'
if (headers/'include').exists():headers= headers/'include'
for f in headers.glob('*'):
    assert sha(f)==trusted['include/'+f.name]
descriptions={
'aobench':'Render the supplied ambient occlusion scene with the same geometry, intersections and full sample count: nsubsamples squared primary rays per pixel and the original 8 by 8 ambient rays at each hit. Never lower sample counts, resolution or skip shading. Random samples may be generated differently for safe parallelism; maintain uniform independent sampling. RGB output has width*height*3 floats. The fixed image check is RMSE <=.06 and absolute mean difference <=.015 against a scalar render with independent random samples; preserve this stochastic algorithm, not merely the threshold. Performance: 512x512 at 1 and 4 cores and 2048x2048 at 40 cores; checks also use nsubsamples=3.',
'volume':'Render the supplied low-resolution density volume with its camera. Preserve the original ray marching, transmittance, shadow, interpolation and sample steps; do not lower sampling quality. Output width*height floats. Full image tolerance .0005+.0005*abs(reference). Performance 896x1184 at 1, 4 and 40 cores. Correctness also checks scaled camera resolution and modified density.',
'raytracer':'Trace every pixel ray through the provided Sponza BVH and triangles, preserving the original intersection rules. Output width*height float depth and integer hit identifiers. Hit identifiers must match exactly; depth tolerance .0005+.0005*abs(reference). No precomputed/cached hits. Performance 900x900 at 1, 4 and 40 cores; checks also change camera and resolution.',
'deferred':'Render the supplied 1280x720 deferred-lighting frame, preserving all lights, geometry and shading. InputData and Framebuffer types are in include/deferred.h. Write all r/g/b uint8 framebuffer planes; tolerance at most one intensity level per component. Performance 1 and 4 cores, checks also alter light colors. Do not cache rendered frames; reusable scratch storage is allowed, with current-frame depth bounds and lighting recomputed on each invocation.'}
for c in cases:
    key=c['id'];a=R/'campaigns'/key
    if a.exists():continue
    p=a/'payload';p.mkdir(parents=True);shutil.copytree(TEMPLATE/'project',p/'project');(p/'source/src').mkdir(parents=True);(p/'validation').mkdir()
    shutil.copyfile(R/'render-suite/cases'/key/'src/candidate.cpp',p/'source/src/candidate.cpp');shutil.copytree(headers,p/'source/include')
    (p/'source/Makefile').write_text('all: build/solution\nbuild/solution: src/candidate.cpp\n\tmkdir -p build\n\tg++ -std=c++17 -O3 -march=native -fPIC -shared -fopenmp -Wl,-Bsymbolic -Iinclude $< -o $@\n')
    (p/'source/run.sh').write_text('#!/usr/bin/env bash\nset -euo pipefail\nexec "${FOREST_RENDER_SUITE:?}/render_driver" "$FOREST_RENDER_SUITE" '+key+' ./build/solution '+str(c['n'])+' 271 '+str(c['threads'])+' bench\n')
    case={**c,'suite':'/scratch_p/nimarano/forest-reference-render-20261023','trusted_files':{k:v for k,v in trusted.items() if k in ['render_driver','cases.json','cases/'+key+'/naive.so'] or k.startswith('include/')}}
    write(p/'validation/case.json',case);shutil.copyfile(R/'render_protocol.py',p/'validation/protocol.py');shutil.copyfile(TEMPLATE/'benchmark_evaluator.py',p/'benchmark_evaluator.py');shutil.copyfile(TEMPLATE/'pilot.py',p/'pilot.py')
    statement='Optimize the supplied original scalar renderer on AMD EPYC 9654 with GCC 14.2. Use the actual AB-MCTS research trees and persistent Mother memory/integration policy.\n'+descriptions[key]+'''\nEdit only src/candidate.cpp. Preserve extern C void run(RenderInput*,float*image,int*ids,int threads). The include/ files document the ABI and are immutable. Respect threads as the maximum CPU thread budget. Inputs are read-only. Fully overwrite the specified output on every call. No cached answers, external libraries, file/network access, timing or environment inspection, phase detection, hardcoded output or changes to the protected protocol. C++17, OpenMP and x86 intrinsics are available. Allocation inside run is timed. The timing excludes input generation, oracle and compilation. The optimized ISPC reference implementation is withheld. Explore independent topics, record failed trials, integrate memory and independently confirm final G.\n'''
    cfg=json.loads((TEMPLATE/'settings.json').read_text());cfg['problem']='reference-'+key;cfg['forest']['statement']=statement;cfg['protocol']['environment']={'OMP_NUM_THREADS':str(c['cpus']),'OPENBLAS_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'};cfg['protocol']['timeout_seconds']=1200;cfg['budget']['confirmation_seconds']=600
    session=uuid.uuid4().hex;remote='/scratch_p/nimarano/forest-reference-run-'+key+'-'+session;cfg['codex'].update(session_id=session,mailbox_dir=remote+'/pending/mailbox')
    plan=json.loads((TEMPLATE/'plan.json').read_text());plan.update(session_id=session,remote_root=remote,subject='reference-'+key,source_path=str(R/'render-suite/cases'/key/'src/candidate.cpp'),source_sha256=sha(p/'source/src/candidate.cpp'),created_at=time.time(),hardware='x64cpu',case_id=key,gpus=0,cpus=c['cpus'])
    for name,data in [('settings.json',cfg),('plan.json',plan)]:write(p/name,data);write(a/name,data)
    (p/'statement.txt').write_text(statement);(a/'statement.txt').write_text(statement)
    write(p/'runtime-manifest.json',{f.relative_to(p).as_posix():sha(f) for f in p.rglob('*') if f.is_file()})
    with tarfile.open(a/'payload.tar.gz','w:gz') as t:
        for f in p.iterdir():t.add(f,arcname=f.name)
    prep={'condition':key,'remote_root':remote,'remote_payload':remote+'.tar.gz','remote_results':remote+'.results.tar.gz','artifact':str(a),'session_id':session,'model_mcp':False,'payload_sha256':sha(a/'payload.tar.gz')};write(a/'preparation.json',prep)
    cmd=f'''root={remote}
test ! -e "$root"
echo '{prep['payload_sha256']}  {remote}.tar.gz' | sha256sum -c -
mkdir "$root"
tar -xzf "$root.tar.gz" -C "$root"
export PYTHONPATH="$root/project/src" PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
export FOREST_REFERENCE_DRIVER=/scratch_p/nimarano/forest-reference-render-20261023/render_driver
mkdir -p "$root/cache"
echo '{{"reference_phase_job":"781186","architecture":"x86_64"}}' > "$root/cache/preflight.json"
lscpu > "$root/allocation-cpu.txt"
cd "$root"
set +e
/scratch_p/nimarano/forest-reference-study-20261023-x64env/bin/python -u pilot.py --root "$root"
rc=$?
echo "$rc" > engine-exit-code.txt
tar -czf "$root.results.tar.gz" results-* allocation-cpu.txt engine-exit-code.txt
exit "$rc"
'''
    (a/'command.sh').write_text(cmd);print(key,c['cpus'],remote,flush=True)
