"""The UI must preserve evidence and imported files without launching compute."""
import csv
import hashlib
import io
import json
import sqlite3
import stat
import zipfile

import pytest

from hpc_forest.webapp.campaigns import Campaigns
from hpc_forest.webapp.paths import AppError, relative_name
from hpc_forest.webapp.projects import Projects, unpack, validate_contract
from hpc_forest.webapp.store import Store


def zip_bytes(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.fixture
def projects(tmp_path):
    return Projects(Store(tmp_path / "app"))


@pytest.fixture
def project(projects):
    return projects.import_files("Produit <x>", [
        ("project/src/main.cpp", b"int main() { return 0; }\n"),
        ("project/CMakeLists.txt", b"add_executable(main src/main.cpp)\nadd_test(NAME ok COMMAND main)"),
        ("project/tests/input.txt", b"expected"),
        ("project/.git/config", b"ignored"),
    ])


def complete(project):
    return {**project["contract"], "benchmark_command": "./build/main 4096",
            "expected_result": "Sortie identique, code de retour 0"}


@pytest.mark.parametrize("path", [
    "../oops", "a/../../oops", "/absolute", "C:\\Windows\\oops", "a:secret", "a//b",
    "a/./b", "NUL.cpp", "lpt1", "a/b.", "a/b ", "a/\x00x", ".git/config", "a\\..\\b",
])
def test_reject_nonportable_and_escape_paths(path):
    with pytest.raises(AppError):
        relative_name(path)
    with pytest.raises(AppError):
        unpack([("x.zip", zip_bytes([(path, b"x")]))])


@pytest.mark.parametrize("entries", [
    [("a.cpp", b"1"), ("A.cpp", b"2")],
    [("a.cpp", b"1"), ("a.cpp/child", b"2")],
])
def test_reject_conflicting_uploads(entries):
    with pytest.raises(AppError):
        unpack(entries)


def test_reject_zip_symlinks_and_expansion_limit(monkeypatch):
    entry = zipfile.ZipInfo("link.cpp")
    entry.create_system = 3
    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
    with pytest.raises(AppError, match="liens"):
        unpack([("p.zip", zip_bytes([(entry, b"../outside")]))])
    monkeypatch.setattr("hpc_forest.webapp.projects.MAX_EXPANDED", 5)
    with pytest.raises(AppError, match="limites"):
        unpack([("p.zip", zip_bytes([("a.cpp", b"123456")]))])


def test_project_persists_and_prepare_freezes_original(projects, project):
    assert project["ignored_files"] == 1
    assert project["ready"] is False
    assert "--no-tests=error" in project["contract"]["test_command"]
    with pytest.raises(AppError, match="Complétez"):
        projects.prepare(project["id"])
    projects.update(project["id"], complete(project))
    projects.attach(project["id"], "statement", "spec.md", b"User constraints")
    restarted = Projects(Store(projects.store.root))
    mission = restarted.prepare(project["id"])
    other = restarted.prepare(project["id"])
    assert mission["id"] != other["id"]
    assert not mission["submitted"]
    with zipfile.ZipFile(projects.store.root / "prepared" / mission["id"] / "input.zip") as archive:
        manifest = json.loads(archive.read("forest-project.json"))
        assert manifest["model"] == "gpt-6-luna"
        assert manifest["reasoning_effort"] == "max"
        assert manifest["execution"] == "ROMEO"
        assert manifest["verification"] == "not_run"
        assert manifest["memory"] == "fresh"
        assert not manifest["submitted"]
        for item in manifest["files"]:
            assert hashlib.sha256(archive.read("source/" + item["path"])).hexdigest() == item["sha256"]
        assert archive.read("attachments/" + manifest["attachments"][0]["stored"]) == b"User constraints"
    original = projects.store.root / "projects" / project["id"] / "source/src/main.cpp"
    original.write_bytes(b"changed")
    with pytest.raises(AppError, match="changé"):
        restarted.prepare(project["id"])
    assert len(list((projects.store.root / "prepared").iterdir())) == 2


@pytest.mark.parametrize(("key", "value"), [
    ("duration_minutes", True), ("duration_minutes", 0), ("duration_minutes", 1441),
    ("target", []), ("target", "external"), ("editable_paths", ["tests/"]),
    ("editable_paths", ["tests\\input.txt"]), ("editable_paths", ["src/tests/test.cpp"]),
    ("editable_paths", ["../code.cpp"]), ("build_command", "cc 'unfinished"),
])
def test_invalid_contract_rejected(project, key, value):
    with pytest.raises(AppError):
        validate_contract({**complete(project), key: value})


def test_contract_model_is_fixed_and_whitespace_not_ready(projects, project):
    with pytest.raises(AppError):
        projects.update(project["id"], {**complete(project), "model": "other"})
    value = projects.update(project["id"], {**complete(project), "test_command": "  \n "})
    assert not value["ready"]
    value = projects.update(project["id"], {**complete(project), "editable_paths": ["missing.cpp"]})
    assert not value["ready"]


@pytest.fixture
def campaign(tmp_path):
    root = tmp_path / "campaign"
    root.mkdir()
    with sqlite3.connect(root / "registry.sqlite3") as db:
        db.executescript("""
            CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE trials(id TEXT,trial_id TEXT,tree_id TEXT,role TEXT,state TEXT,
                                mission TEXT,result TEXT,created REAL,epoch INTEGER);
            CREATE TABLE evaluations(id INTEGER,experiment_id TEXT,phase TEXT,payload TEXT,
                                     created REAL,epoch INTEGER);
            CREATE TABLE events(id INTEGER,kind TEXT,payload TEXT,created REAL);
        """)
        metadata = {
            "current_epoch": 1, "status": "confirmed", "protocol_id": "same-machine-protocol",
            "config": {"codex": {"model": "gpt-6-luna", "reasoning_effort": "max"}},
            "identity": {"hostname": "romeo-c040", "machine": "x86_64"},
            "best_confirmed": {"epoch": 1, "protocol_id": "same-machine-protocol",
                               "reference_seconds": 0.2, "mean_seconds": 0.1},
            "forest_plan:1": {"children": [{"role": "T1", "subject": "Vectoriser"}]},
            "active_forest:1": {"analysts": {}, "decisions": []},
            "postprocess:1": {"status": "complete", "search_stop_reason": "budget_exhausted"},
            "final_g_confirmation:1": {"status": "confirmed"},
        }
        db.executemany("INSERT INTO metadata VALUES(?,?)", [(k, json.dumps(v)) for k, v in metadata.items()])
        for index, (identifier, correct, score, phase) in enumerate([
            ("a", True, 2.0, "search"), ("b", False, 0, "search"),
            ("c", None, None, "search"), ("g", True, 2.0, "postprocess"),
        ]):
            db.execute("INSERT INTO trials VALUES(?,?,?,?,?,?,?,?,?)", (
                identifier, "treequest-" + identifier, "tree-1", "G" if identifier == "g" else "T1",
                "done", json.dumps({"parent_id": "treequest-a" if identifier == "b" else None,
                                    "budget_phase": phase, "delegation_parent": "R/T1"}),
                json.dumps({"status": "infrastructure_error" if correct is None else "valid" if correct else "incorrect",
                            "correct": correct, "score": score, "mean_seconds": 0.1 if correct else None,
                            "times": [0.1] if correct else [], "reason": "=danger"}), index, 1))
        db.execute("INSERT INTO evaluations VALUES(1,'a','search','{}',1,1)")
    for folder, text in [("worktrees/a/src", "int main(){return 1;}\n"),
                         ("repo/src", "int main(){return 0;}\n")]:
        (root / folder).mkdir(parents=True)
        (root / folder / "main.cpp").write_text(text)
    (root / "submission.zip").write_bytes(zip_bytes([("src/main.cpp", b"code")]))
    (root / "report").mkdir()
    (root / "report/rapport.md").write_text("Report")
    return root


def test_evidence_is_read_only_and_preserves_outcomes(tmp_path, campaign):
    before = (campaign / "registry.sqlite3").read_bytes()
    service = Campaigns(Store(tmp_path / "store"))
    record = service.register(campaign)
    assert service.register(campaign)["id"] == record["id"]
    value = service.snapshot(record["id"])
    assert value["speedup"] == 2
    assert value["trial_count"] == 4
    assert len(value["trees"]) == 1
    assert len(value["integrations"]) == 1
    assert value["analyses"] == []
    assert value["decisions"] == []
    assert value["trees"][0]["nodes"][1]["parent"] == "treequest-a"
    assert service.trial(record["id"], "b")["score"] == 0
    assert service.trial(record["id"], "c")["score"] is None
    source = service.source(record["id"], "a", "src/main.cpp")
    assert source["comparison"] == "reference"
    assert "-int main(){return 0;}" in source["diff"]
    assert "+int main(){return 1;}" in source["diff"]
    with pytest.raises(AppError):
        service.source(record["id"], "a", "../../registry.sqlite3")
    with pytest.raises(AppError):
        service.source(record["id"], "other", "src/main.cpp")
    assert "'=danger" in service.csv(record["id"])
    assert service.download(record["id"], "code").name == "submission.zip"
    assert (campaign / "registry.sqlite3").read_bytes() == before


def test_intermediate_integration_is_not_a_research_tree(tmp_path, campaign):
    with sqlite3.connect(campaign / "registry.sqlite3") as db:
        db.execute("UPDATE trials SET role='Gm1',mission=? WHERE id='c'", (json.dumps({
            "budget_phase": "search", "kind": "intermediate_integration", "sources": ["a", "b"],
            "base_source_id": "a",
        }),))
        db.execute("UPDATE metadata SET value=? WHERE key='active_forest:1'", (json.dumps({
            "children": [{"role": "Gm1", "kind": "intermediate_integration"},
                         {"role": "T2", "subject": "Nouvelle piste"}],
        }),))
    service = Campaigns(Store(tmp_path / "store"))
    value = service.snapshot(service.register(campaign)["id"])
    assert [tree["id"] for tree in value["trees"]] == ["T1", "T2"]
    assert len(value["integrations"]) == 2
    assert value["integrations"][0]["base_source_id"] == "a"
    assert len(value["trees"][0]["nodes"]) == 2


@pytest.mark.parametrize("backend", ["recipe", "codex"])
def test_csv_does_not_attribute_recipe_trials_to_the_default_model(tmp_path, campaign, backend):
    with sqlite3.connect(campaign / "registry.sqlite3") as db:
        config = json.loads(db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0])
        config.update(backend=backend, codex={"model": "gpt-6-luna", "reasoning_effort": "max"})
        db.execute("UPDATE metadata SET value=? WHERE key='config'", (json.dumps(config),))
    service = Campaigns(Store(tmp_path / "store"))
    identifier = service.register(campaign)["id"]
    rows = list(csv.DictReader(io.StringIO(service.csv(identifier))))
    assert {row["generator_model"] for row in rows} == ({"gpt-6-luna"} if backend == "codex" else {""})
    assert {row["generator_effort"] for row in rows} == ({"max"} if backend == "codex" else {""})


