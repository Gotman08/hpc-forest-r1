"""Historical projects remain immutable; migrations create new identities."""
import copy

import pytest
from test_web_execution import application as application_fixture

from hpc_forest.webapp.paths import AppError
from hpc_forest.webapp.project_protocol import execution_environment
from hpc_forest.webapp.projects import project_view

application = application_fixture


def test_project_migration_preserves_original_files_contract_and_preparation(application):
    store, _, projects, prepared, missions = application
    project = store.get(prepared["project_id"])
    payload = store.payload(project)
    payload["contract"]["advisor"] = {"enabled": True}
    old = store.update(project["id"], payload, kind="project")
    before = copy.deepcopy(old)
    assert not project_view(old)["ready"]
    with pytest.raises(AppError, match="TabPFN"):
        projects.prepare(old["id"])
    new = projects.migrate(old["id"])
    assert new["id"] != old["id"] and new["migration_from"] == old["id"]
    assert "advisor" not in new["contract"]
    assert new["files"] == old["files"] and new["attachments"] == old["attachments"]
    assert store.get(old["id"]) == before
    assert store.get(prepared["id"])["project_id"] == old["id"]
    assert projects.prepare(new["id"])["project_id"] == new["id"]


def test_user_commands_do_not_inherit_known_credential_environment():
    inherited = {"PATH": "/bin", "OMP_NUM_THREADS": "1", "SLURM_JOB_ID": "123",
                 "CODEX_HOME": "/private/profile", "OPENAI_API_KEY": "fixture",
                 "HF_TOKEN": "fixture", "CUSTOM_PASSWORD": "fixture", "SSH_AUTH_SOCK": "/agent"}
    assert execution_environment(inherited) == {"PATH": "/bin", "OMP_NUM_THREADS": "1", "SLURM_JOB_ID": "123"}
