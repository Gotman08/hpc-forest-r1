"""The critic must reserve the provisional N-tree finalization before dispatch."""
import time

import pytest
from test_memory import memory_db as memory_fixture
from test_mother_conversation import persistent_settings

from hpc_forest.memory.contract import POLICY
from hpc_forest.mother_review import review_admission

memory_db = memory_fixture


@pytest.mark.parametrize("width,can_review", [(2, True), (20, False), (600, False)])
def test_prelaunch_pairwise_forecast_reserves_n_minus_one_integrations(memory_db, width, can_review):
    db, _, _, root = memory_db
    config = persistent_settings(root)
    config["forest"].update(integration="pairwise", plan_review_calls=2)
    db.set("config", config)
    db.set("deadline", time.time() + 1800)
    assert db.get("forest_plan:1") is None and db.get("research_scheduler:1") is None
    decision = review_admission(db, width)
    assert decision["can_review"] is can_review
    assert decision["planned_integration_steps"] == max(1, width - 1)


def test_prelaunch_memory_guided_forecast_reserves_selection_and_actual_rounds(memory_db):
    db, _, _, root = memory_db
    config = persistent_settings(root)
    config["forest"].update(integration=POLICY, plan_review_calls=2)
    config["harness"]["enabled"] = True
    config["memory"] = {"mode": "active", "assembly_rounds": 3}
    db.set("config", config)
    db.set("deadline", time.time() + 1800)
    decision = review_admission(db, 20)
    assert decision["planned_integration_steps"] == 2  # Nominal work, not the conditional upper bound.
    assert decision["reserved_selection_seconds"] > 0
    assert decision["can_review"]
