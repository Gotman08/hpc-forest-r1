"""Finite queue for this reviewed 21-case experiment, with no model-call replay."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import tarfile
import time

from launch_support import CONFIG, REPO, R, read, sha, start, write

sys.path.insert(0, str(REPO/'src'))
from hpc_forest.codex_worker import RomeoFiles
from hpc_forest.core import FileLock

ORDER = ['stencil_y_retry2','sgemm_retry1','stencil_y_retry1','transpose_retry1','stencil3d_retry1','base64_retry1','binomial_retry1','gemm_cpu_retry1','aobench','blackscholes','deferred','mandelbrot','raytracer','stencil3d','sumabs','volume',
         'noise','popcount','sgemm','stencil_y','transpose']
TERMINAL = {'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL'}


def check():
    manifest = read(R/'reviewed-queue.json')
    assert manifest['max_concurrent_campaigns'] == 8
    assert manifest['pending_order'] == ORDER
    assert len(manifest['campaigns']) == 29
    for key, hashes in manifest['campaigns'].items():
        directory = R/'campaigns'/key
        for name, digest in hashes.items():
            assert sha(directory/name) == digest, (key, name, 'changed after review')
        plan = read(directory/'slurm-plan.json')
        args = read(directory/'job-arguments.json')
        assert plan['submittable'] and args['command'] in plan['script']
        assert plan['resolved']['total_cpus'] == args['cpus_per_task']
        assert plan['resolved']['total_gpus'] == args['gpus_per_node']
    return manifest


async def call(files, name, **args):
    result = await files.session.call_tool(name, args)
    value = result.structuredContent
    if value is None:
        value = json.loads(next(c.text for c in result.content if c.type == 'text'))
    return value


def log(event, **values):
    record = {'at':time.time(), 'event':event, **values}
    with (R/'queue-events.jsonl').open('a',encoding='utf8') as stream:
        stream.write(json.dumps(record,ensure_ascii=False)+'\n')
    print(json.dumps(record,ensure_ascii=False),flush=True)


async def collect(files, directory, job):
    efficiency = await call(files, 'job_efficiency', job_id=job)
    if efficiency.get('ok') and efficiency.get('found'):
        write(directory/'efficiency.json', efficiency)
    prep = read(directory/'preparation.json')
    bundle = directory/'results.tar.gz'
    receipt = await files.download(prep['remote_results'], bundle)
    write(directory/'result-transfer.json', receipt)
    dest = directory/'results'
    dest.mkdir(exist_ok=True)
    with tarfile.open(bundle) as archive:
        archive.extractall('\\\\?\\'+str(dest.resolve()),
            members=(m.replace(name=str(Path(m.name))) for m in archive.getmembers()
                     if str(Path(m.name)) != '.'), filter='data')
    result = read(dest/f'results-{job}/results.json')
    assert str(result['job_id']) == job
    assert result['session_id'] == read(directory/'plan.json')['session_id']
    write(directory/'collected.json', {'job_id':job, 'at':time.time(),
          'pipeline_complete':result.get('pipeline_complete'), 'sha256':sha(bundle)})
    log('collected', case=directory.name, job=job, complete=result.get('pipeline_complete'), error=result.get('error'))


async def run():
    manifest = check()
    with FileLock(R/'execution-queue.lock'):
        async with RomeoFiles(CONFIG) as files:
            update = await call(files, 'mcp_update_check')
            write(R/'queue-mcp-update-check.json', update)
            expire = time.monotonic()+10*3600
            while time.monotonic() < expire and not (R/'queue.stop').exists():
                active, finished, uncertain = [], [], []
                for key in manifest['campaigns']:
                    directory = R/'campaigns'/key
                    if not (directory/'job.json').exists():
                        if (directory/'submission-claimed.json').exists():
                            uncertain.append(key)
                        continue
                    job = str(read(directory/'job.json')['job_id'])
                    if (directory/'collected.json').exists():
                        finished.append(key)
                        continue
                    status = await call(files, 'job_status', job_id=job)
                    write(directory/'latest-status.json', status)
                    terminal = status.get('finished') is True or status.get('state','').split('+')[0] in TERMINAL
                    if not status.get('ok'):
                        efficiency = await call(files, 'job_efficiency', job_id=job)
                        terminal = efficiency.get('found') and efficiency.get('state','').split('+')[0] in TERMINAL
                    if terminal:
                        try:
                            await collect(files, directory, job)
                            finished.append(key)
                        except Exception as exc:
                            log('collection_error', case=key, job=job, error=str(exc))
                            active.append(key)
                    else:
                        active.append(key)
                for key in ORDER:
                    if len(active) >= manifest['max_concurrent_campaigns'] or uncertain:
                        break
                    directory = R/'campaigns'/key
                    if (directory/'job.json').exists():
                        continue
                    check()
                    plan = read(directory/'slurm-plan.json')
                    # Durable claim first: an unknown submission is never repeated.
                    with (directory/'submission-claimed.json').open('x',encoding='utf8') as stream:
                        json.dump({'at':time.time(),'plan_id':plan['plan_id']},stream)
                    sub = await call(files, 'job_submit', plan_id=plan['plan_id'], confirm=True)
                    write(directory/'slurm-submission.json', sub)
                    if not sub.get('ok') or not sub.get('job_id'):
                        uncertain.append(key)
                        log('submission_uncertain', case=key)
                        break
                    job = str(sub['job_id'])
                    start(key, job)
                    active.append(key)
                    log('started', case=key, job=job)
                write(R/'queue-status.json', {'pid':os.getpid(),'at':time.time(),
                    'active':active,'collected':finished,'uncertain':uncertain,'total':len(manifest['campaigns']),
                    'programs':21})
                if len(finished) == len(manifest['campaigns']):
                    log('all_collected', total=len(finished), programs=21)
                    return
                if uncertain:
                    log('needs_submission_reconciliation', cases=uncertain)
                    return
                await asyncio.sleep(60)
            log('stopped_without_cancelling_allocations')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    if args.check:
        check()
        print('29 frozen reviewed plans verified for 21 programs; queue bound 8; no submissions performed')
    else:
        asyncio.run(run())
