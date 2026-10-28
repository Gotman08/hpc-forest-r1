"""New users start with no projects or past calculations; publication ships no state."""
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hpc_forest.webapp.api import create_app


def test_new_storage_has_no_seeded_projects_missions_or_history(tmp_path):
    app = create_app(tmp_path / "new-user")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        for path in ("projects", "campaigns", "missions", "history"):
            response = client.get("/api/" + path)
            assert response.status_code == 200
            assert response.json() == []
        assert client.get("/api/info").json()["submission_enabled"] is False


def test_new_user_does_not_inherit_another_users_projects(tmp_path):
    first = create_app(tmp_path / "first-user")
    first.state.projects.import_files("Private project", [("main.c", b"int main(void){return 0;}\n")])
    with TestClient(first, base_url="http://127.0.0.1") as client:
        response = client.get("/api/projects")
        assert response.status_code == 200
        assert isinstance(response.json(), list) and len(response.json()) == 1
    second = create_app(tmp_path / "second-user")
    with TestClient(second, base_url="http://127.0.0.1") as client:
        assert client.get("/api/projects").json() == []
        assert client.get("/api/history").json() == []


def test_current_git_checkout_ships_no_computation_history():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                            capture_output=True, text=True, check=False)
    if result.returncode or Path(result.stdout.strip()).resolve() != root:
        pytest.skip("Checkout publication guard requires its own Git repository")
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    private_roots = {"experiments", "evidence", "artifacts", "work", "runs", ".hpc-forest"}
    forbidden = [name for name in tracked if name and (
        name.split("/")[0] in private_roots or Path(name).suffix in {".sqlite3", ".db"})]
    assert forbidden == [], f"Computation history must stay local: {forbidden[:10]}"
