from pathlib import Path
import json,os,subprocess,shutil,hashlib,tarfile,time,sys
R=Path(__file__).resolve().parent;ROOT=R.parents[1]
REPO=Path(r'C:\Users\nicol\Documents\Codex\2026-10-20\new-chat\outputs\hpc-forest-r1')
PY=Path(r'C:\Users\nicol\Documents\Codex\2026-10-20\new-chat\work\hpc-forest-mcp-venv\Scripts\python.exe')
CONFIG=Path(r'C:\Users\nicol\Documents\Codex\2026-10-20\new-chat\work\romeo-worker-config.toml')
def read(p):return json.loads(p.read_text(encoding='utf8'))
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def broker():
    p=R/'broker';p.mkdir(exist_ok=True)
    with (p/'stdout.log').open('wb') as out,(p/'stderr.log').open('wb') as err:
        x=subprocess.Popen([str(PY),'-u',str(R/'broker.py')],stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
    write(p/'process.json',{'pid':x.pid,'started':time.time()});print('broker PID',x.pid)

def start(key,job):
    a=R/'campaigns'/key;plan=read(a/'plan.json');prep=read(a/'preparation.json')
    receipt={'scope':plan['scope'],'session_id':plan['session_id'],'model':plan['model'],'effort':plan['effort'],'wall_seconds':plan['wall_seconds'],'completion':plan['completion'],'job_id':job,'channel':plan['remote_root']+'/results-'+job+'/mailbox','gpus':plan['gpus'],'tokens':None,'hpc_allocation_authorized':True,'plan_sha256':sha(a/'plan.json'),'payload_sha256':sha(a/'payload.tar.gz'),'user_request':'Implémenter complètement la nouvelle architecture Forest, puis relancer tous les tests des CSV sur ROMEO avec les mêmes entrées, comparer les résultats et les temps. GPT-6 Luna effort max pour tous les rôles, mémoire neuve par programme.','authorized_at':time.time()}
    write(a/'authorization.json',receipt);write(a/'job.json',{'job_id':job,'started':time.time()})
    env={**os.environ,'PYTHONPATH':str(a/'payload/project/src'),'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8','FOREST_STUDY_BROKER':str(R/'broker/connection.json')}
    args=[str(PY),'-u',str(R/'relay.py'),'--artifact',str(a),'--config',str(CONFIG)]
    with (a/'relay.stdout.log').open('wb') as out,(a/'relay.stderr.log').open('wb') as err:
        x=subprocess.Popen(args,stdout=out,stderr=err,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
    write(a/'relay-process.json',{'pid':x.pid,'started':time.time(),'command':args});print(key,job,'relay PID',x.pid)

if __name__=='__main__':
    if sys.argv[1]=='broker':broker()
    elif sys.argv[1]=='start':start(sys.argv[2],sys.argv[3])
