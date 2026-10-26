"""Compare the same delivered commits on registered and reserved distributions."""
import argparse
import csv
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--registered', type=Path, required=True)
    parser.add_argument('--reserved', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    registered, reserved = read(args.registered / 'common-measurements.json'), read(args.reserved / 'common-measurements.json')
    if set(registered) != set(reserved):
        raise ValueError('Evaluation distributions cover different problem families')
    rows, audited = [], []
    for case in sorted(registered):
        a, b = registered[case], reserved[case]
        sources_a = {c['id']: c['commit'] for c in a['candidates'] if c['id'] != 'naive'}
        sources_b = {c['id']: c['commit'] for c in b['candidates'] if c['id'] != 'naive'}
        if sources_a != sources_b or a['protected_inputs'] != b['protected_inputs']:
            raise ValueError('Source selection changed before reserved evaluation: ' + case)
        public, hidden = a['evaluation_case'], b['evaluation_case']
        if ({n for n, _ in public['performance']} & {n for n, _ in hidden['performance']}
                or set(public['data_seeds'].values()) & set(hidden['data_seeds'].values())):
            raise ValueError('Reserved sizes or seeds overlap: ' + case)
        identities = set(sources_a) | {r['id'] for r in a['excluded']} | {r['id'] for r in b['excluded']}
        for identity in sorted(identities):
            x, y = a['outcomes'].get(identity, {}), b['outcomes'].get(identity, {})
            rows.append({'case': case, 'candidate': identity, 'commit': sources_a.get(identity),
                'registered_status': x.get('status', 'not_delivered'),
                'reserved_status': y.get('status', 'not_delivered'),
                'registered_speedup': x.get('speedup'), 'reserved_speedup': y.get('speedup'),
                'registered_seconds': x.get('mean_seconds'), 'reserved_seconds': y.get('mean_seconds'),
                'reserved_failure_reason': y.get('reason'), 'same_delivered_commit': identity in sources_a})
        audited.append({'case': case, 'same_delivered_commits': sources_a,
                        'disjoint_shapes_and_seeds': True, 'no_reselection': True})
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / 'generalization-comparison.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output / 'reserved-source-audit.json').write_text(json.dumps({'cases': audited,
        'interpretation': 'Different shapes change scaling and baseline cost. Differences are transfer observations, not standalone proof of overfitting.'}, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'cases': len(audited), 'deliveries_or_failures': len(rows)}))


if __name__ == '__main__':
    main()
