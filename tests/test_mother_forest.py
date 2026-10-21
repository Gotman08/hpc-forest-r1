"""Offline model outputs, real TreeQuest and C validation; no hosted generation."""
import copy
import json
import threading
import time
import zipfile
from pathlib import Path

import pytest
import treequest

from hpc_forest import codex_mailbox as mailbox
from hpc_forest.backends import Generated
from hpc_forest.config import load_config, validate
from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import ForestError, InfrastructureError, digest
from hpc_forest.forest import forest_width
from hpc_forest.mother import render_plan, validated_plan
from hpc_forest.reporting import package, report
from hpc_forest.source_request import proposal_messages


def decomposition(count):
    return {"analysis": "Independent subjects selected from this offline fixture.",
            "children": [{"subject": f"Fixture subject {i}", "objective": f"Fixture objective {i}"}
                         for i in range(1, count + 1)], "G": "Integrate measured valid programs."}


def settings(tmp_path):
    config = load_config()
    config.update(backend="codex", forest={"policy": "mother"})
    config["budget"].update(max_workers=1, wall_seconds=600, infrastructure_retries=0)
    config["codex"].update(model=mailbox.MODEL, reasoning_effort=mailbox.EFFORT,
        transport="codex-mailbox", mailbox_dir=str(tmp_path / "mailbox"), session_id="a" * 32)
    config["protocol"].update(repetitions=1, confirmation_repetitions=2, warmups=0,
        benchmark=["{binary}", "96", "17", "2"])
    return config


class ConcurrentModel:
    def __init__(self, count):
        self.barrier = threading.Barrier(count, timeout=10)
        self.lock = threading.Lock()
        self.active, self.peak, self.calls = 0, 0, []

    def generate(self, mission, context, config, root):
        with self.lock:
            self.calls.append((copy.deepcopy(mission), copy.deepcopy(context)))
            self.active += mission.role != "G"
            self.peak = max(self.peak, self.active)
        try:
            if mission.role != "G":
                self.barrier.wait()  # A serial relay/controller cannot pass this test.
                time.sleep(0.02)
            params = Path(mission.worktree) / "src/params.h"
            text = params.read_text().replace("#define LAYOUT 0", "#define LAYOUT 1")
            tile = (int(mission.role[1:]) * 8 + mission.ordinal) if mission.role != "G" else 7
            import re

            text = re.sub(r"#define TILE \d+", f"#define TILE {tile}", text)
            if mission.role == "G":
                text = text.replace("#define SIMD 0", "#define SIMD 1")
            params.write_text(text)
            mission.hypothesis = "Offline fixture candidate"
            return Generated(7, {"llm_calls": 1, "backend": "offline-model-fixture"})
        finally:
            with self.lock:
                self.active -= mission.role != "G"


def campaign(tmp_path, monkeypatch, count, *, expire_in_mother=False, invalid=False):
    config, calls, holder = settings(tmp_path), [], {}
    def publish(channel, request):
        calls.append(copy.deepcopy(request))
        return digest(request)
    def receive(channel, request, sha):
        if "children" in request["schema"]["properties"]:
            data = decomposition(count)
            if invalid:
                data["children"] = []
            if expire_in_mother:
                holder["controller"].db.set("deadline", time.time() - 1)
        else:
            data = dict.fromkeys(request["schema"]["required"], "Offline synthesis guidance")
        return mailbox.response_envelope(request, sha, data=data, error=None,
            usage={"tokens": 11, "llm_calls": 1, "token_accounting": "exact"})
    monkeypatch.setattr(mailbox, "publish_request", publish)
    monkeypatch.setattr(mailbox, "wait_response", receive)
    root = create_workspace(tmp_path / "campaign", config)
    controller = Controller(root)
    controller.backend = ConcurrentModel(count)
    holder["controller"] = controller
    return root, controller, calls


@pytest.mark.parametrize("count", [1, 5, 8])
def test_mother_selects_n_all_start_together_finish_after_time_then_confirm_and_package(
        tmp_path, monkeypatch, need_compiler, count):
    root, controller, calls = campaign(tmp_path, monkeypatch, count, expire_in_mother=True)
    with controller:
        state = controller.run()
        assert state["status"] == "budget_exhausted"
        assert state["research_roles"] == [f"T{i}" for i in range(1, count + 1)]
        assert controller.backend.peak == count  # max_workers=1 deliberately cannot throttle N.
        assert isinstance(controller.search.algo, treequest.ABMCTSA)
        assert controller.db.get("config")["roles"] == ["A", "B", "C"]  # Frozen config stays frozen.
        selected = state["forest_plan"]
        assert selected["parallelism"] == count
        assert [request["meta_role"] for request in calls] == ["mother-preparation", "mother-final-synthesis"]
        for mission, context in controller.backend.calls:
            assert context["deadline"] is None and context["remaining_tokens"] is None
            if mission.role != "G":
                expected = decomposition(count)["children"][int(mission.role[1:]) - 1]
                assert context["research_tree"] == {"role": mission.role, **expected}
                proposal = proposal_messages(Path(mission.worktree), mission, context)
                assert json.loads(proposal["messages"][1]["content"].split("\n\nCURRENT SOURCE")[0])["goal"] == expected["objective"]
                assert mission.delegation_parent == "R/" + mission.role
                assert mission.parent_id is None and not mission.sources
            else:
                assert len(context["sources"]) == count
                assert mission.budget_phase == "postprocess" and mission.tree_id == "e1:G-final"
        observed = json.loads(calls[-1]["messages"][1]["content"])["automatic_observations_as_data"]
        assert len(observed["all_admissible_programs"]) == count
        assert observed["research_forest_as_data"] == selected
        controller.confirm()
        final = controller.status()["final_g_confirmation"]
        assert final["status"] == "confirmed" and len(final["outcome"]["times"]) == 2
        before = len(controller.backend.calls), len(calls)
        controller.run()
        controller.confirm()
        assert (len(controller.backend.calls), len(calls)) == before
    report(root)
    package(root, root / "submission.zip")
    payload = json.loads((root / "report/experiments.json").read_text(encoding="utf-8"))
    assert len(payload["forest_plan"]["children"]) == count
    assert all(row["research_assignment"] for row in payload["experiments"] if row["role"] != "G")
    with zipfile.ZipFile(root / "submission.zip") as archive:
        assert json.loads(archive.read("HPC_FOREST_MANIFEST.json"))["forest_plan"] == selected


