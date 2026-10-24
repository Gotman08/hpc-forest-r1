"""Exact source evidence; byte differences do not establish semantic novelty."""
from __future__ import annotations

from pathlib import Path

from .core import InfrastructureError, digest
from .gitops import git

CONFIG_SUFFIXES = {".json", ".toml", ".yaml", ".yml", ".ini", ".cfg"}


def manifest(repo, commit):
    files = {}
    for entry in git(repo, "ls-tree", "-r", "-z", commit, "--", "src", binary=True).split(b"\0"):
        if entry:
            header, path = entry.split(b"\t", 1)
            mode, kind, blob = header.split()
            if kind != b"blob" or mode not in {b"100644", b"100755"}:
                raise InfrastructureError("Source diversity requires regular committed files")
            files[path.decode("utf8")] = [mode.decode("ascii"), blob.decode("ascii")]
    return files


def compare_sources(base, candidate, inputs):
    changed = sorted(path for path in base.keys() | candidate.keys() if base.get(path) != candidate.get(path))
    configuration = [path for path in changed if Path(path).suffix.lower() in CONFIG_SUFFIXES]
    matched = [identity for identity, files in inputs.items() if candidate == files]
    # Matching newly changed whole files proves reuse, not the value of an algorithm
    # or whether a merged fragment was inspired by a different tree.
    reused = {identity: sum(path in candidate and candidate[path] == files.get(path) for path in changed)
              for identity, files in inputs.items()}
    kind = ("unchanged_from_base" if not changed else "identical_to_input" if matched else
            "configuration_files_only" if len(configuration) == len(changed) else "nonconfiguration_files_changed")
    return {"available": True, "kind": kind, "program_digest": digest(candidate),
            "nonconfiguration_digest": digest({k: v for k, v in candidate.items() if Path(k).suffix.lower() not in CONFIG_SUFFIXES}),
            "changed_file_count": len(changed), "configuration_file_count": len(configuration),
            "changed_paths": changed[:12], "paths_truncated": len(changed) > 12,
            "identical_input_ids": matched, "changed_files_matching_inputs": reused,
            "semantic_novelty": "not_established_by_file_hashes"}


def source_evidence(root, mission, outcome):
    repo = Path(root) / "repo"
    if not outcome.get("commit") or not mission.get("base_commit") or not (repo / ".git").exists():
        return {"available": False, "reason": "Exact source commits unavailable"}
    try:
        snapshots = {}
        def load(commit):
            if commit not in snapshots:
                snapshots[commit] = manifest(repo, commit)
            return snapshots[commit]
        base, candidate = load(mission["base_commit"]), load(outcome["commit"])
        inputs = {identity: load(commit) for identity, commit in
                  zip(mission.get("sources", []), mission.get("source_commits", []), strict=True)}
        return compare_sources(base, candidate, inputs)
    except (InfrastructureError, ValueError, UnicodeError) as exc:
        # Missing derived diagnostics never change a measured result or its AB-MCTS reward.
        return {"available": False, "reason": str(exc)[:400]}


def compact_evidence(value):
    result = {key: value[key] for key in ("available", "kind", "changed_file_count", "configuration_file_count",
              "semantic_novelty") if key in value}
    if "identical_input_ids" in value:
        result.update(identical_input_ids=value["identical_input_ids"][:6],
                      identical_input_count=len(value["identical_input_ids"]))
    return result


def diversity_counts(connection, scope, params):
    fingerprint = "coalesce(json_extract(payload,'$.facts.outcome.tree_hash'),json_extract(payload,'$.facts.source_change.program_digest'))"
    row = connection.execute("SELECT count(" + fingerprint + ") AS observed, count(DISTINCT " + fingerprint + ") AS distinct_programs, "
        "sum(json_extract(payload,'$.facts.source_change.kind')='configuration_files_only') AS configuration_only "
        "FROM memory_facts WHERE " + scope + " AND kind='experiment'", params).fetchone()
    result = {key: row[key] or 0 for key in row.keys()}
    result["repeated_programs"] = result["observed"] - result["distinct_programs"]
    return result
