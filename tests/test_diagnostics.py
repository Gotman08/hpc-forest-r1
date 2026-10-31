"""Real local subprocess/MCP checks plus explicitly synthetic profiler command tests."""
import asyncio
import copy
import json
import os
import sqlite3
import sys
import time

import pytest

from hpc_forest import diagnostic_collectors as collectors
from hpc_forest import mother
from hpc_forest.codex_process import command_for, usage_from_events
from hpc_forest.config import load_config
from hpc_forest.core import InfrastructureError, atomic_json, file_digest, protected_manifest
from hpc_forest.diagnostics import DiagnosticFailure, Diagnostics
from hpc_forest.diagnostics_contract import authorize, load_grant, owned
from hpc_forest.diagnostics_mcp import READ_TOOLS, TOOLS, DiagnosticsMCP, create_server
from hpc_forest.gitops import initialize_source
from hpc_forest.model_policy import EFFORT, MODEL
from hpc_forest.registry import Registry


@pytest.fixture
def diagnostic_campaign(tmp_path):
    root = tmp_path / "campaign"
    root.mkdir()
    source = tmp_path / "input"
    (source / "src").mkdir(parents=True)
    (source / "src/program.py").write_text(
        "import sys\nassert sys.argv[1] == 'search'\nprint(sum(i*i for i in range(1000)))\n")
    commit = initialize_source(source, root / "repo")
    trusted = root / "trusted"
    trusted.mkdir()
    (trusted / "build.py").write_text(
        "import pathlib,sys\np=pathlib.Path(sys.argv[1]);p.write_bytes(b'diagnostic-fixture')\n")
    (trusted / "check.py").write_text(
        'import sys\nassert sys.argv[1] == "search"\nprint(\'{"correct":true,"cases":1}\')\n')
    config = load_config()
    config.update(backend="codex", forest={"policy": "mother"}, target_id="diagnostic-" + tmp_path.name,
                  compiler={}, investigation={"enabled": True, "require_allocation": False})
    config["codex"].update(session_id="a" * 32, transport="codex-mailbox", mailbox_dir=str(root / "mailbox"))
    config["protocol"].update(build=["{python}", "{trusted}/build.py", "{binary}"],
        check=["{python}", "{trusted}/check.py", "{phase}"],
        benchmark=["{python}", "{worktree}/src/program.py", "{phase}"])
    atomic_json(trusted / "config.json", config)
    db = Registry(root / "registry.sqlite3")
    for key, value in {"config": config, "manifest": protected_manifest(trusted), "current_epoch": 1,
                       "protocol_id": "frozen-protocol", "deadline": time.time() + 600}.items():
        db.set(key, value)
    with db.connection:
        db.connection.execute("INSERT INTO epochs VALUES(1,?,'frozen-protocol','baseline-e1',?,NULL)", (commit, time.time()))
        db.connection.execute("INSERT INTO evaluations(experiment_id,epoch,phase,payload,created) VALUES(?,1,'search',?,?)",
            ("baseline-e1", json.dumps({"commit": commit, "correct": True, "score": 0.5,
                                       "mean_seconds": 1.0, "binary_sha256": "official-binary"}), time.time()))
    db.close()
    return root, config


def request_for(root, role="mother-investigation", *, source_ids=None):
    import uuid

    request = {"nonce": uuid.uuid4().hex, "session_id": "a" * 32, "mission_id": "investigation-test",
               "meta_role": role, "expires_at": time.time() + 300, "model": MODEL, "reasoning_effort": EFFORT,
               "messages": [{"role": "system", "content": "Investigate within the controller grant."},
                            {"role": "user", "content": "Inspect evidence."}],
               "schema": {"type": "object", "properties": {"result": {"type": "string"}},
                          "required": ["result"], "additionalProperties": False}}
    authorize(root, request, source_ids=source_ids)
    return request


