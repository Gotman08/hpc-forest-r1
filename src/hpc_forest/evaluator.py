from __future__ import annotations

import hashlib
import importlib.metadata
import io
import json
import os
import platform
import random
import secrets
import socket
import statistics
import sys
import tarfile
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from .contracts import compare_bytes
from .core import (
    BudgetExhausted,
    FileLock,
    InfrastructureError,
    Outcome,
    digest,
    expand_command,
    file_digest,
    run_process,
    verify_protected,
)
from .execution_validation import (
    allocation_evidence,
    build_probe,
    environment,
    probe_environment,
    read_probe,
    requirements,
)
from .gitops import ensure_clean, git, worktree_changed
from .storage.files import atomic_bytes
from .support.budgets import expired, time_left
from .support.protocol import v2

# Protocol 2 compares timed outputs as text with a tight numeric tolerance: another
# floating-point summation order stays valid, another result does not.
OUTPUT_COMPARISON = {"mode": "auto", "rel_tol": 1e-9, "abs_tol": 1e-12}
MAX_VERIFIED_OUTPUT = 16 * 1024 * 1024


def create_evaluator(root, config, manifest, protocol_id, deadline=None):
    """Use the same protected evaluator for search, harness checks and confirmation."""
    if config.get("app_protocol"):
        from .webapp.runner_support import ProjectEvaluator
        return ProjectEvaluator(root, config, manifest, protocol_id, deadline)
    return Evaluator(root, config, manifest, protocol_id, deadline)


def target_identity(config: dict) -> dict:
    validation = None
    if config.get("execution_validation"):
        # Observation time belongs to the audit receipt, not the frozen target.
        # Keep the allocation, affinity, topology and requirements in its identity.
        validation = {key: value for key, value in
                      allocation_evidence(config["execution_validation"]).items()
                      if key != "observed_at"}
    return {
        "target": config["target_id"],
        "hostname": socket.gethostname(),
        "system": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpus": os.cpu_count(),
        "python": sys.version,
        "python_executable": sys.executable,
        "compiler": config.get("compiler", {}),
        "dependencies": {
            name: importlib.metadata.version(name) for name in ["treequest", "numpy", "scipy"]
        },
        "controller_implementation": digest(
            {
                p.relative_to(Path(__file__).parent).as_posix(): file_digest(p)
                for p in sorted(Path(__file__).parent.rglob("*.py"))
            }
        ),
        "environment": config["protocol"]["environment"],
        **({"execution_validation": validation} if validation is not None else {}),
    }


