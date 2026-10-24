from pathlib import Path
import concurrent.futures as cf
import hashlib, json, subprocess, urllib.request, time, tarfile, shutil

ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'upstream'
DEST.mkdir(exist_ok=True)
REPOS = ['BartMassey/popcount','lemire/fastbase64','lemire/fastvalidate-utf-8',
         'sslotin/amh-code','siboehm/SGEMM_CUDA','NVIDIA-developer-blog/code-samples',
         'HuriyehBabak/CUDA_Kernels_S4ConvD']

def fetch(url, path):
    if path.exists(): return
    req=urllib.request.Request(url,headers={'User-Agent':'HPC-Forest-reproducibility-study'})
    with urllib.request.urlopen(req, timeout=90) as response, path.open('wb') as out:
        shutil.copyfileobj(response,out)

def clone(repo):
    path=DEST/repo.split('/')[-1]
    try:
        if not path.exists():
            r=subprocess.run(['git','clone','--depth','1','https://github.com/'+repo+'.git',str(path)],capture_output=True,text=True,timeout=300)
            if r.returncode: raise RuntimeError(r.stderr[-2000:])
        commit=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        return {'kind':'git','repository':repo,'path':str(path),'commit':commit,'ok':True}
    except Exception as e: return {'kind':'git','repository':repo,'ok':False,'error':str(e)}

def page(url):
    name=hashlib.sha256(url.encode()).hexdigest()[:16]
    path=DEST/(name+('.pdf' if '.pdf' in url else '.html'))
    try:
        fetch(url,path)
        return {'kind':'page','url':url,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size,'ok':True}
    except Exception as e: return {'kind':'page','url':url,'ok':False,'error':str(e)}

def asset(a):
    path=DEST/a['name']
    try:
        fetch(a['url'],path)
        assert hashlib.sha256(path.read_bytes()).hexdigest()==a['sha256'], 'checksum mismatch'
        if a['name'].startswith('ispc-examples'):
            with tarfile.open(path) as t: t.extractall(DEST,filter='data')
        return {'kind':'asset',**a,'path':str(path),'ok':True}
    except Exception as e: return {'kind':'asset',**a,'ok':False,'error':str(e)}

def main():
    d=json.loads((ROOT/'workbook.json').read_text(encoding='utf8'))
    urls=sorted({r[11] for r in d[0]['data'][7:] if not r[11].startswith('https://github.com/')})
    assets=json.loads((ROOT/'ispc-assets.json').read_text())
    results=[]
    with cf.ThreadPoolExecutor(max_workers=5) as pool:
        futures=[pool.submit(clone,r) for r in REPOS]+[pool.submit(page,u) for u in urls]+[pool.submit(asset,a) for a in assets]
        for f in cf.as_completed(futures):
            item=f.result(); item['observed_at']=time.time(); results.append(item)
            (ROOT/'acquisition.json').write_text(json.dumps(results,indent=2),encoding='utf8')
            print(json.dumps(item),flush=True)

if __name__=='__main__': main()