def test_real_workload_isolated_evidence_idempotence_and_official_score_unchanged(diagnostic_campaign):
    root, _ = diagnostic_campaign
    request = request_for(root)
    service = Diagnostics(root, request["diagnostics"], request)
    before = protected_manifest(root / "trusted")
    result = service.collect("baseline-e1", "runtime", "Measure the fixed workload", request_key="one")
    assert result["status"] == "complete", result
    assert result["score"] is None and result["observations"][0]["wall_seconds"] > 0
    assert service.collect("baseline-e1", "runtime", "Measure the fixed workload", request_key="one") == result
    assert len(list((root / "diagnostics/collections").glob("*/summary.json"))) == 1
    with pytest.raises(ValueError, match="reused"):
        service.collect("baseline-e1", "runtime", "Different question", request_key="one")
    assert protected_manifest(root / "trusted") == before
    db = Registry(root / "registry.sqlite3", readonly=True)
    assert json.loads(db.one("SELECT payload FROM evaluations")["payload"])["score"] == 0.5
    db.close()
    manifest = service.evidence(result["id"])
    assert "build-provenance.json" in {p["path"] for p in manifest["items"]}
    provenance = json.loads((root / "diagnostics/collections" / result["id"] / "build-provenance.json").read_text())
    assert provenance["execution_kind"] == "diagnostic" and provenance["input_phase"] == "search"
    page = service.evidence(result["id"], "runtime.log", limit=1)
    assert page["lines"] == ["332833500"]
    raw = service.evidence(result["id"], "runtime.log", limit=3, binary=True)
    assert raw["next_offset"] == 3 and raw["encoding"] == "base64"
    (root / "diagnostics/collections" / result["id"] / "runtime.log").write_text("changed")
    with pytest.raises(InfrastructureError, match="changed"):
        service.evidence(result["id"], "runtime.log")


def test_retried_accented_question_returns_the_same_collection(diagnostic_campaign):
    root, _ = diagnostic_campaign
    request = request_for(root)
    service = Diagnostics(root, request["diagnostics"], request)
    question = "Pourquoi le débit mémoire baisse-t-il après l'étape de réduction ?"
    result = service.collect("baseline-e1", "runtime", question, request_key="accents")
    assert result["status"] == "complete", result
    # The summary is written as UTF-8; reading it with the Windows code page broke retries.
    assert service.collect("baseline-e1", "runtime", question, request_key="accents") == result


def test_research_grants_allow_measured_sources_but_deny_login_and_foreign_sources(diagnostic_campaign, monkeypatch):
    root, _ = diagnostic_campaign
    generator = request_for(root, "generator")
    service = Diagnostics(root, generator["diagnostics"], generator)
    assert service.sources()["items"][0]["id"] == "baseline-e1"
    assert service.grant["can_collect"]
    assert service.collect("baseline-e1", "runtime", "Measured control", request_key="control")["status"] == "complete"
    with pytest.raises(ValueError, match="outside"):
        service.collect("unmeasured-candidate", "runtime", "Denied")
    service.policy["require_allocation"] = True
    service.grant["allocation_id"] = "12345"
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    with pytest.raises(DiagnosticFailure, match="login"):
        service.capabilities(probe=True)
    with pytest.raises(InfrastructureError, match="another request"):
        load_grant(root, generator["diagnostics"], {**generator, "nonce": "b" * 32})


def test_error_audit_retains_request_permissions_and_missing_value(diagnostic_campaign, monkeypatch):
    root, _ = diagnostic_campaign
    request = request_for(root)
    service = Diagnostics(root, request["diagnostics"], request)
    monkeypatch.setattr("hpc_forest.diagnostics.shutil.which", lambda name: None)
    result = service.audit("collect", {"collector": "ncu"},
        lambda: service.collect("baseline-e1", "ncu", "GPU metrics", request_key="gpu"))
    assert result["status"] == "unavailable" and result["score"] is None
    assert result["missing"] and not result["observations"]
    audit = json.loads(next((root / "diagnostics/audit").glob("*.json")).read_text())
    assert audit["permission"]["can_collect"] and audit["result"] == result
    assert service.evidence(result["id"], "summary.json")["sha256"]