def export_commit(worktree: Path, commit: str, destination: Path) -> Path:
    """Extract exactly the files of a commit, refusing links and paths outside it."""
    data = git(worktree, "archive", "--format=tar", commit, binary=True)
    destination.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            name = Path(member.name)
            if not (member.isfile() or member.isdir()) or name.is_absolute() or ".." in name.parts:
                raise InfrastructureError("Commit export contains an unsafe entry: " + member.name)
        archive.extractall(destination, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    return destination


def _probe_loaded(trace: Path) -> bool:
    try:
        with trace.open(encoding="utf-8") as stream:
            return json.loads(stream.readline()) == {"schema": "forest-gomp-probe-v1", "loaded": True}
    except (OSError, ValueError):
        return False


def _child_rusage() -> dict[str, float | int] | None:
    """Global child counters for diagnostics; never a candidate resource measurement."""
    try:
        import resource

        ru = resource.getrusage(resource.RUSAGE_CHILDREN)
        return {
            "utime": float(ru.ru_utime),
            "stime": float(ru.ru_stime),
            "minflt": int(ru.ru_minflt),
        }
    except (ImportError, OSError, AttributeError):
        return None


def _summarize_rusage(samples: list[dict[str, float | int]]) -> dict[str, float | int]:
    return {
        "user_seconds": round(statistics.mean(float(s["user_seconds"]) for s in samples), 6),
        "sys_seconds": round(statistics.mean(float(s["sys_seconds"]) for s in samples), 6),
        "cpu_utilization_ratio": round(
            statistics.mean(float(s["cpu_utilization_ratio"]) for s in samples), 4
        ),
        "minor_page_faults": round(
            statistics.mean(float(s["minor_page_faults"]) for s in samples), 1
        ),
    }


class Evaluator:
    def __init__(self, root: Path, config: dict, manifest: dict, protocol_id: str, deadline: float | None):
        self.root, self.config = root, config
        self.protocol = config["protocol"]
        self.manifest, self.protocol_id, self.deadline = manifest, protocol_id, deadline
        self.last_wall_times = {}
        # Protocol 2: confirmation seeds drawn per confirmation, unknown beforehand.
        self.confirmation_environment = None
        # Same target string across campaigns -> same exclusive OS lock.
        self.lock_path = (
            Path(tempfile.gettempdir())
            / "hpc-forest-locks"
            / (digest(config["target_id"]) + ".lock")
        )

    def _timeout(self, build=False) -> float:
        limit = self.protocol["build_timeout_seconds" if build else "timeout_seconds"]
        return time_left(self.deadline, limit)

    def _variables(self, worktree: Path, build: Path, phase: str) -> dict:
        return {
            "python": sys.executable,
            "trusted": str(self.root / "trusted"),
            "worktree": str(worktree),
            "build": str(build),
            "binary": str(build / ("solution.exe" if os.name == "nt" else "solution")),
            "phase": phase,
        }

    def _run(self, name, variables, log, build=False, stderr_log=None, env=None):
        limit = float(self.protocol["build_timeout_seconds" if build else "timeout_seconds"])
        remaining = time_left(self.deadline, limit)
        result = run_process(
            expand_command(self.protocol[name], **variables),
            self._cwd(variables, build),
            log,
            min(limit, remaining),
            self.protocol["environment"] | (env or {}),
            stderr_log=stderr_log,
        )
        result.budget_shortened = bool(result.timed_out and self.deadline is not None and remaining < limit)
        if self.last_wall_times:
            key = name + "_seconds"
            self.last_wall_times[key] = self.last_wall_times.get(key, 0.0) + result.seconds
        return result

    def _cwd(self, variables, build=False) -> Path:
        # Protocol 2 runs candidate programs outside the source tree: a relative
        # write cannot dirty the commit under evaluation.
        return Path(variables["build" if v2(self.config) and not build else "worktree"])

    @contextmanager
    def _target(self):
        """Queue exclusive target work without treating another tree as a failure."""
        queued = time.monotonic()
        lock = FileLock(self.lock_path)
        while True:
            try:
                lock.__enter__()
                break
            except InfrastructureError as exc:
                if not str(exc).startswith("Resource already locked:"):
                    raise
                if expired(self.deadline):
                    raise BudgetExhausted("Evaluation expired waiting for target") from exc
                time.sleep(max(0, time_left(self.deadline, 0.05)))
        started = time.monotonic()
        self.last_wall_times = {"lock_wait_seconds": started - queued}
        try:
            yield
        finally:
            self.last_wall_times["work_seconds"] = time.monotonic() - started
            lock.__exit__(None, None, None)

    def _build(self, experiment: str, epoch: int, worktree: Path, commit: str, phase: str):
        verify_protected(self.root / "trusted", self.manifest)
        ensure_clean(worktree, commit)
        tree_hash = git(worktree, "rev-parse", "HEAD^{tree}")
        cache_key = digest({"tree": tree_hash, "protocol": self.protocol_id, "epoch": epoch})
        outcome = Outcome("pending", commit=commit, tree_hash=tree_hash, cache_key=cache_key)
        history = self.root / "logs" / f"e{epoch}" / experiment / phase
        attempt = f"attempt-{len(list(history.glob('attempt-*'))) + 1:03d}"
        logs = history / attempt
        logs.mkdir(parents=True, exist_ok=False)
        build = self.root / "builds" / f"e{epoch}" / experiment / phase / attempt
        build.mkdir(parents=True, exist_ok=True)
        if v2(self.config):
            # Protocol 2 builds and runs an export of the exact commit: files that
            # .gitignore hides in the worktree never reach the evaluated binary.
            worktree = export_commit(worktree, commit, build / "source")
        variables = self._variables(worktree, build, phase)
        variables["_baseline_reference"] = experiment == f"baseline-e{epoch}"
        built = self._run("build", variables, logs / "build.log", build=True)
        outcome.logs.append(built.log)
        if built.returncode == 70:
            raise InfrastructureError("Compiler/toolchain unavailable; inspect build log")
        if getattr(built, "budget_shortened", False):
            outcome.status, outcome.correct, outcome.score = "cancelled_budget", None, None
            outcome.reason = "Campaign wall-clock budget exhausted before candidate build timeout"
            return outcome, variables, logs
        if built.returncode or built.timed_out:
            outcome.status, outcome.correct, outcome.score = "build_failed", False, 0.0
            outcome.reason = "Build failed or exceeded candidate timeout"
            return outcome, variables, logs
        if not Path(variables["binary"]).is_file():
            raise InfrastructureError("Successful build did not produce the contracted executable")
        outcome.binary_sha256 = file_digest(Path(variables["binary"]))
        return outcome, variables, logs

    def _check(self, outcome: Outcome, variables: dict, logs: Path, *, warmups: bool = True):
        if outcome.status in {"build_failed", "cancelled_budget"}:
            return outcome, variables, logs
        checked = self._run("check", variables, logs / "correctness.log",
                            env=self.confirmation_environment if variables["phase"] == "confirmation" else None)
        outcome.logs.append(checked.log)
        if checked.returncode == 70:
            raise InfrastructureError("Correctness runner infrastructure failed")
        if getattr(checked, "budget_shortened", False):
            outcome.status, outcome.correct, outcome.score = "cancelled_budget", None, None
            outcome.reason = "Campaign wall-clock budget exhausted before candidate check timeout"
            return outcome, variables, logs
        if checked.returncode or checked.timed_out:
            outcome.status, outcome.correct, outcome.score = "incorrect", False, 0.0
            outcome.reason = "Protected correctness checks failed"
            return outcome, variables, logs
        try:
            check_data = json.loads(Path(checked.log).read_text(encoding="utf-8"))
            valid = (
                check_data["correct"] is True
                and type(check_data["cases"]) is int
                and check_data["cases"] > 0
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise InfrastructureError(
                "Checker must return JSON {correct: true, cases: positive-int}"
            ) from exc
        if not valid:
            outcome.status, outcome.correct, outcome.score = "incorrect", False, 0.0
            return outcome, variables, logs
        outcome.correct = True
        self._execution_check(outcome, variables, logs)
        if outcome.correct is not True:
            return outcome, variables, logs
        for i in range(self.protocol["warmups"] if warmups else 0):
            result = self._run("benchmark", variables, logs / f"warmup-{i}.log")
            outcome.logs.append(result.log)
            if getattr(result, "budget_shortened", False):
                outcome.status, outcome.correct, outcome.score = "cancelled_budget", None, None
                outcome.reason = "Campaign wall-clock budget exhausted during warmup"
                return outcome, variables, logs
            if result.returncode or result.timed_out:
                outcome.status, outcome.correct, outcome.score = "runtime_failed", False, 0.0
                return outcome, variables, logs
        return outcome, variables, logs

    def _execution_check(self, outcome: Outcome, variables: dict, logs: Path):
        """Observe the actual workload separately from official performance samples."""
        contract = requirements(self.config.get("execution_validation"))
        if contract is None:
            return
        allocation = allocation_evidence(contract)
        if allocation["status"] != "passed":
            raise InfrastructureError("Execution allocation mismatch: " + "; ".join(allocation["reasons"]))
        evidence = {"allocation": allocation, "parallelism": {"status": "not_required"}}
        outcome.execution_validation = evidence
        destination = logs / "execution-validation.json"
        if variables.get("_baseline_reference"):
            evidence["parallelism"] = {"status": "reference_only",
                                       "reason": "Unchanged original; not eligible as a parallel winner"}
        elif contract["parallelism"] == "gnu_openmp_required":
            library = build_probe(logs)
            binary, trace = Path(variables["binary"]), logs / "parallel-probe.jsonl"
            env = probe_environment(binary, library, trace,
                                    self.protocol["environment"] | environment(contract))
            command = self.protocol.get("parallel_probe", self.protocol["benchmark"])
            limit = self._timeout()
            result = run_process(expand_command(command, **variables), self._cwd(variables),
                                 logs / "parallel-workload.log", limit, env)
            outcome.logs.append(result.log)
            if result.timed_out and self.deadline is not None and limit < self.protocol["timeout_seconds"]:
                outcome.status, outcome.correct, outcome.score = "cancelled_budget", None, None
                outcome.reason = "Campaign deadline exhausted during parallelism observation"
                evidence["parallelism"] = {"status": "not_verified", "reason": outcome.reason}
                from .core import atomic_json

                atomic_json(destination, evidence)
                return
            # The observer exits 70 when it cannot start. Protocol 2 credits a 70 to
            # the candidate once the observer has recorded that it loaded.
            if result.returncode == 70 and not (v2(self.config) and _probe_loaded(trace)):
                raise InfrastructureError("Parallelism observer failed; no candidate score")
            if result.returncode or result.timed_out:
                outcome.status, outcome.correct, outcome.score = "incorrect", False, 0.0
                outcome.reason = "Parallel validation workload failed or timed out"
                evidence["parallelism"] = {"status": "failed", "reason": outcome.reason}
            else:
                evidence["parallelism"] = read_probe(contract, trace, allocation, binary,
                                                      outcome.binary_sha256, logs / "parallelism.json")
                if evidence["parallelism"]["status"] != "passed":
                    outcome.status, outcome.correct, outcome.score = "incorrect", False, 0.0
                    outcome.reason = "Required GNU OpenMP team, CPU work or placement not observed"
        from .core import atomic_json

        atomic_json(destination, evidence)
        outcome.logs.append(str(destination))

    def _prepare(self, experiment: str, epoch: int, worktree: Path, commit: str, phase: str,
                 *, warmups: bool = True):
        outcome, variables, logs = self._build(experiment, epoch, worktree, commit, phase)
        return self._check(outcome, variables, logs, warmups=warmups)

    # True when the benchmark command is a protected runner rather than the candidate.
    RUNNER_OWNED_BENCHMARK = False

    def _sample(self, item, index: int) -> None:
        outcome, variables, logs = item
        strict = v2(self.config)
        if file_digest(Path(variables["binary"])) != outcome.binary_sha256:
            if not strict:
                raise InfrastructureError("Executable changed after compilation")
            return self._candidate_fault(item, "runtime_failed", "The candidate executable changed after compilation")
        before_ru = _child_rusage()
        result = self._run("benchmark", variables, logs / f"sample-{index}.log",
                           stderr_log=logs / f"sample-{index}.stderr.log" if strict else None)
        after_ru = _child_rusage()
        if file_digest(Path(variables["binary"])) != outcome.binary_sha256:
            if not strict:
                raise InfrastructureError("Executable changed during benchmarking")
            return self._candidate_fault(item, "runtime_failed", "The candidate executable changed while it ran")
        outcome.logs.append(result.log)
        if getattr(result, "budget_shortened", False):
            outcome.status, outcome.correct, outcome.score = "cancelled_budget", None, None
            outcome.reason = "Campaign wall-clock budget exhausted during benchmark sample"
            outcome.times.clear()
            variables.pop("_rusage_samples", None)
        elif strict and self.RUNNER_OWNED_BENCHMARK and result.returncode == 70:
            raise InfrastructureError("Protected benchmark runner infrastructure failed")
        elif result.returncode or result.timed_out:
            outcome.status, outcome.correct, outcome.score = "runtime_failed", False, 0.0
            outcome.times.clear()
            variables.pop("_rusage_samples", None)
        else:
            outcome.times.append(result.seconds)
            if before_ru is not None and after_ru is not None:
                user_s = max(0.0, float(after_ru["utime"]) - float(before_ru["utime"]))
                sys_s = max(0.0, float(after_ru["stime"]) - float(before_ru["stime"]))
                ratio = (user_s + sys_s) / result.seconds if result.seconds > 0 else 0.0
                variables.setdefault("_rusage_samples", []).append(
                    {
                        "user_seconds": round(user_s, 6),
                        "sys_seconds": round(sys_s, 6),
                        "cpu_utilization_ratio": round(ratio, 4),
                        "minor_page_faults": max(
                            0, int(after_ru["minflt"]) - int(before_ru["minflt"])
                        ),
                    }
                )
            if strict:
                self._collect_output(item, index)

    @staticmethod
    def _candidate_fault(item, status: str, reason: str) -> None:
        """Protocol 2: a fault caused by the candidate's own program scores zero."""
        outcome, variables, _ = item
        outcome.status, outcome.correct, outcome.score, outcome.reason = status, False, 0.0, reason
        outcome.times.clear()
        variables.pop("_rusage_samples", None)
        variables.pop("_outputs", None)

    def _collect_output(self, item, index: int) -> None:
        """Keep a timed run's output for comparison, or check it with the contracted verifier."""
        outcome, variables, logs = item
        stdout = logs / f"sample-{index}.log"
        verify = self.protocol.get("benchmark_verify")
        if verify:
            checked = run_process(expand_command(verify, **variables, output=str(stdout)), self._cwd(variables),
                                  logs / f"verify-{index}.log", self._timeout(), self.protocol["environment"])
            if checked.returncode == 70:
                raise InfrastructureError("Benchmark output verifier failed")
            if checked.returncode or checked.timed_out:
                self._candidate_fault(item, "incorrect", "A timed run failed the contracted output verifier")
                outcome.output_verification = "mismatch"
            else:
                outcome.output_verification = "verified"
            return
        variables.setdefault("_outputs", []).append(self._sample_output(item, index))

    def _sample_output(self, item, index: int) -> bytes | None:
        path = item[2] / f"sample-{index}.log"
        return path.read_bytes() if path.stat().st_size <= MAX_VERIFIED_OUTPUT else None

    @staticmethod
    def _same_output(left, right) -> bool:
        return left is not None and right is not None and compare_bytes(left, right, OUTPUT_COMPARISON)

    def _reference_output(self, item) -> bytes | None:
        """The reference's timed output, only when all of its samples agree."""
        outputs = item[1].get("_outputs") or [None]
        first = outputs[0]
        return first if all(self._same_output(first, other) for other in outputs) else None

    def _verify_outputs(self, item, reference: bytes | None) -> None:
        outcome, variables, _ = item
        if outcome.correct is not True or self.protocol.get("benchmark_verify"):
            return
        outputs = variables.get("_outputs") or []
        if reference is None or not outputs or any(output is None for output in outputs):
            # Recorded as not verified, never assumed correct or wrong.
            outcome.output_verification = "reference_unstable" if reference is None else "unverifiable"
        elif all(self._same_output(reference, output) for output in outputs):
            outcome.output_verification = "verified"
        else:
            self._candidate_fault(item, "incorrect", "A timed run produced an output different from the reference")
            outcome.output_verification = "mismatch"

    def _settle_search_outputs(self, item, epoch: int, reference_sha: str | None) -> None:
        """Record the reference output once; hold every later timed output to it."""
        outcome, variables, _ = item
        if outcome.correct is not True or self.protocol.get("benchmark_verify"):
            return
        path = self.root / "builds" / f"e{epoch}" / "benchmark-reference.out"
        if variables.get("_baseline_reference"):
            reference = self._reference_output(item)
            if reference is None:
                outcome.output_verification = "reference_unstable"
                return
            atomic_bytes(path, reference)
            outcome.output_sha256 = hashlib.sha256(reference).hexdigest()
            outcome.output_verification = "reference"
            return
        reference = None
        if reference_sha:
            if not path.is_file():
                raise InfrastructureError("The recorded benchmark reference output is missing")
            reference = path.read_bytes()
            if hashlib.sha256(reference).hexdigest() != reference_sha:
                raise InfrastructureError("The recorded benchmark reference output changed")
        self._verify_outputs(item, reference)

    @staticmethod
    def _record_rusage(item) -> None:
        outcome, variables, logs = item
        samples = variables.get("_rusage_samples")
        if outcome.correct is True and samples:
            try:
                # RUSAGE_CHILDREN may include concurrent compilers and other children.
                # Keep these counters out of correctness logs, model feedback and selection.
                payload = {
                    "scope": "controller_children_during_benchmark_windows",
                    "candidate_process_only": False,
                    "excluded_from_selection_and_feedback": True,
                    "window_deltas": _summarize_rusage(samples),
                }
                (logs / "process-counters-diagnostic.json").write_text(
                    json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8"
                )
            except OSError:
                pass

    def _finalize(self, outcome: Outcome, baseline: float | None) -> Outcome:
        if outcome.correct is True and outcome.times:
            outcome.mean_seconds = statistics.mean(outcome.times)
            if v2(self.config):
                # Protocol 2 decides on the median: one disturbed sample cannot move it.
                outcome.median_seconds = statistics.median(outcome.times)
            center = outcome.median_seconds if outcome.median_seconds is not None else outcome.mean_seconds
            t0 = baseline if baseline is not None else center
            outcome.score = 1.0 / (1.0 + center / t0)
            outcome.status = "valid"
        return outcome

    def evaluate(
        self, experiment: str, epoch: int, worktree: Path, commit: str, baseline: float | None,
        *, reference_output: str | None = None,
    ) -> Outcome:
        with self._target():
            try:
                item = self._prepare(experiment, epoch, worktree, commit, "search")
                for i in range(self.protocol["repetitions"]):
                    if item[0].correct is not True:
                        break
                    self._sample(item, i)
                self._record_rusage(item)
                if v2(self.config):
                    self._settle_search_outputs(item, epoch, reference_output)
                    if worktree_changed(worktree, commit):
                        self._candidate_fault(item, "contract_violation",
                                              "The candidate modified its source tree during evaluation")
                else:
                    ensure_clean(worktree, commit)
                return self._finalize(item[0], baseline)
            finally:
                verify_protected(self.root / "trusted", self.manifest)

    def _acquire(self, lock: FileLock) -> None:
        while True:
            try:
                lock.__enter__()
                return
            except InfrastructureError as exc:
                if not str(exc).startswith("Resource already locked:"):
                    raise
                if expired(self.deadline):
                    raise BudgetExhausted("Development check expired waiting for target") from exc
                time.sleep(max(0, time_left(self.deadline, 0.05)))

    def precheck(self, experiment: str, epoch: int, worktree: Path, commit: str) -> Outcome:
        """Development-only compile/check: no benchmark, holdout, cache, or tree reward.

        Protocol 2 also compiles in calm: no development build runs on this target
        while another tree's program is being timed.
        """
        lock, held = FileLock(self.lock_path), False
        if v2(self.config):
            self._acquire(lock)
            held = True
        try:
            try:
                outcome, variables, logs = self._build(experiment, epoch, worktree, commit, "search")
            except BudgetExhausted as exc:
                raise BudgetExhausted("Development check expired waiting for target") from exc
            if outcome.status == "cancelled_budget":
                raise BudgetExhausted("Development check expired waiting for target")
            if outcome.status == "build_failed":
                if expired(self.deadline):
                    raise BudgetExhausted("Development check expired waiting for target")
                ensure_clean(worktree, commit)
                outcome.score = None
                return outcome
            if not held:
                self._acquire(lock)
                held = True
            outcome, _, _ = self._check(outcome, variables, logs, warmups=False)
            if outcome.status == "cancelled_budget":
                raise BudgetExhausted("Development check expired waiting for target")
            ensure_clean(worktree, commit)
            if outcome.correct:
                outcome.status = "development_valid"
            outcome.score = None
            return outcome
        finally:
            if held:
                lock.__exit__(None, None, None)
            verify_protected(self.root / "trusted", self.manifest)

    def confirm(self, candidates: list[dict], epoch: int) -> dict[str, Outcome]:
        strict = v2(self.config)
        reference_id = next((c["id"] for c in candidates if c.get("baseline")), None)
        with self._target(), self._hidden_confirmation():
            items, failed = {}, {}

            def isolate(key, commit, exc):
                # Protocol 2: one finalist's infrastructure failure removes only that
                # finalist. Without its reference, no confirmation can conclude.
                if not strict or key == reference_id:
                    raise exc
                items.pop(key, None)
                failed[key] = Outcome("infrastructure_error", commit=commit, reason=str(exc))

            try:
                for candidate in candidates:
                    try:
                        items[candidate["id"]] = self._prepare(
                            candidate["id"],
                            epoch,
                            Path(candidate["worktree"]),
                            candidate["commit"],
                            "confirmation",
                        )
                    except InfrastructureError as exc:
                        isolate(candidate["id"], candidate["commit"], exc)
                # Fresh seeds in the correctness runner; timing samples alternate across finalists.
                rng = random.Random(self.config["seed"] + epoch)
                for repeat in range(self.protocol["confirmation_repetitions"]):
                    order = list(items)
                    rng.shuffle(order)
                    for key in order:
                        if key in items and items[key][0].correct is True:
                            try:
                                self._sample(items[key], repeat)
                            except InfrastructureError as exc:
                                isolate(key, items[key][0].commit, exc)
                for item in items.values():
                    self._record_rusage(item)
                for candidate in candidates:
                    if candidate["id"] not in items:
                        continue
                    worktree = Path(candidate["worktree"])
                    if not strict or candidate["id"] == reference_id:
                        ensure_clean(worktree, candidate["commit"])
                    elif worktree_changed(worktree, candidate["commit"]):
                        self._candidate_fault(items[candidate["id"]], "contract_violation",
                                              "The candidate modified its source tree during confirmation")
                if strict and not self.protocol.get("benchmark_verify") and reference_id in items:
                    expected = self._reference_output(items[reference_id])
                    items[reference_id][0].output_verification = (
                        "reference" if expected is not None else "reference_unstable")
                    for key, item in items.items():
                        if key != reference_id:
                            self._verify_outputs(item, expected)
                reference = items[reference_id][0] if reference_id in items else None
                t0 = None
                if reference and reference.times:
                    t0 = (statistics.median if strict else statistics.mean)(reference.times)
                return {**{key: self._finalize(item[0], t0) for key, item in items.items()}, **failed}
            finally:
                verify_protected(self.root / "trusted", self.manifest)

    @contextmanager
    def _hidden_confirmation(self):
        """Protocol 2 checks confirmation on inputs drawn now, never stored beforehand."""
        if v2(self.config):
            # Small seeds: kernels mix them into C int arithmetic without overflow.
            seeds = ",".join(str(secrets.randbelow(100_000)) for _ in range(4))
            self.confirmation_environment = {"FOREST_CONFIRMATION_SEEDS": seeds}
        try:
            yield
        finally:
            self.confirmation_environment = None

    def remeasure(self, reference: dict, winner: dict, epoch: int) -> dict:
        """Protocol 2: a fresh interleaved series of the provisional winner and its reference.

        The confirmation picked the winner on its own samples; new samples remove that
        selection bias before the gain and its confidence bound are computed.
        """
        with self._target(), self._hidden_confirmation():
            try:
                items = {c["id"]: self._prepare(c["id"], epoch, Path(c["worktree"]), c["commit"], "confirmation")
                         for c in (reference, winner)}
                rng = random.Random(self.config["seed"] + epoch + 1)
                for repeat in range(self.protocol["confirmation_repetitions"]):
                    order = list(items)
                    rng.shuffle(order)
                    for key in order:
                        if items[key][0].correct is True:
                            self._sample(items[key], repeat)
                ensure_clean(Path(reference["worktree"]), reference["commit"])
                if worktree_changed(Path(winner["worktree"]), winner["commit"]):
                    self._candidate_fault(items[winner["id"]], "contract_violation",
                                          "The candidate modified its source tree during the fresh measurement")
                if not self.protocol.get("benchmark_verify"):
                    self._verify_outputs(items[winner["id"]], self._reference_output(items[reference["id"]]))
                base, best = items[reference["id"]][0], items[winner["id"]][0]
                if base.correct is not True or not base.times:
                    raise InfrastructureError("The reference failed its fresh measurement")
                return {"reference_times": list(base.times),
                        "winner_times": list(best.times) if best.correct is True else [],
                        "winner_status": best.status, "winner_reason": best.reason,
                        "output_verification": best.output_verification}
            finally:
                verify_protected(self.root / "trusted", self.manifest)

    def serialize_identity(self) -> dict:
        return {
            "protocol_id": self.protocol_id,
            "target": target_identity(self.config),
            "protocol": self.protocol,
            "protected_files": self.manifest,
        }
