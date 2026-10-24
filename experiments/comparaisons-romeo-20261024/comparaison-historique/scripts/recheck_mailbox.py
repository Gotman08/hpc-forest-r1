"""Ten predeclared sequential retries of one observed Windows I/O failure."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT=Path(__file__).resolve().parents[3] if Path(__file__).parent.name == 'scripts' else Path(__file__).resolve().parents[1]
SOURCE=ROOT/'work/engine-snapshots/6ee21f4'
OUT=ROOT/'outputs/comparaison-historique/regression-tests/mailbox-repeats'
TEMP=ROOT/'work/mailbox-repeats'

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True);TEMP.mkdir(exist_ok=True)
    env={**os.environ,'PYTHONPATH':str(SOURCE/'src'),'TEMP':str(TEMP),'TMP':str(TEMP),'TMPDIR':str(TEMP),
         'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8'}
    node='tests/test_finish_started.py::test_unlimited_mailbox_still_verifies_identity_and_receives_completed_response'
    results=[]
    for i in range(10):
        folder=OUT/str(i+1);folder.mkdir(exist_ok=True)
        cmd=[sys.executable,'-m','pytest','-q',node,'--junitxml='+str(folder/'pytest.xml'),'--basetemp='+str(TEMP/str(i+1))]
        with (folder/'pytest.log').open('w',encoding='utf8') as f:
            run=subprocess.run(cmd,cwd=SOURCE,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=60)
        xml=ElementTree.parse(folder/'pytest.xml').getroot()
        results.append({'repetition':i+1,'exit_code':run.returncode,'suites':[s.attrib for s in xml.iter('testsuite')]})
        (OUT/'results.json').write_text(json.dumps({'predeclared_repetitions':10,'source_commit':'6ee21f4','nodeid':node,
            'mailbox_file_sha256':hashlib.sha256((SOURCE/'src/hpc_forest/codex_mailbox.py').read_bytes()).hexdigest(),
            'results':results},indent=2))
    print(json.dumps({'repetitions':10,'passed':sum(r['exit_code']==0 for r in results),'failed':sum(r['exit_code']!=0 for r in results)}))
