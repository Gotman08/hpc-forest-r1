"""Paired factorial contrasts with explicit failures, plan and conversation audits."""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
from collections import Counter
from pathlib import Path

from audit_advice import audit as audit_adviser
from audit_control import audit as audit_mother
from campaign_evidence import arm_summary, positive, read, valid, write_csv

from hpc_forest.core import digest

CONTRASTS = [('corrected', 'off')]


def contrasts(rows):
    indexed = {(r['case'], r['repeat'], r['condition']): r for r in rows}
    paired = []
    for case, repeat in sorted({(r['case'], r['repeat']) for r in rows}):
        for a, b in CONTRASTS:
            left, right = indexed.get((case, repeat, a), {}), indexed.get((case, repeat, b), {})
            for distribution in ('registered', 'reserved'):
                x, y = left.get(distribution + '_speedup'), right.get(distribution + '_speedup')
                ratio = x / y if positive(x) and positive(y) else None
                paired.append({'case': case, 'repeat': repeat, 'contrast': a + '/' + b,
                    'distribution': distribution, 'ratio': ratio,
                    'log_ratio': math.log(ratio) if ratio else None,
                    'numerator_delivered': left.get('pipeline_complete', False),
                    'denominator_delivered': right.get('pipeline_complete', False),
                    'both_valid_and_within_cap': ratio is not None})
    aggregates = []
    for case, contrast, distribution in sorted({(p['case'], p['contrast'], p['distribution']) for p in paired}):
        members = [p for p in paired if (p['case'], p['contrast'], p['distribution']) == (case, contrast, distribution)]
        values = [p['ratio'] for p in members if p['ratio'] is not None]
        aggregates.append({'case': case, 'contrast': contrast, 'distribution': distribution,
            'assigned_pairs': len(members), 'complete_valid_pairs': len(values),
            'geometric_mean_ratio': math.exp(statistics.mean(math.log(x) for x in values)) if values else None,
            'median_ratio': statistics.median(values) if values else None,
            'minimum_ratio': min(values) if values else None, 'maximum_ratio': max(values) if values else None,
            'wins': sum(x > 1 for x in values), 'losses': sum(x < 1 for x in values),
            'conditional_on_delivery': len(values) != len(members)})
    return paired, aggregates


