"""Full native transport fixtures with real C builds, TreeQuest and confirmation."""
import copy
import json
import re
import threading
import uuid
from types import SimpleNamespace

import pytest
from test_active_architecture import action, decision, report_data
from test_mother_conversation import native_campaign, persistent_settings
from test_mother_forest import decomposition

from hpc_forest import codex_process
from hpc_forest.active_state import state
from hpc_forest.memory_contract import empty_read
from hpc_forest.reporting import report


@pytest.mark.parametrize("failed_integration", [False, True])
@pytest.mark.parametrize("corrected", [False, True])
def test_live_loop_branches_integrates_closes_and_confirms(tmp_path, monkeypatch, need_compiler, failed_integration, corrected):
    cfg = persistent_settings(tmp_path)
    cfg["budget"]["wall_seconds"] = 3600
    cfg["forest"]["active"] = {"mode": "full", "analysis_every": 1, "analysis_calls": 1, "steering_calls": 1,
                               "code_analysis": corrected, "closure_guards": corrected}
    if corrected:
        # This pipeline exercises closure when protected work no longer fits;
        # the complementary two-experiment continuation is covered directly.
        cfg["forest"]["active"]["progress_budget_fraction"] = 0.001
    cfg["memory"] = {"mode": "active", "context_characters": 64000}
    cfg["harness"].update(enabled=True, max_attempts=1)
    monkeypatch.setattr("test_mother_conversation.persistent_settings", lambda _: copy.deepcopy(cfg))
    root, controller, fixture = native_campaign(tmp_path, monkeypatch, 2)
    initial = threading.Barrier(2, timeout=20)
    calls, steering = [], []

    def process(argv, output, log, timeout, **kwargs):
        request = json.loads((output / "request.json").read_text(encoding="utf8"))
        schema = request["schema"]["properties"]
        calls.append(request)
        turn = request.get("conversation")
        thread = (turn or {}).get("thread_id") or str(uuid.uuid4())
        if "children" in schema:
            value = decomposition(2)
        elif request.get("active_control"):
            payload = json.loads(request["messages"][1]["content"])
            catalog = payload["history"][0]["view"]["items"]
            sources = [v["id"] for v in catalog if v["kind"] == "trial" and v["measured_outcome"]["correct"]]
            if request["active_control"]["kind"] == "analyst":
                value = report_data(sources[0] if sources else "baseline-e1")
                if corrected:
                    page = payload["code_packet"]["sources"][0]
                    value["code_findings"] = [{"mechanism": "Fixture examines the versioned tile parameter",
                        "citations": [{k: page[k] for k in ("evidence_id", "path", "sha256", "start_line", "end_line")}]}]
                assert "--ephemeral" in argv
            else:
                assert "resume" in argv and turn["phase"] == "steering"
                trees = payload["trees"]
                if "Gm1" not in trees and len(sources) >= 2:
                    actions = [action("branch", sources=[sources[0]]),
                               action("integrate", sources=sources[:2]),
                               action("share", "T1", sources=sources[:1]), action("suspend", "T2")]
                elif "Gm1" in trees and trees["Gm1"]["completed_ids"]:
                    actions = [action("close")]
                    if corrected:
                        actions[0]["hypothesis_review"] = [{"report_id": h["report_id"], "index": h["index"],
                            "disposition": "rejected", "evidence_ids": [],
                            "reason": "The fixture has no further distinct experiment after the bounded trial allowance"}
                            for h in payload["closure_hypotheses"]]
                else:
                    actions = [action("continue", "T1")]
                value = decision(payload, *actions)
                steering.append(value)
        else:
            payload, sources = kwargs["stdin"].split("\n\nCURRENT SOURCE AS DATA:\n", 1)
            payload = json.loads(payload)
            role = payload["role"]
            if role in {"T1", "T2"} and payload["ordinal"] == 1:
                initial.wait()
            content = sources.split("--- BEGIN FILE src/params.h ---\n", 1)[1].split("\n--- END FILE src/params.h ---", 1)[0]
            tile = {"T1": 8, "T2": 24, "T3": 40, "Gm1": 64, "G": 80}[role] + payload["ordinal"]
            content = re.sub(r"#define TILE \d+", f"#define TILE {tile}", content).replace("#define LAYOUT 0", "#define LAYOUT 1")
            if role in {"Gm1", "G"}:
                content = content.replace("#define SIMD 0", "#define SIMD 1")
            if role == "Gm1" and failed_integration:
                content += "\nint fixture_invalid_code = ;\n"
            value = {"hypothesis": "Offline fixture", "transformations": ["Fixture"],
                     "sources_kept": payload["integration_source_ids"],
                     "files": [{"path": "src/params.h", "content": content}], "notes": "Offline fixture",
                     "memory_read": empty_read(), "memory_lessons": []}
            if role == "Gm1":
                assert turn is None  # Intermediate G is not final Mother assembly.
                assert payload["context_as_data"]["intermediate_integration"]["decision_id"]
        (output / "agent-result.json").write_text(json.dumps(value), encoding="utf8")
        log.write_text("\n".join(json.dumps(v) for v in [
            {"type": "thread.started", "thread_id": thread},
            {"type": "turn.completed", "usage": {"input_tokens": 2 * ((turn or {}).get("turn", 0) + 1),
                                                "output_tokens": (turn or {}).get("turn", 0) + 1}}]), encoding="utf8")
        return SimpleNamespace(returncode=0, timed_out=False, log=str(log))

    monkeypatch.setattr(codex_process, "run_process", process)
    with controller:
        result = controller.run(max_batches=4)
        if result["status"] == "checkpointed":
            result = controller.run(max_batches=2)
        controller.confirm()
        result = controller.status()
        assert result["status"] == "confirmed"
        runtime = state(controller.db, 1)
        assert runtime["closed"]
        if corrected:
            assert runtime["lifecycle"]["closure_history"][-1]["closure_confirmed"]
            assert all(a["coverage"]["cited_sources"] for a in runtime["analysts"].values() if a.get("report_id"))
        assert [c["role"] for c in runtime["children"]] == ["T3", "Gm1"]
        gm = controller.db.one("SELECT * FROM trials WHERE role='Gm1'")
        assert gm is not None and gm["state"] == "completed"
        outcome = json.loads(gm["result"])
        assert outcome["correct"] is (not failed_integration)
        if failed_integration:
            assert outcome["score"] == 0
        mission = json.loads(gm["mission"])
        assert mission["kind"] == "intermediate_integration" and len(mission["sources"]) == 2
        assert mission["parent_id"] is None and mission["base_source_id"] in mission["sources"]
        branch = controller.db.one("SELECT mission FROM trials WHERE role='T3' ORDER BY created LIMIT 1")
        assert json.loads(branch["mission"])["base_source_id"]
        assert not controller.db.rows("SELECT id FROM trials WHERE state='pending'")
        assert result["costs"]["tokens_reserved"] == 0 and result["costs"]["unknown_usage_calls"] == 0
        mother = [r for r in calls if r.get("conversation")]
        assert {r["conversation"]["id"] for r in mother} == {mother[0]["conversation"]["id"]}
        assert [r["conversation"]["turn"] for r in mother] == list(range(len(mother)))
        assert mother[-1]["conversation"]["phase"] == "assembly"
        assert result["final_g_confirmation"]["status"] in {"confirmed", "rejected"}
        assert len(steering) >= 2
        report(root)
        assert (root / "report" / "active-decisions.csv").is_file()
        assert (root / "report" / "active-control.csv").is_file()
