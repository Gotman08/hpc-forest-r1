"""One bounded MCP connection for the study's independent local model relays."""
import asyncio
import concurrent.futures
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import threading
import time
import traceback
from engine_study import ROOT, REPO, CONFIG, write
import sys
sys.path.insert(0,str(REPO/'src'))
from hpc_forest.codex_worker import RomeoFiles

FOLDER=ROOT/'work/engine-broker'
FOLDER.mkdir(parents=True,exist_ok=True)
TOKEN=secrets.token_hex(32)
LOOP=asyncio.new_event_loop()
STATE={}

def allowed(name,args):
    if name not in {'list_dir','download_from_romeo','upload_to_romeo'}:
        raise ValueError('Only study file operations are supported')
    remote=args.get('path') if name=='list_dir' else args.get('remote_path')
    if not isinstance(remote,str) or '..' in remote.split('/') or not remote.startswith((
        '/scratch_p/nimarano/forest-engine-history-', '/gpfs/scratch/nimarano/forest-engine-history-')):
        raise ValueError('Outside study remote roots')
    if name!='list_dir':
        local=Path(args['local_path']).resolve()
        if not local.is_relative_to(ROOT/'work') and not local.is_relative_to(ROOT/'outputs/comparaison-moteurs'):
            raise ValueError('Outside study local roots')
        if args.get('verify') is not True:
            raise ValueError('Transfers must retain integrity verification')

async def invoke(name,args):
    allowed(name,args)
    started=time.time()
    semaphore=STATE['transfers'] if name!='list_dir' else STATE['listings']
    async with semaphore:
        entered=time.time()
        try:
            value=await STATE['files'].call(name,**args)
        except Exception as exc:
            value={'ok':False,'error':type(exc).__name__+': '+str(exc)}
        with (FOLDER/'operations.jsonl').open('a',encoding='utf8') as stream:
            stream.write(json.dumps({'tool':name,'started':started,'queue_seconds':entered-started,
                'seconds':time.time()-entered,'ok':value.get('ok'),'error':value.get('error'),
                'remote_path':args.get('remote_path',args.get('path'))},ensure_ascii=False)+'\n')
        return value

async def initialize():
    files=RomeoFiles(CONFIG)
    await files.__aenter__()
    STATE.update(files=files,transfers=asyncio.Semaphore(2),listings=asyncio.Semaphore(1))

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        if self.path!='/call' or self.headers.get('Authorization')!='Bearer '+TOKEN:
            self.send_error(403);return
        size=int(self.headers.get('Content-Length','0'))
        if size<1 or size>65536:
            self.send_error(413);return
        try:
            request=json.loads(self.rfile.read(size))
            future=asyncio.run_coroutine_threadsafe(invoke(request['name'],request['arguments']),LOOP)
            response=future.result(timeout=600)
        except Exception as exc:
            response={'ok':False,'error':type(exc).__name__+': '+str(exc)}
        body=json.dumps(response).encode()
        self.send_response(200);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)));self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass

if __name__=='__main__':
    thread=threading.Thread(target=LOOP.run_forever,daemon=True);thread.start()
    asyncio.run_coroutine_threadsafe(initialize(),LOOP).result(timeout=60)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    write(FOLDER/'connection.json',{'port':server.server_port,'token':TOKEN,'pid':os.getpid()})
    write(FOLDER/'public-config.json',{'pid':os.getpid(),'started':time.time(),'parallel_transfers':2,
        'parallel_listings':1,'heartbeat_seconds':30,'file_rpc_timeout_seconds':180,
        'integrity_checks_preserved':True,'model_generation_unchanged':True})
    print('STUDY_BROKER_READY',server.server_port,flush=True)
    server.serve_forever()
