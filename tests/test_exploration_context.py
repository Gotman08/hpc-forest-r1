"""Diverse inspiration exposes real scoped code, never fabricated search parents."""
import copy
from types import SimpleNamespace

import pytest
from test_evolution_archive import enable, entry

from hpc_forest.core import Mission, digest
from hpc_forest.evolution_archive import attach
from hpc_forest.exploration_context import SOURCE_CHARACTERS, summarize
from hpc_forest.source_request import proposal_messages


@pytest.fixture
def archive(db, tmp_path, monkeypatch):
    config = enable(db)
    code = {"fast": "void run() { for(int i=0;i<10;i++) a[i]+=1; }\n",
            "slow": "// Different measured alternative\nvoid run() { sort(values); }\n",
            "other": "void run() { private_other_tree(); }\n"}
    for identity, text in code.items():
        record = entry(identity, text, 1 if identity == "fast" else 8,
                       role="T2" if identity == "other" else "T1")
        db.set("evolution_entry:" + identity, record)
    monkeypatch.setattr("hpc_forest.exploration_context.committed_source_snapshot",
                        lambda root, commit: {"src/main.cpp": code[commit]})
    worktree = tmp_path / "worktree"
    (worktree / "src").mkdir(parents=True)
    (worktree / "src/main.cpp").write_text("void run() {}\n")
    mission = Mission("new", "e1:T1", "trial", 1, "T1", "base", None, "R/T1", 1, 4, str(worktree))
    return SimpleNamespace(config=config, db=db, root=tmp_path), mission, code


def test_slower_correct_code_is_visible_without_cross_tree_leak_or_parent_change(archive):
    controller, mission, _ = archive
    original = copy.deepcopy(mission)
    before = controller.db.get("evolution_entry:slow")
    result = attach(controller, mission, {})
    context = result["exploration_context"]
    assert context["intent"] == "explore_from_assigned_base"
    pages = context["source_excerpts"]
    assert {p["evidence_id"] for p in pages} == {"fast", "slow"}
    assert any("sort(values)" in p["text"] for p in pages)
    assert sum(len(p["text"]) for p in pages) <= SOURCE_CHARACTERS
    assert all(p["sha256"] and p["start_line"] >= 1 for p in pages)
    assert mission == original and controller.db.get("evolution_entry:slow") == before
    assert not controller.db.rows("SELECT * FROM evaluations")


def test_explicit_import_allows_source_but_never_changes_treequest_base(archive):
    controller, mission, _ = archive
    mission.import_ids = ["other"]
    mission.parent_id, mission.base_commit = "fast", "fast"
    context = attach(controller, mission, {})["exploration_context"]
    assert context["intent"] == "refine_selected_parent"
    assert context["selected_parent_id"] == "fast" and context["base_commit"] == "fast"
    assert {p["evidence_id"] for p in context["source_excerpts"]} == {"slow", "other"}


def test_changed_archive_source_is_not_presented_as_verified_code(archive):
    controller, mission, code = archive
    code["slow"] = "void injected() {}\n"
    context = attach(controller, mission, {})["exploration_context"]
    assert {p["evidence_id"] for p in context["source_excerpts"]} == {"fast"}
    assert context["unavailable_sources"][0]["id"] == "slow"


def test_source_exposure_stays_bounded_and_marks_omissions(archive):
    controller, mission, code = archive
    code["slow"] = "float helper();\n" * 2000 + "void run() { helper(); }\n"
    updated = controller.db.get("evolution_entry:slow")
    updated["source_sha256"] = digest({"src/main.cpp": code["slow"]})
    controller.db.set("evolution_entry:slow", updated)
    context = attach(controller, mission, {})["exploration_context"]
    assert sum(len(p["text"]) for p in context["source_excerpts"]) <= SOURCE_CHARACTERS
    assert any(p["truncated"] for p in context["source_excerpts"])
    assert any("void run()" in p["text"] for p in context["source_excerpts"] if p["evidence_id"] == "slow")


def test_neutral_proposal_uses_inspiration_without_adding_a_model_or_algorithm(archive):
    controller, mission, _ = archive
    context = attach(controller, mission, {"research_tree": {"role": "T1", "objective": "Fixture objective"}})
    rendered = proposal_messages(controller.root / "worktree", mission, context)
    assert "choose a materially different code mechanism" in rendered["messages"][0]["content"]
    assert "sort(values)" in rendered["messages"][1]["content"]
    assert rendered["schema"]["properties"]["sources_kept"]["maxItems"] == 0
    assert controller.config["codex"]["model"] == "gpt-6-luna"
    assert controller.config["codex"]["reasoning_effort"] == "max"


def test_renamed_hypotheses_and_commits_do_not_inflate_program_diversity():
    def record(identity, text, correct=True):
        return {"id": identity, "kind": "trial", "mission": {"base_commit": "root", "hypothesis": identity},
                "source_files": {"src/main.c": text}, "outcome": {"commit": identity, "correct": correct}}

    result = summarize([record("a", "same"), record("b", "same"), record("c", "different"),
                        record("bad", "broken", False)])
    assert result["settled_trials"] == 4 and result["correct_source_variants"] == 2
    assert result["parent_sources"] == 1
