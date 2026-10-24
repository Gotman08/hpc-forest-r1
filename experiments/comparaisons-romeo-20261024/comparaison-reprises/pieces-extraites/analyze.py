"""Paired old/new speedups, preserving the original documentary row definitions."""
from pathlib import Path
import collections
import csv
import datetime
import json
import math
import statistics as st

R = Path(__file__).resolve().parent
O = R.parents[1]/'outputs/comparaison-reprises'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


old = read(R.parent/'reference-study/analysis.json')
cases = {r['case_id'] for r in read(R/'campaigns.json')}
groups = {'cpu': read(R/'paired-cpu-results.json') + read(R/'paired-cpu-base64-results.json'), 'extra': read(R/'paired-extra-results.json'),
          'render': sum([read(R/('paired-render-'+case+'-results.json'))
                         for case in ['aobench', 'deferred', 'raytracer', 'volume']], [])}
utf8_audit = read(R/'paired-cpu-utf8-audit.json')
identities={}
for stem in ['paired-cpu','paired-cpu-base64','paired-extra',*['paired-render-'+c for c in ['aobench','deferred','raytracer','volume']]]:
    manifest=read(R/stem/'manifest.json')
    artifacts=read(R/(stem+'-environment.json'))['candidate_artifact_sha256']
    for key in {m['case_id'] for m in manifest}:
        old_m=next(m for m in manifest if m['case_id']==key and m['variant']=='old_selected')
        new_m=next(m for m in manifest if m['case_id']==key and m['variant']=='new_selected')
        a=artifacts.get(key+'/old_selected/candidate.so')
        b=artifacts.get(key+'/new_selected/candidate.so')
        identities[key]={'old_source_sha256':old_m['sha256'],'new_source_sha256':new_m['sha256'],
                         'source_identical_old_new':old_m['sha256']==new_m['sha256'],
                         'binary_identical_old_new':a==b if a and b else None}
assert all(r['cases'] == 79729 for r in utf8_audit['records'])
assert all(r['failed'] == 0 for r in utf8_audit['records'] if r['variant'] in {'old_selected', 'new_selected', 'old_g', 'new_g'}), utf8_audit


def samples(row, variant):
    result = []
    for item in groups[row['group']]:
        m = item.get('measurement', {})
        if (item['case_id'] != row['case_id'] or item['variant'] != variant
                or item.get('diagnostic') or item.get('exit_code') != 0
                or m.get('correct') is not True or m.get('n') != row['n']
                or row['threads'] is not None and m.get('threads') != row['threads']
                or m.get('pattern', 0) != row.get('pattern', 0)):
            continue
        seconds = m.get('seconds', m.get('latency_ms', 0)/1000)
        if seconds > 0 and math.isfinite(seconds):
            result.append({**m, 'seconds': seconds, 'block': item['block']})
    return result


def aggregate(records, method):
    if not records:
        return None
    times = [r['seconds'] for r in records]
    return {'seconds': {'median': st.median, 'mean': st.mean, 'min': min}[method](times),
            'count': len(times), 'min': min(times), 'max': max(times),
            'cv_pct': 100*st.stdev(times)/st.mean(times) if len(times) > 1 else 0}


def paired_range(a, b):
    by_block = {r['block']: r['seconds'] for r in b}
    ratios = [r['seconds']/by_block[r['block']] for r in a if r['block'] in by_block]
    return [min(ratios), max(ratios)] if ratios else None