def test_source_pages_and_path_boundaries(diagnostic_campaign):
    root, _ = diagnostic_campaign
    request = request_for(root)
    service = Diagnostics(root, request["diagnostics"], request)
    assert service.source_files("baseline-e1")["items"] == ["src/program.py"]
    page = service.source_files("baseline-e1", "src/program.py", limit=1)
    assert page["sha256"] == file_digest(root / "repo/src/program.py")
    for path in ("../authorization.json", "/etc/passwd", "C:/private", "a/../b", "a\\b"):
        with pytest.raises(ValueError):
            owned(root, path)
    with pytest.raises(ValueError):
        service.source_files("baseline-e1", "../authorization.json")


def test_native_command_and_event_permissions_are_effective(diagnostic_campaign, monkeypatch, tmp_path):
    root, _ = diagnostic_campaign
    request = request_for(root)
    binding = DiagnosticsMCP.bind(root, request)
    monkeypatch.setattr("hpc_forest.codex_process.shutil.which", lambda name: sys.executable)
    argv = command_for(request, tmp_path / "native", diagnostics_mcp=binding)
    overrides = {arg.split("=", 1)[0]: json.loads(arg.split("=", 1)[1])
                 for previous, arg in zip(argv, argv[1:], strict=False) if previous == "--config"}
    assert overrides["features.code_mode_host"] is True
    assert overrides["mcp_servers.hpc_diagnostics.required"] is True
    assert overrides["mcp_servers.hpc_diagnostics.enabled_tools"] == list(TOOLS)
    assert overrides["features.shell_tool"] is False and overrides["features.apps"] is False
    log = tmp_path / "events.jsonl"
    log.write_text(json.dumps({"type": "item.completed", "item": {"type": "mcp_tool_call",
        "server": "hpc_diagnostics", "tool": "diagnostic_collect", "id": "tool", "status": "completed"}}))
    assert not usage_from_events(log, diagnostic_tools=TOOLS)[1]
    assert usage_from_events(log, diagnostic_tools=READ_TOOLS)[1]
    assert usage_from_events(log)[1]
    log.write_text(json.dumps({"type": "item.completed", "item": {"type": "error",
        "message": "Code Mode is unavailable"}}))
    assert usage_from_events(log, diagnostic_tools=TOOLS)[0]["tool_runtime_errors"]


def test_mcp_real_stdio_tools_and_errors(diagnostic_campaign):
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    root, _ = diagnostic_campaign
    db = Registry(root / "registry.sqlite3")
    db.set("search_closed:1", {"at": time.time()})
    db.close()
    request = request_for(root, "generator")
    binding = DiagnosticsMCP.bind(root, request)
    service = Diagnostics(root, request["diagnostics"], request)
    timeline = root / "diagnostics/probes/native-table"
    timeline.mkdir(parents=True)
    with sqlite3.connect(timeline / "timeline.sqlite") as connection:
        connection.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, duration_ns INTEGER)")
        connection.execute("INSERT INTO events VALUES (1, 250)")
    service._manifest(timeline)
    overrides = binding.overrides()
    args = overrides["mcp_servers.hpc_diagnostics.args"]
    env = {**{k: os.environ[k] for k in overrides["mcp_servers.hpc_diagnostics.env_vars"] if k in os.environ},
           **{k.removeprefix("mcp_servers.hpc_diagnostics.env."): v for k, v in overrides.items()
              if k.startswith("mcp_servers.hpc_diagnostics.env.")}}

    async def check():
        async with stdio_client(StdioServerParameters(command=sys.executable, args=args, env=env)) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                listed = await client.list_tools()
                assert {t.name for t in listed.tools} == set(READ_TOOLS)
                sources = await client.call_tool("diagnostic_sources", {})
                assert sources.structuredContent["items"][0]["id"] == "baseline-e1"
                source = await client.call_tool("diagnostic_source", {"source_id": "baseline-e1", "path": "src/program.py"})
                assert source.structuredContent["ok"] and source.structuredContent["sha256"]
                rows = await client.call_tool("diagnostic_table", {"evidence_id": "native-table",
                    "artifact": "timeline.sqlite", "table": "events", "order_by": "id"})
                assert rows.structuredContent["rows"] == [{"id": 1, "duration_ns": 250}]
                denied = await client.call_tool("diagnostic_capabilities", {"probe": True})
                assert denied.structuredContent["status"] == "permission_denied"
                assert not denied.structuredContent["ok"]
    asyncio.run(check())


