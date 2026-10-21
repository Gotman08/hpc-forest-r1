import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
state = json.loads((HERE/'state.json').read_text())
sys.path[:0] = [str(HERE),str(Path(state['repository'])/'src'),str(HERE/'artifact/payload/validation')]
import protocol
from cuda_evaluator import gpu_seconds
from hpc_forest.core import InfrastructureError


def metric():
    return {'metric':'geomean_cuda_event_seconds','correct':True,'cases':3,
        'timed_launches_per_size':100,'warmup_launches':10,
        'details':[{'n':n,'ok':True,'latency_ms':v} for n,v in zip([4096,8192,16384],[1.,2.,4.])],
        'seconds':.002}


def test_gpu_metric_uses_events_in_seconds():
    assert gpu_seconds(metric()) == pytest.approx(.002)


@pytest.mark.parametrize('change',[{'seconds':20.},{'metric':'wallclock'},
    {'correct':False},{'cases':4},{'timed_launches_per_size':1}])
def test_invalid_aggregate_rejected(change):
    data = metric()
    data.update(change)
    with pytest.raises(InfrastructureError):
        gpu_seconds(data)


@pytest.mark.parametrize('bad',[0.,-1.,float('nan'),float('inf')])
def test_invalid_gpu_latency_rejected(bad):
    data = metric()
    data['details'][0]['latency_ms'] = bad
    with pytest.raises(InfrastructureError):
        gpu_seconds(data)


def test_launch_contract_rejects_unknown_or_noninteger():
    good = {'block':256,'items_per_block':256,'shared_memory_bytes':0}
    assert protocol.launch_settings(good) == good
    for change in [{'block':True},{'block':1025},{'items_per_block':0},
                   {'shared_memory_bytes':49153},{'extra':1}]:
        with pytest.raises(ValueError):
            protocol.launch_settings({**good,**change})


def test_oracle_is_one_body_velocity_then_position():
    particles = np.array([[1,2,3,.5,-.25,1,1e30]],dtype='<f4')
    rows, expected = protocol.cpu_expected(particles,.25)
    assert rows.tolist() == [0]
    assert np.allclose(expected[0,:3],[1.125,1.9375,3.25])
    assert np.array_equal(expected[0,3:],particles[0,3:])


def test_oracle_two_particles_has_attractive_force():
    particles = np.array([[0,0,0,0,0,0,2],[1,0,0,0,0,0,3]],dtype='<f4')
    _, expected = protocol.cpu_expected(particles,.01)
    denom = (1+float(np.float32(.001)))**1.5
    assert expected[0,3] == pytest.approx(3/denom*float(np.float32(.01)))
    assert expected[1,3] == pytest.approx(-2/denom*float(np.float32(.01)))
    assert np.array_equal(expected[:,6],particles[:,6])


def test_input_phases_are_distinct_and_reproducible(tmp_path):
    first = protocol.make_inputs(tmp_path/'first',20261021)
    second = protocol.make_inputs(tmp_path/'second',20261022)
    again = protocol.make_inputs(tmp_path/'again',20261021)
    assert len(first) == 11
    assert [c['input_sha256'] for c in first] == [c['input_sha256'] for c in again]
    assert all(a['input_sha256'] != b['input_sha256'] for a,b in zip(first,second))


def test_all_output_values_and_exact_mass_checked():
    inputs = np.ones((31,7),dtype='<f4')
    candidate = inputs.copy()
    candidate[30,5] += 1
    assert not protocol.compare(candidate,inputs,inputs)['ok']
    candidate = inputs.copy()
    candidate[0,6] = np.nextafter(candidate[0,6],np.float32(2))
    assert not protocol.compare(candidate,inputs,inputs)['ok']


def test_reference_hash_and_mechanical_extraction():
    source = Path(state['artifact'])/'payload/validation'
    original = (source/'original.cu').read_text(encoding='utf8')
    expected = original[original.index('// Structure'):original.index('int main()')]
    expected = expected.replace('__global__ void nbody_step_naive(',
        'extern "C" __global__ void nbody_step_naive(',1)
    assert (source/'reference.cu').read_text(encoding='utf8') == expected
    assert protocol.sha(source/'original.cu') == state['source_sha256']


def test_frozen_settings_no_token_or_cycle_limit():
    settings = json.loads((Path(state['artifact'])/'settings.json').read_text())
    from hpc_forest.config import validate
    validate(settings)
    assert settings['budget']['wall_seconds'] == 1800
    assert settings['budget']['tokens'] is None and settings['budget']['search_slots'] is None
    assert settings['schedule']['cycles'] is None and settings['budget']['max_depth'] == 0
    assert settings['forest']['integration'] == 'pairwise'
    assert settings['skills']['enabled']
