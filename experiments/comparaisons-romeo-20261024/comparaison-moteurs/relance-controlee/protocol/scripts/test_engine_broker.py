"""Real bounded transfer probe on seven owned study directories, without model calls."""
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path
from engine_study import ROOT, REPO, CONFIG, STUDY, CONDITIONS, read, write
sys.path.insert(0,str(REPO/'src'))
from hpc_forest import codex_worker
from engine_broker_client import install
install(codex_worker,ROOT/'work/engine-broker/connection.json')

async def main():
    folder=ROOT/'work/engine-broker/probe'
    folder.mkdir(exist_ok=True)
    rows=[]
    async with codex_worker.RomeoFiles(CONFIG) as files:
        async def probe(key):
            local=folder/(key+'.json')
            write(local,{'condition':key,'probe':True,'payload':'x'*8192,'at':time.time()})
            remote=read(STUDY/key/'plan.json')['remote_root']+'/transfer-probe-'+key+'.json'
            started=time.time()
            up=await files.upload(local,remote)
            dest=folder/(key+'-returned.json')
            down=await files.download(remote,dest)
            assert local.read_bytes()==dest.read_bytes()
            row={'condition':key,'seconds':time.time()-started,'upload_verified':up['verifie'],
                 'download_verified':down['verifie'],'sha256':hashlib.sha256(local.read_bytes()).hexdigest()}
            rows.append(row)
            print(json.dumps(row),flush=True)
        await asyncio.gather(*(probe(key) for key in CONDITIONS))
    write(folder/'result.json',{'all_passed':len(rows)==7,'rows':rows,'finished':time.time()})

if __name__=='__main__':asyncio.run(main())
