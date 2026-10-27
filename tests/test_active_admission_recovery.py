"""Regressions from the real Luna pilot's exhausted-integration control stall."""
import copy

import pytest
from test_active_architecture import action, campaign, decision, trial  # noqa: F401
from test_active_corrections import analyze, corrected, grounded  # noqa: F401

from hpc_forest import active_control as controls
from hpc_forest import active_lifecycle as life
from hpc_forest.active_analysis import validate
from hpc_forest.active_snapshot import freeze
from hpc_forest.active_state import apply, key, state
from hpc_forest.core import InfrastructureError


def idle_campaign(c):
    nodes = [trial(c, role) for role in ('T1', 'T2')]
    for role in ('T1', 'T2'):
        analyze(c, role)
    snap = freeze(c, 1)
    apply(c.db, 1, 'combine', snap,
          decision(snap, action('integrate', sources=[n.id for n in nodes])))
    c.search.initialize(1, 'Gm1', 23)
    trial(c, 'Gm1')
    c.db.set('active_unavailable:1', {'Gm1': 'checkpoint_limit'})
    current = state(c.db, 1)
    current['suspended'] = ['T1', 'T2']
    c.db.set(key(1), current)
    assert life.idle_review(c.db, 1)
    return freeze(c, 1)


@pytest.mark.parametrize('kind', ['continue', 'resume'])
def test_exhausted_integration_cannot_cancel_idle_recovery(corrected, kind):  # noqa: F811
    snap = idle_campaign(corrected)
    before = copy.deepcopy(state(corrected.db, 1)['lifecycle'])
    receipt = apply(corrected.db, 1, 'invalid-restart', snap, decision(snap, action(kind, 'Gm1')))
    result = receipt['actions'][0]
    assert result['status'] == 'rejected'
    assert 'Gm1' in result['reason'] and 'checkpoint_limit' in result['reason']
    assert state(corrected.db, 1)['lifecycle'] == before
    assert apply(corrected.db, 1, 'invalid-restart', snap, decision(snap, action(kind, 'Gm1'))) == receipt
    assert life.resume_after_idle_review(corrected.db, 1, ['T1', 'T2'])
    current = state(corrected.db, 1)
    assert not current['closed'] and current['suspended'] == []
    assert corrected.db.get('active_unavailable:1') == {'Gm1': 'checkpoint_limit'}
    assert corrected.db.one('SELECT count(*) AS n FROM trials')['n'] == 3
    assert not life.resume_after_idle_review(corrected.db, 1, ['T1', 'T2'])


def test_advice_to_suspended_tree_preserves_pending_idle_review(corrected):  # noqa: F811
    snap = idle_campaign(corrected)
    closing = copy.deepcopy(state(corrected.db, 1)['lifecycle']['closing'])
    apply(corrected.db, 1, 'advice-only', snap, decision(snap, action('continue', 'T1')))
    current = state(corrected.db, 1)
    assert current['advice']['T1']['decision_id'] == 'advice-only:0'
    assert current['lifecycle']['closing'] == closing
    assert current['suspended'] == ['T1', 'T2']
    assert life.resume_after_idle_review(corrected.db, 1, ['T1', 'T2'])


def test_explicit_resume_still_reactivates_available_tree(corrected):  # noqa: F811
    snap = idle_campaign(corrected)
    receipt = apply(corrected.db, 1, 'resume-real-tree', snap, decision(snap, action('resume', 'T1')))
    assert receipt['actions'][0]['status'] == 'applied'
    current = state(corrected.db, 1)
    assert current['suspended'] == ['T2'] and current['lifecycle']['closing'] is None


def test_mother_snapshot_discloses_unavailable_admissions(corrected):  # noqa: F811
    snap = idle_campaign(corrected)
    assert snap['trees']['Gm1']['unavailable_reason'] == 'checkpoint_limit'
    assert snap['trees']['T1']['unavailable_reason'] is None


def test_citation_repair_reports_exact_limit_and_observed_count(corrected):  # noqa: F811
    node = trial(corrected, 'T1')
    job = controls.create(corrected, 1, 'analyst', 'T1')
    snap = controls.snapshot(corrected, job)
    data = grounded(snap, node.id)
    data['code_findings'][0]['citations'] *= 5
    with pytest.raises(InfrastructureError, match=r'1 to 4 citations.*received 5'):
        validate(data, snap, job)
