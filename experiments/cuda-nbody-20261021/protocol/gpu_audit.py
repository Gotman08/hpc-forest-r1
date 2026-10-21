"""Independent verification of protected CUDA-event metrics and holdout confirmation."""
import hashlib
import json
import math
import sqlite3
import statistics
import sys
import time
from pathlib import Path

from local_status import HERE, STATE, read

sys.path.insert(0,str(Path(STATE['repository'])/'src'))
from cuda_evaluator import gpu_seconds


def audit():
    result = read(HERE/'evidence/results.json')
    path = HERE/'evidence/registry.sqlite3'
    if not result or not path.exists():
        print(json.dumps({'gpu_audit':'pending'}))
        return
    checks = []
    def check(name,passed,detail=None):
        checks.append({'name':name,'pass':bool(passed),'detail':detail})
    with sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(r) for r in db.execute('SELECT * FROM evaluations ORDER BY created,id')]
        meta = {r['key']:json.loads(r['value']) for r in db.execute('SELECT * FROM metadata')}
    for row in rows:
        row['payload'] = json.loads(row['payload'])
    config = meta['config']
    check('one_gpu_metric_adapter',config['protocol']['benchmark'][1].endswith('/protocol.py')
        and config['protocol']['benchmark'][2] == 'benchmark')
    check('input_confirmation_phase_separate',config['protocol']['check'][-1] == '{phase}'
        and config['protocol']['benchmark'][-1] == '{phase}')
    preflight = read(HERE/'evidence/gpu-preflight.json')
    check('independent_cpu_oracle_original_passed',preflight.get('passed') is True)
    allocation = read(HERE/'evidence/allocation.json')
    check('actual_one_gpu_gh200_allocation',allocation.get('machine') == 'aarch64'
        and len(str(allocation.get('cuda_visible_devices','')).split(',')) == 1
        and bool(allocation.get('cuda_visible_devices'))
        and 'GH200' in json.dumps(preflight.get('device',{})))
    reference = Path(STATE['artifact'])/'payload/validation/original.cu'
    original = Path(json.loads((Path(STATE['artifact'])/'plan.json').read_text())['source_path'])
    check('user_original_file_unchanged',hashlib.sha256(original.read_bytes()).hexdigest()
        == hashlib.sha256(reference.read_bytes()).hexdigest() == STATE['source_sha256'])
    local_logs = list((HERE/'evidence').rglob('sample-*.log'))
    metrics = []
    for log in local_logs:
        data = read(log)
        try:
            seconds = gpu_seconds(data)
            metrics.append({'file':str(log),'seconds':seconds,'phase':data['phase'],
                'per_size_ms':{str(r['n']):r['latency_ms'] for r in data['details']}})
        except Exception as exc:
            check('protected_metric_'+log.name,False,str(exc))
    check('all_downloaded_event_metrics_valid',bool(metrics) and len(metrics) == len(local_logs),
        {'metrics':len(metrics),'logs':len(local_logs)})
    summaries = []
    for row in rows:
        value = row['payload']
        if row['phase'] != 'confirmation' or not value.get('times'):
            continue
        check('five_independent_samples_'+row['experiment_id'],len(value['times']) == 5
            and all(math.isfinite(v) and v > 0 for v in value['times'])
            and math.isclose(statistics.mean(value['times']),value['mean_seconds'],rel_tol=1e-12))
        summaries.append({'experiment_id':row['experiment_id'],'correct':value['correct'],
            'status':value['status'],'mean_ms':value['mean_seconds']*1000,
            'times_ms':[t*1000 for t in value['times']],'commit':value.get('commit')})
    check('all_confirmed_finalists_five_metric_logs_collected',len(metrics) == 5*len(summaries),
        {'collected':len(metrics),'expected':5*len(summaries)})
    for summary in summaries:
        selected = [m for m in metrics if summary['experiment_id'] in Path(m['file']).parts]
        check('raw_event_samples_match_confirmed_result_'+summary['experiment_id'],
            len(selected)==5 and all(m['phase']=='confirmation' for m in selected)
            and math.isclose(statistics.mean(m['seconds'] for m in selected)*1000,
                summary['mean_ms'],rel_tol=1e-12,abs_tol=0))
    final = result.get('final_g_confirmation') or {}
    check('final_g_confirmed',final.get('status') == 'confirmed'
        and final.get('outcome',{}).get('correct') is True)
    output = {'job_id':STATE['job_id'],'at':time.time(),'checks':checks,
        'all_passed':all(c['pass'] for c in checks),'metric':'mean of repeated geometric means of CUDA-event times',
        'performance_sizes':[4096,8192,16384],'confirmation':summaries,'metrics':metrics,
        'excluded_from_timing':['NVRTC compilation','allocation','host/device transfers','process startup']}
    (HERE/'gpu-audit.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:output[k] for k in ('job_id','all_passed','confirmation')}))


if __name__ == '__main__':
    audit()
