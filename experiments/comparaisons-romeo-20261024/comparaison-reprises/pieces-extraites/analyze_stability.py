"""Keep the post-hoc Black-Scholes stability check separate from primary results."""
import json
import statistics as st
from pathlib import Path

R = Path(__file__).resolve().parent
O = R.parents[1] / 'outputs/comparaison-reprises'
stem = 'paired-cpu-blackscholes-stability'


def read(p):
    return json.loads(p.read_text(encoding='utf8'))


primary = read(R / 'paired-cpu-results.json')
secondary = read(R / (stem + '-results.json'))
assert all(r['exit_code'] == 0 and r['measurement']['correct'] is True for r in secondary)
a = read(R / 'paired-cpu/manifest.json')
b = read(R / stem / 'manifest.json')
assert [r for r in a if r['case_id'] == 'blackscholes'] == b
rows = []
for threads in [1, 4, 40]:
    row = {'threads': threads}
    for name, all_records, expected in [('primary', primary, 7), ('stability', secondary, 21)]:
        variants = {}
        for r in all_records:
            m = r.get('measurement', {})
            if r['case_id'] == 'blackscholes' and not r['diagnostic'] and m.get('threads') == threads:
                variants.setdefault(r['variant'], []).append(r)
        assert all(len(v) == expected for v in variants.values())
        for records in variants.values():
            assert all(r['exit_code'] == 0 and r['measurement']['correct'] is True for r in records)
        baselines = {r['block']: r['measurement']['input_sha256'] for r in variants['naive']}
        assert all(baselines[r['block']] == r['measurement']['input_sha256'] for v in variants.values() for r in v)
        times = {k: st.median(r['measurement']['seconds'] for r in v) for k, v in variants.items()}
        old_times = {r['block']: r['measurement']['seconds'] for r in variants['old_selected']}
        ratios = [old_times[r['block']] / r['measurement']['seconds'] for r in variants['new_selected']]
        row[name] = {'blocks': expected, 'median_seconds': times,
                     'old_speedup': times['naive'] / times['old_selected'],
                     'new_speedup': times['naive'] / times['new_selected'],
                     'new_vs_old': times['old_selected'] / times['new_selected'],
                     'paired_ratio_range': [min(ratios), max(ratios)],
                     'new_faster_blocks': sum(x > 1 for x in ratios),
                     'old_faster_blocks': sum(x < 1 for x in ratios)}
    rows.append(row)
output = {'purpose': read(R / stem / 'stability-protocol.json'),
          'primary_job': read(R / 'paired-cpu-environment.json')['job'],
          'stability_job': read(R / (stem + '-environment.json'))['job'],
          'primary_affinity': read(R / 'paired-cpu-environment.json')['affinity'],
          'stability_affinity': read(R / (stem + '-environment.json'))['affinity'],
          'same_source_manifests': True, 'rows': rows,
          'note': 'The extra 21 blocks follow an observed instability; they do not replace the primary seven blocks, alter candidates or prove which hardware effect caused the variation.',
          'measurements': secondary}
(O / 'STABILITE-BLACKSCHOLES.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf8')
print(json.dumps({k: v for k, v in output.items() if k != 'measurements'}, ensure_ascii=False))
