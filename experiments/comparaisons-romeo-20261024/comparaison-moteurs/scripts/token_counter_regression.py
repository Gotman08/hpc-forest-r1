"""Reproduce cumulative-token double counting in seven frozen engine parsers."""
import json
import os
from pathlib import Path
import subprocess
from engine_study import ROOT,CONDITIONS,PYTHON,read,write

def main():
    folder=ROOT/'work/token-counter-regression';folder.mkdir(exist_ok=True)
    for name,usage in [('first',{'input_tokens':100,'cached_input_tokens':40,'output_tokens':10}),
                       ('resumed',{'input_tokens':150,'cached_input_tokens':60,'output_tokens':15})]:
        (folder/(name+'.jsonl')).write_text(json.dumps({'type':'turn.completed','usage':usage})+'\n',encoding='utf8')
    script=folder/'probe.py'
    script.write_text('''from pathlib import Path
import json
from hpc_forest.codex_process import usage_from_events
p=Path(__file__).parent
a,_=usage_from_events(p/'first.jsonl',observe_only=True)
b,_=usage_from_events(p/'resumed.jsonl',observe_only=True)
print(json.dumps({'first_parsed':a['tokens'],'resumed_parsed':b['tokens'],'engine_sum':a['tokens']+b['tokens']}))
''',encoding='utf8')
    rows=[]
    for key in CONDITIONS:
        source=ROOT/'work/engine-study-r3'/key/'payload/project/src'
        env={**os.environ,'PYTHONPATH':str(source),'PYTHONDONTWRITEBYTECODE':'1'}
        proc=subprocess.run([str(PYTHON),str(script)],env=env,capture_output=True,text=True,timeout=30)
        assert proc.returncode==0,proc.stderr
        result=json.loads(proc.stdout)
        assert result['first_parsed']==110 and result['resumed_parsed']==165 and result['engine_sum']==275
        rows.append({'condition':key,**result,'correct_thread_total':165,'correct_second_increment':55,
            'overcount':110,'reproduced':True})
    write(ROOT/'outputs/comparaison-moteurs/protocol/token-counter-regression.json',{
        'assumption_verified_separately':'Native turn.completed usage is cumulative per thread in this local Codex version',
        'engine_sources_modified':False,'gpu_or_model_calls':0,'results':rows})
    print(json.dumps({'engines_checked':len(rows),'overcount_reproduced':all(r['reproduced'] for r in rows)}))

if __name__=='__main__':main()