def test_native_timeline_pages_keep_units_raw_evidence_and_bound_queries(tmp_path):
    from hpc_forest.diagnostic_evidence import sqlite_page

    path = tmp_path / "timeline.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, duration_ns INTEGER, label TEXT, blob BLOB)")
        connection.executemany("INSERT INTO events VALUES (?, ?, ?, ?)", [
            (i, 10 * i, "x" * 1500, b"binary") for i in range(60)])
        connection.execute("CREATE VIEW hidden AS SELECT * FROM events")
    before = file_digest(path)
    assert sqlite_page(path)["tables"] == ["events"]
    page = sqlite_page(path, "events", columns=["id", "duration_ns"], order_by="id", offset=2, limit=2)
    assert page["rows"] == [{"id": 2, "duration_ns": 20}, {"id": 3, "duration_ns": 30}]
    assert page["next_offset"] == 4 and "Native" in page["units"]
    filtered = sqlite_page(path, "events", equals={"id": 4})
    assert filtered["rows"][0]["blob"] == {"binary_bytes": 6, "omitted": True}
    assert filtered["truncated_cells"]
    bounded = sqlite_page(path, "events", limit=100)
    assert bounded["page_truncated"] and 0 < bounded["next_offset"] < 60
    for arguments in ({"table": "hidden"}, {"table": "events", "columns": ["id; DROP TABLE events"]},
                      {"table": "events", "equals": {"id": 2**64}}, {"table": "events", "equals": []},
                      {"table": "events", "order_by": []}, {"table": "events", "limit": 0}):
        with pytest.raises(ValueError):
            sqlite_page(path, **arguments)
    assert file_digest(path) == before


def test_diagnostic_check_failure_is_not_success_or_an_official_result(diagnostic_campaign, monkeypatch):
    from hpc_forest import diagnostics

    root, _ = diagnostic_campaign
    request = request_for(root)
    service = Diagnostics(root, request["diagnostics"], request)
    original = diagnostics.expand_command
    def command(argv, **kwargs):
        if argv == service.config["protocol"]["check"]:
            return [sys.executable, "-c", 'print(\'{"correct":false,"cases":1}\')']
        return original(argv, **kwargs)
    monkeypatch.setattr(diagnostics, "expand_command", command)
    result = service.audit("collect", {}, lambda: service.collect(
        "baseline-e1", "runtime", "Check instrumentation validity", request_key="failed-check"))
    assert result["status"] == "diagnostic_check_failed" and not result["ok"]
    assert result["score"] is None and not result["observations"]
    assert not (root / "diagnostics/collections" / result["id"] / "runtime.log").exists()
    db = Registry(root / "registry.sqlite3", readonly=True)
    try:
        assert json.loads(db.one("SELECT payload FROM evaluations")["payload"])["score"] == 0.5
    finally:
        db.close()


def test_collectors_preserve_launch_order_and_typed_filters(tmp_path):
    """Synthetic command capture, not a claim that HPCToolkit/CUDA were measured."""
    binary = tmp_path / "program"
    calls = []
    def run(argv, name, **kwargs):
        calls.append((argv, name, kwargs))
    tools = {name: name for name in collectors.PROBES}
    workload = ["srun", "-n", "2", str(binary), "fixed-input"]
    collectors.collect("hpctoolkit", {"events": ["CPUTIME", "gpu=nvidia"]}, workload, binary, tmp_path, run, tools)
    assert calls[0][0][:4] == ["srun", "-n", "2", "hpcrun"]
    assert calls[0][0][-2:] == [str(binary), "fixed-input"]
    assert calls[1][0][:3] == ["hpcstruct", "-j", "1"]
    with pytest.raises(ValueError, match="MPI kernel replay"):
        collectors.collect("ncu", {}, workload, binary, tmp_path, run, tools)
    for options in ({"command": "rm"}, {"metrics": ["--import"]}, {"launch_count": True}, {"launch_count": 1000}):
        with pytest.raises(ValueError):
            collectors.options_for("ncu", options)
    path = tmp_path / "counters.csv"
    path.write_text("<not supported>;;cycles;0;0\n123;;instructions;4000;50.00\n")
    values = collectors.perf_counters(path)
    assert values[0]["value"] is None and values[1]["value"] == 123
    assert values[1]["running_percent"] == "50.00"


