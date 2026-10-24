from pathlib import Path
import json,shutil,uuid,time,hashlib,tarfile
R=Path(__file__).resolve().parent;TEMPLATE=R/'campaigns/sgemm/payload';OUT=R.parents[1]/'outputs/comparaison-references/protocol'
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
descriptions={
'popcount':'For each pass j from 0 to parameter-1 and element i from 0 to n-1, update uint32 result += popcount(uint32(input1[i]) XOR result), starting at zero. Preserve unsigned 32-bit wraparound and this loop-carried dependency. Write one uint32. Benchmark n=1000, parameter=100, one core.',
'argmin':'Return the first index of the smallest signed int32 value among n=8192 values. Input has 64-byte alignment. Cover random, decreasing, equal, repeated minima and INT32 extrema. One core. Both random and decreasing inputs are benchmarked in final validation.',
'blackscholes':'Compute the exact supplied FP32 Black-Scholes implementation with its CND approximation. input1 contains 5 consecutive arrays of length n: S,X,T,r,v; output is n floats. Match abs error <=.001+5e-5*abs(reference). Performance uses published constants [100,98,2,.02,5]; correctness also tests varied per-element inputs. All entries must be processed, with no hardcoded output.',
'binomial':'Compute the supplied 64-step FP32 binomial put algorithm exactly as specified by the baseline, including its existing endpoint convention. input1 contains 5 consecutive arrays of length n: S,X,T,r,v; output is n floats. Match abs error <=.001+5e-5*abs(reference). Performance uses published constants [100,98,2,.02,5]; correctness tests varied per-element inputs. All entries must be processed, with no hardcoded output.',
'noise':'Compute the supplied Perlin noise and turbulence image. input1 is four floats x0,y0,x1,y1, output is an n by n FP32 image. n=768 performance, smaller checks and shifted bounds. Match abs error <=5e-5+5e-5*abs(reference). One core.',
'mandelbrot':'Compute the supplied Mandelbrot iteration counts exactly for a width=(3*n/2), height=n image; input1 contains x0,y0,x1,y1. parameter is the maximum count (512); output is width*height int32 values. n=1024 performance; smaller checks and shifted bounds. No approximation of membership or iteration counts. Benchmark one and four CPU cores.',
'stencil3d':'Compute the supplied 6 time steps of the 3D finite-difference stencil. input1 contains n^3 FP32 initial even-grid values; input2 contains n^3 vsq values. Output contains both consecutive n^3 buffers (even then odd), initialized as in the baseline before computing. Coefficients [.5,-.25,.125,-.0625], interior [4,n-4) on all axes. Preserve boundaries. n=256 benchmark, smaller checks. Abs error <=5e-5+5e-5*abs(reference). Benchmark one and four cores.',
'base64':'Decode valid standard padded Base64 bytes from input1 (n bytes). Output starts with decoded byte count as uint64 at offset 0; bytes at offset 8..15 are reserved; decoded data begins at byte offset 16. Performance uses the upstream Lena image: n=141020 and 105764 decoded bytes. Check random valid data and other lengths. One core; output must be exact.',
'utf8':'Validate UTF-8 input1 of n bytes according to Unicode scalar-value rules (reject malformed continuations, overlong encodings, surrogates, values >0x10ffff, truncated sequences). Write uint32 1 for valid and 0 otherwise. n=65536 performance on valid mixed-width text, also ASCII and malformed correctness checks. One core. The supplied baseline contains a documented correctness repair of the historical benchmark validator.',
'gemm_cpu':'Compute row-major FP32 C=A@B, from input1=A and input2=B; completely overwrite output C, with no accumulation across invocations. n=1024 performance, checks n=32,128. Inputs vary and include signed values. Match an independent FP64 oracle with abs error <=.002+5e-5*abs(reference). At most eight CPU threads. No external BLAS library calls.'}
cases=json.loads((R/'cpu-suite/cases.json').read_text());files=json.loads((R/'cpu-trusted-files.json').read_text())
for case in cases:
    key=case['id'];a=R/'campaigns'/key
    if a.exists():continue
    p=a/'payload';p.mkdir(parents=True)
    shutil.copytree(TEMPLATE/'project',p/'project');(p/'source/src').mkdir(parents=True);(p/'validation').mkdir()
    source=(R/'cpu-suite/cases'/key/'src/candidate.cpp').read_text()
    if key=='utf8':
        source=source.replace('bytes[index++] > 0xBF','(bytes[index++] & 0xC0) != 0x80').replace('byte2 > 0xBF','(byte2 & 0xC0) != 0x80').replace('(((byte1 << 28) + (byte2 - 0x90)) >> 30) != 0','(byte1 > 0xF4 || (byte1 == 0xF0 && byte2 < 0x90) || (byte1 == 0xF4 && byte2 > 0x8F))')
    (p/'source/src/candidate.cpp').write_text(source)
    (p/'source/Makefile').write_text('all: build/solution\nbuild/solution: src/candidate.cpp\n\tmkdir -p build\n\tg++ -std=c++17 -O3 -march=native -fPIC -shared -fopenmp -Wl,-Bsymbolic $< -o $@\n')
    (p/'source/run.sh').write_text('#!/usr/bin/env bash\nset -euo pipefail\nexec "${FOREST_PYTHON:-python3}" "${FOREST_REFERENCE_SUITE:?}/cpu_driver.py" '+key+' ./build/solution '+str(case['n'])+' 271 '+str(case['threads'])+' bench\n')
    cpus=case.get('max_threads',case['threads']);perf=[[case['n'],case['threads']]]
    if case.get('ispc_tasks'):perf=[[case['n'],1],[case['n'],4]]+([[2097152,40]] if cpus==40 else [])
    c={**case,'suite':'/scratch_p/nimarano/forest-reference-cpu-suite-20261023','performance':perf,'trusted_files':{k:v for k,v in files.items() if k in ['cpu_driver.py','cases.json','build/timing.so','cases/'+key+'/naive.so']}}
    write(p/'validation/case.json',c);shutil.copyfile(R/'cpu_protocol.py',p/'validation/protocol.py')
    ev=(R/'benchmark_evaluator.py').read_text().replace("assert math.isclose(v,d['details'][0]['latency_ms']/1000,rel_tol=1e-10)","assert math.isclose(v,math.exp(sum(math.log(x['seconds']) for x in d['details'])/len(d['details'])),rel_tol=1e-10)")
    (p/'benchmark_evaluator.py').write_text(ev)
    pilot=(TEMPLATE/'pilot.py').read_text().replace('platform.machine() != "aarch64"','platform.machine() != "x86_64"').replace('or not os.environ.get("CUDA_VISIBLE_DEVICES")','or bool(os.environ.get("CUDA_VISIBLE_DEVICES"))').replace('!= 4','!= plan["cpus"]').replace('os.environ["CUDA_VISIBLE_DEVICES"]','os.environ.get("CUDA_VISIBLE_DEVICES", "")')
    (p/'pilot.py').write_text(pilot)
    statement='Optimize the supplied baseline on AMD EPYC 9654 with GCC 14.2. Use the actual AB-MCTS research trees and persistent Mother memory/integration policy.\n'+descriptions[key]+'''
Edit only src/candidate.cpp. Keep extern C void run(const void*input1,const void*input2,void*output,int n,int parameter,int threads). Respect the threads argument as the CPU thread budget. Inputs are read-only and 64-byte aligned. Overwrite the full specified output on every call; no cached answers, external tools or libraries, filesystem, environment inspection, timing inspection or phase detection. Ordinary C++17, OpenMP and x86 intrinsics are available. Do not modify the protected correctness or timing protocol. Scratch allocation inside run is allowed and included in timing. The harness measures native wall-clock time, excluding input generation, oracle and compilation. Search and confirmation use different seeds. Numerical tolerances are fixed. The optimized reference source is withheld. Choose topics independently, record failed attempts, complete memory integration and independently confirm final G.
'''
    cfg=json.loads((TEMPLATE/'settings.json').read_text());cfg['problem']='reference-'+key;cfg['forest']['statement']=statement;cfg['protocol']['environment']={'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':str(cpus),'PYTHONDONTWRITEBYTECODE':'1'};cfg['protocol']['timeout_seconds']=300;cfg['budget']['confirmation_seconds']=300
    session=uuid.uuid4().hex;remote='/scratch_p/nimarano/forest-reference-run-'+key+'-'+session;cfg['codex'].update(session_id=session,mailbox_dir=remote+'/pending/mailbox')
    plan=json.loads((TEMPLATE/'plan.json').read_text());plan.update(session_id=session,remote_root=remote,subject='reference-'+key,source_path=str(R/'cpu-suite/cases'/key/'src/candidate.cpp'),source_sha256=sha(p/'source/src/candidate.cpp'),created_at=time.time(),hardware='x64cpu',case_id=key,gpus=0,cpus=cpus)
    for name,data in [('settings.json',cfg),('plan.json',plan)]:write(p/name,data);write(a/name,data)
    (p/'statement.txt').write_text(statement);(a/'statement.txt').write_text(statement)
    write(p/'runtime-manifest.json',{f.relative_to(p).as_posix():sha(f) for f in p.rglob('*') if f.is_file()})
    with tarfile.open(a/'payload.tar.gz','w:gz') as t:
        for f in p.iterdir():t.add(f,arcname=f.name)
    prep={'condition':key,'remote_root':remote,'remote_payload':remote+'.tar.gz','remote_results':remote+'.results.tar.gz','artifact':str(a),'session_id':session,'model_mcp':False,'payload_sha256':sha(a/'payload.tar.gz')}
    write(a/'preparation.json',prep)
    cmd=f'''root={remote}
test ! -e "$root"
echo '{prep['payload_sha256']}  {remote}.tar.gz' | sha256sum -c -
mkdir "$root"
tar -xzf "$root.tar.gz" -C "$root"
export PYTHONPATH="$root/project/src" PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
export FOREST_REFERENCE_DRIVER=/scratch_p/nimarano/forest-reference-cpu-suite-20261023/cpu_driver.py
mkdir -p "$root/cache"
echo '{{"reference_phase_job":"781157","architecture":"x86_64"}}' > "$root/cache/preflight.json"
lscpu > "$root/allocation-cpu.txt"
cd "$root"
set +e
/scratch_p/nimarano/forest-reference-study-20261023-x64env/bin/python -u pilot.py --root "$root"
rc=$?
echo "$rc" > engine-exit-code.txt
tar -czf "$root.results.tar.gz" results-* allocation-cpu.txt engine-exit-code.txt
exit "$rc"
'''
    (a/'command.sh').write_text(cmd)
    dest=OUT/key;dest.mkdir(parents=True,exist_ok=True)
    for name in ['plan.json','settings.json','preparation.json','statement.txt']:shutil.copyfile(a/name,dest/name)
    print(key,cpus,remote,flush=True)
