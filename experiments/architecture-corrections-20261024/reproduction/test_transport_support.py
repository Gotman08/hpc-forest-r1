"""Offline fault injection for the study's transport-only adapter."""
import asyncio
import hashlib
import json
import tempfile
import time
from pathlib import Path

from hpc_forest import codex_worker as worker
from engine_broker_client import install

R=Path(__file__).resolve().parent


async def checks():
    counts={'transient_recovery':0,'integrity_failure':0,'explicit_single_attempt':0}

    async def transient():
        counts['transient_recovery']+=1
        if counts['transient_recovery']<5:
            raise OSError('simulated transient DNS failure')
        return 'verified'

    assert await worker.retry_transfer(transient,retry_delay=0)=='verified'

    async def integrity():
        counts['integrity_failure']+=1
        raise worker.TransferVerificationError('simulated hash mismatch')

    try:
        await worker.retry_transfer(integrity,retry_delay=0)
    except worker.TransferVerificationError:
        pass
    else:
        raise AssertionError('Integrity failure was not propagated')

    async def single():
        counts['explicit_single_attempt']+=1
        raise OSError('simulated unavailable endpoint')

    try:
        await worker.retry_transfer(single,attempts=1,retry_delay=0)
    except worker.InfrastructureError:
        pass
    else:
        raise AssertionError('Explicit attempt limit ignored')
    try:
        await worker.retry_transfer(transient,deadline=time.time()-1,retry_delay=0)
    except worker.InfrastructureError:
        pass
    else:
        raise AssertionError('Original expired deadline ignored')
    assert counts=={'transient_recovery':5,'integrity_failure':1,'explicit_single_attempt':1}
    return counts


def main():
    native=worker.run_codex
    with tempfile.TemporaryDirectory(prefix='forest-transport-test-') as directory:
        connection=Path(directory)/'connection.json'
        connection.write_text(json.dumps({'port':0,'token':'offline-test-only'}),encoding='utf8')
        install(worker,connection)
        assert worker.run_codex is native
        counts=asyncio.run(checks())
    result={'checks_passed':4,'fault_injection_counts':counts,'network_used':False,
            'native_generation_unchanged':worker.run_codex is native,
            'validated_at':time.time(),
            'support_sha256':hashlib.sha256((R/'engine_broker_client.py').read_bytes()).hexdigest()}
    (R/'transport-validation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':
    main()