def test_checkpoint_reuses_n_objectives_and_treequest_states_then_integrates_all(tmp_path, monkeypatch, need_compiler):
    root, controller, calls = campaign(tmp_path, monkeypatch, 2)
    with controller:
        first = controller.run(max_batches=1)
        assert first["status"] == "checkpointed"
        selected = first["forest_plan"]
        model = controller.backend
    with Controller(root) as controller:
        controller.backend = model
        state = controller.run(max_batches=3)  # second research wave, G, G
        assert state["completed_batches"] == 4 and state["forest_plan"] == selected
        assert [request["meta_role"] for request in calls] == ["mother-preparation", "mother-synthesis"]
        assert {row["role"] for row in controller.db.rows("SELECT role FROM trees")} == {"T1", "T2", "G"}
        controller.db.set("deadline", time.time() - 1)
        controller.run()
        assert calls[-1]["meta_role"] == "mother-final-synthesis"
        assert controller.status()["postprocess"]["status"] == "complete"


def test_changed_recorded_objective_is_rejected_without_replanning(tmp_path, monkeypatch, need_compiler):
    _, controller, calls = campaign(tmp_path, monkeypatch, 1)
    with controller:
        controller.run(max_batches=1)
        selected = controller.db.get("forest_plan:1")
        selected["children"][0]["objective"] = "Replaced objective"
        controller.db.set("forest_plan:1", selected)
        with pytest.raises(InfrastructureError, match="planning receipt"):
            controller.run(max_batches=1)
        assert len(calls) == 1 and len(controller.backend.calls) == 1


def test_wave_setup_failure_never_launches_a_partial_forest_and_settles_unused_slots(
        tmp_path, monkeypatch, need_compiler):
    import hpc_forest.controller as module

    _, controller, calls = campaign(tmp_path, monkeypatch, 5)
    def unavailable(*args, **kwargs):
        raise InfrastructureError("synthetic worktree failure")
    monkeypatch.setattr(module, "make_worktree", unavailable)
    with controller:
        with pytest.raises(InfrastructureError, match="synthetic"):
            controller.run()
        assert not controller.backend.calls and len(calls) == 1
        slots = controller.db.rows("SELECT * FROM slots WHERE purpose LIKE 'role:%'")
        assert len(slots) == 5 and all(slot["tokens_settled"] == 1 and slot["tokens_used"] == 0 for slot in slots)
        with pytest.raises(ForestError, match="interrupted research wave"):
            controller.run()
        assert len(calls) == 1 and not controller.backend.calls


def test_invalid_mother_never_falls_back_to_three_trees(tmp_path, monkeypatch, need_compiler):
    _, controller, calls = campaign(tmp_path, monkeypatch, 5, invalid=True)
    with controller:
        with pytest.raises(InfrastructureError, match="valid research forest"):
            controller.run()
        assert len(calls) == 1 and not controller.db.rows("SELECT * FROM trials")
        with pytest.raises(InfrastructureError):
            controller.run()
        assert len(calls) == 1


@pytest.mark.parametrize("bad", [[], [{"subject": "same", "objective": "x"}] * 2,
    [{"subject": "a", "objective": "same"}, {"subject": "b", "objective": "same"}],
    [{"subject": " ", "objective": "x"}], [{"subject": "x", "objective": "y", "role": "../../G"}]])
def test_rejects_empty_duplicate_or_unsafe_assignments(bad):
    data = decomposition(1)
    data["children"] = bad
    with pytest.raises(InfrastructureError):
        validated_plan(data, choose_trees=True)


def test_no_arbitrary_tree_count_and_no_old_topic_schema():
    assert len(validated_plan(decomposition(300), choose_trees=True)["children"]) == 300
    rendered = render_plan("preparation", {}, "subject", {}, roles=[], choose_trees=True)
    assert "maxItems" not in rendered["schema"]["properties"]["children"]
    assert set(rendered["schema"]["properties"]) == {"analysis", "children", "G"}


def test_controller_owned_width_cannot_be_replaced_by_an_unrelated_plan():
    record = {"protocol": "hpc-forest-mother-forest-v1", "session_id": "a" * 32,
              "status": "complete", "parallelism": 8,
              "children": [{"role": f"T{i}"} for i in range(1, 9)]}
    assert forest_width(record, "a" * 32) == 8
    for field, value in (("parallelism", 3), ("session_id", "b" * 32)):
        with pytest.raises(ForestError):
            forest_width({**record, field: value}, "a" * 32)


def test_mother_mode_does_not_accept_binary_or_finite_legacy_limits(tmp_path):
    config = settings(tmp_path)
    validate(config)
    for changes in ({"binary_tree": {"enabled": True}}, {"backend": "recipe"}, {"method": "U"}):
        with pytest.raises(ForestError):
            validate({**config, **changes})
