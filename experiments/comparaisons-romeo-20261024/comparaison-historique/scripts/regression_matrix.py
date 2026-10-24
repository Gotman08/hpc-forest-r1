"""Apply the same regression test to the parent and the fixing revision."""
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from historical_audit import write

ROOT = Path(__file__).resolve().parents[3] if Path(__file__).parent.name == "scripts" else Path(__file__).resolve().parents[1]
REPO=Path(r'C:\Users\nicol\Documents\Codex\2026-10-20\new-chat\outputs\hpc-forest-r1')
OUT=ROOT/'outputs/comparaison-historique/regression-tests'
WORK=ROOT/'work/regression-snapshots'
CASES=[
 ('84ed198','memory-overview',['tests/test_memory_overview.py::test_tree_summary_keeps_valid_slow_alternatives_after_a_failure']),
 ('9628345','memory-decisions',['tests/test_memory_decisions.py::test_consultations_survive_new_round_and_connection_without_cross_campaign_access','tests/test_memory_decisions.py::test_finish_ignores_unused_legacy_ids_without_selecting_a_program','tests/test_memory_decisions.py::test_bad_optional_lessons_are_diagnosed_without_touching_source_or_relaxing_reads']),
 ('06f2b38','omitted-lessons',['tests/test_memory_decisions.py::test_missing_optional_lessons_are_reported_without_discarding_code']),
 ('106196b','provisional-budget',['tests/test_mother_review_budget.py']),
]


def snapshot(ref):
    sha=subprocess.check_output(['git','-C',str(REPO),'rev-parse',ref],text=True).strip()
    root=WORK/sha[:7]
    if not root.exists():
        root.mkdir(parents=True)
        data=subprocess.check_output(['git','-C',str(REPO),'archive','--format=zip',sha,'src','tests','pyproject.toml'])
        with zipfile.ZipFile(io.BytesIO(data)) as z:z.extractall(root)
    return root,sha


if __name__=='__main__':
    results=[]
    for ref,label,nodeids in CASES:
        test_root,after_sha=snapshot(ref)
        for phase,source_ref in [('before',ref+'^'),('after',ref)]:
            src,commit=snapshot(source_ref)
            logs=OUT/label/phase;logs.mkdir(parents=True,exist_ok=True)
            temp=WORK/(label+'-'+phase);temp.mkdir(exist_ok=True)
            env={**os.environ,'PYTHONPATH':str(src/'src'),'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8',
                 'TEMP':str(temp),'TMP':str(temp),'TMPDIR':str(temp),'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'}
            command=[sys.executable,'-m','pytest','-q',*nodeids,'--junitxml='+str(logs/'pytest.xml'),'--basetemp='+str(temp/'tests')]
            with (logs/'pytest.log').open('w',encoding='utf8') as f:
                proc=subprocess.run(command,cwd=test_root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180)
            xml=ElementTree.parse(logs/'pytest.xml').getroot()
            result={'case':label,'phase':phase,'engine_commit':commit,'test_commit':after_sha,'nodeids':nodeids,'exit_code':proc.returncode,
                    'suites':[s.attrib for s in xml.iter('testsuite')],
                    'failures':[dict(name=t.get('name'),details='\n'.join((x.text or '') for x in t if x.tag in {'failure','error'}))
                     for t in xml.iter('testcase') if any(x.tag in {'failure','error'} for x in t)]}
            write(logs/'result.json',result);results.append(result)
            write(OUT/'results.json',results)
            print(json.dumps({k:result[k] for k in ('case','phase','engine_commit','exit_code','suites')}),flush=True)
