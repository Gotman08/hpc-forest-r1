"""Real bounded transfer probe on seven owned study directories, without model calls."""
import asyncio
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from engine_study import ROOT, REPO, CONFIG, STUDY, CONDITIONS, read, write
sys.path.insert(0,str(REPO/'src'))
from hpc_forest import codex_worker
from engine_broker_client import install
connection=Path(os.environ.get('FOREST_STUDY_BROKER',str(ROOT/'work/engine-broker/connection.json')))
install(codex_worker,connection)

async def main():
    folder=connection.parent/('probe-'+uuid.uuid4().hex[:8])
    folder.mkdir(exist_ok=True)
    rows=[]
    async with codex_worker.RomeoFiles(CONFIG) as files:
        async def probe(key):
            local=folder/(key+'.json')
            write(local,{'condition':key,'probe':True,'payload':'x'*8192,'at':time.time()})
            remote=read(STUDY/key/'plan.json')['remote_root']+'/transfer-probe-'+folder.name+'-'+key+'.json'
            started=time.time()
            up=await files.upload(local,remote)
            if 'fast' in str(connection):
                write(local,{'condition':key,'probe':True,'payload':'y'*8192,'updated':True,'at':time.time()})
                update=await files.upload(local,remote)
                assert update['verifie']
            dest=folder/(key+'-returned.json')
            down=await files.download(remote,dest)
            assert local.read_bytes()==dest.read_bytes()
            row={'condition':key,'seconds':time.time()-started,'upload_verified':up['verifie'],
                 'download_verified':down['verifie'],'sha256':hashlib.sha256(local.read_bytes()).hexdigest()}
            rows.append(row)
            print(json.dumps(row),flush=True)
        await asyncio.gather(*(probe(key) for key in CONDITIONS))
    write(folder/'result.json',{'all_passed':len(rows)==7,'rows':rows,'finished':time.time()})
    write(connection.parent/'last-probe.json',{'path':str(folder),'all_passed':len(rows)==7})

if __name__=='__main__':asyncio.run(main())
