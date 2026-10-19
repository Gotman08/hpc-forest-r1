from __future__ import annotations

import itertools
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from importlib.resources import files
from pathlib import Path

from .backends import CodexBackend, RecipeBackend
from .binary_search import SearchExhausted, enabled
from .config import load_config, validate
from .core import (
    BudgetExhausted,
    CandidateRejected,
    FileLock,
    ForestError,
    InfrastructureError,
    Mission,
    Outcome,
    atomic_json,
    digest,
    local_target_id,
    protected_manifest,
    verify_protected,
)
from .evaluator import Evaluator, target_identity
from .gitops import commit_candidate, git, initialize_source, make_worktree
from .harness_research import DocumentationReader
from .knowledge import Knowledge
from .observations import measured_observations
from .ollama_backend import OllamaBackend, resolve_model
from .registry import Registry
from .search import Search
from .support.budgets import search_deadline
from .toolchain import compiler_identity

RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "hypothesis": {"type": "string"},
        "transformations": {"type": "array", "items": {"type": "string"}},
        "sources_kept": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
    "required": ["hypothesis", "transformations", "sources_kept", "notes"],
}


def create_workspace(
    destination: Path,
    config: dict | None = None,
    source: Path | None = None,
    validation: Path | None = None,
) -> Path:
    destination = destination.resolve()
    if destination.exists():
        raise ForestError(f"Refusing to overwrite an existing directory: {destination}")
    config = json.loads(json.dumps(config or load_config()))
    validate(config)
    if config["backend"] == "ollama":
        config["ollama"] = resolve_model(config["ollama"])
    config["target_id"] = config.get("target_id", local_target_id())
    config["compiler"] = compiler_identity()
    assets = Path(str(files("hpc_forest") / "assets"))
    source = source.resolve() if source else assets / "matmul"
    validation = validation.resolve() if validation else assets / "validation"
    if not source.is_dir() or not validation.is_dir():
        raise ForestError("Source and validation directories must exist")
    research = config.get("harness", {}).get("research", {})
    corpus = None
    if config.get("harness", {}).get("enabled") and research.get("enabled"):
        DocumentationReader(research, destination / "research-preflight", time.time())
        if research.get("corpus"):
            corpus = Path(research["corpus"]).resolve(strict=True)
    destination.mkdir(parents=True)
    trusted = destination / "trusted"
    shutil.copytree(validation, trusted, ignore=shutil.ignore_patterns("__pycache__"))
    if corpus:
        shutil.copyfile(corpus, trusted / "research-corpus.json")
        research["corpus"] = str(trusted / "research-corpus.json")
    atomic_json(trusted / "config.json", config)
    atomic_json(trusted / "result-schema.json", RESULT_SCHEMA)
    commit = initialize_source(source, destination / "repo")
    if (destination / "repo" / "run.sh").exists():
        runner = destination / "repo" / "run.sh"
        runner.chmod(runner.stat().st_mode | 0o111)
        git(destination / "repo", "update-index", "--chmod=+x", "run.sh")
        git(
            destination / "repo",
            "commit",
            "--allow-empty",
            "-m",
            "chore: preserve runner executable mode",
        )
        commit = git(destination / "repo", "rev-parse", "HEAD")
    db = Registry(destination / "registry.sqlite3")
    try:
        manifest = protected_manifest(trusted)
        identity = target_identity(config)
        protocol_id = digest(
            {"protocol": config["protocol"], "manifest": manifest, "target": identity}
        )
        for key, value in {
            "config": config,
            "manifest": manifest,
            "identity": identity,
            "protocol_id": protocol_id,
            "current_epoch": 1,
            "status": "ready",
            "started": None,
            "deadline": None,
        }.items():
            db.set(key, value)
        with db.connection:
            db.connection.execute(
                "INSERT INTO epochs(id,base_commit,protocol_id,created) VALUES(1,?,?,?)",
                (commit, protocol_id, time.time()),
            )
        Knowledge(db).add(
            "Greedy binary search persistence" if enabled(config) else "TreeQuest AB-MCTS ask tell persistence",
            "https://github.com/SakanaAI/treequest",
            "0.3.2",
            ("Binary-greedy evaluates two children of the same parent, then continues only "
             "the faster correct child. Pruned nodes remain archived. " if enabled(config) else
             "AB-MCTS-A selects new proposals and continuations. Scores are normalized to [0,1]. ") +
            "Persist each role's state per epoch. Integration receives one measured full-program "
            "reward in G only. Keep provenance separate from the selected search parent.",
            "Use the pinned TreeQuest version; local trusted checkpoints only.",
        )
        Knowledge(db).add(
            "C matrix locality SIMD OpenMP correctness",
            "local:matmul-training-task",
            "0.1.0",
            "The training task multiplies deterministic integer-valued double matrices. "
            "A changes memory locality and blocking; B changes SIMD and column chunks; "
            "C changes OpenMP scheduling. Tests compare every element, including odd sizes. "
            "Full-process time includes initialization and process startup. No measured gain is guaranteed.",
            "D/E are disabled for the CPU-only demonstration.",
        )
        db.event("workspace_created", {"base_commit": commit, "protocol_id": protocol_id})
    finally:
        db.close()
    return destination


