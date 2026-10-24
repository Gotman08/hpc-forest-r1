"""Summarize only completed render comparisons; final joined report comes later."""
from pathlib import Path
from collections import defaultdict
import json
import statistics as st

R = Path(__file__).resolve().parent
rows = []
failures = []
for case in ['aobench', 'volume', 'deferred', 'raytracer']:
    p = R / ('paired-render-' + case + '-results.json')
    if not p.exists():
        continue
    records = json.loads(p.read_text(encoding='utf8'))
    grouped = defaultdict(lambda: defaultdict(list))
    for r in records:
        m = r.get('measurement', {})
        if r.get('exit_code') != 0 or m.get('correct') is not True:
            failures.append(r)
        if not r['diagnostic']:
            grouped[(m.get('n'), m.get('threads'))][r['variant']].append(r)
    for (n, threads), variants in grouped.items():
        for records in variants.values():
            assert len(records) == 3 and all(x.get('exit_code') == 0 and x['measurement']['correct'] for x in records)
        times = {k: st.median(x['measurement']['seconds'] for x in v) for k, v in variants.items()}
        paired = {x['block']: x['measurement']['seconds'] for x in variants['old_selected']}
        rr = [paired[x['block']] / x['measurement']['seconds'] for x in variants['new_selected']]
        rows.append({'case': case, 'n': n, 'threads': threads, 'old_speedup': times['naive']/times['old_selected'],
                     'new_speedup': times['naive']/times['new_selected'], 'new_vs_old': times['old_selected']/times['new_selected'],
                     'paired_range': [min(rr), max(rr)], 'times': times})
out = {'rows': rows, 'failures': failures, 'all_selected_diagnostics_pass': all(x['variant'] not in {'old_selected','new_selected'} for x in failures)}
(R / 'render-preview.json').write_text(json.dumps(out, indent=2), encoding='utf8')
print(json.dumps(out))
