"""Bounded, model-independent development checks inside a single search mission.

No optimization code or repair is supplied here. All edits come from the wrapped
backend. Development results never become tree rewards or confirmation results.
"""
from __future__ import annotations

import copy
import time
from dataclasses import asdict
from pathlib import Path

from .backends import Generated
from .core import (
    BudgetExhausted,
    CandidateRejected,
    InfrastructureError,
    atomic_json,
    digest,
    protected_manifest,
    verify_protected,
)
from .evaluator import Evaluator
from .gitops import assert_allowed_changes, git, initialize_source
from .harness_research import DocumentationReader
from .support.budgets import generation_deadline, search_deadline
from .support.sources import SourceLimitExceeded, source_snapshot


def wrap_backend(backend, config):
    if not config.get("harness", {}).get("enabled") or isinstance(backend, NodeHarness):
        return backend
    return NodeHarness(backend)


def _source_snapshot(worktree):
    try:
        return source_snapshot(worktree)
    except SourceLimitExceeded as exc:
        raise CandidateRejected("Development source snapshot exceeds one MiB") from exc


class NodeHarness:
    """Repair failed development proposals using only measured compiler/checker feedback.

    A first passing development check ends the local episode. Optimization and
    branch selection continue through TreeQuest; this does not hide a second
    optimizer inside a vertex or choose a transformation for the model.
    """

    def __init__(self, backend):
        self.backend = backend

    def generate(self, mission, context, config, root):
        root, worktree = Path(root), Path(mission.worktree)
        settings = config["harness"]
        attempts = settings["max_attempts"]
        ceiling = settings["call_token_ceiling"]
        reservation = config["budget"]["mission_tokens"]
        if reservation < attempts * ceiling:
            raise InfrastructureError("Reserve every possible harness call before admitting a node")
        # All local work shares the original mission deadline and confirmation reserve.
        deadline = min(
            generation_deadline(context, config["budget"]["generation_seconds"]),
            search_deadline(context["deadline"], config["budget"]["confirmation_seconds"]),
        )
        journal = root / "logs" / mission.id / "node-harness.json"
        if journal.exists():
            raise InfrastructureError("This harness episode already started; never replay model calls")
        manifest = protected_manifest(root / "trusted")
        history, total_tokens = [], 0
        bounded, usage_unknown = False, False
        last = Generated()
        source_ids, source_commits = list(mission.sources), list(mission.source_commits)
        reader = None

        def persist(state):
            atomic_json(journal, {
                "schema": "hpc-forest-node-harness-v1", "mission_id": mission.id,
                "tree_id": mission.tree_id, "parent_id": mission.parent_id,
                "delegation_parent": mission.delegation_parent,
                "state": state, "reserved_tokens": reservation,
                "known_or_bounded_tokens": total_tokens,
                "unknown_usage": usage_unknown, "attempts": history,
                "development_checks": sum("development_outcome" in h for h in history),
                "outer_tree_reward_assigned": False, "holdout_access": False,
            })

        def result():
            persist("finished")
            return Generated(None if usage_unknown else total_tokens,
                {"backend": "node-harness", "llm_calls": sum(
                    h.get("llm_calls", 0) for h in history),
                 "harness_attempts": len(history),
                 "development_evaluations": sum("development_outcome" in h for h in history),
                 "attempt_usage": [h.get("generation_usage", {}) for h in history],
                 "journal": str(journal), "automatic_measured_feedback_only": not bool(reader),
                 "research_enabled": bool(reader),
                 "research_actions": sum("research_results" in h for h in history),
                 "contract_rejected": last.usage.get("contract_rejected", False)},
                last.error, last.infrastructure_error, bounded)

        persist("started")
        try:
            if mission.role == "G" and not context.get("sources"):
                last = Generated(0, {"llm_calls": 0}, error="No admissible integration sources")
                return result()
            if settings.get("research", {}).get("enabled"):
                if not getattr(self.backend, "supports_harness_research", False):
                    raise InfrastructureError("This backend has no structured documentation action")
                reader = DocumentationReader(settings["research"], journal.parent / "research", deadline)
            for number in range(1, attempts + 1):
                if time.time() >= deadline:
                    if not history:
                        last = Generated(0, error="No development time remains")
                        return result()
                    break
                assert_allowed_changes(worktree)
                if git(worktree, "rev-parse", "HEAD") != mission.base_commit:
                    raise CandidateRejected("A model changed the mission's Git parent")
                before_digest = digest(_source_snapshot(worktree))
                child = copy.deepcopy(mission)
                child.id = f"{mission.id}-h{number:02d}"
                child.sources, child.source_commits = list(source_ids), list(source_commits)
                call_config, call_context = copy.deepcopy(config), copy.deepcopy(context)
                call_config["budget"]["mission_tokens"] = ceiling
                call_config["budget"]["generation_seconds"] = max(0.001, deadline - time.time())
                call_context["deadline"] = deadline
                call_context["generation_deadline"] = deadline
                call_context["remaining_tokens"] = min(
                    reservation - total_tokens, context.get("remaining_tokens", reservation))
                call_context.setdefault("automatic_observations", {})["node_development"] = {
                    "attempt": number, "remaining_attempts": attempts - number + 1,
                    "previous_attempts": copy.deepcopy(history),
                    "confirmation_data_available": False,
                }
                if reader:
                    call_context["node_research"] = reader.capabilities()
                record = {"attempt": number, "generation_id": child.id,
                          "state": "model_call_claimed", "llm_calls": 1,
                          "source_digest_before_call": before_digest}
                history.append(record)
                persist("model_call_claimed")
                try:
                    last = self.backend.generate(child, call_context, call_config, root)
                except Exception as exc:
                    # The service may have accepted the call. Charge its ceiling and stop.
                    total_tokens += ceiling
                    bounded = True
                    record.update(state="generation_interrupted", error=type(exc).__name__)
                    last = Generated(error="Model interface interrupted; inspect generation logs",
                                     infrastructure_error=True)
                    return result()
                record["generation_usage"] = copy.deepcopy(last.usage)
                calls = last.usage.get("llm_calls", 1)
                record["llm_calls"] = calls if type(calls) is int and calls >= 0 else 1
                record["generation_error"] = last.error
                if last.tokens is None:
                    usage_unknown = True
                    last.error, last.infrastructure_error = "Model usage is unknown", True
                elif type(last.tokens) is not int or last.tokens < 0:
                    total_tokens += ceiling
                    bounded = True
                    last.error, last.infrastructure_error = "Invalid model usage", True
                else:
                    total_tokens += last.tokens
                    bounded |= last.tokens_upper_bound
                    if last.tokens > ceiling:
                        last.error, last.infrastructure_error = "Model exceeded its call reservation", True
                record["tokens"] = last.tokens
                persist("generation_complete")
                verify_protected(root / "trusted", manifest)
                assert_allowed_changes(worktree)
                if git(worktree, "rev-parse", "HEAD") != mission.base_commit:
                    raise CandidateRejected("A model changed the mission's Git parent")
                if last.infrastructure_error or usage_unknown:
                    return result()
                if last.error:
                    record["state"] = "generation_failed"
                    continue
                if reader and (research := last.usage.get("research_request")):
                    if digest(_source_snapshot(worktree)) != before_digest:
                        raise CandidateRejected("A documentation action changed source files")
                    record["research_results"] = reader.read(research, number)
                    record["state"] = "documentation_read"
                    # A read is not a candidate and cannot receive an outer reward.
                    last.error = "Documentation action ended without a subsequent source proposal"
                    persist(record["state"])
                    continue
                # Retain only metadata which a normal generation backend is allowed to change.
                for name in ("hypothesis", "transformations", "sources", "source_commits"):
                    setattr(mission, name, copy.deepcopy(getattr(child, name)))
                source_files = _source_snapshot(worktree)
                record["source_digest"] = digest(source_files)
                atomic_json(journal.parent / f"harness-source-{number:02d}.json", source_files)
                # The development checker sees a private source snapshot, never the mutable
                # candidate directory or a confirmation phase. Its score is never backpropagated.
                probe = root / "harness-probes" / mission.id / f"attempt-{number:02d}"
                probe.parent.mkdir(parents=True, exist_ok=True)
                commit = initialize_source(worktree, probe)
                evaluator = Evaluator(root, config, manifest, context["protocol_id"], deadline)
                outcome = evaluator.precheck(child.id, mission.epoch, probe, commit)
                data = asdict(outcome)
                data.pop("score", None)
                data.pop("mean_seconds", None)
                record["development_outcome"] = data
                record["measured_diagnostics"] = []
                for name in outcome.logs[:2]:
                    path = Path(name)
                    if path.is_file() and path.resolve().is_relative_to(root.resolve()):
                        raw = path.read_bytes()
                        record["measured_diagnostics"].append({
                            "path": str(path.relative_to(root)),
                            "text": raw[:4000].decode("utf8", errors="replace"),
                            "truncated": len(raw) > 4000,
                        })
                record["state"] = "development_passed" if outcome.correct else "development_failed"
                persist(record["state"])
                if outcome.correct:
                    break
            return result()
        except CandidateRejected as exc:
            last.error, last.infrastructure_error = str(exc), False
            last.usage["contract_rejected"] = True
            return result()
        except BudgetExhausted as exc:
            last.error, last.infrastructure_error = str(exc), False
            return result()
        except (InfrastructureError, OSError, ValueError) as exc:
            last.error, last.infrastructure_error = f"Development harness failed: {exc}", True
            return result()
        finally:
            verify_protected(root / "trusted", manifest)
