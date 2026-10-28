"""Advisor warmup through existing real schedulers/builds, without hosted models."""
import copy

from test_active_pipeline import test_live_loop_branches_integrates_closes_and_confirms as _run_live
from test_independent_forest import (
    test_fast_tree_continues_after_its_score_and_all_admitted_work_drains as _run_uneven,
)
from test_mother_conversation import persistent_settings as _settings


def test_advisor_warmup_preserves_independent_progress_and_draining(tmp_path, monkeypatch, need_compiler):
    config = _settings(tmp_path)
    config["advisor"] = {"enabled": True}
    monkeypatch.setattr("test_mother_conversation.persistent_settings", lambda _: copy.deepcopy(config))
    monkeypatch.setattr("hpc_forest.advisor.run_process",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("No model call during warmup")))
    _run_uneven(tmp_path, monkeypatch, need_compiler, None)


def test_advisor_warmup_preserves_active_analysts_closure_and_confirmation(tmp_path, monkeypatch, need_compiler):
    config = _settings(tmp_path)
    config["advisor"] = {"enabled": True}
    monkeypatch.setattr("test_active_pipeline.persistent_settings", lambda _: copy.deepcopy(config))
    # No runtime is supplied: reaching eight examples must also fail back to FIFO.
    monkeypatch.setattr("hpc_forest.advisor.run_process",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("No unprovisioned model call")))
    _run_live(tmp_path, monkeypatch, need_compiler, False, True)