rows = []
for previous in old['rows']:
    if previous.get('case_id') not in cases:
        continue
    row = {k: previous.get(k) for k in ['id', 'label', 'case_id', 'group', 'n', 'threads',
           'pattern', 'aggregation', 'baseline_variant', 'reference_variant', 'published_speedup',
           'published_hardware', 'hardware', 'compiler', 'published_input', 'source', 'notes']}
    if row['case_id'] == 'base64':
        row['notes'] = row['notes'].split('Deux erreurs')[0].strip()
    if row['case_id'] == 'blackscholes' and row['threads'] == 40:
        row['notes'] += ' Forte variabilité confirmée par 21 blocs supplémentaires dans une autre allocation ; aucune conclusion robuste sur le gain. Voir STABILITE-BLACKSCHOLES.json. Les sept blocs primaires restent affichés.'
    row['previous_forest_speedup'] = previous['forest_speedup']
    row['previous_reference_speedup'] = previous['reference_speedup']
    row.update(identities[row['case_id']])
    ss = {name: samples(row, variant) for name, variant in [
        ('baseline', row['baseline_variant']), ('reference', row['reference_variant']),
        ('old_selected', 'old_selected'), ('new_selected', 'new_selected'),
        ('old_g', 'old_g'), ('new_g', 'new_g')]}
    expected = {'cpu': 7, 'extra': 9, 'render': 3}[row['group']]
    for name in ['baseline', 'reference', 'old_selected', 'new_selected']:
        assert len(ss[name]) == expected, (row['id'], name, len(ss[name]), expected)
        assert len({r['block'] for r in ss[name]}) == expected
    for name, value in ss.items():
        row[name] = aggregate(value, row['aggregation'])
    times = {name: value['seconds'] for name, value in row.items()
             if isinstance(value, dict) and 'seconds' in value}
    for name in ['reference', 'old_selected', 'new_selected', 'old_g', 'new_g']:
        row[name+'_speedup'] = times['baseline']/times[name] if name in times else None
    row['new_vs_old'] = times['old_selected']/times['new_selected']
    row['new_vs_reference'] = times['reference']/times['new_selected']
    row['new_vs_old_range'] = paired_range(ss['old_selected'], ss['new_selected'])
    row['new_vs_old_min'], row['new_vs_old_max'] = row['new_vs_old_range']
    row['new_vs_reference_range'] = paired_range(ss['reference'], ss['new_selected'])
    row['new_speedup_range'] = paired_range(ss['baseline'], ss['new_selected'])
    row['change_percent'] = 100*(row['new_vs_old']-1)
    row['time_reduction_percent'] = 100*(1-times['new_selected']/times['old_selected'])
    lo, hi = row['new_vs_old_range']
    row['verdict'] = ('Code ou binaire identique : variation de mesure' if row['source_identical_old_new'] or row['binary_identical_old_new'] else
                      'Nouveau plus rapide dans chaque bloc' if lo > 1 else
                      'Ancien plus rapide dans chaque bloc' if hi < 1 else
                      'Écart dans la variabilité observée')
    reference_lo, reference_hi = row['new_vs_reference_range']
    row['reference_verdict'] = ('Forest dépasse la référence dans chaque bloc' if reference_lo > 1 else
                              'Référence plus rapide dans chaque bloc' if reference_hi < 1 else
                              'Forest et référence dans la variabilité observée')
    hashes = {r['block']: r.get('input_sha256') for r in ss['baseline']}
    row['input_hashes_verified'] = bool(hashes) and all(hashes.values())
    if row['input_hashes_verified']:
        for name, values in ss.items():
            assert all(hashes[r['block']] == r.get('input_sha256') for r in values), (row['id'], name)
    rows.append(row)

raw = []
for group, records in groups.items():
    for record in records:
        m = record.get('measurement', {})
        raw.append({'group': group, 'case_id': record['case_id'], 'variant': record['variant'],
                    'block': record['block'], 'diagnostic': record.get('diagnostic', False),
                    'n': m.get('n'), 'threads': m.get('threads'), 'seed': m.get('seed'),
                    'pattern': m.get('pattern'), 'seconds': m.get('seconds', m.get('latency_ms', 0)/1000) or None,
                    'correct': m.get('correct'), 'exit_code': record.get('exit_code'),
                    'input_sha256': m.get('input_sha256'), 'max_abs_error': m.get('max_abs_error'),
                    'rmse': m.get('rmse'), 'error': record.get('error', m.get('error'))})
assert len(rows) == 35
failures = [r for r in raw if r['correct'] is not True or r['exit_code'] != 0]
assert all(r['variant'] not in {'old_selected', 'new_selected'} for r in failures), failures
summary = {'cases': len(cases), 'documentary_observations': len(rows), 'records': len(raw),
           'verdict_counts': dict(collections.Counter(r['verdict'] for r in rows)),
           'reference_verdict_counts': dict(collections.Counter(r['reference_verdict'] for r in rows)),
           'failures': failures, 'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
data = {'summary': summary, 'rows': rows, 'measurements': raw, 'utf8_audit': utf8_audit}
(R/'analysis.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')
(O/'RESULTATS.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')
fields = ['id', 'label', 'published_speedup', 'previous_reference_speedup', 'reference_speedup',
          'previous_forest_speedup', 'old_selected_speedup', 'new_selected_speedup', 'old_g_speedup', 'new_g_speedup',
          'new_vs_old', 'new_vs_reference', 'change_percent', 'time_reduction_percent', 'verdict',
          'reference_verdict', 'published_hardware', 'hardware', 'n', 'threads', 'aggregation', 'source']
fields += ['source_identical_old_new','binary_identical_old_new','old_source_sha256','new_source_sha256']
fields += ['new_vs_old_min','new_vs_old_max','compiler','input_hashes_verified','notes']
with (O/'COMPARAISON.csv').open('w', encoding='utf-8-sig', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows({k: r.get(k) for k in fields} for r in rows)
print(json.dumps(summary, ensure_ascii=False))
