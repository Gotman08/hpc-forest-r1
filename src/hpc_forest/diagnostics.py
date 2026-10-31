"""Persistent diagnostic evidence on the controller's already allocated target."""
from __future__ import annotations

import base64
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from . import diagnostic_collectors as adapters
from . import diagnostic_compiler, diagnostic_cuda
from .core import (
    FileLock,
    InfrastructureError,
    _kill_owned,
    atomic_json,
    expand_command,
    file_digest,
    verify_protected,
)
from .diagnostics_contract import identifier, load_grant, owned, target_lock
from .webapp.project_protocol import execution_environment


class DiagnosticFailure(Exception):
    def __init__(self, status, reason):
        self.status = status
        super().__init__(reason)


def git_read(repo, *arguments, binary=False, deadline=None):
    """Read immutable objects without inheriting an MCP stdin or Git overrides.

    In particular Git for Windows must not inherit the native JSON-RPC pipe.
    Global hooks, credential prompts and inherited GIT_DIR are irrelevant here.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_OPTIONAL_LOCKS="0")
    remaining = 20 if deadline is None else min(20, deadline - time.time())
    if remaining <= 0:
        raise DiagnosticFailure("budget_exhausted", "Diagnostic source copy deadline reached")
    try:
        result = subprocess.run(["git", "-c", "core.longpaths=true", "-C", str(repo), *arguments],
            stdin=subprocess.DEVNULL, capture_output=True, env=env, timeout=remaining, check=True)
    except subprocess.TimeoutExpired as exc:
        raise DiagnosticFailure("budget_exhausted", "Diagnostic Git object read timed out") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise InfrastructureError("Diagnostic Git object read failed: " + type(exc).__name__) from exc
    return result.stdout if binary else result.stdout.decode("utf8").strip()


def tree_files(repo, commit, *, deadline=None):
    for entry in git_read(repo, "ls-tree", "-rz", commit, binary=True, deadline=deadline).decode("utf8").split("\0"):
        if entry:
            metadata, name = entry.split("\t", 1)
            yield metadata.split()[0], name


def files_under(root):
    """Never traverse links left by a workload; keep raw files in place."""
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(base) / d).is_symlink()
                   and not (hasattr(Path(base) / d, "is_junction") and (Path(base) / d).is_junction())]
        for name in names:
            path = Path(base) / name
            if path.is_file() and not path.is_symlink():
                yield path


class Diagnostics:
    def __init__(self, root: Path, binding: dict, request=None):
        self.root = root.resolve(strict=True)
        self.grant = load_grant(self.root, binding, request)
        self.binding = binding
        self.config = json.loads((self.root / "trusted/config.json").read_text(encoding="utf8"))
        self.directory = self.root / "diagnostics"
        self.policy = self.grant["policy"]

    def audit(self, action, arguments, operation):
        identity = uuid.uuid4().hex
        path = self.directory / "audit" / (identity + ".json")
        record = {"id": identity, "request_id": self.grant["nonce"], "role": self.grant["role"],
                  "action": action, "arguments": arguments, "started_at": time.time(),
                  "permission": {"can_collect": self.grant["can_collect"], "expires_at": self.grant["expires_at"]},
                  "status": "started_without_result"}
        atomic_json(path, record)
        try:
            value = operation()
            result = {"ok": value.get("status") not in {
                "unavailable", "permission_denied", "budget_exhausted", "artifact_limit",
                "collector_failed", "target_mismatch", "build_failed", "diagnostic_check_failed",
                "started_without_result"}, **value}
        except (OSError, ValueError, InfrastructureError, DiagnosticFailure) as exc:
            result = {"ok": False, "status": getattr(exc, "status", "rejected"),
                      "error": str(exc)[:2000], "score": None}
        atomic_json(path, {**record, "status": "complete", "finished_at": time.time(), "result": result})
        return result

    def execution_allowed(self):
        if not self.grant["can_collect"]:
            raise DiagnosticFailure("permission_denied", "This role has read-only diagnostic access")
        if time.time() >= self.grant["expires_at"]:
            raise DiagnosticFailure("budget_exhausted", "Diagnostic grant expired")
        if (platform.machine() != self.grant["machine"] or platform.node() != self.grant["hostname"]):
            raise DiagnosticFailure("target_mismatch", "Diagnostics must run on the bound compute node")
        if self.policy["require_allocation"] and (
                not str(self.grant.get("allocation_id") or "").isdigit()
                or os.environ.get("SLURM_JOB_ID") != self.grant["allocation_id"]):
            raise DiagnosticFailure("permission_denied", "An existing bound Slurm allocation is required; login execution is forbidden")
        verify_protected(self.root / "trusted", self.grant["manifest"])
        compiler = self.config.get("compiler", {})
        if compiler.get("path") and compiler.get("sha256") and (
                file_digest(Path(compiler["path"])) != compiler["sha256"]):
            raise DiagnosticFailure("target_mismatch", "Frozen compiler changed; a new campaign is required")

    def _executor(self, directory, deadline, cwd, environment=None):
        records = []
        clean = execution_environment(dict(os.environ))
        env = {**{k: "" for k in os.environ if k not in clean}, **clean,
               **self.config["protocol"]["environment"], **(environment or {}), "LC_ALL": "C"}
        # Use the controller's CPU affinity, not the worker's orchestration CPU.
        affinity = self.grant.get("affinity")

        def run(argv, name, *, env=None, optional=False):
            identifier(name)
            log = directory / (name + ".log")
            command = list(map(str, argv))
            effective = command
            if affinity and platform.system() == "Linux":
                effective = ["taskset", "-c", ",".join(map(str, affinity)), *command]
            record = {"argv": command, "effective_argv": effective, "cwd": str(cwd),
                      "environment": {**self.config["protocol"]["environment"], **(environment or {}), **(env or {})},
                      "started_at": time.time(), "log": str(log), "returncode": None,
                      "seconds": None, "timed_out": False, "optional": optional}
            # Do not record inherited credentials or the host environment.
            records.append(record)
            atomic_json(directory / (name + ".command.json"), record)
            started = time.monotonic()
            failure = None
            try:
                if time.time() >= deadline:
                    raise DiagnosticFailure("budget_exhausted", "Diagnostic execution deadline reached")
                with log.open("wb") as output:
                    process = subprocess.Popen(effective, cwd=cwd, env={**base_env, **(env or {})},
                        stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                        start_new_session=os.name != "nt")
                    try:
                        while process.poll() is None:
                            if time.time() >= deadline:
                                record["timed_out"] = True
                                failure = "budget_exhausted"
                                _kill_owned(process)
                                break
                            if sum(p.stat().st_size for p in files_under(directory)) > self.policy["max_bytes"]:
                                failure = "artifact_limit"
                                _kill_owned(process)
                                break
                            try:
                                process.wait(timeout=0.1)
                            except subprocess.TimeoutExpired:
                                pass
                    finally:
                        if process.poll() is None:
                            _kill_owned(process)
                        process.wait(timeout=10)
                record["returncode"] = process.returncode
                if sum(p.stat().st_size for p in files_under(directory)) > self.policy["max_bytes"]:
                    failure = "artifact_limit"
                if process.returncode and not failure:
                    with log.open("rb") as stream:
                        stream.seek(max(0, log.stat().st_size - 12000))
                        text = stream.read(12000).decode(errors="replace").lower()
                    failure = "permission_denied" if any(t in text for t in (
                        "permission", "not permitted", "err_nvgpuctrperm", "perf_event_paranoid")) else "collector_failed"
            except OSError as exc:
                log.write_text(str(exc), encoding="utf8")
                failure = "unavailable"
            finally:
                record.update(seconds=time.monotonic() - started, failure=failure)
                atomic_json(directory / (name + ".command.json"), record)
            if failure and (not optional or failure in {"artifact_limit", "budget_exhausted"}):
                raise DiagnosticFailure(failure, f"{name}: inspect preserved {log.name}")
            return record

        base_env = env
        return run, records

    def _locked(self, operation):
        self.execution_allowed()
        deadline = min(self.grant["expires_at"], time.time() + self.policy["collection_seconds"])
        lock = FileLock(target_lock(self.config))
        while True:
            try:
                lock.__enter__()
                break
            except InfrastructureError as exc:
                if not str(exc).startswith("Resource already locked:"):
                    raise
                if time.time() >= deadline:
                    raise DiagnosticFailure("budget_exhausted", "Waiting for the official target lock") from exc
                time.sleep(0.05)
        try:
            self.execution_allowed()
            return operation(deadline)
        finally:
            lock.__exit__(None, None, None)

    def capabilities(self, probe=False):
        """PATH absence is scoped to this allocation, never a cluster-wide assertion."""
        tools = {name: shutil.which(name) for name in adapters.PROBES}
        collectors = {name: {**asdict(adapter), "availability":
            "unsupported_platform" if adapter.platforms and platform.system() not in adapter.platforms else
            "missing_executable" if any(not tools.get(tool) for tool in adapter.tools) else "probe_required",
            "missing_executables": [tool for tool in adapter.tools if not tools.get(tool)]}
            for name, adapter in adapters.COLLECTORS.items()}
        result = {"host": platform.node(), "architecture": platform.machine(), "system": platform.system(),
                  "allocation_id": os.environ.get("SLURM_JOB_ID"), "collectors": collectors,
                  "tools": tools, "permissions": {"can_collect": self.grant["can_collect"], **self.policy},
                  "counter_availability": "unknown_until_probe_and_collection",
                  "other_runtimes": "No implicit support: register an adapter and validate it on the target"}
        result["previous_probes"] = [p.parent.name for p in sorted(
            (self.directory / "probes").glob("*/capabilities.json"))][-20:]
        if probe:
            def perform(deadline):
                directory = self.directory / "probes" / uuid.uuid4().hex
                directory.mkdir(parents=True)
                run, records = self._executor(directory, deadline, directory)
                try:
                    for name, executable in tools.items():
                        if executable:
                            run([executable, *adapters.PROBES[name]], name, optional=True)
                            if name in adapters.DETAIL_PROBES:
                                run([executable, *adapters.DETAIL_PROBES[name]], name + "-details", optional=True)
                    for file in ("/proc/sys/kernel/perf_event_paranoid", "/proc/sys/kernel/kptr_restrict", "/proc/cpuinfo"):
                        path = Path(file)
                        if path.is_file():
                            (directory / path.name).write_bytes(path.read_bytes())
                except DiagnosticFailure as exc:
                    result.update(status=exc.status, error=str(exc))
                finally:
                    result["probe_id"] = directory.name
                    result["probe_results"] = [{k: r[k] for k in ("argv", "returncode", "failure", "log")} for r in records]
                    atomic_json(directory / "capabilities.json", result)
                    self._manifest(directory)
                return result
            return self._locked(perform)
        return result

    def source(self, source_id):
        try:
            return self.grant["sources"][source_id]
        except (KeyError, TypeError):
            raise ValueError("Source is outside this controller grant") from None

    def sources(self, offset=0, limit=40):
        return self._page([{"id": k, **v} for k, v in self.grant["sources"].items()], offset, limit)

    @staticmethod
    def _page(items, offset, limit):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid pagination")
        return {"items": items[offset:offset + limit], "total": len(items),
                "next_offset": offset + limit if offset + limit < len(items) else None}

    def source_files(self, source_id, path=None, offset=0, limit=80, byte_offset=None):
        source = self.source(source_id)
        files = {}
        if self.config.get("app_protocol"):
            files.update({name.removeprefix("original/"): ("trusted", name)
                          for name in self.grant["manifest"] if name.startswith("original/")})
        for mode, name in tree_files(self.root / "repo", source["commit"]):
            if mode not in {"100644", "100755"}:
                continue
            public = name.removeprefix("src/") if self.config.get("app_protocol") else name
            files[public] = ("git", name)
        if path is None:
            return self._page(sorted(files), offset, limit)
        if path not in files:
            raise ValueError("Unknown source file")
        kind, name = files[path]
        raw = owned(self.root / "trusted", name).read_bytes() if kind == "trusted" else git_read(
            self.root / "repo", "show", source["commit"] + ":" + name, binary=True)
        import hashlib

        if kind == "trusted" and hashlib.sha256(raw).hexdigest() != self.grant["manifest"][name]:
            raise InfrastructureError("Protected diagnostic source changed")
        if byte_offset is not None:
            if type(byte_offset) is not int or byte_offset < 0:
                raise ValueError("Invalid source byte offset")
            data = raw[byte_offset:byte_offset + 12000]
            return {"source_id": source_id, "commit": source["commit"], "path": path,
                    "sha256": hashlib.sha256(raw).hexdigest(), "encoding": "base64",
                    "data": base64.b64encode(data).decode(), "offset_bytes": byte_offset,
                    "next_offset": byte_offset + len(data) if byte_offset + len(data) < len(raw) else None}
        return {"source_id": source_id, "commit": source["commit"], "path": path,
                "sha256": hashlib.sha256(raw).hexdigest(), **self._text_page(raw, offset, limit)}

    def _copy_source(self, source, destination, deadline):
        destination.mkdir()
        size = 0
        for mode, name in tree_files(self.root / "repo", source["commit"], deadline=deadline):
            if mode not in {"100644", "100755"}:
                raise ValueError("Diagnostic sources cannot contain links or submodules")
            target = owned(destination, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = git_read(self.root / "repo", "show", source["commit"] + ":" + name, binary=True, deadline=deadline)
            size += len(raw)
            if size > self.policy["max_bytes"]:
                raise DiagnosticFailure("artifact_limit", "Source snapshot exceeds the diagnostic allowance")
            target.write_bytes(raw)
            if mode == "100755":
                target.chmod(target.stat().st_mode | 0o100)

    def _build(self, source, directory, collector, deadline):
        worktree, trusted, build = (directory / n for n in ("source", "trusted", "build"))
        self._copy_source(source, worktree, deadline)
        if (sum(p.stat().st_size for p in files_under(worktree))
                + sum(p.stat().st_size for p in files_under(self.root / "trusted")) > self.policy["max_bytes"]):
            raise DiagnosticFailure("artifact_limit", "Diagnostic inputs exceed the artifact allowance")
        shutil.copytree(self.root / "trusted", trusted, symlinks=True)
        if any(p.is_symlink() for p in trusted.rglob("*")):
            raise ValueError("Diagnostic protected inputs cannot contain links")
        build.mkdir()
        binary = build / ("solution.exe" if os.name == "nt" else "solution")
        if self.config.get("app_protocol"):
            binary = build / "project" / self.config["app_protocol"]["binary"]
        # Reuse the frozen research inputs. A diagnostic is a separate execution,
        # not a new protocol phase, and must never expose confirmation inputs.
        variables = {"python": sys.executable, "trusted": str(trusted), "worktree": str(worktree),
                     "build": str(build), "binary": str(binary), "phase": "search"}
        run, records = self._executor(directory, deadline, worktree)
        mode = collector if collector in {"compiler", "scorep", "scalasca"} else (
            "symbols" if collector in {"perf-record", "hpctoolkit", "nsys", "ncu", "disassembly"} else "capture")
        environment, coverage = diagnostic_compiler.prepare(directory / "compiler", self.config, mode, run)
        cuda_environment = (diagnostic_cuda.prepare(directory / "cuda-capture", run)
                            if diagnostic_cuda.applicable(self.config, collector) else {})
        environment.update(cuda_environment)
        if collector in {"scorep", "scalasca"}:
            environment["FOREST_DIAGNOSTIC_SCOREP"] = shutil.which("scorep")
        build_runner, build_records = self._executor(directory, deadline, worktree, environment)
        build_runner(expand_command(self.config["protocol"]["build"], **variables), "build")
        if not binary.is_file() or binary.is_symlink():
            raise DiagnosticFailure("build_failed", "Diagnostic build produced no regular executable")
        compiler_records = [json.loads(p.read_text(encoding="utf8")) for p in (directory / "compiler/records").glob("*.json")]
        coverage["invocations"] = compiler_records
        coverage["status"] = "observed_invocations" if compiler_records else "no_invocations_intercepted"
        coverage["complete"] = False  # A PATH wrapper cannot prove it saw every compiler.
        coverage["requested_mode"] = mode
        atomic_json(directory / "compiler-coverage.json", coverage)
        if collector in {"compiler", "scorep", "scalasca"} and not compiler_records and not cuda_environment:
            raise DiagnosticFailure("unavailable", "Compiler interception saw no invocation; no instrumentation can be claimed")
        if collector == "compiler" and not cuda_environment and not any(r["diagnostic_flags"] for r in compiler_records):
            raise DiagnosticFailure("unavailable", "No supported source compilation emitted optimization reports")
        if collector in {"scorep", "scalasca"} and not any(r["scorep_instrumented"] for r in compiler_records):
            raise DiagnosticFailure("unavailable", "Score-P did not instrument this build")
        checked = run(expand_command(self.config["protocol"]["check"], **variables), "diagnostic-check", env=cuda_environment)
        if cuda_environment:
            coverage = diagnostic_cuda.evidence(directory / "cuda-capture")
            atomic_json(directory / "cuda-compiler-coverage.json", coverage)
            if not coverage["binaries"]:
                raise DiagnosticFailure("unavailable", "No native NVRTC CUBIN captured from the diagnostic workload")
        try:
            check_data = json.loads(Path(checked["log"]).read_text(encoding="utf8"))
            valid = (check_data["correct"] is True and type(check_data["cases"]) is int and check_data["cases"] > 0)
        except (ValueError, KeyError, TypeError) as exc:
            raise DiagnosticFailure("diagnostic_check_failed", "Diagnostic checker produced no valid result") from exc
        if not valid:
            raise DiagnosticFailure("diagnostic_check_failed", "Instrumented copy failed its diagnostic check; official results are unchanged")
        command = expand_command(self.config["protocol"]["benchmark"], **variables)
        cwd = worktree
        if self.config.get("app_protocol"):
            spec = json.loads((trusted / "project.json").read_text(encoding="utf8"))
            command = shlex.split(spec["contract"]["benchmark_command"])
            if any(any(c in arg for c in "|;&<>`$\n") for arg in command):
                raise DiagnosticFailure("unavailable", "Profiler adapter requires a direct executable command; compound shell workloads need a new adapter")
            command[0] = str(binary)
            cwd = build / "project"
        atomic_json(directory / "build-provenance.json", {
            "binary_sha256": file_digest(binary), "source": source, "variables": variables,
            "build_argv": expand_command(self.config["protocol"]["build"], **variables),
            "workload_argv": command, "instrumentation": mode,
            "execution_kind": "diagnostic", "input_phase": "search",
            "diagnostic_check": "passed", "official_score": None})
        return binary, command, cwd, records + build_records

    def _target_denial(self, collector):
        """Reuse only a recognized profiler permission fact on the same target/tool."""
        executable = shutil.which("ncu") if collector == "ncu" else None
        if not executable:
            return None
        tool_hash = file_digest(Path(executable))
        for path in sorted((self.directory / "collections").glob("*/summary.json")):
            value = json.loads(path.read_text(encoding="utf8"))
            fact = value.get("target_permission_denied", {})
            if (value.get("collector") == collector and value.get("status") == "permission_denied"
                    and fact.get("code") == "ERR_NVGPUCTRPERM" and fact.get("tool_sha256") == tool_hash
                    and value.get("host") == self.grant["hostname"]
                    and value.get("allocation_id") == self.grant["allocation_id"]
                    and value.get("protocol_id") == self.grant["protocol_id"]
                    and value.get("architecture") == self.grant["machine"]):
                return value
        return None

    def collect(self, source_id, collector, question, options=None, request_key=None):
        source = self.source(source_id)
        options = adapters.options_for(collector, options)
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise ValueError("A bounded diagnostic question is required")
        identity = identifier(request_key) if request_key else uuid.uuid4().hex
        if len(identity) > 60:
            raise ValueError("Diagnostic request_key exceeds 60 characters")
        # A request key is scoped to the calling grant, making transport retries idempotent.
        identity = self.grant["nonce"] + "-" + identity
        directory = self.directory / "collections" / identity
        with FileLock(self.directory / "locks" / (self.grant["nonce"] + ".lock")):
            if directory.exists():
                record = json.loads((directory / "summary.json").read_text(encoding="utf8"))
                if (record["source_id"], record["collector"], record["question"], record["options"]) != (
                        source_id, collector, question, options):
                    raise ValueError("Diagnostic request key reused for different arguments")
                return record
            self.execution_allowed()
            collections = list((self.directory / "collections").glob(self.grant["nonce"] + "-*/summary.json"))
            if len(collections) >= self.policy["max_collections"]:
                raise DiagnosticFailure("budget_exhausted", "Collection allowance exhausted")
            directory.mkdir(parents=True)
            adapter = adapters.COLLECTORS[collector]
            summary = {"id": identity, "request_id": self.grant["nonce"], "source_id": source_id,
                       "source": source, "collector": collector, "question": question, "options": options,
                       "status": "started_without_result", "created_at": time.time(), "score": None,
                       "protocol_id": self.grant["protocol_id"], "host": self.grant["hostname"],
                       "allocation_id": self.grant["allocation_id"], "architecture": self.grant["machine"],
                       "scope": adapter.scope, "units": adapter.units, "limitations": [adapter.limitations],
                       "hypotheses": [], "missing": [], "observations": []}
            atomic_json(directory / "summary.json", summary)
            def reuse_denial():
                previous = self._target_denial(collector)
                if previous is None:
                    return False
                summary.update(status="permission_denied", error=previous["error"],
                    target_permission_denied=previous["target_permission_denied"],
                    reused_target_capability_from=previous.get("reused_target_capability_from", previous["id"]))
                summary["missing"].append({"measurement": collector, "reason": summary["error"]})
                return True

            def perform(deadline):
                if reuse_denial():
                    return  # Another collector may have established the fact while this one waited.
                probe, _ = self._executor(directory, deadline, directory)
                for tool in adapter.tools:
                    executable = shutil.which(tool)
                    probe([executable, *adapters.PROBES[tool]], "version-" + tool, optional=True)
                atomic_json(directory / "toolchain.json", {
                    "tools": {tool: {"path": shutil.which(tool), "sha256": file_digest(Path(shutil.which(tool)))}
                              for tool in adapter.tools}, "libc": platform.libc_ver(),
                    "affinity": self.grant["affinity"], "environment": self.config["protocol"]["environment"]})
                binary, workload, cwd, _ = self._build(source, directory, collector, deadline)
                run, records = self._executor(directory, deadline, cwd)
                if shutil.which("objdump"):
                    run([shutil.which("objdump"), "-p", str(binary)], "linked-libraries", optional=True)
                tools = {tool: shutil.which(tool) for tool in adapter.tools}
                if collector == "disassembly" and diagnostic_cuda.applicable(self.config, collector):
                    coverage = json.loads((directory / "cuda-compiler-coverage.json").read_text(encoding="utf8"))
                    diagnostic_cuda.disassemble(coverage, directory, run)
                else:
                    adapters.collect(collector, options, workload, binary, directory, run, tools)
                summary["observations"] = [{"command": r["argv"], "wall_seconds": r["seconds"],
                    "unit": "seconds", "meaning": "diagnostic command elapsed including profiler overhead"} for r in records
                    if not r["optional"]]
                if collector == "perf-stat":
                    summary["counters"] = adapters.perf_counters(directory / "counters.csv")
                    summary["missing"] += [c for c in summary["counters"] if c["value"] is None]
                    if not summary["counters"]:
                        summary["missing"].append({"measurement": "counters", "reason": "No counter rows produced"})
                expected = {
                    "perf-record": ("perf.data",), "hpctoolkit": ("hpctoolkit-measurements/*", "hpctoolkit-database/*"),
                    "nsys": ("*.nsys-rep", "*.sqlite"), "ncu": ("kernels.ncu-rep",),
                    "scorep": ("scorep-measurement/*.cubex",), "scalasca": ("scorep-measurement/*.cubex",),
                }.get(collector, ())
                for pattern in expected:
                    if not any(p.is_file() and p.stat().st_size for p in directory.glob(pattern)):
                        summary["missing"].append({"measurement": pattern, "reason": "No native evidence produced"})
                summary["status"] = "partial" if summary["missing"] else "complete"
            try:
                # Missing executables and known target permissions cannot improve
                # by waiting behind an official GPU evaluation.
                capability = self.capabilities()["collectors"][collector]
                atomic_json(directory / "capabilities.json", capability)
                if capability["availability"] != "probe_required":
                    raise DiagnosticFailure("unavailable", capability["availability"] + ": " + ",".join(capability["missing_executables"]))
                if not reuse_denial():
                    self._locked(perform)
            except (OSError, ValueError, InfrastructureError, DiagnosticFailure) as exc:
                summary.update(status=getattr(exc, "status", "collector_failed"), error=str(exc))
                summary["missing"].append({"measurement": collector, "reason": str(exc)})
                if collector == "ncu" and summary["status"] == "permission_denied":
                    log, executable = directory / "ncu-profile.log", shutil.which("ncu")
                    if executable and log.is_file() and not log.is_symlink():
                        with log.open("rb") as stream:
                            stream.seek(max(0, log.stat().st_size - 12000))
                            denied = b"ERR_NVGPUCTRPERM" in stream.read(12000)
                        if denied:
                            summary["target_permission_denied"] = {"code": "ERR_NVGPUCTRPERM",
                                "tool_sha256": file_digest(Path(executable))}
            finally:
                verify_protected(self.root / "trusted", self.grant["manifest"])
                summary["finished_at"] = time.time()
                atomic_json(directory / "summary.json", summary)
                self._manifest(directory)
            return summary

    def survey(self, source_id, question, request_key):
        """Account for every adapter on an optimized source within the same grant.

        Reuse completed evidence for the exact commit, never baseline evidence
        for a different program. Failed/absent collectors remain explicit rows.
        Each new collection keeps its own native files and ordinary cost limits.
        """
        self.execution_allowed()
        source = self.source(source_id)
        identifier(request_key)
        if len(request_key) > 35:
            raise ValueError("Survey request_key exceeds 35 characters")
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise ValueError("A bounded diagnostic question is required")
        previous = {}
        for path in sorted((self.directory / "collections").glob("*/summary.json")):
            value = json.loads(path.read_text(encoding="utf8"))
            if (value["source_id"] in self.grant["sources"]
                    and value["source"]["commit"] == source["commit"]
                    and value["status"] in {"complete", "partial"}):
                previous[value["collector"]] = value
        rows = []
        # Dynamic GPU trace first; then compiler/code evidence and counters.
        order = ("nsys", "compiler", "disassembly", "ncu", "runtime", "perf-stat",
                 "perf-record", "hpctoolkit", "scorep", "scalasca")
        for collector in order:
            reused = collector in previous
            try:
                value = previous[collector] if reused else self.collect(
                    source_id, collector, question, request_key=request_key + "-" + collector)
                row = {k: value[k] for k in ("id", "source_id", "collector", "status", "score")}
                row.update(error=value.get("error"), reused=reused,
                           reused_target_capability_from=value.get("reused_target_capability_from"))
            except (DiagnosticFailure, InfrastructureError, OSError, ValueError) as exc:
                row = {"collector": collector, "source_id": source_id, "score": None,
                       "status": getattr(exc, "status", "collector_failed"), "error": str(exc)}
            rows.append(row)
        return {"source_id": source_id, "commit": source["commit"], "collectors": rows,
                "score": None, "status": "complete" if all(r["status"] == "complete" for r in rows) else "partial",
                "instruction": "Read native artifacts for successful tools. Missing/denied tools supply no measurements."}

    def _manifest(self, directory):
        artifacts = []
        for path in sorted(files_under(directory)):
            name = path.relative_to(directory).as_posix()
            if name == "artifacts.json" or name.startswith(("trusted/", "source/", "compiler/")):
                continue
            artifacts.append({"path": name, "bytes": path.stat().st_size, "sha256": file_digest(path)})
        atomic_json(directory / "artifacts.json", {"items": artifacts})

    def summaries(self, offset=0, limit=40):
        items = []
        for path in sorted((self.directory / "collections").glob("*/summary.json")):
            record = json.loads(path.read_text(encoding="utf8"))
            if (record["source_id"] in self.grant["sources"]
                    and record["source"]["commit"] == self.grant["sources"][record["source_id"]]["commit"]):
                items.append({k: record[k] for k in ("id", "source_id", "collector", "question", "status", "created_at")})
        return self._page(items, offset, limit)

    def _artifacts(self, evidence_id):
        identifier(evidence_id)
        directory = self.directory / "collections" / evidence_id
        if directory.is_dir():
            summary = json.loads((directory / "summary.json").read_text(encoding="utf8"))
            if self.source(summary["source_id"])["commit"] != summary["source"]["commit"]:
                raise ValueError("Evidence is from another source version")
        else:
            directory = self.directory / "probes" / evidence_id
            # Probe IDs are not secrets, but restrict them to this campaign's actual files.
            if not directory.is_dir():
                raise ValueError("Unknown diagnostic evidence")
        manifest = json.loads((directory / "artifacts.json").read_text(encoding="utf8"))["items"]
        return directory, manifest

    def _artifact(self, evidence_id, artifact):
        directory, manifest = self._artifacts(evidence_id)
        entry = next((e for e in manifest if e["path"] == artifact), None)
        if entry is None:
            raise ValueError("Artifact is outside the recorded evidence manifest")
        path = owned(directory, artifact)
        if file_digest(path) != entry["sha256"]:
            raise InfrastructureError("Diagnostic artifact changed after collection")
        return path, entry

    def table(self, evidence_id, artifact, **options):
        from .diagnostic_evidence import sqlite_page

        path, entry = self._artifact(evidence_id, artifact)
        return {**entry, **sqlite_page(path, **options)}

    def evidence(self, evidence_id, artifact=None, offset=0, limit=80, binary=False):
        if artifact is None:
            _, manifest = self._artifacts(evidence_id)
            return self._page(manifest, offset, limit)
        path, entry = self._artifact(evidence_id, artifact)
        if binary:
            if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 49152:
                raise ValueError("Invalid byte pagination")
            with path.open("rb") as stream:
                stream.seek(offset)
                data = stream.read(limit)
            return {**entry, "encoding": "base64", "offset_bytes": offset,
                    "data": base64.b64encode(data).decode(),
                    "next_offset": offset + len(data) if offset + len(data) < entry["bytes"] else None}
        # Read bounded lines rather than loading a multi-GB profiler database.
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid line pagination")
        lines, size, truncated = [], 0, False
        with path.open("r", encoding="utf8", errors="replace") as stream:
            for index, line in enumerate(stream):
                if index < offset:
                    continue
                if len(lines) >= limit or size + len(line) > 24000:
                    truncated = True
                    break
                lines.append(line.rstrip("\n"))
                size += len(line)
        return {**entry, "start_line": offset + 1, "lines": lines,
                "next_offset": offset + len(lines) if truncated else None,
                "byte_read_available": True, "long_line_requires_byte_read": truncated and not lines}

    @staticmethod
    def _text_page(raw, offset, limit):
        lines = raw.decode("utf8", errors="replace").splitlines()
        page = Diagnostics._page(lines, offset, limit)
        size, visible = 0, []
        for line in page["items"]:
            if size + len(line) > 24000:
                break
            visible.append(line)
            size += len(line)
        page["items"] = visible
        page["next_offset"] = offset + len(visible) if offset + len(visible) < len(lines) else None
        page["long_line_requires_byte_read"] = bool(page["next_offset"] is not None and not visible)
        return {"start_line": offset + 1, **page}
