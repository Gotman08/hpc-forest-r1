"""Experimental controls must fail closed before any search dispatch."""
import importlib.util
import json
import tarfile
from pathlib import Path

import pytest

from hpc_forest import mother
from hpc_forest.core import InfrastructureError, digest

STUDY = Path(__file__).resolve().parents[1] / 'experiments/controlled-advisor-20261026'


def load(name):
    spec = importlib.util.spec_from_file_location(name, STUDY / 'reproduction' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen():
    plan = {'analysis': 'Independent decomposition',
            'children': [{'subject': 'first', 'objective': 'Explore the code'}], 'G': 'Combine measured sources'}
    return {'plan': plan, 'plan_sha256': digest(plan)}


def test_common_plan_is_data_in_real_first_turn_and_cannot_change():
    record = frozen()
    original_render, original_validate = mother.render_plan, mother.validated_plan
    restore = load('frozen_planning').install(record)
    try:
        rendered = mother.render_plan('preparation', {}, 'contract', {}, choose_trees=True)
        payload = json.loads(rendered['messages'][1]['content'])
        assert payload['frozen_initial_plan_as_data'] == record['plan']
        assert mother.validated_plan(record['plan'], choose_trees=True) == record['plan']
        with pytest.raises(InfrastructureError, match='changed the frozen'):
            mother.validated_plan({**record['plan'], 'G': 'Different'}, choose_trees=True)
        # A later fixed-role synthesis is not frozen by the study hook.
        assert mother.validated_plan({'analysis': 'later', 'T1': 'new', 'G': 'assembly'}, ['T1'])
    finally:
        restore()
    assert mother.render_plan is original_render and mother.validated_plan is original_validate


def test_tampered_plan_rejected_before_installation():
    with pytest.raises(InfrastructureError, match='digest'):
        load('frozen_planning').install({**frozen(), 'plan_sha256': 'wrong'})


def test_predeclared_factorial_has_equal_budgets_unique_orders_and_no_results():
    protocol = json.loads((STUDY / 'protocol.json').read_text(encoding='utf8'))
    assert protocol['analysis']['searches'] == 30
    assert len(protocol['cases']) == 2 and all(len(c['seeds']) == 3 for c in protocol['cases'])
    assert protocol['search_target_seconds_per_arm'] == 5400
    assert protocol['end_to_end_cap_seconds_per_arm'] == 7200
    assert all(len(o) == 5 and set(o) == set(protocol['conditions']) for o in protocol['orders'])
    assert protocol['conditions'] == load('prepare').CONDITIONS
    assert protocol['generator_pool'] == [] and not protocol['operator_algorithm_hints']
    for case in protocol['cases']:
        assert load('prepare').manifest(STUDY / 'inputs' / case['case']) == case['files']


def test_missing_delivery_is_visible_and_not_assigned_a_speedup(monkeypatch):
    monkeypatch.syspath_prepend(str(STUDY / 'reproduction'))
    module = load('analyze_controlled')
    rows = []
    for repeat, off, current in [(1, 10, 5), (2, 4, 8), (3, None, 7)]:
        for condition, speedup in [('off', off), ('current', current)]:
            rows.append({'case': 'gemm_cpu', 'repeat': repeat, 'condition': condition,
                         'registered_speedup': speedup, 'pipeline_complete': speedup is not None})
    paired, summary = module.contrasts(rows)
    contrast = next(r for r in summary if r['contrast'] == 'current/off' and r['distribution'] == 'registered')
    assert contrast['assigned_pairs'] == 3 and contrast['complete_valid_pairs'] == 2
    assert contrast['geometric_mean_ratio'] == pytest.approx(1)
    assert contrast['conditional_on_delivery']
    missing = next(r for r in paired if r['contrast'] == 'current/off' and r['repeat'] == 3)
    assert missing['ratio'] is None and missing['denominator_delivered'] is False


def test_settled_block_archive_is_complete_and_outside_working_directory(tmp_path, monkeypatch):
    module = load('run_block')
    block = tmp_path / 'block'
    block.mkdir()
    (block / 'result.json').write_text('{"complete":true}', encoding='utf8')
    archive = tmp_path / 'preserved.tar.gz'
    monkeypatch.setenv('FOREST_STUDY_ARCHIVE', str(archive))
    module.checkpoint_archive(block)
    with tarfile.open(archive) as stream:
        assert json.loads(stream.extractfile('./result.json').read()) == {'complete': True}
    (block / 'second.json').write_text('[]', encoding='utf8')
    module.checkpoint_archive(block)
    with tarfile.open(archive) as stream:
        assert './result.json' in stream.getnames() and './second.json' in stream.getnames()
    monkeypatch.setenv('FOREST_STUDY_ARCHIVE', str(block / 'recursive.tar.gz'))
    with pytest.raises(RuntimeError, match='outside'):
        module.checkpoint_archive(block)
