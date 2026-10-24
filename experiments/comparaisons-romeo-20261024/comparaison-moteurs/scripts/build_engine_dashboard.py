"""Embed all comparison data into a standalone, offline HTML dashboard."""
import json
from pathlib import Path
from engine_study import ROOT, read

def build():
    out=ROOT/'outputs/comparaison-moteurs'
    data=read(out/'data/dashboard.json')
    # Escape script delimiters without changing the JSON data.
    serialized=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=Path(__file__).with_name('engine_dashboard.html').read_text(encoding='utf8')
    assert template.count('__STUDY_DATA__')==1
    target=out/'TABLEAU-DE-BORD.html'
    target.write_text(template.replace('__STUDY_DATA__',serialized),encoding='utf8')
    print(json.dumps({'path':str(target),'bytes':target.stat().st_size}))

if __name__=='__main__':build()