class Controller:
    def __init__(self, root: Path):
        self.root = root.resolve()
        if not (self.root / "registry.sqlite3").is_file():
            raise ForestError(f"Not an initialized campaign: {self.root}")
        self.db = Registry(self.root / "registry.sqlite3")
        self.config = self.db.get("config")
        self.search = Search(self.db)
        self.backend = {"recipe": RecipeBackend, "codex": CodexBackend, "ollama": OllamaBackend}[
            self.config["backend"]
        ]()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.close()

    def _start(self) -> None:
        verify_protected(self.root / "trusted", self.db.get("manifest"))
        if target_identity(self.config) != self.db.get("identity"):
            raise InfrastructureError(
                "Target changed; create a new campaign rather than mix measurements"
            )
        if compiler_identity() != self.config["compiler"]:
            raise InfrastructureError("Compiler changed; create a new campaign")
        if self.db.get("started") is None:
            started = time.time()
            self.db.set("started", started)
            self.db.set("deadline", started + self.config["budget"]["wall_seconds"])
        self.evaluator = Evaluator(
            self.root,
            self.config,
            self.db.get("manifest"),
            self.db.get("protocol_id"),
            self.db.get("deadline"),
        )

    def epoch(self) -> dict:
        return self.db.one("SELECT * FROM epochs WHERE id=?", (self.db.get("current_epoch"),))

    def _initialize_trees(self, epoch: int) -> None:
        roles = ["U"] if self.config["method"] == "U" else [*self.config["roles"], "G"]
        for index, role in enumerate(roles):
            self.search.initialize(epoch, role, self.config["seed"] + epoch * 101 + index)

    def _baseline(self, epoch: dict) -> dict:
        existing = self.db.one(
            "SELECT * FROM evaluations WHERE experiment_id=? AND phase='search'",
            (f"baseline-e{epoch['id']}",),
        )
        if existing:
            result = json.loads(existing["payload"])
            if result["correct"] is not True:
                raise ForestError(
                    "Baseline failed validation; inspect evidence before starting a new campaign"
                )
            return result
        slot = self.db.reserve("search", "baseline")
        self.db.settle_tokens(slot, 0)
        # Later epochs have a different exact base, in their own worktree.
        path = self.root / "repo"
        if git(path, "rev-parse", "HEAD") != epoch["base_commit"]:
            path = self.root / "worktrees" / f"baseline-e{epoch['id']}"
            if not path.exists():
                make_worktree(
                    self.root / "repo", path, f"baseline/e{epoch['id']}", epoch["base_commit"]
                )
        result = self.evaluator.evaluate(
            f"baseline-e{epoch['id']}", epoch["id"], path, epoch["base_commit"], None
        )
        self.db.record_evaluation(f"baseline-e{epoch['id']}", epoch["id"], "search", asdict(result))
        if result.correct is not True:
            raise ForestError("Baseline does not pass the protected correctness contract")
        with self.db.connection:
            self.db.connection.execute(
                "UPDATE epochs SET baseline_id=? WHERE id=?",
                (f"baseline-e{epoch['id']}", epoch["id"]),
            )
        return asdict(result)

    def plan(self) -> list[list[str]]:
        roles, schedule = self.config["roles"], self.config["schedule"]
        if self.config["method"] == "U":
            return [["U"] for _ in range(self.config["budget"]["search_slots"] - 1)]
        batches = []
        if self.config["method"] == "H-enumeration":
            for _ in range(schedule["cycles"] * schedule["trials_per_role_per_cycle"]):
                batches.append(roles[:])
            batches += [["G"] for _ in range(2 ** len(roles))]
        else:
            for _ in range(schedule["cycles"]):
                batches += [roles[:] for _ in range(schedule["trials_per_role_per_cycle"])]
                batches += [["G"] for _ in range(schedule["integrations_per_cycle"])]
        return batches

    def _sources(self, mission: Mission) -> list[dict]:
        if mission.role != "G":
            return []
        if self.config["method"] == "H-enumeration":
            key = f"enumeration-archive:{mission.epoch}"
            choices = self.db.get(key)
            if choices is None:
                choices = [
                    self._alternatives(mission.epoch, role)[:2] for role in self.config["roles"]
                ]
                self.db.set(key, choices)
            if any(len(c) < 2 for c in choices):
                return []
            combinations = list(itertools.product(*choices))
            return list(combinations[(mission.ordinal - 1) % len(combinations)])
        sources = []
        for index, role in enumerate(self.config["roles"]):
            alternatives = self._alternatives(mission.epoch, role)[:3]
            if not alternatives:
                return []
            position = ((mission.ordinal - 1) // (2**index)) % len(alternatives)
            sources.append(alternatives[position])
        return sources

    def _alternatives(self, epoch: int, role: str) -> list[dict]:
        result, seen = [], set()
        for candidate in self.db.archive(epoch, role):
            if candidate["tree_hash"] not in seen:
                result.append(candidate)
                seen.add(candidate["tree_hash"])
        return result

    def _context(self, mission: Mission, sources: list[dict]) -> dict:
        annotations = []
        for source in sources:
            annotations.append(
                {k: source[k] for k in ["id", "role", "commit", "transformations", "mean_seconds"]}
            )
            annotations[-1]["diff"] = git(
                self.root / "repo",
                "diff",
                self.epoch()["base_commit"],
                source["commit"],
                "--",
                "src",
            )[:6000]
        feedback = []
        if (self.config["method"] != "H-no-feedback"
                and not (self.search.binary and mission.role != "G")):
            for row in self.db.rows("SELECT * FROM interactions ORDER BY rowid DESC LIMIT 5"):
                feedback.append(
                    {"sources": json.loads(row["sources"]), "outcome": json.loads(row["payload"])}
                )
        return {
            "sources": annotations,
            "interactions": feedback,
            "automatic_observations": (
                measured_observations(self.db, self.root, mission)
                if self.config["method"] != "H-no-feedback" else {}
            ),
            "documents_as_data": Knowledge(self.db).query(f"{mission.role} locality SIMD OpenMP"),
            "deadline": self.db.get("deadline"),
            "generation_deadline": search_deadline(
                self.db.get("deadline"), self.config["budget"]["confirmation_seconds"]
            ),
            "protocol_id": self.db.get("protocol_id"),
            "remaining_tokens": self.config["budget"]["tokens"] - self.db.costs()["tokens_used"],
        }

    def _new_mission(self, role: str, epoch: dict) -> tuple[Mission, dict, str]:
        tree_role = "U" if self.config["method"] == "U" else role
        tree_id = f"e{epoch['id']}:{tree_role}"
        self.search.check_admission(tree_id, self.config["budget"]["max_depth"])
        tokens = (
            0 if self.config["backend"] == "recipe" else self.config["budget"]["mission_tokens"]
        )
        slot = self.db.reserve("search", f"role:{role}", tokens)
        count = self.db.one(
            "SELECT count(*) AS n FROM trials WHERE epoch=? AND role=?", (epoch["id"], role)
        )["n"]
        actions = [*self.config["roles"], "G"] if tree_role == "U" else [role]
        if role == "G" and self.config["method"] == "H-enumeration":
            mission = self.search.ask_enumeration(
                tree_id, epoch["id"], epoch["base_commit"], count + 1, "", slot
            )
        else:
            mission = self.search.ask(
                tree_id, actions, epoch["id"], epoch["base_commit"], count + 1, "", slot
            )
        if tree_role == "U":
            # U chooses its action through TreeQuest, not through the outer scheduler.
            count = self.db.one(
                "SELECT count(*) AS n FROM trials WHERE epoch=? AND role=? AND id<>?",
                (epoch["id"], mission.role, mission.id),
            )["n"]
            mission.ordinal = count + 1
        mission.worktree = str(self.root / "worktrees" / mission.id)
        sources = self._sources(mission)
        mission.sources = [c["id"] for c in sources]
        mission.source_commits = [c["commit"] for c in sources]
        self.search.update_mission(mission)
        if mission.depth > self.config["budget"]["max_depth"]:
            self.search.finish(
                mission,
                Outcome("depth_limited", reason="Selected search path exceeds configured depth"),
            )
            self.db.settle_tokens(slot, 0)
            return mission, {}, slot
        branch = "integration" if mission.role == "G" else "exp"
        branch += f"/{self.config['problem']}/{mission.role}/{mission.id}"
        make_worktree(self.root / "repo", Path(mission.worktree), branch, mission.base_commit)
        return mission, self._context(mission, sources), slot

    def _evaluate_mission(self, mission: Mission, baseline: dict) -> Outcome:
        commit, tree_hash = commit_candidate(
            Path(mission.worktree), mission.id, mission.base_commit
        )
        key = digest(
            {"tree": tree_hash, "protocol": self.db.get("protocol_id"), "epoch": mission.epoch}
        )
        cached = self.db.cached(key)
        if cached:
            self.db.event(
                "duplicate_candidate",
                {"experiment_id": mission.id, "same_as": cached["experiment_id"]},
            )
            return Outcome(
                "duplicate",
                commit=commit,
                tree_hash=tree_hash,
                reason=f"Same code/protocol/epoch as {cached['experiment_id']}; no new reward",
            )
        retries = int(self.config["budget"]["infrastructure_retries"])
        for attempt in range(retries + 1):
            try:
                return self.evaluator.evaluate(
                    mission.id,
                    mission.epoch,
                    Path(mission.worktree),
                    commit,
                    baseline["mean_seconds"],
                )
            except InfrastructureError as exc:
                self.db.event(
                    "infrastructure_error",
                    {"experiment_id": mission.id, "attempt": attempt, "reason": str(exc)},
                )
                if attempt == retries:
                    return Outcome("infrastructure_error", commit=commit, reason=str(exc))
        raise AssertionError("unreachable")

    def run(self, max_batches: int | None = None) -> dict:
        if self.config.get("harness", {}).get("enabled"):
            from .node_harness import wrap_backend

            self.backend = wrap_backend(self.backend, self.config)
        with FileLock(self.root / "campaign.lock"):
            self._start()
            # Generation and search evaluation must not consume the final confirmation reserve.
            # confirm() calls _start() independently and receives the full campaign deadline.
            self.evaluator.deadline = search_deadline(
                self.evaluator.deadline, self.config["budget"]["confirmation_seconds"]
            )
            self.search.recover_pending()
            if self.db.costs()["unknown_usage_calls"]:
                raise BudgetExhausted("Unknown previous LLM usage; start a new budgeted campaign")
            if self.db.costs()["tokens_used"] >= self.config["budget"]["tokens"]:
                raise BudgetExhausted("Campaign token budget reached")
            epoch = self.epoch()
            self._initialize_trees(epoch["id"])
            baseline = self._baseline(epoch)
            self.db.set("status", "running")
            plan = self.plan()
            cursor_key = f"plan_cursor:{epoch['id']}"
            cursor, completed = self.db.get(cursor_key, 0), 0
            try:
                while cursor < len(plan) and (max_batches is None or completed < max_batches):
                    batch = []
                    admission_stopped = False
                    for role in plan[cursor]:
                        try:
                            mission, context, slot = self._new_mission(role, epoch)
                            if context:
                                batch.append((mission, context, slot))
                        except SearchExhausted as exc:
                            self.db.event("tree_exhausted", {"role": role, "reason": str(exc)})
                        except BudgetExhausted:
                            admission_stopped = True
                            break
                    # Generation may overlap; outer and development evaluations are target-locked.
                    with ThreadPoolExecutor(
                        max_workers=int(self.config["budget"]["max_workers"])
                    ) as pool:
                        futures = [
                            pool.submit(self.backend.generate, m, ctx, self.config, self.root)
                            for m, ctx, _ in batch
                        ]
                        generations = []
                        for future in futures:
                            try:
                                generations.append(future.result())
                            except Exception as exc:
                                generations.append(exc)
                        fatal = None
                        for (mission, _, slot), generated in zip(batch, generations, strict=True):
                            settled = False
                            bounded_generation_abort = False
                            try:
                                if isinstance(generated, Exception):
                                    raise InfrastructureError(str(generated)) from generated
                                self.db.settle_tokens(slot, generated.tokens, upper_bound=generated.tokens_upper_bound)
                                settled = True
                                bounded_generation_abort = generated.infrastructure_error and generated.tokens_upper_bound
                                self.db.event(
                                    "generation_usage",
                                    {"experiment_id": mission.id, **generated.usage},
                                )
                                self.search.update_mission(mission)
                                if generated.usage.get("contract_rejected"):
                                    outcome = Outcome("contract_violation", correct=False,
                                                      score=0.0, reason=generated.error)
                                elif generated.error:
                                    outcome = Outcome(
                                        "infrastructure_error" if generated.infrastructure_error else "generation_failed",
                                        reason=generated.error,
                                    )
                                else:
                                    outcome = self._evaluate_mission(mission, baseline)
                                if generated.tokens is None:
                                    fatal = "usage_unavailable"
                                if self.db.costs()["tokens_used"] > self.config["budget"]["tokens"]:
                                    fatal = "token_budget_exceeded"
                            except CandidateRejected as exc:
                                outcome = Outcome(
                                    "contract_violation", correct=False, score=0.0, reason=str(exc)
                                )
                            except BudgetExhausted as exc:
                                outcome = Outcome("cancelled_budget", reason=str(exc))
                                fatal = "budget_exhausted"
                            except (ForestError, OSError, ValueError) as exc:
                                if not settled:
                                    self.db.settle_tokens(
                                        slot, 0 if self.config["backend"] == "recipe" else None
                                    )
                                outcome = Outcome("infrastructure_error", reason=str(exc))
                            self.search.finish(mission, outcome)
                            if outcome.status == "infrastructure_error" and not bounded_generation_abort:
                                fatal = "infrastructure_error"
                            print(f"{mission.role} {mission.id}: {outcome.status}", flush=True)
                    cursor += 1
                    completed += 1
                    self.db.set(cursor_key, cursor)
                    if fatal:
                        self.db.set("status", fatal)
                        break
                    if admission_stopped:
                        raise BudgetExhausted("No remaining search admission")
                else:
                    self.db.set(
                        "status", "search_complete" if cursor == len(plan) else "checkpointed"
                    )
            except BudgetExhausted as exc:
                self.db.set("status", "budget_exhausted")
                self.db.event("budget_stop", {"reason": str(exc)})
            return self.status()

    def confirm(self) -> dict:
        with FileLock(self.root / "campaign.lock"):
            self._start()
            epoch = self.epoch()
            baseline_id = f"baseline-e{epoch['id']}"
            if not epoch["baseline_id"]:
                raise ForestError("Run and validate the baseline before confirmation")
            key = f"confirmation_plan:{epoch['id']}"
            candidates = self.db.get(key)
            if candidates is None:
                candidates = [{"id": baseline_id, "commit": epoch["base_commit"], "baseline": True}]
                seen = {epoch["base_commit"]}
                for candidate in self.db.archive(epoch["id"]):
                    if (
                        candidate["commit"] not in seen
                        and len(candidates) < self.config["budget"]["confirmation_slots"]
                    ):
                        candidates.append(
                            {
                                "id": candidate["id"],
                                "commit": candidate["commit"],
                                "baseline": False,
                            }
                        )
                        seen.add(candidate["commit"])
                for candidate in candidates:
                    candidate["slot_id"] = self.db.reserve("confirmation", candidate["id"])
                    path = self.root / "worktrees" / f"confirm-e{epoch['id']}-{candidate['id']}"
                    candidate["worktree"] = str(path)
                    make_worktree(
                        self.root / "repo",
                        path,
                        f"confirm/e{epoch['id']}/{candidate['id']}",
                        candidate["commit"],
                    )
                self.db.set(key, candidates)
            existing = self.db.evaluations("confirmation", epoch["id"])
            if len(existing) < len(candidates):
                attempts_key = f"confirmation_attempts:{epoch['id']}"
                attempts = self.db.get(attempts_key, 0)
                if attempts > self.config["budget"]["infrastructure_retries"]:
                    raise InfrastructureError("Independent confirmation retry limit reached")
                self.db.set(attempts_key, attempts + 1)
                outcomes = self.evaluator.confirm(candidates, epoch["id"])
                for candidate in candidates:
                    self.db.record_evaluation(
                        candidate["id"],
                        epoch["id"],
                        "confirmation",
                        asdict(outcomes[candidate["id"]]),
                    )
                    self.db.settle_tokens(candidate["slot_id"], 0)
            valid = [
                r
                for r in self.db.evaluations("confirmation", epoch["id"])
                if r["outcome"]["correct"] is True
            ]
            reference = next((r for r in valid if r["experiment_id"] == baseline_id), None)
            if reference is None:
                self.db.set("status", "confirmation_failed")
                raise ForestError("Reference confirmation failed; no candidate can be promoted")
            winner = min(valid, key=lambda r: r["outcome"]["mean_seconds"])
            t0 = reference["outcome"]["mean_seconds"]
            improvement = 1 - winner["outcome"]["mean_seconds"] / t0
            if improvement < self.config["minimum_gain"]:
                winner, improvement = reference, 0.0
            best = {
                "experiment_id": winner["experiment_id"],
                "commit": winner["outcome"]["commit"],
                "epoch": epoch["id"],
                "mean_seconds": winner["outcome"]["mean_seconds"],
                "reference_seconds": t0,
                "improvement_fraction": improvement,
                "protocol_id": self.db.get("protocol_id"),
                "evaluation_digest": digest(winner["outcome"]),
                "is_baseline": winner["experiment_id"] == baseline_id,
            }
            self.db.set("best_confirmed", best)
            self.db.set("status", "confirmed")
            git(
                self.root / "repo",
                "branch",
                "-f",
                f"submit/{self.config['problem']}",
                best["commit"],
            )
            return best

    def new_epoch(self) -> dict:
        with FileLock(self.root / "campaign.lock"):
            best = self.db.get("best_confirmed")
            old = self.epoch()
            if not best or best["epoch"] != old["id"] or best["is_baseline"]:
                raise ForestError("A current independently confirmed improvement is required")
            with self.db.connection:
                self.db.connection.execute(
                    "UPDATE epochs SET closed=? WHERE id=?", (time.time(), old["id"])
                )
                self.db.connection.execute(
                    "INSERT INTO epochs(id,base_commit,protocol_id,created) VALUES(?,?,?,?)",
                    (old["id"] + 1, best["commit"], self.db.get("protocol_id"), time.time()),
                )
            self.db.set("current_epoch", old["id"] + 1)
            self._initialize_trees(old["id"] + 1)
            self.db.event(
                "epoch_advanced", {"old": old["id"], "new": old["id"] + 1, "base": best["commit"]}
            )
            return self.epoch()

    def status(self) -> dict:
        return {
            "status": self.db.get("status"),
            "epoch": self.db.get("current_epoch"),
            "costs": self.db.costs(),
            "deadline": self.db.get("deadline"),
            "best_confirmed": self.db.get("best_confirmed"),
        }
