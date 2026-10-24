"""Descriptive comparisons of the fixed replay; no research-success inference."""
import csv
import itertools
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] if Path(__file__).parent.name == 'scripts' else Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/comparaison-historique'


def read(name):
    return json.loads((OUT/name).read_text(encoding='utf8'))


def write_csv(name, rows):
    if not rows:
        return
    with (OUT/'tables'/name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def main():
    replay = read('gpu/results/summary.json')
    variants = read('data/variants.json')
    lineage = read('data/lineage.json')
    programs = {p['id']: p for p in replay['programs']}
    assert len(programs) == 125 and all(p['fully_measured'] for p in programs.values())
    origins = {(o['job_id'], o['commit']): v['id'] for v in variants for o in v['origins']}
    records = {key: read(f'gpu/results/records/{key}.json') for key in programs}
    size_rows = []
    per_block = {}
    for key, rec in records.items():
        per_block[key] = {s['block']: s['payload']['seconds'] for s in rec['samples']}
        for sample in rec['samples']:
            for d in sample['payload']['details']:
                size_rows.append(dict(program=key, block=sample['block']+1, position=sample['position'],
                                     n=d['n'], latency_ms=d['latency_ms'],
                                     max_absolute_error=d['max_absolute_error'], mass_exact=d['mass_exact']))
    write_csv('mesures-par-taille.csv', size_rows)

    groups = defaultdict(list)
    for v in variants:
        groups[v['source_sha256']].append(v)
    launch_pairs = []
    launch_groups = []
    for source, group in groups.items():
        # Different JSON bytes alone (spacing/key order) are not a launch change.
        if len({json.dumps(v['launch'], sort_keys=True) for v in group}) < 2:
            continue
        launch_groups.append(dict(source_sha256=source, variants=[v['id'] for v in group]))
        for a, b in itertools.combinations(group, 2):
            if a['launch'] == b['launch']:
                continue
            pa, pb = programs[a['id']], programs[b['id']]
            gains = [(1-per_block[b['id']][i]/per_block[a['id']][i])*100 for i in range(5)]
            launch_pairs.append(dict(source_sha256=source, base=a['id'], variant=b['id'],
                                     base_launch=a['launch'], variant_launch=b['launch'],
                                     base_seconds=pa['mean_seconds'], variant_seconds=pb['mean_seconds'],
                                     gain_pct=(1-pb['mean_seconds']/pa['mean_seconds'])*100,
                                     block_gains_pct=gains, faster_blocks=sum(g > 0 for g in gains),
                                     base_campaigns=sorted({o['job_id'] for o in a['origins']}),
                                     variant_campaigns=sorted({o['job_id'] for o in b['origins']})))
    write_csv('comparaisons-lancements.csv', launch_pairs)

    transitions = []
    for row in lineage:
        key = row.get('variant_id')
        base = origins.get((row['campaign'], row.get('base_commit')))
        if key not in programs or base not in programs:
            continue
        gains = [(1-per_block[key][i]/per_block[base][i])*100 for i in range(5)]
        transitions.append(dict(campaign=row['campaign'], trial=row['id'], role=row['role'],
                                variant=key, base=base, identical_program=key==base,
                                change_kind=row['change_kind'],
                                gain_pct=(1-programs[key]['mean_seconds']/programs[base]['mean_seconds'])*100,
                                block_gains_pct=gains, faster_blocks=sum(g>0 for g in gains)))
    write_csv('transitions-par-bloc.csv', transitions)

    ranks = sorted((p for p in programs.values() if p['id']!='baseline-control'), key=lambda p:p['mean_seconds'])
    for p in ranks:
        p['cv_pct'] = p['stdev_seconds']/p['mean_seconds']*100
    winners = [min(per_block, key=lambda k:per_block[k][i]) for i in range(5)]
    source_counts = {k: len(v) for k,v in groups.items()}
    summary = dict(programs=124, unique_kernel_bytes=len(groups), launch_groups=launch_groups,
                   launch_group_count=len(launch_groups), launch_program_count=sum(len(g['variants']) for g in launch_groups),
                   launch_comparison_count=len(launch_pairs), top_10=ranks[:10], block_winners=winners,
                   median_program_cv_pct=statistics.median(p['cv_pct'] for p in ranks),
                   max_program_cv_pct=max(p['cv_pct'] for p in ranks),
                   same_source_identity_counts=source_counts,
                   transitions=transitions, launch_pairs=launch_pairs,
                   interpretation='Five benchmark blocks, not independent model-search campaigns; block gain signs are descriptive, not significance tests.')
    (OUT/'data/replay-analysis.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({k:summary[k] for k in ['programs','unique_kernel_bytes','launch_group_count','launch_program_count','launch_comparison_count','block_winners','median_program_cv_pct','max_program_cv_pct']}))


if __name__ == '__main__':
    main()