def test_investigation_precedes_subject_selection_and_is_not_a_recipe(diagnostic_campaign, monkeypatch):
    root, config = diagnostic_campaign
    db = Registry(root / "registry.sqlite3")
    epoch = db.one("SELECT * FROM epochs")
    baseline = json.loads(db.one("SELECT payload FROM evaluations")["payload"])
    controller = type("ControllerFixture", (), {"root": root, "config": config, "db": db})()
    calls = []
    def plan(controller, mission, context, phase):
        calls.append((phase, copy.deepcopy(context)))
        report = {key: "Fixture interpretation with missing data" for key in mother.INVESTIGATION_SCHEMA["required"]}
        if phase != "investigation":
            report = {"analysis": "From evidence", "children": [{"subject": "Model subject", "objective": "Model objective"}], "G": "Integrate"}
        return {"status": "complete", "request_sha256": phase, "slot_id": "fixture", "plan": report}
    monkeypatch.setattr(mother, "plan_for", plan)
    monkeypatch.setattr(mother, "publish_forest", lambda *args: None)
    selected = mother.prepare_forest(controller, epoch, baseline)
    assert [phase for phase, _ in calls] == ["investigation", "preparation"]
    assert calls[1][1]["investigation"]["interpretation_not_measurement"]
    assert selected["parallelism"] == 1
    prompt = mother.render_plan("investigation", {}, "", {})
    assert "children" not in prompt["schema"]["properties"]
    assert "BEFORE selecting" in prompt["messages"][0]["content"]
    db.close()


def test_mcp_server_tool_schemas(diagnostic_campaign):
    root, _ = diagnostic_campaign
    request = request_for(root)
    server = create_server(Diagnostics(root, request["diagnostics"], request))
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == set(TOOLS)
    collect = next(t for t in tools if t.name == "diagnostic_collect")
    assert collect.annotations.readOnlyHint is False
    assert {"source_id", "collector", "question", "request_key"} <= set(collect.inputSchema["required"])


def test_real_preflight_then_model_investigation_is_accounted_and_not_replayed(diagnostic_campaign, monkeypatch):
    from hpc_forest import codex_mailbox as mailbox
    from hpc_forest.controller import Controller
    from hpc_forest.core import Mission, digest

    root, _ = diagnostic_campaign
    calls = []
    def publish(channel, request):
        calls.append(copy.deepcopy(request))
        return digest(request)
    def respond(channel, request, sha):
        data = {key: "Fixture interpretation; no causal claim" for key in mother.INVESTIGATION_SCHEMA["required"]}
        return mailbox.response_envelope(request, sha, data=data, usage={
            "token_accounting": "exact", "tokens": 10, "llm_calls": 1})
    monkeypatch.setattr(mailbox, "publish_request", publish)
    monkeypatch.setattr(mailbox, "wait_response", respond)
    # Discovery algorithms are covered separately; this test executes the initial workload for real.
    monkeypatch.setattr(Diagnostics, "capabilities", lambda self, probe=False: {
        "collectors": {name: {"availability": "probe_required"} for name in COLLECTOR_NAMES}})
    with Controller(root) as controller:
        commit = controller.epoch()["base_commit"]
        mission = Mission("root", "mother", "", 1, "mother", commit, None, "R", 0, 0, str(root / "repo"))
        result = mother.plan_for(controller, mission, {"deadline_policy": "finish-started"}, "investigation")
        assert result["status"] == "complete", result
        assert "conversation" not in calls[0]
        payload = json.loads(calls[0]["messages"][1]["content"])
        assert payload["diagnostic_preflight_as_data"]["overview"]["status"] == "complete"
        assert payload["diagnostic_preflight_as_data"]["overview"]["score"] is None
        assert mother.plan_for(controller, mission, {}, "investigation") == result
        assert len(calls) == 1 and controller.db.one("SELECT COUNT(*) AS n FROM slots")["n"] == 1


