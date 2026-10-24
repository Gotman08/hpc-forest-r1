"""Check completeness and file links, then package the verified deliverable."""
import ast
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3] if Path(__file__).parent.name == 'scripts' else Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/comparaison-historique'
REPO=Path(r'C:\Users\nicol\Documents\Codex\2026-10-20\new-chat\outputs\hpc-forest-r1')


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def main():
    data=read(OUT/'data/dashboard.json')
    assert len(data['programs'])==124 and all(p['fully_measured'] for p in data['programs'])
    assert len(data['trials'])==138 and sum(t['role']=='G' for t in data['trials'])==15
    assert sum(len(p['origins']) for p in data['programs'])==152
    expected={c['commit'] for c in data['commits'] if c['code_or_test_change']}
    assert len(expected)==12 and {e['commit'] for e in data['engines']}==expected
    assert all(e['test_suites'] and len(e['commands'])==2 for e in data['engines'])
    assert data['verification']['all_checks_passed']
    page=(OUT/'TABLEAU-DE-BORD.html').read_text(encoding='utf8')
    embedded=json.loads(re.search(r'<script type="application/json" id="study">(.*?)</script>',page,re.S).group(1))
    assert embedded==data
    bad_links=[]
    for md in OUT.rglob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)',md.read_text(encoding='utf8')):
            link=link.strip('<>').split('#')[0]
            if not link or re.match(r'^[A-Za-z]+:',link):continue
            if not (md.parent/unquote(link)).exists():bad_links.append([str(md.relative_to(OUT)),link])
    assert not bad_links,bad_links
    for p in data['programs']:
        assert (OUT/'sources'/p['id']/'src/nbody_kernel.cu').exists()
        assert (OUT/'gpu/results/records'/(p['id']+'.json')).exists()
    for t in data['trials']:
        if t.get('patch'):assert (OUT/t['patch']).exists()
    for e in read(OUT/'engines/manifest.json'):
        assert hashlib.sha256((OUT/e['path']).read_bytes()).hexdigest()==e['sha256']
        with zipfile.ZipFile(OUT/e['path']) as z:assert z.testzip() is None
    scripts=['historical_audit.py','reconstruct_history.py','engine_matrix.py','regression_matrix.py',
             'recheck_mailbox.py','gpu_replay.py','verify_replay.py','analyze_replay.py',
             'package_engines.py','build_report.py','dashboard_template.py','finish_engine_matrix.py','finalize_study.py']
    (OUT/'scripts').mkdir(exist_ok=True)
    for name in scripts:
        source=ROOT/'work'/name
        ast.parse(source.read_text(encoding='utf8'))
        shutil.copy2(source,OUT/'scripts'/name)
    head=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip()
    assert head==read(OUT/'data/inventory.json')['head']
    status=subprocess.check_output(['git','-C',str(REPO),'status','--porcelain'],text=True)
    assert status.strip()=='?? A_FAIRE.md',status
    receipt=dict(programs=124,valid_origins=152,trials=138,integrations=15,engine_revisions=12,
                 original_repo_head=head,original_repo_status=status.strip(),
                 markdown_links_valid=True,embedded_dashboard_data_matches=True,archives_integrity=True,
                 engine_test_totals=sum(int(s['tests']) for e in data['engines'] for s in e['test_suites']),
                 engine_test_failures=sum(int(s['failures'])+int(s['errors']) for e in data['engines'] for s in e['test_suites']))
    (OUT/'protocol/delivery-verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
    manifest={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='MANIFEST-SHA256.json'}
    (OUT/'MANIFEST-SHA256.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    archive=ROOT/'outputs/comparaison-historique-complete.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():z.write(p,arcname='comparaison-historique/'+p.relative_to(OUT).as_posix())
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (ROOT/'outputs/comparaison-historique-complete.zip.sha256').write_text(digest+'  '+archive.name+'\n')
    print(json.dumps({**receipt,'files':len(manifest)+1,'zip_bytes':archive.stat().st_size,'zip_sha256':digest}))


if __name__=='__main__':main()
