import time
from pathlib import Path

import pytest

from hpc_forest.config import load_config
from hpc_forest.core import InfrastructureError
from hpc_forest.registry import Registry
from hpc_forest.toolchain import compiler_identity

# These audits validate optional private study archives, not product behaviour.
# Keep their tests unchanged and collect them whenever the original data exists.
_PRIVATE_STUDIES = {
    "test_controlled_storage.py": "controlled-advisor-20261026",
    "test_controlled_study.py": "controlled-advisor-20261026",
    "test_tabpfn_admission_audit.py": "tabpfn-admission-20261025",
    "test_tabpfn_admission_protocol.py": "tabpfn-admission-20261025",
    "test_tabpfn_learning_curves.py": "tabpfn-admission-20261025",
    "test_tabpfn_study_analysis.py": "tabpfn-advisor-20261025",
}
collect_ignore = [name for name, study in _PRIVATE_STUDIES.items()
                  if not (Path(__file__).resolve().parents[1] / "experiments" / study).is_dir()]


def pytest_report_header():
    if collect_ignore:
        return f"Private archival audits not distributed: {len(collect_ignore)} modules"
    return None


@pytest.fixture(scope="session")
def need_compiler():
    try:
        compiler_identity()
    except InfrastructureError as exc:
        pytest.skip(str(exc))


@pytest.fixture
def config():
    c = load_config()
    # Keep the original hard-deadline contract covered; the new default lifecycle
    # has its own explicit finish_started_config fixture and end-to-end tests.
    c["completion"] = {"policy": "hard"}
    c["budget"].update(
        search_slots=6, confirmation_slots=3, wall_seconds=600, infrastructure_retries=0,
        tokens=300000, mission_tokens=16000,
    )
    c["harness"]["call_token_ceiling"] = 16000
    c["schedule"].update(cycles=1, trials_per_role_per_cycle=1, integrations_per_cycle=2)
    c["protocol"].update(
        repetitions=2,
        confirmation_repetitions=2,
        warmups=0,
        benchmark=["{binary}", "96", "17", "2"],
    )
    return c


@pytest.fixture
def finish_started_config(config):
    config["completion"] = {"policy": "finish-started", "postprocess_tokens": None}
    config["budget"].update(tokens=None, mission_tokens=None)
    config["harness"]["call_token_ceiling"] = None
    return config


@pytest.fixture
def db(tmp_path, config):
    registry = Registry(tmp_path / "test.sqlite3")
    registry.set("config", config)
    registry.set("deadline", time.time() + 600)
    with registry.connection:
        registry.connection.execute(
            "INSERT INTO epochs(id,base_commit,protocol_id,created) VALUES(1,'base','p',?)",
            (time.time(),),
        )
    yield registry
    registry.close()
