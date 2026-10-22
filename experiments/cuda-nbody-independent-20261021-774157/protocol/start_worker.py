"""Strictly scoped local native worker for this single user-requested GPU test."""
import argparse
import asyncio
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = json.loads((HERE/'state.json').read_text())
sys.path.insert(0,str(Path(STATE['repository'])/'src'))
from hpc_forest import codex_mailbox, codex_process, codex_worker
from hpc_forest.core import FileLock, InfrastructureError, atomic_json, file_digest
from hpc_forest.native_matrix import install_identity
from hpc_forest.request_pool import RequestPool


async def main(job):
    artifact = Path(STATE['artifact'])
    plan_path = artifact/'plan.json'
    plan = json.loads(plan_path.read_text())
    channel = plan['remote_root']+'/results-'+job+'/mailbox'
    receipt_path = artifact/'authorization.json'
    if not receipt_path.exists():
        atomic_json(receipt_path,{'status':'cuda_nbody_explicitly_authorized',
            'scope':plan['scope'],'session_id':plan['session_id'],'channel':channel,
            'job_id':job,'model':plan['model'],'effort':plan['effort'],
            'completion':plan['completion'],'tokens':None,'wall_seconds':1800,
            'gpus':1,'plan_path':str(plan_path),'plan_sha256':file_digest(plan_path),
            'payload_path':str(artifact/'payload.tar.gz'),
            'payload_sha256':STATE['payload_sha256'],
            'user_request':STATE['user_request'],'created_at':time.time()})
    receipt_sha = file_digest(receipt_path)

    def gate(path, required):
        if Path(path).resolve() != receipt_path.resolve() or file_digest(path) != receipt_sha:
            raise InfrastructureError('Authorization changed')
        value = codex_mailbox.bounded_json(path,65536)
        if (required != {plan['scope']} or value['session_id'] != plan['session_id']
                or value['channel'] != channel or value['job_id'] != job
                or (value['model'],value['effort']) != ('gpt-6-luna','max')
                or value['gpus'] != 1 or value['tokens'] is not None
                or value['wall_seconds'] != 1800 or not value['user_request']
                or file_digest(plan_path) != value['plan_sha256']
                or file_digest(artifact/'payload.tar.gz') != value['payload_sha256']):
            raise InfrastructureError('Not this authorized CUDA campaign')
        return value

    gate(receipt_path,{plan['scope']})
    install_identity('gpt-6-luna','max')
    codex_process.check_dependencies = codex_worker.check_dependencies = gate

    def channel_guard(value):
        if value != channel:
            raise InfrastructureError('Not this authorized channel')
    codex_worker.validate_remote_channel = channel_guard
    original_run = codex_process.run_codex
    def scoped_run(request,*args,**kwargs):
        if request.get('session_id') != plan['session_id']:
            raise InfrastructureError('Wrong request session')
        return original_run(request,*args,**kwargs)
    codex_worker.run_codex = scoped_run
    output = artifact/'worker'
    output.mkdir(exist_ok=True)
    async with codex_worker.RomeoFiles(Path(STATE['runtime']['codex_config'])) as files:
        print('WAITING_FOR_OWNED_GPU_CHANNEL',job,flush=True)
        end = time.monotonic()+7200
        while True:
            try:
                listing = await codex_worker.retry_transfer(
                    lambda:files.call('list_dir',path=channel,limit=30),attempts=1,timeout=10)
                if any(x['name']=='OWNER.json' for x in listing['entries']):
                    break
            except InfrastructureError:
                pass
            if time.monotonic()>end:
                raise InfrastructureError('GPU channel did not appear')
            await asyncio.sleep(5)
        with FileLock(output/'worker.lock'):
            worker = codex_worker.Worker(files,channel,plan['session_id'],output,
                receipt_path,{plan['scope']},executable=STATE['runtime']['codex_executable'],
                defer_diagnostics=True,model_mcp_config=Path(STATE['runtime']['codex_config']),
                documentation=True)
            await worker.hello()
            print('LUNA_MAX_CUDA_WORKER_READY',flush=True)
            pool = RequestPool(worker)
            try:
                async with worker.keepalive(True):
                    while True:
                        listing = await worker.transfer_call(
                            lambda:files.call('list_dir',path=channel,limit=40))
                        names = {x['name'] for x in listing['entries']}
                        width = await worker.controller_forest_width() if 'forest-plan.json' in names else 1
                        await pool.pump(await worker.request_names(width),width)
                        if 'DONE.json' in names:
                            await pool.drain()
                            await worker.transfer_call(lambda:files.download(channel+'/DONE.json',output/'DONE.json'))
                            done = codex_mailbox.bounded_json(output/'DONE.json',65536)
                            if done.get('session_id') != plan['session_id']:
                                raise InfrastructureError('Wrong completion session')
                            pending = await worker.flush_diagnostics(deadline=math.inf)
                            atomic_json(HERE/'worker-finished.json',{'job_id':job,
                                'pipeline_complete':done.get('pipeline_complete'),
                                'pending_diagnostics':pending,'at':time.time()})
                            return 0 if done.get('pipeline_complete') else 1
                        await asyncio.sleep(2)
            finally:
                await pool.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--job-id',required=True)
    raise SystemExit(asyncio.run(main(parser.parse_args().job_id)))
