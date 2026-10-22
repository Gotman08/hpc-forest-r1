"""Native-turn fixtures, real source edits, compiler, AB-MCTS and confirmation."""
import copy
import json
import re
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_mother_conversation import NativeFixture, persistent_settings
from test_mother_forest import decomposition

from hpc_forest import codex_mailbox as mailbox
from hpc_forest import codex_process
from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import ForestError, InfrastructureError, canonical
from hpc_forest.memory_contract import POLICY, empty_read
from hpc_forest.memory_retrieval import MemoryReader
from hpc_forest.memory_store import sync_memory
from hpc_forest.model_skills import campaign_traces, policy, verify_binding
from hpc_forest.reporting import report


class MemoryNativeFixture:
    def __init__(self, count=2):
        self.calls, self.controller = [], None
        self.barrier = threading.Barrier(count, timeout=15)
        self.count = count

    def process(self, argv, output, log, timeout, **kwargs):
        request = json.loads((output / "request.json").read_text(encoding="utf8"))
        self.calls.append(copy.deepcopy(request))
        turn = request.get("conversation")
        thread = (turn or {}).get("thread_id") or str(uuid.uuid4())
        if "children" in request["schema"]["properties"]:
            value = decomposition(self.count)
            self.controller.db.set("deadline", time.time() - 1)
        elif request.get("meta_role") == "mother-memory-selection":
            payload = json.loads(kwargs["stdin"])
            selection = payload["assembly_selection"]
            read = empty_read()
            if selection["round"] > 1:
                action, sources = "finish", []
            elif "last_read" not in payload["memory"]:
                action, sources = "read", []
                read = {**read, "operation": "search", "query": "optimization"}
            else:
                action = "integrate"
                cards = payload["memory"]["last_read"]["items"]
                sources = [item["id"] for item in cards if item["kind"] == "experiment"
                           and item["measured_outcome"]["correct"] is True
                           and item["measured_outcome"]["mean_seconds"] is not None][:2]
                assert sources
            value = {"action": action, "read": read, "base_id": sources[0] if sources else "",
                     "source_ids": sources, "idea_ids": [], "rationale": "Offline combination fixture"}
        else:
            payload, source = kwargs["stdin"].split("\n\nCURRENT SOURCE AS DATA:\n", 1)
            payload = json.loads(payload)
            role = payload["role"]
            memory = payload["context_as_data"]["memory"]
            content = source.split("--- BEGIN FILE src/params.h ---\n", 1)[1].split(
                "\n--- END FILE src/params.h ---", 1)[0]
            content = content.replace("\nint deliberately_invalid = ;\n", "\n")
            tile = 71 if role == "G" else int(role[1:]) * 8 + 1
            content = re.sub(r"#define TILE \d+", f"#define TILE {tile}", content)
            content = content.replace("#define LAYOUT 0", "#define LAYOUT 1")
            if role == "G":
                content = content.replace("#define SIMD 0", "#define SIMD 1")
                assert "integration_selection" in payload["context_as_data"]
                assert "resume" in argv and turn["phase"] == "assembly"
            elif request["mission_id"].endswith("-h01"):
                self.barrier.wait()
            value = {"hypothesis": "optimization source fixture", "transformations": ["layout fixture"],
                     "sources_kept": payload["integration_source_ids"], "notes": "offline fixture",
                     "files": [{"path": "src/params.h", "content": content}],
                     "memory_read": empty_read(), "memory_lessons": []}
            if role == "T1" and request["mission_id"].endswith("-h01"):
                value.update(files=[], transformations=[], sources_kept=[],
                             memory_read={**empty_read(), "operation": "search"})
            elif role == "T1" and request["mission_id"].endswith("-h02"):
                value["files"][0]["content"] += "\nint deliberately_invalid = ;\n"
            if "baseline-e1" in memory["evidence_ids"]:
                value["memory_lessons"] = [{"claim": "Test this optimization against the reference",
                    "evidence_ids": ["baseline-e1"], "applicability": "current compiler and target",
                    "next_experiment": "combine layout and SIMD"}]
            if role == "T2":
                value["memory_lessons"].append({"claim": "An unsupported optional annotation",
                    "evidence_ids": ["invented-evidence"], "applicability": "", "next_experiment": ""})
        if request.get("model_skills"):
            value["skill_usage"] = [{"name": entry["name"], "status": "applied",
                "summary": "Offline fixture exercises the requested phase", "references": []}
                for entry in request["model_skills"]["loaded"]]
        (output / "agent-result.json").write_text(json.dumps(value), encoding="utf8")
        log.write_text("\n".join(json.dumps(event) for event in [
            {"type": "thread.started", "thread_id": thread},
            {"type": "turn.completed", "usage": {"input_tokens": 2, "output_tokens": 1}}]), encoding="utf8")
        return SimpleNamespace(returncode=0, timed_out=False, log=str(log))


def campaign(tmp_path, monkeypatch, *, mode="active", skills_enabled=False):
    config = persistent_settings(tmp_path)
    if skills_enabled:
        config["skills"] = policy()
    config["memory"] = {"mode": mode, "assembly_rounds": 2, "selection_calls": 2, "page_size": 12}
    config["forest"]["integration"] = POLICY if mode == "active" else "pairwise"
    config["harness"].update(enabled=True, max_attempts=2, call_token_ceiling=None)
    config["protocol"]["repetitions"] = 1
    mailbox.initialize_channel(Path(config["codex"]["mailbox_dir"]), config["codex"]["session_id"], "offline-memory-fixture")
    fixture = MemoryNativeFixture() if mode == "active" else NativeFixture(2)
    monkeypatch.setattr(codex_process, "run_process", fixture.process)
    monkeypatch.setattr(codex_process, "shutil", SimpleNamespace(which=lambda _: "codex.exe"))
    monkeypatch.setattr(codex_process, "check_dependencies", lambda *args: {
        "completion": {"policy": "finish-started", "token_policy": "observe-only"}})
    def receive(channel, request, sha):
        return codex_process.run_codex(request, sha, tmp_path / "native-worker" / request["nonce"],
                                      tmp_path / "offline-gate", set())
    monkeypatch.setattr(mailbox, "wait_response", receive)
    root = create_workspace(tmp_path / "campaign", config)
    fixture.controller = Controller(root)
    return root, fixture.controller, fixture


