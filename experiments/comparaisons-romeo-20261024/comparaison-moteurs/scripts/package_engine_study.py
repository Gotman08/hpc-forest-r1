"""Package reproducible evidence, validate links and seal the final deliverables."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile
from engine_study import ROOT,REPO,CONDITIONS,read,write,sha

BASE=ROOT/'outputs/comparaison-moteurs'
SCRIPTS=['engine_study.py','engine_extract.py','engine_native_audit.py','engine_diagnostics.py',
    'engine_transport_analysis.py','verify_engine_inputs.py','prepare_engine_replay.py','gpu_replay.py',
    'verify_engine_replay.py','collect_engine_replay.py','build_engine_comparison.py','build_engine_dashboard.py','engine_dashboard.html',
    'package_engine_study.py','build_engine_behavior.py','build_study_overview.py','token_counter_regression.py','engine_relay.py','engine_broker_client.py','engine_transfer_broker.py',
    'engine_transfer_broker_fast.py','test_engine_broker.py','engine_monitor.py']

def prepare():
    for name in SCRIPTS:
        dest=BASE/'scripts'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'work'/name,dest)
    capsules=[]
    for series,work,out in [('S1','engine-study',''),('S2','engine-study-r2','relance-controlee'),('S3','engine-study-r3','serie-atomique')]:
        for key in CONDITIONS:
            artifact=ROOT/'work'/work/key;target=BASE/'capsules'/series/key;target.mkdir(parents=True,exist_ok=True)
            names=['payload.tar.gz','engine_relay.py','engine_broker_client.py','relay-process.json','authorization.json']
            for name in names:
                if (artifact/name).exists():shutil.copyfile(artifact/name,target/name)
            capsules.append({'series':series,'condition':key,'payload':(target/'payload.tar.gz').relative_to(BASE).as_posix(),
                'payload_sha256':sha(target/'payload.tar.gz'),'original_preparation_sha256':read(artifact/'preparation.json')['payload_sha256']})
    assert all(c['payload_sha256']==c['original_preparation_sha256'] for c in capsules)
    write(BASE/'protocol/capsule-integrity.json',capsules)
    replay=ROOT/'work/engine-final-replay/payload.tar.gz'
    if replay.exists():shutil.copyfile(replay,BASE/'gpu-comparaison/payload.tar.gz')
    # These are exact credentials of owned local brokers, never report content.
    secrets=[read(ROOT/'work'/b/'connection.json')['token'].encode() for b in ['engine-broker','engine-broker-fast']]
    exposed=[]
    for path in BASE.rglob('*'):
        if path.is_file() and path.suffix.lower() in {'.json','.jsonl','.txt','.py','.html','.md','.log','.csv','.toml'}:
            content=path.read_bytes()
            if any(s in content for s in secrets):exposed.append(path.relative_to(BASE).as_posix())
    assert not exposed,'Private local transport credential found in output'
    write(BASE/'protocol/credential-exclusion.json',{'checked_owned_broker_credentials':2,'exposed_files':exposed,
        'connection_files_included':False,'method':'Exact byte search for both temporary local broker tokens in text deliverables'})
    print(json.dumps({'capsules_verified':len(capsules),'analysis_scripts':len(SCRIPTS),'credentials_excluded':True}))

def seal():
    report=BASE/'RAPPORT.md';dashboard=BASE/'TABLEAU-DE-BORD.html'
    assert report.exists() and dashboard.exists()
    rows=read(BASE/'data/comparison.json');assert len(rows)==21
    verification=read(BASE/'protocol/new-replay-verification.json');assert verification['all_consistency_checks_passed']
    assert len(read(BASE/'data/comparison-trials.json'))==225
    assert len(read(BASE/'data/comparison-native-calls.json'))==389
    head=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip()
    status=subprocess.check_output(['git','-C',str(REPO),'status','--porcelain'],text=True).strip()
    assert head=='934627c1399b48e4aa0f25630e9c4223680a3511'
    assert status=='?? A_FAIRE.md',repr(status)
    write(BASE/'protocol/repository-unchanged.json',{'head':head,'status':status,'preexisting_untracked_file':'A_FAIRE.md','unchanged':True})
    links=[];missing=[]
    for doc in [report,BASE/'COMPORTEMENTS.md',BASE/'METHODE.md',BASE/'REPRODUCTION.md',ROOT/'outputs/BILAN-COMPLET.md']:
        body=doc.read_text(encoding='utf8')
        for match in re.finditer(r'\]\(([^)]+)\)',body):
            href=match.group(1).strip('<>')
            if '://' in href or href.startswith('#'):continue
            path=(doc.parent/href.split('#')[0]).resolve()
            links.append({'from':str(doc.relative_to(ROOT/'outputs')),'target':href,'exists':path.exists()})
            if not path.exists():missing.append(links[-1])
    assert not missing,missing
    class LinkParser(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for name,value in attrs:
                if name=='href' and value and '://' not in value and not value.startswith('#'):
                    target=(dashboard.parent/value.split('#')[0]).resolve()
                    links.append({'from':str(dashboard.relative_to(ROOT/'outputs')),'target':value,'exists':target.exists()})
                    if not target.exists():missing.append(links[-1])
    LinkParser().feed(dashboard.read_text(encoding='utf8'))
    for trial in read(BASE/'data/comparison-trials.json'):
        paths=[]
        if trial.get('patch'):paths.append(trial['patch'])
        if trial.get('variant_id'):paths.append(trial['evidence_prefix']+'sources/'+trial['variant_id']+'/src/nbody_kernel.cu')
        for href in paths:
            exists=(BASE/href).exists()
            links.append({'from':'dashboard-generated-trial-link','target':href,'exists':exists})
            if not exists:missing.append(links[-1])
    for p in read(BASE/'data/dashboard.json')['programs']:
        program_links=['gpu-comparaison/sources/'+p['id']+'/src/'+filename for filename in ['nbody_kernel.cu','launch.json']]
        program_links.append('gpu-comparaison/results/records/'+p['id']+'.json')
        for href in program_links:
            exists=(BASE/href).exists()
            links.append({'from':'dashboard-generated-program-link','target':href,'exists':exists})
            if not exists:missing.append(links[-1])
    assert not missing,missing
    write(BASE/'protocol/deliverable-verification.json',{'campaigns':len(rows),'trials':225,'native_calls':389,'markdown_links':links,
        'all_links_exist':True,'gpu_verification_passed':True,'repository_unchanged':True})
    files=[p for p in sorted(BASE.rglob('*')) if p.is_file() and p.name!='MANIFEST-SHA256.json']
    manifest={p.relative_to(BASE).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in files}
    write(BASE/'MANIFEST-SHA256.json',manifest)
    archive=ROOT/'outputs/historique-moteurs-et-cuda.zip'
    included=[];excluded=[]
    candidates=[p for parent in [ROOT/'outputs/comparaison-historique',BASE] for p in sorted(parent.rglob('*')) if p.is_file()]
    candidates.append(ROOT/'outputs/BILAN-COMPLET.md')
    for p in candidates:
        if p.name=='results.tar.gz' and 'evidence' in p.parts:
            excluded.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p),'reason':'Raw arrays already represented by source, registry and verified structured logs; original archive remains in the local output folder'})
        else:included.append(p)
    index={'description':'Reports, sources, diagnostics, exact engine payloads and reproducible analysis; raw campaign result tarballs excluded',
        'included_file_count':len(included)+1,'index_included':True,'excluded_raw_archives':excluded}
    # Keep the ZIP index outside sealed folders to avoid manifest recursion.
    write(ROOT/'outputs/historique-moteurs-et-cuda-index.json',index)
    included.append(ROOT/'outputs/historique-moteurs-et-cuda-index.json')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in included:z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(included)
    checksum=sha(archive)
    archive.with_suffix('.zip.sha256').write_text(checksum+'  '+archive.name+'\n',encoding='ascii')
    print(json.dumps({'files_sealed':len(manifest),'zip_files':len(included),'zip_bytes':archive.stat().st_size,'zip_sha256':checksum,
        'excluded_raw_archives':len(excluded),'link_checks':len(links),'repository_unchanged':True}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','seal']);args=parser.parse_args()
    prepare() if args.action=='prepare' else seal()
