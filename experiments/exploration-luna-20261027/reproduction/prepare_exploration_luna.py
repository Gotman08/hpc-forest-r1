"""Reuse the audited pilot pipeline for two fresh paired repeats, with source diversity."""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import prepare_quality_luna as preparation

NAME = 'exploration-luna-20261027'
preparation.STUDY = preparation.REPO / 'experiments' / NAME
preparation.WORK = preparation.TASK / 'work' / NAME
save = preparation.atomic_json


def configured_write(path, value):
    if path == preparation.STUDY / 'protocol.json':
        for case in value['cases']:
            case['seeds'] = [307, 409]
        value.update(
            schema='forest-exploration-luna-paired-v1',
            orders=[['off', 'corrected'], ['corrected', 'off']],
            evolution={'enabled': True, 'archive_size': 12, 'inspirations': 3},
            controller_changes='Progress-anchor review; ordinary Mother report batching; scoped source inspiration',
            local_validation='docs/VALIDATION-EXPLORATION-20261027.md',
            source_comparison='quality-luna-20261027-r3',
            repetition_schedule='Four campaigns per wave; repeat 2 after all repeat 1 campaigns settle',
            material_limits='Two waves of four independent five-CPU allocations; all final codes remeasured sequentially together on one allocation. Shared nodes are not exclusive.',
            extra_metrics=['real evaluated trials', 'distinct correct source texts', 'parent identities',
                           'root/refinement proposals', 'control call count and duration', 'source excerpt exposure'])
        value['analysis'].update(replicates_per_problem_condition=2, searches=8,
            scope='Two paired independent repetitions per case; descriptive pilot, not a reliable superiority estimate')
    elif path.name == 'settings.json' and path.parent.name == 'payload':
        value['evolution'] = {'enabled': True, 'archive_size': 12, 'inspirations': 3}
        value['forest']['active']['mother_every_reports'] = 2
    return save(path, value)


def main():
    preparation.atomic_json = configured_write
    preparation.main()
    # The original immutable evidence readers remain in their historical study.
    for directory in (preparation.STUDY / 'reproduction', preparation.WORK / 'common'):
        preparation.change(directory / 'audit_control.py',
            'result = read(root / "arm-result.json")',
            'result = read(root / "arm-result.json", {}) or {}')
        preparation.change(directory / 'audit_advice.py',
            'd.get("preflight_reason")', 'd.get("validation", {}).get("reason")')
        preparation.change(directory / 'analyze_controlled.py',
            'One search per condition/problem: functional pilot only, no superiority inference.',
            'Two searches per condition/problem: descriptive pilot only, no reliable superiority inference.')
        preparation.change(directory / 'finish_study.py',
            'afterany of all four independent search blocks', 'afterany of all eight independent search blocks')

    import finalize_quality_luna as finalization

    original_write = finalization.atomic_json

    def finalized_write(path, value):
        if path.name == 'pipeline-arguments.json':
            rows = preparation.read(preparation.WORK / 'preparations.json')
            waves = {1: [], 2: []}
            for stage, row in zip(value['stages'][1:-1], rows, strict=True):
                stage['name'] = f"{row['case']}-r{row['repeat']}-{row['arms'][0]['condition']}"
                waves[row['repeat']].append(stage['name'])
            for stage, row in zip(value['stages'][1:-1], rows, strict=True):
                stage['depends_on'] = ['qualify'] if row['repeat'] == 1 else waves[1]
            # Stable topological stage ordering makes the dependency graph reviewable.
            first = [s for s in value['stages'][1:-1] if s['name'] in waves[1]]
            second = [s for s in value['stages'][1:-1] if s['name'] in waves[2]]
            value['stages'] = [value['stages'][0], *first, *second, value['stages'][-1]]
            value['stages'][-1]['depends_on'] = [*waves[1], *waves[2]]
            value['name'] = NAME
        return original_write(path, value)

    finalization.atomic_json = finalized_write
    finalization.main()
    rows = preparation.read(preparation.WORK / 'preparations.json')
    pairs = {}
    for row in rows:
        payload = Path(row['archive']).parent / 'payload'
        cfg = preparation.read(payload / 'settings.json')
        cfg['advisor'].update(row['arms'][0]['advisor'])
        assert cfg['evolution']['enabled'] and cfg['forest']['active']['mother_every_reports'] == 2
        assert cfg['seed'] == row['seed']
        value = copy.deepcopy(cfg)
        value['codex'].pop('mailbox_dir')
        value['advisor'].pop('enabled')
        pair = (row['case'], row['repeat'])
        if pair in pairs:
            assert pairs[pair] == value, pair
        pairs[pair] = value
    assert len(rows) == 8 and len(pairs) == 4
    save(preparation.STUDY / 'paired-configuration-audit.json', {
        'pairs': len(pairs), 'arms': len(rows), 'only_adviser_enabled_differs_within_pair': True,
        'model': 'gpt-6-luna', 'effort': 'max', 'evolution_enabled_in_both_arms': True,
        'maximum_concurrent_campaigns': 4, 'seeds': [307, 409]})
    shutil.copyfile(__file__, preparation.STUDY / 'reproduction' / Path(__file__).name)
    print(json.dumps({'study': str(preparation.STUDY), 'searches': 8, 'paired_repetitions': 4,
                      'pipeline': str(preparation.STUDY / 'pipeline-arguments.json')}))


if __name__ == '__main__':
    main()
