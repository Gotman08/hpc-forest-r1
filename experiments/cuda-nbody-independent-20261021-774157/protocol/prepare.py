"""Prepare a fresh, separately scoped CUDA campaign without importing old optimizations."""
import copy
import hashlib
import json
import shlex
import shutil
import sys
import tarfile
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]/'outputs/hpc-forest-r1'
sys.path.insert(0,str(REPO/'src'))
from hpc_forest.config import DEFAULT, validate
from hpc_forest.model_skills import policy


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf8')


def main():
    artifact = HERE/'artifact'
    artifact.mkdir(exist_ok=False)
    payload = artifact/'payload'
    payload.mkdir()
    session = uuid.uuid4().hex
    remote = '/scratch_p/nimarano/hpc-forest-cuda-nbody-'+session
    source = Path('C:/Users/nicol/.gemini/antigravity/scratch/cuda_nbody_naive/nbody_naive.cu')
    original = source.read_text(encoding='utf8')
    # Mechanical extraction only: remove main/host headers, add C entry linkage.
    kernel = original[original.index('// Structure'):original.index('int main()')]
    kernel = kernel.replace('__global__ void nbody_step_naive(',
                            'extern "C" __global__ void nbody_step_naive(',1)
    src = payload/'source/src'
    src.mkdir(parents=True)
    (src/'nbody_kernel.cu').write_text(kernel,encoding='utf8',newline='\n')
    write(src/'launch.json',{'block':256,'items_per_block':256,'shared_memory_bytes':0})
    trusted = payload/'validation'
    trusted.mkdir()
    shutil.copyfile(source,trusted/'original.cu')
    shutil.copyfile(src/'nbody_kernel.cu',trusted/'reference.cu')
    shutil.copyfile(HERE/'protocol.py',trusted/'protocol.py')
    optimizer = source.parent/'optimizer'
    shutil.copyfile(optimizer/'optimizer_agent/use_harness.py',trusted/'use_harness.py')
    shutil.copyfile(optimizer/'SOURCE_COMMIT.txt',trusted/'evaluator-source-commit.txt')
    shutil.copytree(optimizer/'cuda_test_harness',payload/'cuda_test_harness',
        ignore=shutil.ignore_patterns('build*','cmake-build*','__pycache__','.git','out','CMakeFiles'))
    shutil.copytree(REPO/'src',payload/'project/src',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('pilot.py','cuda_evaluator.py'):
        shutil.copyfile(HERE/name,payload/name)
    statement = '''Optimize the supplied one-step gravitational N-body CUDA kernel for one NVIDIA GH200
on ROMEO ARM/aarch64. The only allocation used by official measurements is one GPU, four CPU cores.
Device-only C++17 is compiled with NVRTC CUDA 12.6.3, native compute capability from that GPU;
no global fast-math option. You may use supported CUDA device intrinsics with correct outputs.
Preserve the AoS Particle layout: seven float32 x,y,z,vx,vy,vz,mass (28 bytes).
Preserve entry extern "C" __global__ void nbody_step_naive(const Particle*,Particle*,int,float).
The input buffer is read-only. Output one complete updated state per particle.
The supplied physics uses G=1, float32 softening 0.001, updated velocity then updated position.
All sizes, positive varying masses, nonzero velocities, coincident positions, zero/negative dt must work.
All output values are checked, not just the printed first particle. Nonfinite outputs are invalid.
GPU original-reference comparison: atol 5e-5, rtol 2e-4; masses must remain exact.
An independent FP64 CPU oracle validates the reference, all small rows and 32 distributed large rows.
Search and independent confirmation use different input data. No benchmark-specific constants or input detection.
The sole primary objective is the geometric mean of CUDA-event kernel times for N=4096,8192,16384.
Compilation, transfers and process startup are excluded. Each size has 10 warmups and 100 timed launches.
Search evaluates three independent timing repeats; final confirmation uses five fresh repeats with alternated candidates.
Correctness also includes N=1,2,31,127,257,4095 and extreme positive mass for a single isolated particle.
Only edit src/nbody_kernel.cu and src/launch.json. Additional self-contained device helpers may go inside the kernel file.
The trusted host harness launches exactly this one kernel. Host code, extra kernels requiring extra launches,
host preprocessing and new host buffers are outside this interface. Choose any valid device implementation yourself.
launch.json must contain exactly block (1..1024), items_per_block (1..1048576), shared_memory_bytes (0..49152).
The host uses grid.x=ceil(N/items_per_block), block.x=block, other dimensions=1.
Those settings allow any correct per-block ownership scheme; they are not a performance recommendation.
Official docs and the user's existing ROMEO MCP are available. Consult relevant technical references and actual
target facts when useful. Never request an additional allocation or modify the protected evaluator, oracle or timing.
Mother chooses any useful N complementary research objectives from the actual problem and code.
The controller admits individual trials and serializes GPU measurements to avoid interference. All N research trees
start concurrently and each continues after its own measured feedback without waiting for another tree's generation.
At closure the same Mother conversation assembles the source programs in measured pairs;
research is permanently closed and no further models/trees may be launched. Final G is independently confirmed.
Original user source, supplied as data:
'''+original
    (payload/'statement.txt').write_text(statement,encoding='utf8',newline='\n')
    plan = {'scope':'cuda-nbody-luna-max-independent-v2','session_id':session,
        'model':'gpt-6-luna','effort':'max','subject':'cuda-nbody',
        'remote_root':remote,'wall_seconds':1800,'token_budget':None,
        'source_path':str(source),'source_sha256':sha(source),'created_at':time.time(),
        'completion':{'policy':'finish-started','postprocess_tokens':None,
            'token_policy':'observe-only','reserve_policy':'adaptive','confirm_final_g':True},
        'forest':{'policy':'mother','conversation':'persistent','integration':'pairwise'},
        'schedule':{'cycles':None,'trials_per_role_per_cycle':1,'integrations_per_cycle':0},
        'skills':policy(),'gpus':1,'cpus':4,'old_candidates_imported':False}
    write(payload/'plan.json',plan)
    config = copy.deepcopy(DEFAULT)
    config.update(problem='cuda-nbody',method='H',backend='codex',seed=23,
        completion=plan['completion'],forest={**plan['forest'],'statement':statement},
        schedule=plan['schedule'],skills=plan['skills'],minimum_gain=.03)
    config['budget'].update(wall_seconds=1800,tokens=None,mission_tokens=None,max_depth=0,
        search_slots=None,max_workers=1,confirmation_slots=3,confirmation_seconds=120,
        generation_seconds=600,infrastructure_retries=0)
    config['codex'] = {'model':'gpt-6-luna','reasoning_effort':'max','transport':'codex-mailbox',
        'mailbox_dir':remote+'/pending/mailbox','session_id':session}
    config['protocol'] = {
        'build':['{python}','{trusted}/protocol.py','build','{worktree}','{build}'],
        'check':['{python}','{trusted}/protocol.py','check','{binary}','{phase}'],
        'benchmark':['{python}','{trusted}/protocol.py','benchmark','{binary}','{phase}'],
        'repetitions':3,'confirmation_repetitions':5,'warmups':0,
        'timeout_seconds':240,'build_timeout_seconds':120,
        'environment':{'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1',
            'FOREST_CUDA_HARNESS':remote+'/harness-build/cuda_test_harness',
            'FOREST_CUDA_CACHE':remote+'/cache',
            'FOREST_GPU_TARGET':'NVIDIA GH200, one GPU; NVRTC CUDA 12.6.3',
            'PYTHONDONTWRITEBYTECODE':'1'}}
    config['harness'] = {'enabled':True,'max_attempts':3,'call_token_ceiling':None,
        'research':{'enabled':True,'corpus':None,'corpus_sha256':None,
            'allowed_hosts':['docs.nvidia.com','developer.nvidia.com','www.openmp.org',
                'www.mpi-forum.org','gcc.gnu.org','clang.llvm.org','www.intel.com']}}
    validate(config)
    write(payload/'settings.json',config)
    manifest = {p.relative_to(payload).as_posix():sha(p) for p in sorted(payload.rglob('*')) if p.is_file()}
    write(payload/'runtime-manifest.json',manifest)
    for name in ('plan.json','settings.json','runtime-manifest.json','statement.txt'):
        shutil.copyfile(payload/name,artifact/name)
    archive = artifact/'payload.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for path in sorted(payload.rglob('*')):
            if path.is_file():
                tar.add(path,arcname=path.relative_to(payload).as_posix(),recursive=False)
    runtime = {'python':str(HERE.parent/'hpc-forest-mcp-venv/Scripts/python.exe'),
        'codex_config':'C:/Users/nicol/.codex/config.toml',
        'codex_executable':'C:/Users/nicol/AppData/Local/OpenAI/Codex/bin/896a0166b774037a/codex.EXE'}
    remote_python = '/scratch_p/nimarano/hpc-forest-localmodels-20261015-r1/venv-r3/bin/python'
    q = shlex.quote
    command = '\n'.join(['set -euo pipefail','export PYTHONDONTWRITEBYTECODE=1',
        'export OPENBLAS_NUM_THREADS=1','export OMP_NUM_THREADS=1',
        'test -n "${CUDA_VISIBLE_DEVICES:-}"','test ! -e '+q(remote),
        "printf '%s  %s\\n' "+sha(archive)+' '+q(remote+'.tar.gz')+' | sha256sum -c -',
        'mkdir '+q(remote),'tar -xzf '+q(remote+'.tar.gz')+' -C '+q(remote),
        'export PYTHONPATH='+q(remote+'/project/src'),
        'export FOREST_CUDA_HARNESS='+q(remote+'/harness-build/cuda_test_harness'),
        'export FOREST_CUDA_CACHE='+q(remote+'/cache'),
        'export TMPDIR="${SLURM_TMPDIR:-/tmp}/forest-cuda-${SLURM_JOB_ID}"',
        'mkdir -p "$TMPDIR"','cd '+q(remote),
        'cmake -S cuda_test_harness -B harness-build -DCMAKE_BUILD_TYPE=Release',
        'cmake --build harness-build --parallel 4',
        q(remote_python)+' validation/protocol.py preflight validation cache > gpu-preflight.log',
        'cat gpu-preflight.log',
        'exec '+q(remote_python)+' -u pilot.py --root '+q(remote),''])
    state = {'repository':str(REPO),'artifact':str(artifact),'scope':plan['scope'],
        'session_id':session,'model':plan['model'],'effort':plan['effort'],'subject':plan['subject'],
        'target_seconds':1800,'tokens':None,'remote_root':remote,'remote_payload':remote+'.tar.gz',
        'payload_sha256':sha(archive),'runtime_manifest_sha256':sha(payload/'runtime-manifest.json'),
        'runtime':runtime,'job_command':command,'batch_command':'bash -lc '+q(command),
        'hosting':{'cpus_per_task':4,'gpus':1,'mem_gb':16,'time_limit':'02:00:00'},
        'user_request':'mtn refais un test CUDA N-body de 30 min avec Luna Max sans limite de tokens, vérifie que les N arbres avancent sans s’attendre, que Mother garde la même conversation et que G final est confirmé et exporté.',
        'source_sha256':sha(source),'created_at':time.time()}
    write(HERE/'state.json',state)
    write(HERE/'preparation.json',{'original_source_sha256':sha(source),
        'extracted_reference_sha256':sha(trusted/'reference.cu'),
        'extraction':'remove host includes and main; add extern C to entry only',
        'evaluator_source_commit_metadata':(optimizer/'SOURCE_COMMIT.txt').read_text().strip(),
        'evaluator_files_individually_hashed':True,'old_candidates_imported':False,
        'manifest_files':len(manifest),'payload_bytes':archive.stat().st_size,
        'core_verification_receipt':str(HERE.parent/'independent-fixes-20261021-b50004dd/verification.json')})
    print(json.dumps({'prepared':str(HERE),'session_id':session,'files':len(manifest),
        'bytes':archive.stat().st_size,'sha256':sha(archive)}))


if __name__ == '__main__':
    main()
