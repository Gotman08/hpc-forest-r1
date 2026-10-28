"""Crash boundaries, concurrent writers, backups and safe restoration."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from hpc_forest.core import FileLock, ForestError, InfrastructureError, atomic_json, file_digest
from hpc_forest.maintenance import migrate_config
from hpc_forest.registry import Registry
from hpc_forest.storage.backups import backup_application, restore_application, verify_backup
from hpc_forest.storage.files import atomic_path
from hpc_forest.storage.sqlite import backup_database
from hpc_forest.webapp.store import Store


def test_failed_atomic_write_preserves_previous_file(tmp_path):
    path = tmp_path / "state.json"
    atomic_json(path, {"before": True})
    before = path.read_bytes()
    with pytest.raises(RuntimeError), atomic_path(path) as temporary:
        temporary.write_bytes(b"half a document")
        raise RuntimeError("process failed before publish")
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_concurrent_atomic_writes_publish_complete_documents(tmp_path):
    path = tmp_path / "state.json"
    values = [{"i": n, "padding": str(n) * 10000} for n in range(20)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda value: atomic_json(path, value), values))
    assert json.loads(path.read_text()) in values
    assert len(list(tmp_path.iterdir())) == 1


def test_concurrent_record_mutations_do_not_lose_fields(tmp_path):
    store = Store(tmp_path)
    record = store.create("mission", {"state": "planned"})
    def change(index):
        store.mutate(record["id"], lambda value: {**value, str(index): index}, kind="mission")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(change, range(40)))
    assert all(store.get(record["id"])[str(i)] == i for i in range(40))
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda _: store.transition(record["id"], "planned",
                                                         {"state": "submitting"}, kind="mission"), range(20)))
    assert claims.count(True) == 1


def test_sqlite_backup_includes_uncheckpointed_wal(tmp_path):
    source = tmp_path / "source.sqlite3"
    db = sqlite3.connect(source)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE evidence(value TEXT)")
    db.execute("INSERT INTO evidence VALUES('measured')")
    db.commit()
    destination = tmp_path / "copy.sqlite3"
    backup_database(source, destination)
    with sqlite3.connect(destination) as copy:
        assert copy.execute("SELECT value FROM evidence").fetchall() == [("measured",)]
    db.close()


def test_legacy_registry_is_backed_up_before_schema_migration(tmp_path):
    path = tmp_path / "registry.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE slots(id TEXT PRIMARY KEY, phase TEXT, purpose TEXT, "
                   "tokens_reserved INTEGER, tokens_used INTEGER, usage_known INTEGER, created REAL)")
        db.execute("INSERT INTO slots VALUES('old','search','generation',0,17,1,1)")
    before = path.read_bytes()
    readonly = Registry(path, readonly=True)
    assert readonly.one("SELECT tokens_used FROM slots")["tokens_used"] == 17
    readonly.close()
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.before-*.sqlite3"))
    current = Registry(path)
    assert current.one("SELECT tokens_settled,tokens_used FROM slots") == {"tokens_settled": 1, "tokens_used": 17}
    current.close()
    backup, = tmp_path.glob("*.before-*.sqlite3")
    with sqlite3.connect(backup) as db:
        assert "tokens_settled" not in {row[1] for row in db.execute("PRAGMA table_info(slots)")}
        assert db.execute("SELECT tokens_used FROM slots").fetchone() == (17,)
    current = Registry(path)
    current.close()
    assert len(list(tmp_path.glob("*.before-*.sqlite3"))) == 1


def test_backup_restore_verifies_bytes_preserves_data_and_quarantines_submission(tmp_path):
    source = tmp_path / "app"
    store = Store(source)
    pending = store.create("mission", {"state": "planned", "prepared_id": "one"})
    completed = store.create("mission", {"state": "completed", "prepared_id": "two", "job_id": "123"})
    campaign = store.create("campaign", {"source_root": str(source / "missions/one/view")})
    external = store.create("campaign", {"source_root": str(tmp_path / "external")})
    (source / "original.tmp").write_bytes(b"preserve even a user temporary file")
    (source / "original.lock").write_bytes(b"preserve project lockfiles")
    backup, restored = tmp_path / "backup", tmp_path / "restored"
    with FileLock(source / "application.lock"), pytest.raises(InfrastructureError):
        backup_application(source, backup)
    backup_application(source, backup)
    before = file_digest(backup / "data/application.sqlite3")
    result = restore_application(backup, restored)
    assert result["quarantined_missions"] == [pending["id"]]
    assert file_digest(backup / "data/application.sqlite3") == before
    assert Store(restored).get(pending["id"])["state"] == "recovery_required"
    assert Store(restored).get(completed["id"])["job_id"] == "123"
    assert Store(restored).get(campaign["id"])["source_root"] == str(restored / "missions/one/view")
    assert Store(restored).get(external["id"])["source_root"] == str(tmp_path / "external")
    assert result["external_campaigns"] == [str(tmp_path / "external")]
    assert (restored / "original.tmp").read_bytes() == (source / "original.tmp").read_bytes()
    assert store.get(pending["id"])["state"] == "planned"
    with pytest.raises(ForestError):
        restore_application(backup, restored)
    (backup / "data/original.tmp").write_bytes(b"corrupted")
    with pytest.raises(ForestError, match="integrity"):
        verify_backup(backup)
    with pytest.raises(ForestError):
        restore_application(backup, tmp_path / "corrupt-restore")
    assert not (tmp_path / "corrupt-restore").exists()


def test_explicit_config_migration_does_not_modify_source(tmp_path, config):
    source, destination = tmp_path / "old.json", tmp_path / "new.json"
    atomic_json(source, {**config, "advisor": {"enabled": True}, "advisor_runtime": {}})
    before = source.read_bytes()
    receipt = migrate_config(source, destination)
    assert receipt["removed_settings"] == ["advisor", "advisor_runtime"]
    assert "advisor" not in json.loads(destination.read_text())
    assert source.read_bytes() == before
    with pytest.raises(FileExistsError):
        migrate_config(source, destination)
