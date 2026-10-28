"""Small shared contracts; no LLM is allowed to set an evaluation result."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import socket
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .storage.files import atomic_json as atomic_json


class ForestError(RuntimeError):
    pass


class InfrastructureError(ForestError):
    pass


class CandidateRejected(ForestError):
    pass


class BudgetExhausted(ForestError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FileLock:
    """OS-owned lock, released after a crash; never remove a lock held by another process."""

    def __init__(self, path: Path):
        self.path = path
        self.stream = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        try:
            if os.fstat(self.stream.fileno()).st_size == 0:
                self.stream.write(b"0")
                self.stream.flush()
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            self.stream = None
            raise InfrastructureError(f"Resource already locked: {self.path}") from exc
        return self

    def __exit__(self, *_):
        if self.stream:
            if os.name == "nt":
                import msvcrt

                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
            self.stream.close()


@dataclass
class ProcessResult:
    argv: list[str]
    returncode: int
    seconds: float
    timed_out: bool
    log: str


def _kill_owned(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    # The still-running process belongs to this Popen handle, never a name match.
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()


def _terminate_owned(process: subprocess.Popen) -> None:
    _kill_owned(process)
    process.communicate(timeout=5)


def run_process(
    argv: list[str],
    cwd: Path,
    log: Path,
    timeout: float | None,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
) -> ProcessResult:
    if timeout is not None and timeout <= 0:
        raise BudgetExhausted("Wall-clock deadline reached")
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    expired = threading.Event()
    try:
        with log.open("wb") as out:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                stdout=out,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                env={**os.environ, **(env or {})},
                start_new_session=os.name != "nt",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
            def expire():
                if process.poll() is None:
                    expired.set()
                    try:
                        _kill_owned(process)
                    except (OSError, subprocess.SubprocessError):
                        if process.poll() is None:
                            process.kill()

            # POSIX communicate(timeout=...) polls waitpid with sleeps up to 50 ms
            # when stdout/stderr are files. A watchdog enforces the same limit while
            # the caller observes process completion through a blocking wait.
            watchdog = threading.Timer(timeout, expire) if timeout is not None else None
            if watchdog is not None:
                watchdog.daemon = True
                watchdog.start()
            try:
                process.communicate(None if stdin is None else stdin.encode())
            except BaseException:
                _terminate_owned(process)
                raise
            finally:
                if watchdog is not None:
                    watchdog.cancel()
                    watchdog.join()
    except OSError as exc:
        raise InfrastructureError(f"Could not execute {argv[0]}: {exc}") from exc
    result = ProcessResult(
        argv, process.returncode, time.perf_counter() - started, expired.is_set(), str(log)
    )
    atomic_json(log.with_suffix(log.suffix + ".json"), asdict(result))
    return result


def protected_manifest(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): file_digest(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }


def verify_protected(root: Path, expected: dict[str, str]) -> None:
    if protected_manifest(root) != expected:
        raise InfrastructureError("Controller-owned protocol/tests changed; campaign stopped")


def expand_command(command: list[str], **variables: str) -> list[str]:
    result = []
    for arg in command:
        for key, value in variables.items():
            arg = arg.replace("{" + key + "}", str(value))
        result.append(arg)
    return result


@dataclass
class Mission:
    id: str
    tree_id: str
    trial_id: str
    epoch: int
    role: str
    base_commit: str
    parent_id: str | None
    delegation_parent: str
    depth: int
    ordinal: int
    worktree: str
    hypothesis: str = ""
    sources: list[str] = field(default_factory=list)
    source_commits: list[str] = field(default_factory=list)
    transformations: dict[str, Any] = field(default_factory=dict)
    budget_phase: str = "search"
    kind: str = "research"
    base_source_id: str | None = None
    control_decision_id: str | None = None
    import_ids: list[str] = field(default_factory=list)
    advice_ids: list[str] = field(default_factory=list)
    generator: dict[str, str] = field(default_factory=dict)
    search_action: str = ""
    selection: dict[str, Any] = field(default_factory=dict)


@dataclass
class Outcome:
    status: str
    commit: str | None = None
    tree_hash: str | None = None
    binary_sha256: str | None = None
    correct: bool | None = None
    times: list[float] = field(default_factory=list)
    mean_seconds: float | None = None
    score: float | None = None
    reason: str = ""
    logs: list[str] = field(default_factory=list)
    cache_key: str | None = None


def local_target_id() -> str:
    return f"local:{socket.gethostname()}"