def test_large_reference_is_not_misrepresented_as_a_new_file(tmp_path, campaign):
    (campaign / "repo/src/main.cpp").write_text("x" * (256 * 1024 + 1))
    service = Campaigns(Store(tmp_path / "store"))
    value = service.source(service.register(campaign)["id"], "a", "src/main.cpp")
    assert not value["diff_available"]
    assert value["diff"] == ""
    assert "int main" in value["content"]


def test_unfinished_analyst_calls_are_not_counted_as_reports(tmp_path, campaign):
    with sqlite3.connect(campaign / "registry.sqlite3") as db:
        db.execute("UPDATE metadata SET value=? WHERE key='active_forest:1'", (json.dumps({
            "analysts": {
                "T1": {"status": "running"}, "T2": {"status": "unavailable"},
                "T3": {"status": "complete", "report_id": "proof-1", "report": {"action": "report"}},
            },
        }),))
    service = Campaigns(Store(tmp_path / "store"))
    value = service.snapshot(service.register(campaign)["id"])
    assert len(value["analyses"]) == 1
    assert value["analyses"][0]["role"] == "T3"
    assert value["analyses"][0]["report_id"] == "proof-1"


def test_incomplete_pipeline_does_not_expose_stale_archive(tmp_path, campaign):
    with sqlite3.connect(campaign / "registry.sqlite3") as db:
        db.execute("DELETE FROM metadata WHERE key='postprocess:1'")
    service = Campaigns(Store(tmp_path / "store"))
    identifier = service.register(campaign)["id"]
    assert not service.snapshot(identifier)["downloads"]["code"]
    with pytest.raises(AppError):
        service.download(identifier, "code")


