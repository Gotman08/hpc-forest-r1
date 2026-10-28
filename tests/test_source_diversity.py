"""Diversity observations come from committed files, never from claimed ideas."""
import json

from test_memory import fact, mission
from test_memory import memory_db as memory_fixture

from hpc_forest.gitops import git, initialize_source
from hpc_forest.memory.retrieval import MemoryReader
from hpc_forest.source_diversity import compare_sources, source_evidence

memory_db = memory_fixture


def test_only_configuration_changes_are_distinct_from_source_changes_and_copies():
    base = {"src/program.c": "code-a", "src/options.json": "settings-a"}
    configured = {**base, "src/options.json": "settings-b"}
    other = {**base, "src/program.c": "code-b"}
    combined = {**other, "src/options.json": "settings-b"}
    assert compare_sources(base, base, {"A": base})["kind"] == "unchanged_from_base"
    assert compare_sources(base, configured, {"A": base})["kind"] == "configuration_files_only"
    assert compare_sources(base, other, {"A": other})["kind"] == "identical_to_input"
    observation = compare_sources(base, combined, {"A": configured, "B": other})
    assert observation["kind"] == "nonconfiguration_files_changed"
    assert observation["changed_files_matching_inputs"] == {"A": 1, "B": 1}
    assert observation["semantic_novelty"] == "not_established_by_file_hashes"
    assert compare_sources(base, configured, {})["nonconfiguration_digest"] == compare_sources(base, base, {})["nonconfiguration_digest"]


def test_exact_commits_override_model_description_and_missing_archives_are_explicit(tmp_path):
    source = tmp_path / "input"
    (source / "src").mkdir(parents=True)
    (source / "src/program.c").write_text("int main(void) { return 0; }\n")
    (source / "src/options.json").write_text('{"parameter": 1}\n')
    root = tmp_path / "campaign"
    root.mkdir()
    repo = root / "repo"
    base = initialize_source(source, repo)
    (repo / "src/options.json").write_text('{"parameter": 2}\n')
    git(repo, "add", "src")
    git(repo, "commit", "-m", "fixture: adjust configuration")
    changed = git(repo, "rev-parse", "HEAD")
    task = {"base_commit": base, "sources": ["source-a"], "source_commits": [base],
            "hypothesis": "Claims a complete algorithm rewrite"}
    evidence = source_evidence(root, task, {"commit": changed})
    assert evidence["available"] and evidence["kind"] == "configuration_files_only"
    assert evidence["changed_paths"] == ["src/options.json"]
    assert evidence["changed_file_count"] == 1
    assert not source_evidence(root, task, {"commit": "missing-commit"})["available"]
    assert not source_evidence(root, task, {"correct": False})["available"]


def test_repeated_programs_do_not_count_renamed_hypotheses_as_new_variants(memory_db):
    db, store, config, root = memory_db
    db.set("forest_plan:1", {"children": [{"role": "T1", "subject": "topic", "objective": "test"}]})
    for identity, fingerprint, seconds in [("fast", "same", 1), ("renamed", "same", 1.1), ("slow", "different", 8)]:
        fact(store, identity, claim=identity + " hypothesis", seconds=seconds)
        db.connection.execute("UPDATE memory_facts SET payload=json_set(payload,'$.facts.outcome.tree_hash',?) WHERE id=?",
                              (fingerprint, identity))
    fact(store, "infra", seconds=None, correct=None)
    fact(store, "sibling", role="T2")
    db.connection.commit()
    with MemoryReader(root, mission(), config, "p") as reader:
        item = reader.catalog()["items"][0]
        assert item["source_diversity"] == {"observed": 3, "distinct_programs": 2, "configuration_only": 0,
                                            "repeated_programs": 1}
        assert item["alternative"]["id"] == "slow"
        assert item["results"]["unmeasured"] == 1
        assert "sibling" not in json.dumps(item)
