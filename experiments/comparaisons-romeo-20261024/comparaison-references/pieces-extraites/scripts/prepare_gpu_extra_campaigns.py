from pathlib import Path
import json,shutil,uuid,time,hashlib,tarfile
R=Path(__file__).resolve().parent;T=R/'campaigns/sgemm/payload';S=R/'gpu-extra'
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
desc={
'reduction':'Reduce n signed int32 integers to one exact int32 sum. Values are bounded to [-5,5], so the true sum fits int32. Performance n=4194304 (2^22); checks include n=1,127,1024,65536 and performance n. input1=x; input2,input3 ignored. output has one int32; scratch contains 2*n+65536 int32 values. Complete the entire reduction on device, not only the first stage.',
'sumabs':'Compute one FP32 sum(abs(x)) for n FP32 values. Performance n=268435456 (exactly 1 GiB of input). Checks include 1,127,1024,1048576 and performance n. input1=x; other inputs ignored; output one float; scratch n+65536 floats. Each call must reset/overwrite output. Compare to an independent FP64 sum with absolute error <=.001+2e-4*abs(reference). Allocation and transfers excluded; all launches and necessary resets included.',
's4convd':'Compute depthwise same-length convolution forward and both gradients. input1=x[B,H,L], input2=k[H,K], input3=gy[B,H,L], row major FP32. API n=B,h=H,l=L,ks=K. Performance B=16384,H=128,L=48,K=47. Output is contiguous [y.flatten(),gx.flatten(),gk.flatten()] of 2*B*H*L+H*K floats. scratch has 2*B*H*L+65536 floats. y[b,h,t]=sum_j x[b,h,t+j-K/2]*k[h,j] with zero padding, gx and gk are exact derivatives contracted with gy. Compare all outputs against independent FP64 conv1d/autograd; y,gx atol2e-5 and gk atol.005, all rtol2e-4. Calls must produce fresh outputs without accumulation between calls. All three kernels and resets are timed together. Full FP32, no TF32/FP16/BF16.',
'softmax':'Optimize the provided Python function run(x) computing row-wise numerically stable FP32 softmax. Input x is a contiguous CUDA FP32 matrix, performance shape 4096x4096; correctness also checks 32x32,97x97,781x781 and independent random inputs. Return a same-shape CUDA FP32 tensor; do not modify x. Torch tensor allocation and Triton custom kernels are allowed, but do not call torch.softmax or another existing optimized softmax. Error <=1e-6+1e-5*abs(FP64 reference). Performance uses triton.testing.do_bench identically for naive reference, official tutorial and your implementation, including allocations and host launches but excluding JIT warmup. Edit only src/candidate.py.'}
for c in json.loads((S/'cases.json').read_text()):
    key=c['id'];a=R/'campaigns'/key
    if a.exists():continue
    p=a/'payload';p.mkdir(parents=True);shutil.copytree(T/'project',p/'project');shutil.copytree(S/'cases'/key/'src',p/'source/src');(p/'validation').mkdir()
    ext='py' if key=='softmax' else 'cu';src=p/'source/src'/('candidate.'+ext)
    if key=='reduction':
        code=src.read_text();start=code.index('/* This version uses contiguous');end=code.index('extern "C" void run');src.write_text(code[:start]+'\n#endif\n'+code[end:])
    if key=='sumabs':
        code=src.read_text().replace('template<bool ABS> ','').replace('ABS?fabsf(x[i]):x[i]','x[i]').replace('sum<false>','sum');src.write_text(code)
    (p/'source/Makefile').write_text('all: build/solution\nbuild/solution: src/candidate.'+ext+'\n\tmkdir -p build\n\t'+('cp $< $@' if ext=='py' else 'nvcc -std=c++17 -O3 -arch=sm_90 -shared -Xcompiler=-fPIC $< -o $@')+'\n')
    (p/'source/run.sh').write_text('#!/usr/bin/env bash\nset -euo pipefail\nexec "${FOREST_TORCH_PYTHON:?}" "${FOREST_REFERENCE_SUITE:?}/gpu_extra_driver.py" '+key+' ./build/solution '+str(c['n'])+' 271 bench\n')
    case={**c,'suite':'/scratch_p/nimarano/forest-reference-gpu-extra-20261023','trusted_files':{name:sha(R/name) if name=='gpu_extra_driver.py' else sha(S/name) for name in ['gpu_extra_driver.py','cases.json']}}
    write(p/'validation/case.json',case);shutil.copyfile(R/'gpu_extra_protocol.py',p/'validation/protocol.py');shutil.copyfile(R/'benchmark_evaluator.py',p/'benchmark_evaluator.py');shutil.copyfile(T/'pilot.py',p/'pilot.py')
    statement='Optimize on one NVIDIA GH200 with CUDA 12.6.3. Use the actual AB-MCTS research trees and persistent Mother memory/integration policy.\n'+desc[key]
    if key!='softmax':statement+='\nEdit only src/candidate.cu. Preserve extern C void run(const void*x,const void*k,const void*gy,void*out,void*scratch,int n,int h,int l,int ks). All pointers are device memory owned by the host. Use the default CUDA stream. Do not read beyond buffers. Scratch is not guaranteed initialized. No external optimized library calls; ordinary CUDA primitives and CUB block primitives are allowed.'
    statement+='\nNo cached answers, filesystem or environment inspection, timing inspection, phase detection, or external tools. Every call must compute on the current input. Immutable reference implementations and correctness checks are withheld from source. Choose useful topics independently, record failures, complete memory integration and independently confirm final G. No additional allocations or devices.\n'
    cfg=json.loads((T/'settings.json').read_text());cfg['problem']='reference-'+key;cfg['forest']['statement']=statement;cfg['protocol']['timeout_seconds']=600;cfg['budget']['confirmation_seconds']=600
    session=uuid.uuid4().hex;remote='/scratch_p/nimarano/forest-reference-run-'+key+'-'+session;cfg['codex'].update(session_id=session,mailbox_dir=remote+'/pending/mailbox')
    plan=json.loads((T/'plan.json').read_text());plan.update(session_id=session,remote_root=remote,subject='reference-'+key,source_path=str(src),source_sha256=sha(src),created_at=time.time(),case_id=key)
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
export FOREST_REFERENCE_DRIVER=/scratch_p/nimarano/forest-reference-gpu-extra-20261023/gpu_extra_driver.py
mkdir -p "$root/cache"
echo '{{"reference_phase_job":"781161","architecture":"aarch64"}}' > "$root/cache/preflight.json"
lscpu > "$root/allocation-cpu.txt"
nvidia-smi -q > "$root/allocation-gpu.txt"
cd "$root"
set +e
/scratch_p/nimarano/hpc-forest-localmodels-20261015-r1/venv-r3/bin/python -u pilot.py --root "$root"
rc=$?
echo "$rc" > engine-exit-code.txt
tar -czf "$root.results.tar.gz" results-* allocation-cpu.txt allocation-gpu.txt engine-exit-code.txt
exit "$rc"
''';(a/'command.sh').write_text(cmd);print(key,remote,flush=True)
