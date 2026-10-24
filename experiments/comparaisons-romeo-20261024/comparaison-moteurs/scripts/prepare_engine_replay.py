"""Freeze all valid newly produced CUDA sources and historical winner controls."""
from pathlib import Path
import hashlib
import json
import shlex
import shutil
import tarfile
import time
import uuid
from engine_study import ROOT, OLD, CONDITIONS, read, write, sha

BASE=ROOT/'outputs/comparaison-moteurs'
HISTORY=ROOT/'outputs/comparaison-historique'

def prepare():
    folder=ROOT/'work/engine-final-replay'
    folder.mkdir(exist_ok=False)
    payload=folder/'payload'
    payload.mkdir()
    template=OLD/'work/cuda-memory-reliability-20261023/payload'
    for name in ['validation','cuda_test_harness']:
        shutil.copytree(template/name,payload/name)
    shutil.copyfile(ROOT/'work/gpu_replay.py',payload/'gpu_replay.py')
    variants={}
    def add(files,origin):
        body=files['src/nbody_kernel.cu'];launch=files['src/launch.json']
        key=hashlib.sha256(body+b'\0'+launch).hexdigest()[:16]
        if key not in variants:
            variants[key]={'id':key,'source_sha256':hashlib.sha256(body).hexdigest(),
                'launch_sha256':hashlib.sha256(launch).hexdigest(),'launch':json.loads(launch),'origins':[]}
            for name,data in files.items():
                dest=payload/'sources'/key/name
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        variants[key]['origins'].append(origin)
        return key
    for series,root in [('interrupted',BASE),('shared-scp',BASE/'relance-controlee'),('atomic',BASE/'serie-atomique')]:
        for condition in CONDITIONS:
            path=root/'data'/condition/'variants.json'
            if not path.exists():raise RuntimeError('Missing campaign '+str(path))
            for variant in read(path):
                valid=[o for o in variant['origins'] if o['status']=='valid' and o['correct'] is True]
                if not valid:continue
                files={name:(root/'sources'/variant['id']/name).read_bytes() for name in ['src/nbody_kernel.cu','src/launch.json']}
                for origin in valid:add(files,{'series':series,**origin})
    historical=read(HISTORY/'data/variants.json')
    for condition in CONDITIONS:
        summary=read(HISTORY/'data/campaigns'/condition/'summary.json')
        commit=summary['best_confirmed']['commit']
        variant=next(v for v in historical if any(o['job_id']==condition and o['commit']==commit for o in v['origins']))
        files={name:(HISTORY/'sources'/variant['id']/name).read_bytes() for name in ['src/nbody_kernel.cu','src/launch.json']}
        add(files,{'series':'historical-winner','condition':condition,'commit':commit,'old_variant_id':variant['id']})
    baseline={name:(template/'source'/name).read_bytes() for name in ['src/nbody_kernel.cu','src/launch.json']}
    for name,data in baseline.items():
        p=payload/'sources/baseline-control'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    variants['baseline-control']={'id':'baseline-control','source_sha256':hashlib.sha256(baseline['src/nbody_kernel.cu']).hexdigest(),
        'launch':json.loads(baseline['src/launch.json']),'origins':[{'series':'control'}]}
    write(payload/'variants.json',list(variants.values()))
    write(payload/'manifest.json',{p.relative_to(payload).as_posix():sha(p) for p in sorted(payload.rglob('*')) if p.is_file() and p.name!='manifest.json'})
    with tarfile.open(folder/'payload.tar.gz','w:gz') as archive:
        for path in sorted(payload.iterdir()):archive.add(path,arcname=path.name)
    remote='/scratch_p/nimarano/forest-engine-history-final-replay-'+uuid.uuid4().hex
    tar=remote+'.tar.gz';digest=sha(folder/'payload.tar.gz')
    py='/scratch_p/nimarano/hpc-forest-localmodels-20261015-r1/venv-r3/bin/python'
    command='\n'.join(['set -euo pipefail','export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1',
        'test -n "${CUDA_VISIBLE_DEVICES:-}"',f'test ! -e {remote}',
        f"printf '%s  %s\\n' {digest} {tar} | sha256sum -c -",f'mkdir {remote}',f'tar -xzf {tar} -C {remote}',
        f'export FOREST_CUDA_HARNESS={remote}/harness-build/cuda_test_harness',f'export FOREST_CUDA_CACHE={remote}/cache',
        'export TMPDIR="${SLURM_TMPDIR:-/tmp}/forest-final-${SLURM_JOB_ID}"','mkdir -p "$TMPDIR"',f'cd {remote}',
        'cmake -S cuda_test_harness -B harness-build -DCMAKE_BUILD_TYPE=Release','cmake --build harness-build --parallel 4',
        f'exec {py} -u gpu_replay.py',''])
    prep={'created':time.time(),'artifact':str(folder),'remote_root':remote,'remote_payload':tar,'payload_sha256':digest,
        'programs_including_control':len(variants),'batch_command':'bash -lc '+shlex.quote(command),
        'hosting':{'arch':'armgpu','cpus_per_task':4,'gpus_per_node':1,'mem_gb':16,'time_limit':'02:00:00'},
        'design':'All valid new programs from all three series, plus historical final winners, shuffled in 5 blocks on one GPU; baseline before and after each block'}
    write(folder/'preparation.json',prep)
    dest=BASE/'gpu-comparaison'
    dest.mkdir(exist_ok=True)
    shutil.copytree(payload/'sources',dest/'sources')
    for name in ['variants.json','manifest.json','gpu_replay.py']:
        shutil.copyfile(payload/name,dest/name)
    shutil.copyfile(folder/'preparation.json',dest/'preparation.json')
    print(json.dumps(prep,ensure_ascii=True))

if __name__=='__main__':prepare()
