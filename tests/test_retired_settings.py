"""Retirement must never reinterpret a frozen campaign as a new contract."""
import copy
import json

import pytest

from hpc_forest.compatibility import historical_advisor, without_retired
from hpc_forest.config import validate
from hpc_forest.control_versions import verify
from hpc_forest.core import ForestError
from hpc_forest.search import Search


@pytest.mark.parametrize("setting", [{"advisor": {"enabled": True}},
                                   {"advisor": {"enabled": False}},
                                   {"advisor": {}}, {"advisor_runtime": {}}])
def test_new_and_resumed_execution_require_explicit_migration(config, db, setting):
    config.update(setting)
    before = copy.deepcopy(config)
    with pytest.raises(ForestError, match="TabPFN"):
        validate(config)
    db.set("config", config)
    with pytest.raises(ForestError, match="TabPFN"):
        verify(db, config)
    with pytest.raises(ForestError, match="TabPFN"):
        Search(db).ask("e1:A", ["A"], 1, "base", 1, "", "missing-slot")
    assert config == before
    validate(without_retired(config))
    assert config == before


def test_historical_advice_is_evidence_only():
    totals = {"calls": 13, "reorders": 0}
    data = historical_advisor({"advisor": {"enabled": True}}, totals)
    assert data == {"enabled": True, **totals, "retired": True, "read_only": True}
    assert historical_advisor({}, {}) is None
    assert json.dumps(totals) == '{"calls": 13, "reorders": 0}'