def test_confirmed_slow_candidate_is_not_claimed_as_a_gain(tmp_path, campaign):
    with sqlite3.connect(campaign / "registry.sqlite3") as db:
        best = json.loads(db.execute("SELECT value FROM metadata WHERE key='best_confirmed'").fetchone()[0])
        db.execute("UPDATE metadata SET value=? WHERE key='best_confirmed'", (json.dumps({**best, "mean_seconds": 0.3}),))
    service = Campaigns(Store(tmp_path / "store"))
    value = service.snapshot(service.register(campaign)["id"])
    assert value["state"] == "no_gain"
    assert value["speedup"] == pytest.approx(2 / 3)


def test_previous_confirmation_does_not_hide_a_running_search(tmp_path, campaign):
    with sqlite3.connect(campaign / "registry.sqlite3") as db:
        db.execute("UPDATE metadata SET value=? WHERE key='status'", (json.dumps("searching"),))
    service = Campaigns(Store(tmp_path / "store"))
    value = service.snapshot(service.register(campaign)["id"])
    assert value["state"] == "running"
    assert value["speedup"] == 2  # The earlier verified result remains explicitly recorded.


@pytest.mark.parametrize("change", [{"epoch": 2}, {"protocol_id": "different"},
                                     {"mean_seconds": float("nan")}, {"mean_seconds": 0}])
