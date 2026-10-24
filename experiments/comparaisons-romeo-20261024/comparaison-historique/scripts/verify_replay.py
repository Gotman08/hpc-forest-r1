"""Independently recompute every delivered GPU aggregate from per-size logs."""
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] if Path(__file__).parent.name == "scripts" else Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/comparaison-historique'


def main():
    gpu=OUT/'gpu'
    summary=json.loads((gpu/'results/summary.json').read_text())
    variants=json.loads((gpu/'variants.json').read_text())
    order=json.loads((gpu/'results/benchmark-order.json').read_text())
    expected={v['id'] for v in variants}
    assert len(expected)==125
    assert {r['id'] for r in summary['programs']}==expected
    assert len(order)==5
    for seq in order:
        assert len(seq)==126 and seq[0]==seq[-1]=='baseline-control'
        assert len(set(seq[1:-1]))==124 and set(seq[1:-1])==expected-{'baseline-control'}
    case_rows=[]
    checked,samples,per_size=0,0,0
    all_recomputed={}
    for program in summary['programs']:
        key=program['id']
        record=json.loads((gpu/'results/records'/(key+'.json')).read_text())
        assert record['eligible'] and record['status']=='correct' and program['fully_measured']
        assert record['build']['exit_code']==0
        for phase in ['search','confirmation']:
            result=record['checks'][phase]
            payload=result['payload']; assert result['exit_code']==0 and payload['correct'] and payload['cases']==11
            log=json.loads((gpu/'results'/result['log']).read_text().splitlines()[-1])
            assert log==payload
            assert len(payload['details'])==11
            for d in payload['details']:
                assert d['ok'] and d['mass_exact'] and d['mismatches']==0
                case_rows.append(dict(program=key,phase=phase,n=d['n'],case=d['label'],max_absolute_error=d['max_absolute_error'],mass_exact=d['mass_exact'],mismatches=d['mismatches']))
                checked+=1
        recomputed=[]
        for sample in record['samples']:
            p=sample['payload'];assert sample['exit_code']==0 and p['correct'] and p['cases']==3
            assert p['warmup_launches']==10 and p['timed_launches_per_size']==100
            assert [d['n'] for d in p['details']]==[4096,8192,16384]
            assert all(d['ok'] and d['mass_exact'] and d['mismatches']==0 for d in p['details'])
            assert json.loads((gpu/'results'/sample['log']).read_text().splitlines()[-1])==p
            value=math.exp(statistics.mean(math.log(d['latency_ms']/1000) for d in p['details']))
            assert math.isclose(value,p['seconds'],rel_tol=1e-12,abs_tol=1e-15)
            recomputed.append(value);samples+=1;per_size+=3
        assert len(recomputed)==(10 if key=='baseline-control' else 5)
        assert math.isclose(statistics.mean(recomputed),program['mean_seconds'],rel_tol=1e-12)
        assert math.isclose(statistics.median(recomputed),program['median_seconds'],rel_tol=1e-12)
        assert math.isclose(statistics.stdev(recomputed),program['stdev_seconds'],rel_tol=1e-12,abs_tol=1e-15)
        assert len(program['samples'])==len(recomputed)
        assert all(math.isclose(a,b,rel_tol=1e-12) for a,b in zip(program['samples'],recomputed))
        all_recomputed[key]=recomputed
        if key!='baseline-control':
            variant=next(v for v in variants if v['id']==key)
            source=OUT/'sources'/key/'src/nbody_kernel.cu'
            launch=OUT/'sources'/key/'src/launch.json'
            assert hashlib.sha256(source.read_bytes()).hexdigest()==variant['source_sha256']
            assert hashlib.sha256(launch.read_bytes()).hexdigest()==variant['launch_sha256']
    baseline=all_recomputed['baseline-control'];base_mean=statistics.mean(baseline)
    assert math.isclose(base_mean,summary['baseline_mean_seconds'],rel_tol=1e-12)
    for p in summary['programs']:
        assert math.isclose(base_mean/p['mean_seconds'],p['speedup'],rel_tol=1e-12)
    for b in summary['controls']:
        vals=baseline[b['block']*2:b['block']*2+2]
        assert all(math.isclose(x,y,rel_tol=1e-12) for x,y in zip(vals,b['seconds']))
    receipt=dict(all_checks_passed=True,programs=125,historical_programs=124,correctness_cases_recomputed=checked,
                 benchmark_samples_recomputed=samples,size_latencies_recomputed=per_size,
                 independent_research_campaigns_launched=0,
                 baseline_mean_seconds=base_mean,baseline_min_seconds=min(baseline),baseline_max_seconds=max(baseline),
                 baseline_range_pct=(max(baseline)-min(baseline))/base_mean*100,
                 max_program_cv_pct=max(p['stdev_seconds']/p['mean_seconds']*100 for p in summary['programs']),
                 summary_sha256=hashlib.sha256((gpu/'results/summary.json').read_bytes()).hexdigest())
    (OUT/'protocol/replay-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
    with (OUT/'tables/correction-par-cas.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=case_rows[0].keys());w.writeheader();w.writerows(case_rows)
    print(json.dumps(receipt))


if __name__=='__main__':main()
