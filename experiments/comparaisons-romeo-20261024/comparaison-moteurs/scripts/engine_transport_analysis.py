"""Summarize transfer latency and errors without publishing local credentials."""
from collections import Counter
import json
from pathlib import Path
import shutil
import statistics
from engine_study import ROOT,read,write
from engine_extract import table

def quantile(values,q):
    if not values:return None
    v=sorted(values);p=(len(v)-1)*q;a=int(p);b=min(a+1,len(v)-1)
    return v[a]+(v[b]-v[a])*(p-a)

def main():
    base=ROOT/'outputs/comparaison-moteurs';rows=[];errors=[]
    for series,name,dest in [('shared-scp','engine-broker','relance-controlee'),('atomic','engine-broker-fast','serie-atomique')]:
        folder=ROOT/'work'/name
        ops=[json.loads(line) for line in (folder/'operations.jsonl').read_text().splitlines()]
        target=base/dest/'protocol/transport';target.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(folder/'operations.jsonl',target/'operations.jsonl')
        shutil.copyfile(folder/'public-config.json',target/'public-config.json')
        groups=sorted(set((o['tool'],o.get('transport','shared-scp')) for o in ops))
        first_success={}
        for o in ops:
            if o['ok'] and o['tool']=='list_dir':first_success.setdefault(o['remote_path'],o['started'])
        for o in ops:
            if not o['ok']:
                expected_startup=o['tool']=='list_dir' and o['remote_path'].endswith('/mailbox') and o['started']<first_success.get(o['remote_path'],float('inf'))
                errors.append({'series':series,'before_first_successful_mailbox_listing':expected_startup,**o})
        for tool,transport in groups:
            group=[o for o in ops if o['tool']==tool and o.get('transport','shared-scp')==transport]
            seconds=[o['seconds'] for o in group];queue=[o['queue_seconds'] for o in group]
            rows.append({'series':series,'tool':tool,'transport':transport,'operations':len(group),'errors':sum(not o['ok'] for o in group),
                'duration_median_seconds':statistics.median(seconds),'duration_p95_seconds':quantile(seconds,.95),'duration_max_seconds':max(seconds),
                'queue_median_seconds':statistics.median(queue),'queue_p95_seconds':quantile(queue,.95),'queue_max_seconds':max(queue)})
    write(base/'data/transport-summary.json',rows);write(base/'data/transport-errors.json',errors)
    table(base/'tables/transport-summary.csv',rows);table(base/'tables/transport-errors.csv',errors)
    print(json.dumps({'groups':len(rows),'errors':len(errors),'non_startup_errors':dict(Counter(e['series'] for e in errors if not e['before_first_successful_mailbox_listing']))}))

if __name__=='__main__':main()
