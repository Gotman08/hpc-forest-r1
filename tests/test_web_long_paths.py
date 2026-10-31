"""Remote snapshots retain long diagnostic filenames and read-only SQLite access."""
import os
import sqlite3
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from hpc_forest.config import load_config
from hpc_forest.registry import Registry
from hpc_forest.webapp.campaigns import Campaigns
from hpc_forest.webapp.execution import Missions
from hpc_forest.webapp.paths import AppError, contained, database_uri, filesystem_path
from hpc_forest.webapp.store import Store


@pytest.mark.parametrize("path,expected", [
    (PureWindowsPath(r"C:\evidence\registry.sqlite3"), "file:///C:/evidence/registry.sqlite3"),
    (PureWindowsPath(r"\\?\C:\evidence\registry.sqlite3"), "file:///C:/evidence/registry.sqlite3"),
    (PureWindowsPath(r"\\?\UNC\host\share\registry.sqlite3"), "file://host/share/registry.sqlite3"),
    (PurePosixPath("/tmp/evidence/registry.sqlite3"), "file:///tmp/evidence/registry.sqlite3"),
])
def test_database_uri_preserves_location_without_a_device_authority(path, expected):
    assert database_uri(path) == expected


def test_snapshot_install_preserves_long_evidence_and_read_only_registry(tmp_path):
    source = tmp_path / "registry.sqlite3"
    with_registry = Registry(source)
    with_registry.set("current_epoch", 1)
    with_registry.set("config", load_config())
    with_registry.set("status", "initialized")
    with_registry.close()
    original = source.read_bytes()
    store = Store(tmp_path / "app")
    campaigns = Campaigns(store)
    missions = Missions(store, campaigns)
    mission = store.create("mission", {"name": "Long evidence", "project_id": None})
    archive_folder = store.root / "missions" / mission["id"]
    archive_folder.mkdir(parents=True)
    archive = archive_folder / "view.zip"
    # A valid relative name whose installed absolute path exceeds legacy MAX_PATH.
    member = "diagnostics/collections/" + "request-" + "a" * 95 + "/" + "b" * 64 + "/compiler-coverage.json"
    assert len(str(archive_folder / ("view-" + "a" * 32) / member)) > 260
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("registry.sqlite3", original)
        zipped.writestr(member, '{"complete":true}')
    snapshot = missions.install_view(mission, archive)
    assert snapshot["trial_count"] == 0
    current = missions.get(mission["id"])
    root = campaigns.root(current["campaign_id"])
    assert contained(root, member).read_text(encoding="utf-8") == '{"complete":true}'
    assert (root / "registry.sqlite3").read_bytes() == original
    assert campaigns.snapshot(current["campaign_id"])["trial_count"] == 0
    with sqlite3.connect(database_uri(root / "registry.sqlite3") + "?mode=ro", uri=True) as connection:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM metadata")
    with pytest.raises(AppError):
        contained(root, "../outside.json")
    if os.name == "nt":
        assert str(root).startswith("\\\\?\\")
        assert filesystem_path(root) == root
    else:
        assert filesystem_path(Path("relative")) == Path("relative")
