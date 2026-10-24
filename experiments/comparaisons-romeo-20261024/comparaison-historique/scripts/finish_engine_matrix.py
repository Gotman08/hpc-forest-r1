"""Observe existing Windows pytest processes after extending only supervision."""
import concurrent.futures
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime
from xml.etree import ElementTree

ROOT=Path(__file__).resolve().parents[3] if Path(__file__).parent.name=='scripts' else Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/comparaison-historique'
WORK=ROOT/'work/engine-snapshots'
K=ctypes.WinDLL('kernel32',use_last_error=True)
K.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];K.OpenProcess.restype=wintypes.HANDLE
K.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];K.WaitForSingleObject.restype=wintypes.DWORD
K.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
K.CloseHandle.argtypes=[wintypes.HANDLE]
TARGETS=[('106196b',2364,'2026-10-23T11:43:03.968481+02:00'),('2ea3236',4308,'2026-10-23T11:43:03.989673+02:00'),('2ee6125',15176,'2026-10-23T11:43:06.630164+02:00')]


def finish(target,handle):
    key,pid,started=target;start=datetime.fromisoformat(started).timestamp();logs=OUT/'engine-tests-isolated'/key
    assert K.WaitForSingleObject(handle,3600000)==0,'Process did not finish within extension'
    code=wintypes.DWORD();assert K.GetExitCodeProcess(handle,ctypes.byref(code));K.CloseHandle(handle)
    pytest_end=time.time()
    row=next(r for r in json.loads((OUT/'engine-tests-isolated/plan.json').read_text(encoding='utf8')) if r['commit'].startswith(key))
    command=[sys.executable,'-m','pytest','-q','--junitxml='+str(logs/'pytest.xml'),'--basetemp='+str(WORK/('tests-'+key))]
    commands=[dict(check='pytest',exit_code=code.value,elapsed_seconds=pytest_end-start,command=command,
                   exit_observed_from_windows_process_handle=True,process_id=pid,supervision_extended=True)]
    env={**os.environ,'PYTHONPATH':str(WORK/key/'src'),'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8',
         'TEMP':str(WORK/('os-tmp-'+key)),'TMP':str(WORK/('os-tmp-'+key)),'TMPDIR':str(WORK/('os-tmp-'+key)),
         'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'}
    cmd=[sys.executable,'-m','ruff','check','src','tests'];t=time.time()
    with (logs/'ruff.log').open('w',encoding='utf8') as stream:
        run=subprocess.run(cmd,cwd=WORK/key,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=120)
    commands.append(dict(check='ruff',exit_code=run.returncode,elapsed_seconds=time.time()-t,command=cmd))
    xml=ElementTree.parse(logs/'pytest.xml').getroot()
    result=dict(**row,python=sys.executable,python_version=sys.version,tests='own historical tests, unmodified',
                concurrency=6,started=start,finished=time.time(),commands=commands,
                supervision_note='Original matrix supervisor stopped before its 1800-second timeout. The same pytest process continued unchanged; exit status captured through a Windows process handle.',
                excluded_from_snapshot=['experiments/ except the exact reference.cu test fixture'],
                test_suites=[s.attrib for s in xml.iter('testsuite')],
                failures=[dict(classname=c.get('classname'),name=c.get('name'),diagnostic='\n'.join(x.text or '' for x in c if x.tag in {'failure','error'})) for c in xml.iter('testcase') if any(x.tag in {'failure','error'} for x in c)],
                skips=[dict(classname=c.get('classname'),name=c.get('name'),reason=c.find('skipped').get('message')) for c in xml.iter('testcase') if c.find('skipped') is not None])
    (logs/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps({'commit':key,'pytest_exit':code.value,'ruff_exit':run.returncode,'suites':result['test_suites']}),flush=True)


if __name__=='__main__':
    handles=[K.OpenProcess(0x100000|0x1000,False,t[1]) for t in TARGETS]
    assert all(handles),ctypes.get_last_error()
    (OUT/'protocol/test-supervision-extension.json').write_text(json.dumps(dict(observed_at=time.time(),old_supervisor_pid=26860,targets=TARGETS,
        method='Retain running tests; replace only wall-clock supervisor before original timeout',sources_or_tests_changed=False),indent=2)+'\n')
    print('PROCESS_HANDLES_OPENED',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(finish,TARGETS,handles))
    all_results=[json.loads(p.read_text(encoding='utf8')) for p in (OUT/'engine-tests-isolated').glob('*/result.json')]
    (OUT/'engine-tests-isolated/results.json').write_text(json.dumps(all_results,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print('ALL_ENGINE_CHECKS_COMPLETE',len(all_results),flush=True)
