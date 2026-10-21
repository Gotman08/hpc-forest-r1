from __future__ import annotations

import itertools
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from importlib.resources import files
from pathlib import Path

from .adaptive_budget import admission_deadline, admit, forecast, record_timing
from .backends import CodexBackend, RecipeBackend
from .binary_search import SearchExhausted, enabled
from .completion import finalize
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
from .forest import (
    assignment,
    forest_plan,
    model_selected,
    pairwise_mother,
    persistent_mother,
    research_roles,
)
from .gitops import commit_candidate, git, initialize_source, make_worktree
from .harness_research import DocumentationReader
from .knowledge import Knowledge
from .observations import measured_observations
from .ollama_backend import OllamaBackend, resolve_model
from .registry import Registry
from .search import Search
from .support.budgets import (
    FINISH_STARTED,
    OBSERVE_TOKENS,
    adaptive,
    expired,
    finish_started,
    mandatory_final_g,
    mission_token_reservation,
    postprocess_token_limit,
    search_deadline,
    time_driven,
    unlimited_tokens,
)
from .support.sources import committed_source_snapshot
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
        if not model_selected(config):
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
        if model_selected(self.config):
            from .codex_mailbox import CodexMailboxBackend

            self.backend = CodexMailboxBackend()
            self.mother_enabled = True
            self.statement = self.config["forest"].get("statement", "Improve the supplied program for "
                + self.config["problem"] + " while preserving its full input/output and correctness contract.")

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
            None if finish_started(self.config) else self.db.get("deadline"),
        )

    def epoch(self) -> dict:
        return self.db.one("SELECT * FROM epochs WHERE id=?", (self.db.get("current_epoch"),))

    def _initialize_trees(self, epoch: int) -> None:
        roles = ["U"] if self.config["method"] == "U" else [*research_roles(self.db, epoch), "G"]
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
        started = time.time()
        result = self.evaluator.evaluate(
            f"baseline-e{epoch['id']}", epoch["id"], path, epoch["base_commit"], None
        )
        record_timing(self.db, "baseline", time.time() - started)
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
        roles = research_roles(self.db) if model_selected(self.config) else self.config["roles"]
        if persistent_mother(self.config):
            # Keep the original N AB-MCTS processes searching until the adaptive reserve.
            # Once Mother resumes for assembly there is no edge back to these trees.
            return [roles[:]]
        schedule = self.config["schedule"]
        if self.config["method"] == "U":
            if time_driven(self.config):
                return [["U"]]
            slots = self.config["budget"]["search_slots"]
            count = slots - 1 if slots is not None else schedule["cycles"] * schedule["trials_per_role_per_cycle"]
            return [["U"] for _ in range(count)]
        batches = []
        if self.config["method"] == "H-enumeration":
            for _ in range(schedule["cycles"] * schedule["trials_per_role_per_cycle"]):
                batches.append(roles[:])
            batches += [["G"] for _ in range(2 ** len(roles))]
        else:
            for _ in range(schedule["cycles"] or 1):
                batches += [roles[:] for _ in range(schedule["trials_per_role_per_cycle"])]
                batches += [["G"] for _ in range(schedule["integrations_per_cycle"])]
        if finish_started(self.config) and not model_selected(self.config):
            workers = self.config["budget"]["max_workers"]
            return [batch[index:index + workers] for batch in batches
                    for index in range(0, len(batch), workers)]
        return batches

    def _sources(self, mission: Mission) -> list[dict]:
        if mission.role != "G":
            return []
        if model_selected(self.config):
            result, seen = [], set()
            for candidate in self.db.archive(mission.epoch):
                if candidate["tree_hash"] not in seen:
                    result.append(candidate)
                    seen.add(candidate["tree_hash"])
            return result
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
        pairwise = pairwise_mother(self.config) and mission.budget_phase == "postprocess"
        detailed = None
        if not pairwise and adaptive(self.config) and len(sources) > 24:
            # Keep every source identity/measurement. Repeatable long campaigns
            # cannot inline an ever-growing number of full code diffs. Show the
            # two best and two newest distinct programs per role in detail.
            detailed = set()
            for role in {source["role"] for source in sources}:
                own = [source for source in sources if source["role"] == role]
                newest = sorted(own, key=lambda source: source.get("ordinal", 0), reverse=True)[:2]
                detailed.update(source["id"] for source in own[:2] + newest)
        for source in sources:
            annotations.append(
                {k: source[k] for k in ["id", "role", "commit", "transformations", "mean_seconds"]}
            )
            if pairwise:
                annotations[-1].update(
                    files=committed_source_snapshot(self.root / "repo", source["commit"]),
                    measured_outcome={k: source.get(k) for k in ("status", "correct", "times", "mean_seconds")},
                )
                continue
            if detailed is not None and source["id"] not in detailed:
                annotations[-1]["diff_omitted"] = "Full program remains in the campaign archive; identity and measurements retained"
                continue
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
        child = assignment(self.db, mission.role, mission.epoch) if model_selected(self.config) else None
        context = {
            "sources": annotations,
            "interactions": feedback,
            "automatic_observations": (
                measured_observations(self.db, self.root, mission)
                if self.config["method"] != "H-no-feedback" else {}
            ),
            "documents_as_data": Knowledge(self.db).query(child["objective"] if child else
                f"{mission.role} locality SIMD OpenMP"),
            "deadline": None if finish_started(self.config) else self.db.get("deadline"),
            "generation_deadline": None if finish_started(self.config) else search_deadline(
                self.db.get("deadline"), self.config["budget"]["confirmation_seconds"]),
            "deadline_policy": FINISH_STARTED if finish_started(self.config) else "hard",
            "budget_phase": mission.budget_phase,
            "search_admission_deadline": None if pairwise else admission_deadline(self.db),
            "protocol_id": self.db.get("protocol_id"),
            "token_policy": OBSERVE_TOKENS if unlimited_tokens(self.config) else "limited",
            "remaining_tokens": (
                None if unlimited_tokens(self.config) or (
                    mission.budget_phase == "postprocess" and postprocess_token_limit(self.config) is None) else
                postprocess_token_limit(self.config) - self.db.costs(
                    "postprocess", purpose_prefix=f"postprocess:e{mission.epoch}:")["tokens_used"]
                if mission.budget_phase == "postprocess" else
                self.config["budget"]["tokens"] - self.db.costs("search")["tokens_used"]),
        }
        if model_selected(self.config):
            from .mother import mother_context

            return mother_context(self, mission, context)
        return context

    def _new_mission(self, role: str, epoch: dict, reserved_slot=None) -> tuple[Mission, dict, str]:
        if persistent_mother(self.config):
            if self.db.get(f"mother_assembly_started:{epoch['id']}") is not None:
                raise BudgetExhausted("Mother is assembling; research trees cannot be restarted")
            if role == "G":
                raise InfrastructureError("Persistent Mother produces G after research, without a separate G model")
        tree_role = "U" if self.config["method"] == "U" else role
        tree_id = f"e{epoch['id']}:{tree_role}"
        self.search.check_admission(tree_id, self.config["budget"]["max_depth"])
        tokens = mission_token_reservation(self.config)
        slot = reserved_slot or self.db.reserve("search", f"role:{role}", tokens)
        count = self.db.one(
            "SELECT count(*) AS n FROM trials WHERE epoch=? AND role=?", (epoch["id"], role)
        )["n"]
        actions = [*research_roles(self.db), "G"] if tree_role == "U" else [role]
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
        max_depth = self.config["budget"]["max_depth"]
        if max_depth > 0 and mission.depth > max_depth:
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

    def _complete_generation(self, mission, slot, generated, baseline) -> str | None:
        """Settle one admitted node once, for search or final integration."""
        settled = False
        bounded_generation_abort = False
        fatal = None
        try:
            if isinstance(generated, Exception):
                raise InfrastructureError(str(generated)) from generated
            self.db.settle_tokens(slot, generated.tokens, upper_bound=generated.tokens_upper_bound,
                                  observed_tokens=generated.usage.get("observed_tokens", 0))
            settled = True
            bounded_generation_abort = generated.infrastructure_error and generated.tokens_upper_bound
            self.db.event("generation_usage", {"experiment_id": mission.id,
                "budget_phase": mission.budget_phase, **generated.usage})
            self.search.update_mission(mission)
            if generated.usage.get("contract_rejected"):
                outcome = Outcome("contract_violation", correct=False, score=0.0, reason=generated.error)
            elif (generated.usage.get("generation_not_started") == "search_deadline" or (
                generated.usage.get("llm_calls") == 0 and generated.error in {
                    "Request expired before generation",
                    "Search generation deadline reached before invocation",
                    "No development time remains"})):
                outcome = Outcome("cancelled_budget", reason=generated.error)
                fatal = "budget_exhausted"
            elif generated.error:
                outcome = Outcome("infrastructure_error" if generated.infrastructure_error
                                  else "generation_failed", reason=generated.error)
            else:
                outcome = self._evaluate_mission(mission, baseline)
                if outcome.status == "cancelled_budget":
                    fatal = "budget_exhausted"
            if generated.tokens is None and not unlimited_tokens(self.config):
                fatal = "usage_unavailable"
            if (not unlimited_tokens(self.config) and mission.budget_phase == "search"
                    and self.db.costs("search")["tokens_used"] > self.config["budget"]["tokens"]):
                fatal = "token_budget_exceeded"
            if (not unlimited_tokens(self.config) and mission.budget_phase == "postprocess" and (
                postprocess_token_limit(self.config) is not None and
                self.db.costs("postprocess", purpose_prefix=f"postprocess:e{mission.epoch}:")["tokens_used"]
                    > postprocess_token_limit(self.config)
                or self.db.costs("postprocess")["unknown_usage_calls"]
            )):
                fatal = "postprocess_usage_unavailable_or_exceeded"
        except CandidateRejected as exc:
            outcome = Outcome("contract_violation", correct=False, score=0.0, reason=str(exc))
        except BudgetExhausted as exc:
            outcome = Outcome("cancelled_budget", reason=str(exc))
            fatal = "budget_exhausted"
        except (ForestError, OSError, ValueError) as exc:
            if not settled:
                self.db.settle_tokens(slot, 0 if self.config["backend"] == "recipe" else None)
            outcome = Outcome("infrastructure_error", reason=str(exc))
        self.search.finish(mission, outcome)
        row = self.db.one("SELECT created FROM trials WHERE id=?", (mission.id,))
        record_timing(self.db, "mission:" + mission.role, time.time() - row["created"])
        if outcome.status == "infrastructure_error" and not bounded_generation_abort:
            fatal = "infrastructure_error"
        print(f"{mission.role} {mission.id}: {outcome.status}", flush=True)
        return fatal

    def run(self, max_batches: int | None = None) -> dict:
        if self.config.get("harness", {}).get("enabled"):
            from .node_harness import wrap_backend

            self.backend = wrap_backend(self.backend, self.config)
        with FileLock(self.root / "campaign.lock"):
            self._start()
            # Generation and search evaluation must not consume the final confirmation reserve.
            # confirm() calls _start() independently and receives the full campaign deadline.
            soft = finish_started(self.config)
            if not soft:
                self.evaluator.deadline = search_deadline(
                    self.evaluator.deadline, self.config["budget"]["confirmation_seconds"])
            self.search.recover_pending()
            if not unlimited_tokens(self.config) and not soft and self.db.costs()["unknown_usage_calls"]:
                raise BudgetExhausted("Unknown previous LLM usage; start a new budgeted campaign")
            if (not unlimited_tokens(self.config) and not soft
                    and self.db.costs()["tokens_used"] >= self.config["budget"]["tokens"]):
                raise BudgetExhausted("Campaign token budget reached")
            epoch = self.epoch()
            self.db.set("mother_enabled", bool(getattr(self, "mother_enabled", False)))
            baseline = self._baseline(epoch)
            if soft and self.db.get(f"search_closed:{epoch['id']}") is not None:
                finalize(self, epoch, baseline)
                return self.status()
            if model_selected(self.config):
                from .mother import prepare_forest, publish_forest

                try:
                    selected = prepare_forest(self, epoch, baseline)
                    publish_forest(self, selected)
                except BudgetExhausted:
                    self.db.set("status", "budget_exhausted")
                    finalize(self, epoch, baseline)
                    return self.status()
            self._initialize_trees(epoch["id"])
            self.db.set("status", "running")
            plan = self.plan()
            cursor_key = f"plan_cursor:{epoch['id']}"
            cursor, completed = self.db.get(cursor_key, 0), 0
            repeating = time_driven(self.config)
            empty_key = f"empty_batches:{epoch['id']}"
            try:
                while (repeating or cursor < len(plan)) and (max_batches is None or completed < max_batches):
                    batch = []
                    admitted = 0
                    admission_stopped = False
                    roles = plan[cursor % len(plan)]
                    wave_started = time.monotonic()
                    wave_slots = {}
                    if model_selected(self.config) and roles != ["G"]:
                        wave_slots = self.db.reserve_research_wave(roles, cursor)
                    try:
                        for role in roles:
                            try:
                                if adaptive(self.config) and not wave_slots:
                                    admit(self.db, [m.role for m, _, _ in batch] + [role])
                                mission, context, slot = (self._new_mission(role, epoch, wave_slots[role])
                                    if wave_slots else self._new_mission(role, epoch))
                                admitted += 1
                                if context:
                                    batch.append((mission, context, slot))
                            except SearchExhausted as exc:
                                self.db.event("tree_exhausted", {"role": role, "reason": str(exc)})
                            except BudgetExhausted:
                                admission_stopped = True
                                break
                    except (ForestError, OSError, ValueError):
                        if wave_slots:
                            # No generation is submitted until every N-tree context is ready.
                            self.search.recover_pending()
                            for slot in wave_slots.values():
                                self.db.settle_tokens(slot, 0)
                        raise
                    # Generation may overlap; outer and development evaluations are target-locked.
                    with ThreadPoolExecutor(
                        max_workers=max(1, len(batch)) if model_selected(self.config)
                            else int(self.config["budget"]["max_workers"])
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
                            fatal = self._complete_generation(mission, slot, generated, baseline) or fatal
                    if model_selected(self.config) and roles != ["G"] and len(batch) == len(roles):
                        record_timing(self.db, f"research_wave:{len(roles)}", time.monotonic() - wave_started)
                    cursor += 1
                    completed += 1
                    self.db.set(cursor_key, cursor)
                    empty = 0 if admitted else self.db.get(empty_key, 0) + 1
                    self.db.set(empty_key, empty)
                    if fatal:
                        self.db.set("status", fatal)
                        break
                    if admission_stopped:
                        raise BudgetExhausted("No remaining search admission")
                    if repeating and empty >= len(plan):
                        self.db.set("status", "search_complete")
                        self.db.event("search_exhausted", {"epoch": epoch["id"], "batches": cursor})
                        break
                else:
                    stop_now = soft and expired(admission_deadline(self.db))
                    self.db.set(
                        "status", "search_complete" if not repeating and cursor == len(plan) else
                        "budget_exhausted" if stop_now else "checkpointed"
                    )
            except BudgetExhausted as exc:
                self.db.set("status", "budget_exhausted")
                self.db.event("budget_stop", {"reason": str(exc)})
            if soft and self.db.get("status") != "checkpointed":
                finalize(self, epoch, baseline)
            return self.status()

    def confirm(self) -> dict:
        with FileLock(self.root / "campaign.lock"):
            self._start()
            epoch = self.epoch()
            baseline_id = f"baseline-e{epoch['id']}"
            if not epoch["baseline_id"]:
                raise ForestError("Run and validate the baseline before confirmation")
            if finish_started(self.config):
                finalize(self, epoch, self._baseline(epoch))
                deadline_key = f"confirmation_deadline:{epoch['id']}"
                if mandatory_final_g(self.config):
                    # Like an admitted model, the independent measurements finish.
                    self.db.set(f"confirmation_started:{epoch['id']}", self.db.get(
                        f"confirmation_started:{epoch['id']}", time.time()))
                    self.db.set(deadline_key, None)
                elif self.db.get(deadline_key) is None:
                    self.db.set(deadline_key, time.time() + self.config["budget"]["confirmation_seconds"])
                self.evaluator.deadline = self.db.get(deadline_key)
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
                if mandatory_final_g(self.config):
                    postprocess = self.db.get(f"postprocess:{epoch['id']}", {})
                    final_id = postprocess.get("mission_id")
                    final_commit = postprocess.get("outcome", {}).get("commit")
                    if final_id and final_commit:
                        if not any(candidate["id"] == final_id for candidate in candidates):
                            candidates.append({"id": final_id, "commit": final_commit,
                                               "baseline": False, "mandatory_final_g": True})
                        self.db.set(f"confirmation_extra_slot:{epoch['id']}",
                                    len(candidates) > self.config["budget"]["confirmation_slots"])
                    else:
                        self.db.set(f"final_g_confirmation:{epoch['id']}", {
                            "status": "unavailable", "experiment_id": final_id,
                            "reason": "Final G produced no committed program to confirm"})
                self.db.set(key, candidates)
            for candidate in candidates:
                purpose = (f"confirmation:e{epoch['id']}:" if mandatory_final_g(self.config) else "") + candidate["id"]
                if "slot_id" not in candidate:
                    # A crash between reservation and saving the plan must not
                    # consume another slot or replay any model call.
                    reserved = self.db.one("SELECT id FROM slots WHERE phase='confirmation' AND purpose=?",
                                           (purpose,))
                    candidate["slot_id"] = reserved["id"] if reserved else self.db.reserve("confirmation", purpose)
                path = self.root / "worktrees" / f"confirm-e{epoch['id']}-{candidate['id']}"
                candidate["worktree"] = str(path)
                self.db.set(key, candidates)
                if not path.exists():
                    make_worktree(
                        self.root / "repo",
                        path,
                        f"confirm/e{epoch['id']}/{candidate['id']}",
                        candidate["commit"],
                    )
                elif git(path, "rev-parse", "HEAD") != candidate["commit"]:
                    raise InfrastructureError("Confirmation worktree differs from the persisted candidate")
            existing = self.db.evaluations("confirmation", epoch["id"])
            if len(existing) < len(candidates):
                attempts_key = f"confirmation_attempts:{epoch['id']}"
                attempts = self.db.get(attempts_key, 0)
                if attempts > self.config["budget"]["infrastructure_retries"]:
                    raise InfrastructureError("Independent confirmation retry limit reached")
                self.db.set(attempts_key, attempts + 1)
                started = time.time()
                outcomes = self.evaluator.confirm(candidates, epoch["id"])
                record_timing(self.db, "confirmation", time.time() - started)
                for candidate in candidates:
                    self.db.record_evaluation(
                        candidate["id"],
                        epoch["id"],
                        "confirmation",
                        asdict(outcomes[candidate["id"]]),
                    )
                    self.db.settle_tokens(candidate["slot_id"], 0)
            if mandatory_final_g(self.config):
                final_id = self.db.get(f"postprocess:{epoch['id']}", {}).get("mission_id")
                final = next((r for r in self.db.evaluations("confirmation", epoch["id"])
                              if r["experiment_id"] == final_id), None)
                if final:
                    post = self.db.get(f"postprocess:{epoch['id']}", {})
                    eligible = post.get("outcome", {}).get("correct") is not False
                    self.db.set(f"final_g_confirmation:{epoch['id']}", {
                        "status": "confirmed" if eligible and final["outcome"]["correct"] is True else "rejected",
                        "experiment_id": final_id, "outcome": final["outcome"],
                        "eligible_for_promotion": eligible and final["outcome"]["correct"] is True,
                    })
                elif any(c["id"] == final_id for c in candidates):
                    raise ForestError("Mandatory final G confirmation is missing")
            valid = [
                r
                for r in self.db.evaluations("confirmation", epoch["id"])
                if r["outcome"]["correct"] is True
            ]
            if mandatory_final_g(self.config):
                post = self.db.get(f"postprocess:{epoch['id']}", {})
                if post.get("outcome", {}).get("correct") is False:
                    valid = [r for r in valid if r["experiment_id"] != post.get("mission_id")]
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
            finished_key = f"confirmation_finished:{epoch['id']}"
            if self.db.get(finished_key) is None:
                self.db.set(finished_key, time.time())
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
            "deadline_policy": FINISH_STARTED if finish_started(self.config) else "hard",
            "search_admission_deadline": admission_deadline(self.db),
            "adaptive_budget": forecast(self.db) if adaptive(self.config) else None,
            "last_admission": self.db.get(f"adaptive_budget:{self.db.get('current_epoch')}"),
            "completed_batches": self.db.get(f"plan_cursor:{self.db.get('current_epoch')}", 0),
            "final_g_confirmation": self.db.get(f"final_g_confirmation:{self.db.get('current_epoch')}"),
            "confirmation_deadline": self.db.get(f"confirmation_deadline:{self.db.get('current_epoch')}"),
            "best_confirmed": self.db.get("best_confirmed"),
            "search_costs": self.db.costs("search"),
            "postprocess_costs": self.db.costs("postprocess"),
            "postprocess": self.db.get(f"postprocess:{self.db.get('current_epoch')}")
                if finish_started(self.config) else None,
            "forest_plan": forest_plan(self.db),
            "research_roles": research_roles(self.db),
            "mother_conversation": self.db.get(f"mother_conversation:{self.db.get('current_epoch')}"),
            "mother_assembly_started": self.db.get(f"mother_assembly_started:{self.db.get('current_epoch')}"),
        }