def test_unconfirmed_or_stale_evidence_never_claims_gain(tmp_path, campaign, change):
    with sqlite3.connect(campaign / "registry.sqlite3") as db:
        best = json.loads(db.execute("SELECT value FROM metadata WHERE key='best_confirmed'").fetchone()[0])
        db.execute("UPDATE metadata SET value=? WHERE key='best_confirmed'", (json.dumps({**best, **change}),))
    service = Campaigns(Store(tmp_path / "store"))
    identifier = service.register(campaign)["id"]
    value = service.snapshot(identifier)
    assert value["speedup"] is None
    assert value["state"] == "unconfirmed"
    assert value["downloads"]["code"] is False
    with pytest.raises(AppError):
        service.download(identifier, "code")


@pytest.fixture
def client(tmp_path, campaign):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from hpc_forest.webapp.api import create_app

    with TestClient(create_app(tmp_path / "http-app", [campaign]), base_url="http://127.0.0.1") as client:
        yield client


def test_api_end_to_end_with_uploaded_folder(client):
    headers = {"X-Forest-Request": "1"}
    files = [("files", ("main.cpp", b"int main(){}")),
             ("files", ("Makefile", b"all:\n\ttrue\ntest:\n\ttrue"))]
    response = client.post("/api/projects", headers=headers, files=files,
                           data={"paths": '["demo/src/main.cpp","demo/Makefile"]', "name": "demo"})
    assert response.status_code == 201
    project = response.json()
    assert not project["ready"]
    identifier = project["id"]
    assert client.post(f"/api/projects/{identifier}/prepare", headers=headers).status_code == 400
    response = client.put(f"/api/projects/{identifier}/contract", headers=headers, json=complete(project))
    assert response.status_code == 200
    assert response.json()["ready"]
    mission = client.post(f"/api/projects/{identifier}/prepare", headers=headers).json()
    response = client.get(f'/api/prepared/{mission["id"]}/download')
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.read("source/src/main.cpp") == b"int main(){}"
    assert len(client.get("/api/history").json()) == 3
    info = client.get("/api/info").json()
    assert info["model"] == "gpt-6-luna"
    assert info["effort"] == "max"
    assert not info["submission_enabled"]
    campaign = client.get("/api/campaigns").json()[0]
    assert client.get(f'/api/campaigns/{campaign["id"]}/download/code').status_code == 200
    for url in ["/", "/assets/app.mjs", "/assets/views.mjs", "/assets/styles.css"]:
        response = client.get(url)
        assert response.status_code == 200
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_api_rejects_cross_site_writes_and_rebinding(client):
    assert client.post("/api/projects").status_code == 403
    assert client.get("/api/info", headers={"Host": "malicious.example"}).status_code == 403
    assert client.post("/api/projects", headers={"X-Forest-Request": "1", "Origin": "https://other.example"}).status_code == 403
    assert client.post("/api/projects", headers={"X-Forest-Request": "1", "Content-Length": str(100 * 1024**2)}).status_code == 413
    assert client.get("/api/projects/unknown").status_code == 400
    assert client.get("/assets/../../pyproject.toml").status_code == 404
    streamed = client.put("/api/projects/unknown/contract", headers={"X-Forest-Request": "1", "Content-Type": "application/json"},
                           content=iter([b"x" * (1024 * 1024), b"x"]))
    assert streamed.status_code == 413


@pytest.mark.parametrize("unavailable", [False, True])
def test_history_shows_one_entry_per_submitted_mission(client, unavailable):
    store = client.app.state.store
    campaign = store.list("campaign")[0]
    mission = store.create("mission", {"name": "Submitted", "state": "completed",
                                      "prepared_id": "a" * 32, "campaign_id": campaign["id"]})
    payload = {**campaign, "mission_id": mission["id"], "project_id": "b" * 32}
    if unavailable:
        payload["source_root"] = str(store.root / "offline")
    store.update(campaign["id"], payload, kind="campaign")
    records = client.get("/api/history").json()
    assert [(r["kind"], r["id"]) for r in records] == [("mission", mission["id"])]


def test_api_malformed_contract_and_paths_are_errors_not_crashes(client):
    headers = {"X-Forest-Request": "1"}
    response = client.post("/api/projects", headers=headers, files={"files": ("main.cpp", b"code")},
                           data={"paths": '["../main.cpp"]'})
    assert response.status_code == 400
    project = client.post("/api/projects", headers=headers, files={"files": ("main.cpp", b"code")}).json()
    response = client.put(f'/api/projects/{project["id"]}/contract', headers=headers, json=[])
    assert response.status_code == 400
    response = client.put(f'/api/projects/{project["id"]}/contract', headers=headers, content="not-json")
    assert response.status_code == 400