COLLECTOR_NAMES = tuple(collectors.COLLECTORS)


def test_executor_deadline_partial_logs_and_resource_lock(diagnostic_campaign):
    root, _ = diagnostic_campaign
    request = request_for(root)
    service = Diagnostics(root, request["diagnostics"], request)
    directory = root / "diagnostics/executor-test"
    directory.mkdir()
    run, records = service._executor(directory, time.time() + 0.3, directory)
    with pytest.raises(DiagnosticFailure, match="inspect preserved"):
        run([sys.executable, "-u", "-c", "import time; print('before timeout'); time.sleep(5)"], "slow")
    assert records[0]["timed_out"] and records[0]["returncode"] is not None
    assert (directory / "slow.command.json").is_file()
    with pytest.raises(DiagnosticFailure, match="deadline"):
        service._copy_source(service.source("baseline-e1"), directory / "expired-copy", time.time() - 1)
    from hpc_forest.core import FileLock
    from hpc_forest.diagnostics_contract import target_lock

    service.grant["expires_at"] = time.time() + 0.1
    with FileLock(target_lock(service.config)), pytest.raises(DiagnosticFailure, match="target lock"):
        service._locked(lambda _: pytest.fail("No overlap with official evaluation"))


def test_romeo_worker_enables_the_actual_native_services(tmp_path, monkeypatch):
    from contextlib import asynccontextmanager

    from hpc_forest.webapp import remote_runner

    root = tmp_path / "romeo-worker"
    (root / "campaign/mailbox").mkdir(parents=True)
    atomic_json(root / "launch.json", {"session_id": "a" * 32, "id": "mission", "codex": "codex",
                                      "model": MODEL, "effort": EFFORT})
    atomic_json(root / "campaign/mailbox/DONE.json", {})
    seen = {}
    class Worker:
        def __init__(self, *args, **kwargs):
            seen.update(kwargs)
        async def hello(self):
            pass
        @asynccontextmanager
        async def keepalive(self, enabled):
            yield
        async def request_names(self, width):
            return []
        async def flush_diagnostics(self, **kwargs):
            pass
    class Pool:
        def __init__(self, worker):
            pass
        async def pump(self, *args):
            pass
        async def drain(self):
            pass
        async def close(self):
            pass
    monkeypatch.setattr(remote_runner, "Worker", Worker)
    monkeypatch.setattr(remote_runner, "RequestPool", Pool)
    assert asyncio.run(remote_runner.work(root)) == 0
    assert seen["diagnostics_root"] == root / "campaign"
    assert seen["documentation"] is True and "model_mcp_config" not in seen


@pytest.mark.skipif(os.name != "posix", reason="Native compiler interception uses POSIX wrappers")
def test_real_gcc_reports_on_local_linux(tmp_path):
    """Real compiler execution; independent of simulated profiler adapters and HPC."""
    import shutil

    from hpc_forest import diagnostic_compiler
    from hpc_forest.core import run_process

    gcc = shutil.which("gcc")
    if not gcc:
        pytest.skip("GCC unavailable")
    def run(argv, name, **kwargs):
        result = run_process(argv, tmp_path, tmp_path / (name + ".log"), 30)
        return {"log": result.log}
    env, _ = diagnostic_compiler.prepare(tmp_path / "wrappers", {"compiler": {"path": gcc}}, "compiler", run)
    source = tmp_path / "sample.c"
    source.write_text("int main(void){int a=0; for(int i=0;i<100;i++)a+=i; return a==4950?0:1;}\n")
    result = run_process([str(tmp_path / "wrappers/gcc"), "-O2", str(source), "-o", str(tmp_path / "sample")],
                         tmp_path, tmp_path / "build.log", 30, env)
    assert result.returncode == 0
    record = json.loads(next((tmp_path / "wrappers/records").glob("*.json")).read_text())
    assert record["compiler"]["family"] == "gcc" and "-fopt-info-all" in record["diagnostic_flags"]
    assert list(tmp_path.glob("*.s")) and list(tmp_path.glob("*optimized*"))
