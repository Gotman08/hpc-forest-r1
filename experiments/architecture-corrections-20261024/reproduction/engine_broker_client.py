"""Transport-only compatibility layer; engine search logic and files stay frozen."""
import asyncio
import json
import time
from pathlib import Path
import urllib.request

def install(codex_worker, connection):
    settings=json.loads(Path(connection).read_text(encoding='utf8'))
    original=codex_worker.RomeoFiles
    class SharedRomeoFiles(original):
        async def __aenter__(self):return self
        async def __aexit__(self,*args):return False
        async def call(self,name,**arguments):
            def request():
                body=json.dumps({'name':name,'arguments':arguments}).encode()
                req=urllib.request.Request('http://127.0.0.1:'+str(settings['port'])+'/call',data=body,
                    headers={'Content-Type':'application/json','Authorization':'Bearer '+settings['token']})
                deadline=15 if str(arguments.get('remote_path','')).endswith('/worker-heartbeat.json') else 180
                with urllib.request.urlopen(req,timeout=deadline) as reply:value=json.load(reply)
                if value.get('ok') is not True:
                    from hpc_forest.core import InfrastructureError
                    raise InfrastructureError('Shared ROMEO transport: '+str(value.get('error')))
                return value
            return await asyncio.to_thread(request)
    retry=codex_worker.retry_transfer
    async def transport_retry(operation,**options):
        # Bounded grace for transient DNS failures. Only immutable file I/O is
        # retried here; native generation and conversation receipts are untouched.
        options.setdefault('attempts',8)
        options.setdefault('retry_delay',2)
        original_deadline=options.get('deadline')
        options['deadline']=min(original_deadline if original_deadline is not None else float('inf'),time.time()+90)
        if options.get('timeout') != 20:
            options['timeout']=max(options.get('timeout',30),180)
        return await retry(operation,**options)
    codex_worker.RomeoFiles=SharedRomeoFiles
    codex_worker.retry_transfer=transport_retry
    codex_worker.HEARTBEAT_INTERVAL_SECONDS=30
