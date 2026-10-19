import time

import pytest

from hpc_forest.config import load_config
from hpc_forest.core import InfrastructureError
from hpc_forest.registry import Registry
from hpc_forest.toolchain import compiler_identity


@pytest.fixture(scope="session")
def need_compiler():
    try:
        compiler_identity()
    except InfrastructureError as exc:
        pytest.skip(str(exc))


@pytest.fixture
def config():
    c = load_config()
    c["budget"].update(
        search_slots=6, confirmation_slots=3, wall_seconds=600, infrastructure_retries=0
    )
    c["schedule"].update(cycles=1, trials_per_role_per_cycle=1, integrations_per_cycle=2)
    c["protocol"].update(
        repetitions=2,
        confirmation_repetitions=2,
        warmups=0,
        benchmark=["{binary}", "96", "17", "2"],
    )
    return c


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
