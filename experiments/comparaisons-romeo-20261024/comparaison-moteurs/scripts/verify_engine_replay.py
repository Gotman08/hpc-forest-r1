"""Recompute the new replay's statistics and verify all hashes and outcomes."""
import math
import statistics
from engine_study import ROOT,read,write,sha
from engine_extract import table

def same(a,b):return math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-15)

def main():
    base=ROOT/'outputs/comparaison-moteurs';gpu=base/'gpu-comparaison'
    summary=read(gpu/'results/summary.json');variants=read(gpu/'variants.json')
    order=read(gpu/'results/benchmark-order.json');expected={v['id'] for v in variants}
    assert {r['id'] for r in summary['programs']}==expected
    eligible={r['id'] for r in summary['programs'] if r['correct']}-{'baseline-control'}
    assert len(order)==5
    for seq in order:
        assert seq[0]==seq[-1]=='baseline-control'
        assert len(seq)==len(eligible)+2 and set(seq[1:-1])==eligible
    cases=[];sizes=[];recomputed={};outcomes=[]
    for p in summary['programs']:
        key=p['id'];record=read(gpu/'results/records'/f'{key}.json')
        variant=next(v for v in variants if v['id']==key)
        source=gpu/'sources'/key/'src'
        assert sha(source/'nbody_kernel.cu')==variant['source_sha256']==p['source_sha256']
        assert read(source/'launch.json')==variant['launch']==p['launch']
        if variant.get('launch_sha256'):assert sha(source/'launch.json')==variant['launch_sha256']
        for phase,check in record['checks'].items():
            payload=check.get('payload') or {}
            if payload.get('details'):
                assert len(payload['details'])<=11
                for d in payload['details']:
                    cases.append({'program':key,'phase':phase,**d})
            if p['correct']:
                assert check['exit_code']==0 and payload['correct'] and payload['cases']==11
                assert all(d['ok'] and d['mass_exact'] and d['mismatches']==0 for d in payload['details'])
        values=[]
        for sample in record['samples']:
            payload=sample.get('payload') or {}
            if sample['exit_code']!=0 or not payload.get('correct'):continue
            assert payload['warmup_launches']==10 and payload['timed_launches_per_size']==100
            assert [d['n'] for d in payload['details']]==[4096,8192,16384]
            assert all(d['ok'] and d['mass_exact'] and d['mismatches']==0 for d in payload['details'])
            value=math.exp(statistics.mean(math.log(d['latency_ms']/1000) for d in payload['details']))
            assert same(value,payload['seconds'])
            values.append(value)
            for d in payload['details']:sizes.append({'program':key,'block':sample['block'],'position':sample['position'],**d})
            import json
            assert json.loads((gpu/'results'/sample['log']).read_text().splitlines()[-1])==payload
        if p['fully_measured']:
            assert record['eligible'] and record['status']=='correct'
            assert len(values)==(10 if key=='baseline-control' else 5)
            assert len(p['samples'])==len(values) and all(same(a,b) for a,b in zip(values,p['samples']))
            assert same(statistics.mean(values),p['mean_seconds'])
            assert same(statistics.median(values),p['median_seconds'])
            assert same(statistics.stdev(values),p['stdev_seconds'])
            recomputed[key]=values
        else:assert p['mean_seconds'] is None
        outcomes.append({'program':key,'correct':p['correct'],'fully_measured':p['fully_measured'],'status':p['status']})
    baseline=recomputed['baseline-control'];mean=statistics.mean(baseline)
    assert same(mean,summary['baseline_mean_seconds'])
    for p in summary['programs']:
        if p['fully_measured']:assert same(mean/p['mean_seconds'],p['speedup'])
    for control in summary['controls']:
        assert all(same(a,b) for a,b in zip(control['seconds'],baseline[2*control['block']:2*control['block']+2]))
    environment=read(gpu/'results/environment.json')
    assert environment['protocol_sha256']=='3311797eec4fec382991af5fe8f8fedb76bdaa068facfe1258f688e051ffeb74'
    proof={'all_consistency_checks_passed':True,'programs':len(expected),'correct_programs':sum(p['correct'] for p in outcomes),
        'fully_measured_programs':len(recomputed),'correctness_case_results':len(cases),'timing_samples_recomputed':sum(map(len,recomputed.values())),
        'per_size_latencies_recomputed':len(sizes),'baseline_mean_seconds':mean,'baseline_range_pct':100*(max(baseline)-min(baseline))/mean,
        'median_program_cv_pct':statistics.median(100*p['stdev_seconds']/p['mean_seconds'] for p in summary['programs'] if p['fully_measured']),
        'max_program_cv_pct':max(100*p['stdev_seconds']/p['mean_seconds'] for p in summary['programs'] if p['fully_measured']),
        'summary_sha256':sha(gpu/'results/summary.json'),'job_id':environment['job_id'],'outcomes':outcomes}
    write(base/'protocol/new-replay-verification.json',proof)
    table(base/'tables/rejeu-correction-par-cas.csv',cases)
    table(base/'tables/rejeu-temps-par-taille.csv',sizes)
    print(__import__('json').dumps({k:v for k,v in proof.items() if k!='outcomes'}))

if __name__=='__main__':main()