@pytest.mark.parametrize("skills_enabled", [False, True])
def test_memory_reads_repairs_same_mother_code_and_real_independent_confirmation(
    tmp_path, monkeypatch, need_compiler, skills_enabled,
):
    root, controller, fixture = campaign(tmp_path, monkeypatch, skills_enabled=skills_enabled)
    with controller:
        state = controller.run()
        post = state["postprocess"]
        assert post["status"] == "complete", post
        assert len(post["steps"]) == 1 and post["stop_decision"]["action"] == "finish"
        assert post["stop_decision"]["controller_budget_stop"]
        assert len(post["selections"]) == 1  # Expired target: reject the fixture's extra read, then code.
        assert post["steps"][0]["outcome"]["correct"] is True
        research = controller.db.rows("SELECT * FROM trials WHERE role<>'G'")
        assert len(research) == 2 and all(json.loads(row["result"])["correct"] for row in research)
        usage = [json.loads(row["payload"]) for row in controller.db.rows(
            "SELECT payload FROM events WHERE kind='generation_usage'")]
        assert any(attempt.get("rejected_memory_lessons") for row in usage
                   for attempt in row.get("attempt_usage", [row]))
        t1 = next(row for row in research if row["role"] == "T1")
        journal = json.loads((root / "logs" / t1["id"] / "node-harness.json").read_text())
        assert [row["state"] for row in journal["attempts"]] == ["memory_read", "development_failed", "development_passed"]
        assert journal["development_checks"] == 2
        assert len(controller.db.rows("SELECT * FROM trials")) == 3  # No trial/reward for reads or selection.
        assert not controller.db.rows("SELECT * FROM evaluations WHERE experiment_id LIKE 'memory-select%'")
        assembly = [request for request in fixture.calls if request.get("conversation", {}).get("phase") == "assembly"]
        original = state["forest_plan"]["conversation"]
        assert all(request["conversation"]["thread_id"] == original["thread_id"] for request in assembly)
        assert [request["conversation"]["turn"] for request in assembly] == list(range(1, len(assembly) + 1))
        if skills_enabled:
            assert all(verify_binding(request) for request in fixture.calls)
            traces = campaign_traces(controller.db)
            assert len(traces) == len(fixture.calls)
            assert all(trace["report_status"] == "reported" for trace in traces)
        trials_before = controller.db.rows("SELECT id,result FROM trials ORDER BY id")
        sync_memory(controller.db, root)
        sync_memory(controller.db, root)
        assert trials_before == controller.db.rows("SELECT id,result FROM trials ORDER BY id")
        assert controller.db.one("SELECT count(*) AS n FROM memory_facts WHERE kind='development'")["n"] == 4
        assert controller.db.one("SELECT count(*) AS n FROM memory_facts WHERE kind='lesson'")["n"] > 0
        model_count = len(fixture.calls)
        controller.confirm()
        assert len(fixture.calls) == model_count
        assert controller.db.get("final_g_confirmation:1")["status"] == "confirmed"
        assert controller.run()["postprocess"] == post
        assert len(fixture.calls) == model_count
        with pytest.raises(ForestError, match="already claimed"):
            controller.db.reserve("postprocess", "postprocess:e1:memory:select:1:1")
        result = json.loads((report(root).parent / "experiments.json").read_text())
        assert result["memory"]["mode"] == "active"
        assert result["memory"]["records"]


def test_interrupted_selection_is_never_replayed(tmp_path, monkeypatch, need_compiler):
    root, controller, fixture = campaign(tmp_path, monkeypatch)
    original = mailbox.wait_response
    def interrupt(channel, request, sha):
        if request.get("meta_role") == "mother-memory-selection":
            raise InfrastructureError("offline interrupted selection")
        return original(channel, request, sha)
    monkeypatch.setattr(mailbox, "wait_response", interrupt)
    with controller:
        post = controller.run()["postprocess"]
        assert post["status"] == "failed"
        assert len(post["selections"]) == 1
        calls = len(fixture.calls)
        controller.run()
        assert len(fixture.calls) == calls
        assert not controller.db.rows("SELECT * FROM trials WHERE role='G'")
        with MemoryReader(root, type("Mission", (), {"epoch": 1, "role": "G"})(), controller.config,
                          controller.db.get("protocol_id")) as reader:
            assert "infrastructure_error" not in canonical(reader.search())


def test_record_only_archives_without_changing_legacy_model_contract(tmp_path, monkeypatch, need_compiler):
    root, controller, fixture = campaign(tmp_path, monkeypatch, mode="record-only")
    with controller:
        post = controller.run()["postprocess"]
        assert post["status"] == "complete" and post["integration_policy"] == "pairwise"
        assert len(fixture.calls) == 4  # Mother, two source proposals, one real integration.
        assert all("memory_read" not in request["schema"]["properties"] for request in fixture.calls)
        assert controller.db.one("SELECT count(*) AS n FROM memory_facts")["n"] >= 7
