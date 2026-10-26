"""Ensure multiple input sizes and failed holdouts are not pooled or scored."""
import csv
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('diversified_measurement_export', Path(__file__).with_name('analyze_remeasurement.py'))
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf8')


@pytest.mark.parametrize('failed_on', [False, True])
def test_distinct_shapes_and_incorrect_holdout(tmp_path, monkeypatch, failed_on):
    common, output = tmp_path / 'common', tmp_path / 'out'
    candidates = {'naive': 1., 'r1-advisor_off': .5, 'r1-advisor_on': .25}
    outcomes = {name: {'status': 'valid', 'correct': True, 'mean_seconds': value, 'speedup': 1/value}
                for name, value in candidates.items()}
    if failed_on:
        outcomes['r1-advisor_on'].update(status='incorrect', correct=False, mean_seconds=None, speedup=None, reason='heldout_mismatch')
    write(common / 'allocation.json', {'job_id': 'synthetic-fixture', 'host': 'fixture', 'distribution': 'reserved'})
    write(common / 'common-measurements.json', {'argmin': {'outcomes': outcomes, 'excluded': [], 'program_affinity': [0]}})
    for name, value in candidates.items():
        for sample in range(5):
            details = [{'correct': True, 'n': n, 'threads': 1, 'seed': 7867, 'pattern': 1,
                        'seconds': value*n, 'repetitions': 10, 'warmups': 3,
                        'input_sha256': 'input-' + str(n), 'affinity': [0]} for n in (17, 31)]
            write(common / 'argmin/logs/e1' / name / f'confirmation/attempt-001/sample-{sample}.log',
                  {'correct': not (failed_on and name == 'r1-advisor_on'), 'metric': 'protected_kernel_seconds', 'details': details})
    monkeypatch.setattr('sys.argv', ['export', '--common', str(common), '--output', str(output)])
    EXPORT.main()
    with (output / 'common-thread-times.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == (4 if failed_on else 6)
    assert {int(row['n']) for row in rows} == {17, 31}
    assert all(int(row['samples']) == 5 for row in rows)
    assert all(float(row['speedup']) == 2. for row in rows if row['candidate'] == 'r1-advisor_off')
    with (output / 'common-comparison.csv').open(encoding='utf-8-sig', newline='') as stream:
        comparison = next(csv.DictReader(stream))
    if failed_on:
        assert comparison['on_status'] == 'incorrect'
        assert comparison['on_speedup'] == comparison['on_over_off_speedup'] == ''
        assert not any(row['candidate'] == 'r1-advisor_on' for row in rows)
    else:
        assert float(comparison['on_over_off_speedup']) == 2.
