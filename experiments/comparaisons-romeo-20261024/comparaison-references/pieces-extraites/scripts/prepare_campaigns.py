from pathlib import Path
import json,shutil,os,uuid,time,hashlib,tarfile,sys
R=Path(__file__).resolve().parent
ROOT=R.parents[1]
OLD=Path(r'C:\Users\nicol\Documents\Codex\2026-10-20\new-chat')
FROZEN=OLD/'work/cuda-memory-reliability-20261023/payload'
OUT=ROOT/'outputs/comparaison-references'

def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare(case):
    key=case['id'];a=R/'campaigns'/key;p=a/'payload'
    if p.exists():return
    p.mkdir(parents=True)
    shutil.copytree(FROZEN/'project',p/'project',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(R/'gpu-suite/cases'/key/'src',p/'source/src')
    (p/'validation').mkdir()
    shutil.copyfile(R/'gpu_protocol.py',p/'validation/protocol.py')
    case={**case,'suite':'/scratch_p/nimarano/forest-reference-gpu-suite-20261023'}
    write(p/'validation/case.json',case)
    shutil.copyfile(R/'benchmark_evaluator.py',p/'benchmark_evaluator.py')
    pilot=(FROZEN/'pilot.py').read_text()
    pilot=pilot.replace('from cuda_evaluator import CudaEvaluator','from benchmark_evaluator import BenchmarkEvaluator')
    pilot=pilot.replace('module.Evaluator = CudaEvaluator','module.Evaluator = BenchmarkEvaluator')
    pilot=pilot.replace('plan["scope"] not in {"cuda-nbody-luna-max-independent-v2", "cuda-nbody-luna-max-memory-v1"}','plan["scope"] != "reference-comparison-luna-max-v1"')
    pilot=pilot.replace('(plan["scope"] == "cuda-nbody-luna-max-memory-v1") != guided(settings)','not guided(settings)')
    pilot=pilot.replace('"geomean_cuda_event_seconds"','"protected_kernel_seconds"')
    pilot=pilot.replace('file_digest(Path(os.environ["FOREST_CUDA_HARNESS"]))','file_digest(Path(os.environ["FOREST_REFERENCE_DRIVER"]))')
    pilot=pilot.replace('"romeo-cuda-nbody-"','"romeo-reference-"')
    (p/'pilot.py').write_text(pilot)
    session=uuid.uuid4().hex;remote='/scratch_p/nimarano/forest-reference-run-'+key+'-'+session
    cfg=json.loads((FROZEN/'settings.json').read_text());cfg['problem']='reference-'+key
    descriptions={
      'sgemm':'Compute row-major FP32 square SGEMM C = alpha*(A@B)+beta*C. The performance case is M=N=K=4096, alpha=0.5, beta=3.0. Correctness also checks sizes 128,256,512 and varied signed random values. Match full FP32 cuBLAS within absolute error 0.01. No reduced-precision TF32, FP16 or BF16.',
      'transpose':'Transpose a square FP32 matrix out of place, writing C[col*n+row]=A[row*n+col]. Performance n=1024, correctness n=32,64,256,1024. Sizes are positive multiples of 32. Output must be bit-exact.',
      'stencil_y':'Compute exactly the supplied eighth-order Y derivative on a fixed 64x64x64 FP32 mesh. Preserve the supplied periodic halo convention (period 63 at the endpoints) and coefficients 63*[4/5,-1/5,4/105,-1/280]. Inputs vary and may be signed. Compare to an independent double-precision scalar oracle with abs error <=5e-5+2e-6*abs(reference).'
    }
    statement='''Optimize the supplied baseline on one NVIDIA GH200 with CUDA 12.6.3. Use the real independent AB-MCTS research trees and persistent Mother memory/integration policy. Choose useful topics yourself.\n'''+descriptions[key]+'''
Edit only src/candidate.cu. Preserve the extern C host entry point:
void run(const float*A,const float*B,float*C,float*scratch,int n,int m,int k,float alpha,float beta).
The host provides contiguous device buffers, n=m=k for square matrices, and scratch of at least n*n+65536 floats (64^3+65536 for the derivative). A and B are read-only. C must be fully produced. Do not overwrite any buffer or allocate beyond the declared storage. Scratch contents must not be assumed initialized between calls. The call uses the default CUDA stream; custom device helper functions and multiple launches are allowed. The full run is timed using CUDA events, with allocation, transfers, compilation and correctness checks excluded. Use actual CUDA source, no external optimized math library calls or other resources. Do not read files, environment variables, timers or benchmark state to detect inputs or phases. No persistent cached answers; every invocation must compute its output for the current input. Input dimensions and valid numerical invariants may be specialized.
The driver and oracle are protected. Development harness checks only search inputs; fresh confirmation uses independent seeds. Candidate GPU tests are serialized by the controller. Record failures and measured evidence, integrate after research closes, and independently confirm final G. No new allocations. The published optimized implementations are withheld from the source workspace.
'''
    cfg['forest']['statement']=statement
    cfg['protocol']['build_timeout_seconds']=180
    cfg['protocol']['environment']={'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1','FOREST_GPU_TARGET':'NVIDIA GH200 CUDA 12.6.3'}
    cfg['codex'].update(session_id=session,mailbox_dir=remote+'/pending/mailbox')
    plan=json.loads((FROZEN/'plan.json').read_text())
    plan.update(scope='reference-comparison-luna-max-v1',session_id=session,remote_root=remote,subject='reference-'+key,source_path=str(R/'gpu-suite/cases'/key/'src/candidate.cu'),source_sha256=sha(p/'source/src/candidate.cu'),created_at=time.time(),hardware='armgpu',case_id=key)
    for name,value in [('settings.json',cfg),('plan.json',plan)]:write(p/name,value);write(a/name,value)
    (p/'statement.txt').write_text(statement);(a/'statement.txt').write_text(statement)
    write(p/'runtime-manifest.json',{f.relative_to(p).as_posix():sha(f) for f in p.rglob('*') if f.is_file()})
    with tarfile.open(a/'payload.tar.gz','w:gz') as t:
        for f in sorted(p.iterdir()):t.add(f,arcname=f.name)
    prep={'condition':key,'remote_root':remote,'remote_payload':remote+'.tar.gz','remote_results':remote+'.results.tar.gz','artifact':str(a),'session_id':session,'model_mcp':False,'payload_sha256':sha(a/'payload.tar.gz')}
    write(a/'preparation.json',prep)
    target=OUT/'protocol'/key;target.mkdir(parents=True,exist_ok=True)
    for f in ['settings.json','plan.json','statement.txt','preparation.json']:shutil.copyfile(a/f,target/f)
    print(json.dumps(prep),flush=True)

if __name__=='__main__':
    cases=json.loads((R/'gpu-suite/cases.json').read_text())
    for case in cases:prepare(case)