def analyze(blocks, output, registered=None, reserved=None):
    output.mkdir(parents=True, exist_ok=True)
    rows, details, trajectory, advice, controls, control_events = [], [], [], [], [], []
    errors, threads, plan_hashes = [], set(), {}
    distributions = {'registered': read(registered, {}) if registered else {},
                     'reserved': read(reserved, {}) if reserved else {}}
    for block in blocks:
        plan, frozen = read(block / 'pair.json'), read(block / 'frozen-plan.json')
        case = plan['case']
        if frozen['plan_sha256'] != digest(frozen['plan']):
            raise ValueError('Corrupt common plan')
        if case in plan_hashes and plan_hashes[case] != frozen['plan_sha256']:
            raise ValueError('Different initial plans across repeats')
        plan_hashes[case] = frozen['plan_sha256']
        measured = read(block / 'paired-measurements.json', {}).get('outcomes', {})
        for arm in plan['arms']:
            identity = {'case': case, 'repeat': plan['repeat'], 'condition': arm['condition']}
            root = block / ('forest-app-' + arm['id'])
            try:
                row, detail, points = arm_summary(block, arm, measured)
                actual_plan = detail.get('initial_forest') or {}
                if actual_plan and actual_plan.get('plan_sha256') != frozen['plan_sha256']:
                    raise ValueError('Research used a different initial plan')
                thread = actual_plan.get('conversation', {}).get('thread_id')
                if thread and (thread in threads or thread == frozen['planning_receipt']['thread_id']):
                    raise ValueError('Shared Mother conversation')
                if thread:
                    threads.add(thread)
                row.update(initial_plan_sha256=frozen['plan_sha256'], independent_mother_thread=bool(thread),
                           context_scope=arm['advisor']['context_scope'], validation_policy=arm['advisor']['validation_policy'])
                for point in points:
                    cost = row.get('charged_planning_seconds')
                    point['charged_seconds'] = point['seconds_since_start'] + cost if cost is not None else None
                trajectory.extend(points)
                details.append(detail)
                arows, asummary = audit_adviser(root) if row.get('started', True) else ([], {'not_started': True})
                advice.extend({**identity, **a} for a in arows)
                detail['adviser_audit'] = asummary
                crow, cevents = audit_mother(root) if row.get('started', True) else ({'not_started': True}, [])
                controls.append({**identity, **crow})
                control_events.extend({**identity, **e} for e in cevents)
            except (OSError, ValueError, KeyError, TypeError, StopIteration, sqlite3.Error) as exc:
                # Retain every assigned arm; a failed audit is never a zero-time success.
                errors.append({**identity, 'error': type(exc).__name__ + ': ' + str(exc)})
                result = read(root / 'arm-result.json', {})
                row = {**identity, 'pipeline_complete': result.get('pipeline_complete', False),
                       'finished_within_cap': result.get('finished_within_cap', False), 'audit_failed': True,
                       'error': str(exc)}
            for distribution, data in distributions.items():
                outcome = data.get(case, {}).get('outcomes', {}).get('r' + str(plan['repeat']) + '-' + arm['condition'], {})
                row[distribution + '_status'] = outcome.get('status')
                row[distribution + '_seconds'] = outcome.get('mean_seconds')
                row[distribution + '_speedup'] = outcome.get('speedup') if (not row.get('audit_failed')
                    and row['pipeline_complete'] and row['finished_within_cap'] and valid(outcome)) else None
            rows.append(row)
    paired, aggregate = contrasts(rows)
    for name, values in [('arms', rows), ('paired-contrasts', paired), ('contrast-summary', aggregate),
                          ('trajectory', trajectory), ('adviser-decisions', advice),
                          ('mother-control', controls), ('mother-events', control_events), ('audit-errors', errors)]:
        if values:
            keys = list(dict.fromkeys(k for row in values for k in row))
            write_csv(output / (name + '.csv'), [{k: row.get(k) for k in keys} for row in values])
    summary = {'assigned_arms': len(rows), 'delivered': sum(r['pipeline_complete'] for r in rows),
        'independent_mother_threads': len(threads), 'common_plan_hashes': plan_hashes,
        'audit_errors': errors, 'contrasts': aggregate,
        'condition_counts': dict(Counter(r['condition'] for r in rows)),
        'limits': ['One search per condition/problem: functional pilot only, no superiority inference.',
            'Mother steering is a mediator, not a separately randomized cause.',
            'Only selected children have observed outcomes; no counterfactual regret.',
            'Timing repetitions are not independent search repetitions.',
            'Both conditions use the same corrected engine; only the adviser enable flag differs.']}
    (output / 'analysis.json').write_text(json.dumps({'summary': summary, 'arms': details}, indent=2) + '\n', encoding='utf8')
    lines = ['# Étude contrôlée Forest / TabPFN', '',
        f"Recherches attribuées : {len(rows)} ; livrées : {summary['delivered']} ; erreurs d'audit : {len(errors)}.", '',
        'Luna Max pour tous les rôles LLM. Un plan initial commun par problème, conversations indépendantes.', '',
        '| Problème | Contraste | Entrées | Paires valides | Ratio géométrique | Minimum–maximum |',
        '|---|---|---|---:|---:|---:|']
    for a in aggregate:
        ratio = f"{a['geometric_mean_ratio']:.3f}" if a['geometric_mean_ratio'] is not None else '—'
        interval = f"{a['minimum_ratio']:.3f}–{a['maximum_ratio']:.3f}" if a['minimum_ratio'] is not None else '—'
        lines.append(f"| {a['case']} | {a['contrast']} | {a['distribution']} | {a['complete_valid_pairs']}/{a['assigned_pairs']} | {ratio} | {interval} |")
    lines.extend(['', 'Un ratio supérieur à 1 favorise la condition située à gauche du contraste.', '',
        'Les ratios ne remplacent pas les taux de livraison. Les écarts doivent être lus avec la dispersion des temps,',
        'les erreurs d’infrastructure et les décisions de Mother. Ce tableau automatique ne suffit pas à attribuer',
        'une régression à un composant ; les journaux et chronologies sont conservés pour cette analyse.', ''])
    (output / 'RAPPORT.md').write_text('\n'.join(lines), encoding='utf8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--blocks', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--registered', type=Path)
    parser.add_argument('--reserved', type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.blocks, args.output, args.registered, args.reserved)))
