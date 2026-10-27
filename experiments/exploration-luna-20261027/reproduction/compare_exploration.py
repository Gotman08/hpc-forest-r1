"""Join paired outcomes, measured exploration and the descriptive R3 reference."""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def write_csv(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study', type=Path)
    args = parser.parse_args()
    study = args.study.resolve()
    results = study / 'results'
    analysis = read(results / 'analysis.json')
    previous = read(study.parent / 'quality-luna-20261027-r3/results/analysis.json')
    indexed = {(a['summary']['case'], a['summary']['condition']): a['summary'] for a in previous['arms']}
    rows = []
    for arm in analysis['arms']:
        summary = arm['summary']
        case, repeat, condition = summary['case'], summary['repeat'], summary['condition']
        identity = f'{case}-r{repeat}-{condition}'
        current = read(results / (identity + '-exploration.json'))['summary']
        prior = read(study / 'baseline-r3' / f'{case}-{condition}-exploration.json')['summary']
        baseline = indexed[case, condition]
        elapsed = summary.get('charged_elapsed_seconds')
        row = {k: summary.get(k) for k in ('case', 'repeat', 'seed', 'condition', 'job_id', 'host',
            'delivery_valid', 'pipeline_complete', 'target_seconds', 'cap_seconds', 'elapsed_seconds',
            'charged_elapsed_seconds', 'registered_speedup', 'reserved_speedup', 'stop_reason',
            'advisor_calls', 'advisor_validated_calls', 'advisor_reorders', 'advisor_seconds')}
        for key in ('research_trials', 'correct_measured_trials', 'correct_distinct_source_trees',
                    'selected_parent_ids', 'root_proposals', 'refinement_proposals', 'max_depth',
                    'trials_with_archived_source_excerpts', 'trials_with_slower_inspirations',
                    'analyst_calls', 'mother_calls', 'analyst_call_seconds_sum', 'mother_call_seconds_sum'):
            row[key] = current[key]
            row['r3_' + key] = prior[key]
        row['correct_measured_trials_per_charged_hour'] = current['correct_measured_trials'] * 3600 / elapsed if elapsed else None
        row['r3_correct_measured_trials_per_charged_hour'] = prior['correct_measured_trials'] * 3600 / baseline['charged_elapsed_seconds']
        row['measured_trial_count_ratio_vs_r3'] = current['correct_measured_trials'] / prior['correct_measured_trials']
        row['r3_registered_speedup'] = baseline['registered_speedup']
        row['r3_reserved_speedup'] = baseline['reserved_speedup']
        rows.append(row)
    rows.sort(key=lambda r: (r['case'], r['repeat'], r['condition']))
    grouped = []
    for case, condition in sorted({(r['case'], r['condition']) for r in rows}):
        subset = [r for r in rows if (r['case'], r['condition']) == (case, condition)]
        group = {'case': case, 'condition': condition, 'reported_repeats': len(subset),
                 'delivered': sum(r['pipeline_complete'] is True for r in subset)}
        for metric in ('correct_measured_trials', 'correct_distinct_source_trees', 'selected_parent_ids',
                       'registered_speedup', 'reserved_speedup', 'analyst_calls', 'mother_calls'):
            values = [r[metric] for r in subset if r[metric] is not None]
            group[metric + '_median'] = statistics.median(values) if values else None
            group[metric + '_min'] = min(values) if values else None
            group[metric + '_max'] = max(values) if values else None
        grouped.append(group)
    write_csv(results / 'exploration-comparison.csv', rows)
    write_csv(results / 'exploration-groups.csv', grouped)
    value = {'arms': rows, 'groups': grouped, 'paired_adviser_contrasts': analysis['summary']['contrasts'],
             'assigned_arms': analysis['summary']['assigned_arms'],
             'audit_errors': analysis['summary']['audit_errors'],
             'limitations': ['Two repetitions per case/condition; descriptive pilot.',
                 'R3 is a previous measurement session and changes the whole architecture lot.',
                 'Only within-study pairs isolate the adviser flag; Mother remains a mediator.',
                 'Counts of distinct exact source trees do not establish algorithmic diversity.',
                 'Source exposure does not prove use; call durations overlap each other and research.']}
    (results / 'exploration-comparison.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'arms': len(rows), 'groups': grouped}))


if __name__ == '__main__':
    main()
