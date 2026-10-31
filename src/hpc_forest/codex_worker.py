"""Local Codex relay with verified transfers and optional model ROMEO MCP access."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from functools import partial
from pathlib import Path, PurePosixPath

from .codex_mailbox import (
    EFFORT,
    MAX_REQUEST_BYTES,
    MODEL,
    PROTOCOL,
    bounded_json,
    json_bytes,
    response_envelope,
    sha256,
    unavailable_usage,
)
from .codex_process import check_dependencies, run_codex
from .core import FileLock, InfrastructureError, atomic_json
from .diagnostics_mcp import DiagnosticsMCP
from .documentation_mcp import DocumentationMCP
from .model_mcp import RomeoMCP, load_server
from .model_policy import generator_pool, require_request_identity
from .model_runtime import authenticate
from .storage.files import atomic_bytes
from .support.budgets import FINISH_STARTED, expired

HEARTBEAT_INTERVAL_SECONDS = 10


class TransferVerificationError(InfrastructureError):
    """A failed integrity receipt is not a transient connection failure."""


def _transfer_failure(exc: Exception) -> bool:
    if isinstance(exc, ExceptionGroup):
        return bool(exc.exceptions) and all(_transfer_failure(item) for item in exc.exceptions)
    if isinstance(exc, TransferVerificationError):
        return False
    if isinstance(exc, (InfrastructureError, OSError, TimeoutError)):
        return True
    return type(exc).__module__.split(".", 1)[0] in {"anyio", "mcp", "httpx", "httpcore"}


async def retry_transfer(operation, *, deadline: float | None = None,
                         attempts: int = 3, timeout: float = 30, retry_delay: float = 1):
    """Retry only file transport, with a finite attempt count and the original deadline."""
    for attempt in range(attempts):
        remaining = timeout if deadline is None else min(timeout, deadline - time.time())
        if remaining <= 0:
            raise InfrastructureError("ROMEO file transfer reached the request deadline")
        try:
            return await asyncio.wait_for(operation(), timeout=remaining)
        except Exception as exc:
            if not _transfer_failure(exc):
                raise
            if attempt + 1 == attempts:
                raise InfrastructureError(
                    f"ROMEO file transfer failed after {attempts} attempts: {exc}"
                ) from exc
            pause = retry_delay * (attempt + 1)
            if deadline is not None:
                pause = min(pause, max(0, deadline - time.time()))
            await asyncio.sleep(pause)
    raise AssertionError("A file transfer needs at least one attempt")


class RomeoFiles:
    """The relay's file connection, separate from native models' MCP sessions."""
    def __init__(self, config: Path):
        self.config = config
        self.stack = AsyncExitStack()

    async def __aenter__(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server, _ = load_server(self.config)
        # The SDK default whitelist drops ProgramData. Windows scp then exits 255
        # before authentication; retain the process environment for this local relay.
        parameters = StdioServerParameters(command=server["command"], args=server.get("args", []),
                                           env={**os.environ, **server.get("env", {})}, cwd=server.get("cwd"))
        streams = await self.stack.enter_async_context(stdio_client(parameters))
        self.session = await self.stack.enter_async_context(ClientSession(*streams))
        await self.session.initialize()
        catalog = await self.session.list_tools()
        needed = {"list_dir", "download_from_romeo", "upload_to_romeo"}
        if not needed <= {tool.name for tool in catalog.tools}:
            raise InfrastructureError("ROMEO MCP file tools are unavailable")
        return self

    async def __aexit__(self, *args):
        return await self.stack.__aexit__(*args)

    async def call(self, name, /, **arguments):
        response = await self.session.call_tool(name, arguments)
        data = response.structuredContent
        if data is None:
            data = json.loads(next(c.text for c in response.content if c.type == "text"))
        if response.isError or not isinstance(data, dict) or data.get("ok") is not True:
            raise InfrastructureError(f"ROMEO file operation failed: {name}")
        return data

    async def download(self, remote: str, local: Path):
        receipt = await self.call("download_from_romeo", remote_path=remote,
                                  local_path=str(local.resolve()), verify=True)
        if receipt.get("verifie") is not True or sha256(local.read_bytes()) != receipt.get("remote_sha256"):
            raise TransferVerificationError("A remote request download was not verified")
        return receipt

    async def upload(self, local: Path, remote: str):
        receipt = await self.call("upload_to_romeo", local_path=str(local.resolve()),
                                  remote_path=remote, verify=True)
        if receipt.get("verifie") is not True:
            raise TransferVerificationError("A remote response upload was not verified")
        return receipt

    async def requests(self, channel: str, *, limit=500):
        listing = await self.call("list_dir", path=channel + "/requests", limit=limit)
        if listing.get("truncated"):
            raise InfrastructureError("Mailbox request listing is truncated")
        return [item["name"] for item in listing["entries"]
                if not item.get("is_dir") and not item.get("is_symlink")
                and re.fullmatch(r"[0-9a-f]{32}\.request\.json", item["name"])]


def validate_remote_channel(channel: str):
    path = PurePosixPath(channel)
    if (path.is_absolute() and ".." not in path.parts and path.name == "mailbox"
            and path.parent.name == "campaign"
            and re.fullmatch(r"forest-app-[0-9a-f]{32}", path.parent.parent.name)):
        return
    if (not path.is_absolute() or ".." in path.parts or path.name != "mailbox"
            or not re.fullmatch(r"results-[0-9]+", path.parent.name)
            or not any(p.startswith("hpc-forest-gpt61sol-max-") for p in path.parts)):
        raise InfrastructureError("Expected this campaign's owned ROMEO mailbox")


def validate_request(request: dict, session_id: str, nonce: str, *, model=MODEL, effort=EFFORT, generators=None):
    expected = {"protocol": PROTOCOL, "session_id": session_id, "nonce": nonce}
    if any(request.get(k) != v for k, v in expected.items()):
        raise InfrastructureError("Downloaded request belongs to another session or model")
    require_request_identity(request, {"model": model, "reasoning_effort": effort, "generator_pool": generators or []})
    if request.get("kind") not in {"source-proposal", "transport-smoke"}:
        raise InfrastructureError("Unsupported mailbox request kind")
    if "active_control" in request:
        from .active_contract import validate_request as validate_control

        validate_control(request)
    if "expires_at" not in request or (request["expires_at"] is not None and (
        type(request["expires_at"]) not in {int, float} or not math.isfinite(request["expires_at"])
    )):
        raise InfrastructureError("Invalid request expiry")
    if request.get("expires_at") is None and (
        request.get("deadline_policy") != FINISH_STARTED
        or request.get("budget_phase") not in {"search", "postprocess"}
    ):
        raise InfrastructureError("An unlimited request requires an explicit completion phase")


def validate_cached_response(response: dict, request: dict, request_sha: str):
    expected = response_envelope(request, request_sha)
    if any(response.get(key) != value for key, value in expected.items()):
        raise TransferVerificationError("Cached response belongs to another request or identity")


def validate_claim(path: Path, request_sha: str):
    if path.exists() and bounded_json(path, 4096).get("request_sha256") != request_sha:
        raise TransferVerificationError("Generation claim belongs to a different request hash")


class Worker:
    def __init__(self, transfer, channel: str, session_id: str, output: Path,
                 dependency_receipt: Path | None, required_jobs: set[str],
                 transport_smoke=False, executable="codex", *, defer_diagnostics=False,
                 model_mcp_config: Path | None = None, documentation=False, model=MODEL, effort=EFFORT,
                 generators=None, diagnostics_root: Path | None = None, dsh_settings: dict | None = None):
        selected = {"model": model, "reasoning_effort": effort, "generator_pool": generators or []}
        pool = generator_pool(selected)
        self.generators = pool if generators else []
        self.model, self.effort = model, effort
        self.dsh_settings = dsh_settings
        validate_remote_channel(channel)
        self.transfer, self.channel, self.session_id = transfer, channel, session_id
        self.output, self.dependency_receipt, self.required_jobs = output, dependency_receipt, required_jobs
        self.transport_smoke, self.executable = transport_smoke, executable
        self.defer_diagnostics = defer_diagnostics
        self.diagnostics_root = Path(diagnostics_root).resolve(strict=True) if diagnostics_root is not None else None
        if self.diagnostics_root is not None and transport_smoke:
            raise InfrastructureError("A transport-only smoke cannot enable diagnostic execution")
        self._io_lock = asyncio.Lock()
        self.finish_started = False
        self.output.mkdir(parents=True, exist_ok=True)
        try:
            self.romeo_mcp = RomeoMCP.bind(model_mcp_config) if model_mcp_config is not None else None
        except (OSError, ValueError) as exc:
            raise InfrastructureError("The existing local ROMEO MCP configuration is unavailable or invalid") from exc
        binding = self.romeo_mcp.receipt() if self.romeo_mcp is not None else None
        binding_file = self.output / "model-mcp.json"
        if binding_file.exists() and bounded_json(binding_file) != binding:
            raise InfrastructureError("The model ROMEO MCP binding changed during this campaign")
        if binding is not None:
            if self.transport_smoke:
                raise InfrastructureError("A transport-only smoke cannot enable model tools")
            atomic_json(binding_file, binding)
        try:
            self.documentation_mcp = DocumentationMCP.bind(output / "documentation", session_id) if documentation else None
        except (OSError, ValueError) as exc:
            raise InfrastructureError("The shared official documentation MCP is unavailable: " + str(exc)) from exc
        documentation_binding = self.documentation_mcp.receipt() if self.documentation_mcp is not None else None
        documentation_file = output / "documentation-mcp.json"
        if documentation_file.exists() and bounded_json(documentation_file) != documentation_binding:
            raise InfrastructureError("The official documentation MCP binding changed during this campaign")
        if documentation_binding is not None:
            if self.transport_smoke:
                raise InfrastructureError("A transport-only smoke cannot enable model documentation tools")
            atomic_json(documentation_file, documentation_binding)
        self.completed = set()
        self.retired = set()
        for local in self.output.iterdir():
            if not local.is_dir() or not re.fullmatch(r"[0-9a-f]{32}", local.name):
                continue
            for marker_name, collection in (("delivered.json", self.completed),
                                             ("expired.json", self.retired)):
                marker_path = local / marker_name
                if not marker_path.exists():
                    continue
                marker = bounded_json(marker_path, 65536)
                request_file = local / "downloaded-request.json"
                request = bounded_json(request_file, MAX_REQUEST_BYTES)
                validate_request(request, self.session_id, local.name, model=self.model, effort=self.effort, generators=self.generators)
                if marker.get("request_sha256") != sha256(request_file.read_bytes()):
                    raise InfrastructureError("Cached delivery request changed")
                validate_claim(local / "generation-claimed.json", marker["request_sha256"])
                if marker.get("response_sha256") is not None:
                    response_file = local / "response.json"
                    response = bounded_json(response_file)
                    if (marker["response_sha256"] != sha256(response_file.read_bytes())
                            or response.get("request_sha256") != marker["request_sha256"]):
                        raise InfrastructureError("Cached delivery response changed")
                    validate_cached_response(response, request, marker["request_sha256"])
                elif marker_name == "delivered.json":
                    raise InfrastructureError("Cached delivery has no verified response")
                collection.add(local.name)

    async def transfer_call(self, call, **retry_options):
        # The native processes overlap. One SDK connection carries file transfers serially.
        async with self._io_lock:
            return await retry_transfer(call, **retry_options)

    async def request_names(self, width=None):
        if width is not None and isinstance(self.transfer, RomeoFiles):
            return await self.transfer_call(lambda: self.transfer.requests(self.channel, limit=max(500, width * 4)))
        return await self.transfer_call(lambda: self.transfer.requests(self.channel))

    async def controller_forest_width(self):
        from .forest import forest_width

        path = self.output / "forest-plan.json"
        await self.transfer_call(lambda: self.transfer.download(self.channel + "/forest-plan.json", path))
        return forest_width(bounded_json(path, MAX_REQUEST_BYTES), self.session_id)

    async def _upload_diagnostics(self, local: Path, nonce: str, *, deadline=None):
        marker = local / "diagnostics-delivered.json"
        if marker.exists():
            return
        uploaded = []
        for name in ("codex.jsonl", "invocation.json", "skills-usage.json"):
            if (local / name).exists():
                await self.transfer_call(
                    lambda name=name: self.transfer.upload(
                        local / name, self.channel + f"/logs/{nonce}.{name}"),
                    deadline=deadline, attempts=1, timeout=10,
                )
                uploaded.append(name)
        atomic_json(marker, {"nonce": nonce, "files": uploaded, "delivered_at": time.time()})
        (local / "diagnostics-pending.json").unlink(missing_ok=True)

    async def flush_diagnostics(self, *, deadline: float | None = None):
        """Transfer preserved logs after deadline-sensitive responses have been delivered."""
        deadline = time.time() + 120 if deadline is None else deadline
        failures = []
        for nonce in sorted(self.completed | self.retired):
            if time.time() >= deadline:
                failures.append(nonce)
                atomic_json(self.output / nonce / "diagnostics-pending.json",
                            {"error": "Diagnostic transfer window elapsed"})
                continue
            try:
                await self._upload_diagnostics(self.output / nonce, nonce, deadline=deadline)
            except Exception as exc:
                if not _transfer_failure(exc):
                    raise
                failures.append(nonce)
                atomic_json(self.output / nonce / "diagnostics-pending.json", {"error": str(exc)})
        return failures

    async def hello(self):
        native = {}
        if not self.transport_smoke:
            if self.dependency_receipt is None:
                raise InfrastructureError("A verified DeepSeek dependency receipt is required")
            gate = check_dependencies(self.dependency_receipt, self.required_jobs)
            if gate.get("schema") == "forest-app-authorization-v1" and self.dsh_settings != gate.get("dsh_romeo"):
                raise InfrastructureError("dsh-romeo connection differs from the authorized mission")
            if self.generators and generator_pool({"model": gate.get("next_model"),
                    "reasoning_effort": gate.get("reasoning_effort"),
                    "generator_pool": gate.get("generator_pool", [])}) != self.generators:
                raise InfrastructureError("The worker pool differs from its authorization")
            self.finish_started = gate.get("completion", {}).get("policy") == FINISH_STARTED
            self.executable = shutil.which(self.executable)
            if not self.executable:
                raise InfrastructureError("Codex is unavailable on this PC")
            version = await asyncio.to_thread(subprocess.run, [self.executable, "--version"],
                capture_output=True, text=True, timeout=30, check=True)
            auth = await asyncio.to_thread(authenticate, self.executable,
                {"model": self.model, "reasoning_effort": self.effort, "generator_pool": self.generators},
                dsh_settings=self.dsh_settings)
            native = {"codex_executable": self.executable, "codex_cli_version": version.stdout.strip(),
                      **auth,
                      "model_mcp": self.romeo_mcp.receipt() if self.romeo_mcp is not None else None,
                      "documentation_mcp": self.documentation_mcp.receipt() if self.documentation_mcp is not None else None}
            native["diagnostics_mcp"] = {"server": "hpc_diagnostics", "binding": "per-controller-request"} \
                if self.diagnostics_root is not None else None
        await retry_transfer(lambda: self.transfer.download(
            self.channel + "/OWNER.json", self.output / "OWNER.json"))
        marker = bounded_json(self.output / "OWNER.json", 4096)
        expected = {"protocol": PROTOCOL, "session_id": self.session_id,
                    "model": self.model, "reasoning_effort": self.effort}
        if any(marker.get(k) != v for k, v in expected.items()):
            raise InfrastructureError("The remote channel owner does not match")
        if generator_pool(marker) != generator_pool({**expected, "generator_pool": self.generators}):
            raise InfrastructureError("The remote generator pool does not match")
        ready = {**expected, "mode": "transport-smoke" if self.transport_smoke else "codex",
                 "pid": os.getpid(), "started_at": time.time(), "local_python": sys.executable,
                 "model_weights_on_romeo": False, **native}
        atomic_json(self.output / "worker-ready.json", ready)
        await retry_transfer(lambda: self.transfer.upload(
            self.output / "worker-ready.json", self.channel + "/worker-ready.json"))

    @asynccontextmanager
    async def keepalive(self, enabled: bool):
        """Liveness is independent of model duration; a dead relay cannot hang the controller."""
        stopping = asyncio.Event()
        async def pulse():
            while not stopping.is_set():
                try:
                    data = {"session_id": self.session_id, "model": self.model,
                            "reasoning_effort": self.effort, "alive_at": time.time()}
                    if self.generators:
                        data["generator_pool"] = self.generators
                    # SCP can retain a Windows read handle after an RPC timeout.
                    # Never rewrite or replace the file being transferred.
                    path = self.output / "heartbeat-snapshots" / f"{time.time_ns()}.json"
                    atomic_json(path, data)
                    try:
                        atomic_json(self.output / "worker-heartbeat.json", data)
                    except OSError:
                        pass  # Local monitoring must not prevent the remote heartbeat.
                    if isinstance(self.transfer, RomeoFiles):
                        # Cancelling a timed-out SDK request can close its session.
                        # Isolate pulses from response delivery, and reconnect for
                        # each pulse so a broken heartbeat session cannot persist.
                        async with RomeoFiles(self.transfer.config) as heartbeat_transfer:
                            await retry_transfer(lambda path=path, transfer=heartbeat_transfer: transfer.upload(
                                path, self.channel + "/worker-heartbeat.json"), attempts=1, timeout=20)
                    else:
                        await retry_transfer(lambda path=path: self.transfer.upload(
                            path, self.channel + "/worker-heartbeat.json"), attempts=1, timeout=20)
                except Exception as exc:
                    if stopping.is_set():
                        return
                    if not _transfer_failure(exc):
                        raise
                    atomic_json(self.output / "heartbeat-error.json", {"error": str(exc)})
                if stopping.is_set():
                    return
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
        task = asyncio.create_task(pulse()) if enabled else None
        try:
            yield
        finally:
            if task is not None:
                stopping.set()
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    async def handle(self, filename: str):
        if not re.fullmatch(r"[0-9a-f]{32}\.request\.json", filename):
            raise InfrastructureError("Unsafe request filename")
        nonce = filename.split(".")[0]
        if nonce in self.completed or nonce in self.retired:
            return False
        local = self.output / nonce
        local.mkdir(exist_ok=True)
        request_file = local / "downloaded-request.json"
        receipt = await self.transfer_call(lambda: self.transfer.download(
            self.channel + "/requests/" + filename, request_file))
        atomic_json(local / "download-receipt.json", receipt)
        request = bounded_json(request_file, MAX_REQUEST_BYTES)
        validate_request(request, self.session_id, nonce, model=self.model, effort=self.effort, generators=self.generators)
        request_sha = sha256(request_file.read_bytes())
        response_file = local / "response.json"
        claim = local / "generation-claimed.json"
        validate_claim(claim, request_sha)
        cached = bounded_json(response_file) if response_file.exists() else None
        if cached is not None:
            validate_cached_response(cached, request, request_sha)

        def retire():
            marker = {"request_sha256": request_sha, "expired_at": time.time(),
                      "reason": "Original request deadline elapsed; no late result was substituted"}
            if response_file.exists():
                marker["response_sha256"] = sha256(response_file.read_bytes())
            atomic_json(local / "expired.json", marker)
            self.retired.add(nonce)

        if expired(request["expires_at"], now=time.time()):
            retire()
            return False
        if cached is not None:
            response = cached
        elif claim.exists():
            # A crash may have lost the end of a charged model request. Never regenerate it.
            response = response_envelope(request, request_sha,
                error="Worker interrupted after claiming this request; not replayed",
                infrastructure_error=True,
                usage=unavailable_usage(request))
        elif self.transport_smoke:
            if request["kind"] != "transport-smoke":
                raise InfrastructureError("Transport smoke cannot answer a source proposal")
            response = response_envelope(request, request_sha, data={"ack": nonce},
                error=None, infrastructure_error=False,
                usage={"tokens": 0, "token_accounting": "exact", "llm_calls": 0})
        else:
            if request["kind"] != "source-proposal":
                raise InfrastructureError("The model worker accepts only source proposals")
            with claim.open("x", encoding="utf8") as stream:
                json.dump({"request_sha256": request_sha, "claimed_at": time.time()}, stream)
            try:
                arguments = (request, request_sha, local, self.dependency_receipt, self.required_jobs, self.executable)
                options = {"romeo_mcp": self.romeo_mcp} if self.romeo_mcp is not None else {}
                if self.dsh_settings is not None:
                    options["dsh_settings"] = self.dsh_settings
                if self.documentation_mcp is not None:
                    options["documentation_mcp"] = self.documentation_mcp
                if request.get("diagnostics"):
                    if self.diagnostics_root is None:
                        raise InfrastructureError("Diagnostic campaign is not mounted in this native worker")
                    options["diagnostics_mcp"] = DiagnosticsMCP.bind(self.diagnostics_root, request)
                generate = partial(run_codex, *arguments, **options)
                if getattr(self, "model_executor", None) is not None:
                    response = await asyncio.get_running_loop().run_in_executor(self.model_executor, generate)
                else:
                    response = await asyncio.to_thread(generate)
            except Exception as exc:
                response = response_envelope(request, request_sha,
                    error=f"Local Codex interface failed: {type(exc).__name__}: {exc}",
                    infrastructure_error=True,
                    usage=unavailable_usage(request))
        # Keep byte-identical results for interrupted uploads; a later run only resends them.
        # Publish atomically: a worker killed mid-write must not leave a truncated cache.
        raw = json_bytes(response)
        atomic_bytes(response_file, raw)
        atomic_json(local / "response-ready.json", {"sha256": sha256(raw), "bytes": len(raw)})
        try:
            for source, suffix in ((response_file, "response.json"),
                                   (local / "response-ready.json", "ready.json")):
                await self.transfer_call(lambda source=source, suffix=suffix: self.transfer.upload(
                    source, self.channel + f"/responses/{nonce}.{suffix}"),
                    deadline=request["expires_at"])
        except TransferVerificationError:
            raise
        except InfrastructureError:
            if not expired(request["expires_at"], now=time.time()):
                raise
            retire()
            return False
        self.completed.add(nonce)
        atomic_json(local / "delivered.json", {"request_sha256": request_sha,
                    "response_sha256": sha256(raw), "delivered_at": time.time()})
        if not self.defer_diagnostics:
            await self._upload_diagnostics(local, nonce)
        return True


async def main_async(args):
    with FileLock(args.output / "worker.lock"):
        async with RomeoFiles(args.codex_config) as transfer:
            worker = Worker(transfer, args.channel, args.session_id, args.output,
                            args.dependency_receipt, set(args.required_jobs), args.transport_smoke,
                            args.executable, defer_diagnostics=getattr(args, "mother_trees", False),
                            model_mcp_config=args.codex_config if getattr(args, "mother_trees", False)
                                and not args.transport_smoke else None,
                            documentation=getattr(args, "mother_trees", False) and not args.transport_smoke)
            await worker.hello()
            end = None if worker.finish_started else time.monotonic() + args.max_seconds
            from .request_pool import RequestPool

            pool = RequestPool(worker)
            try:
                async with worker.keepalive(worker.finish_started):
                    while end is None or time.monotonic() < end:
                        if getattr(args, "mother_trees", False):
                            listing = await worker.transfer_call(
                                lambda: transfer.call("list_dir", path=args.channel, limit=30))
                            entries = {entry["name"] for entry in listing["entries"]}
                            width = await worker.controller_forest_width() if "forest-plan.json" in entries else 1
                            await pool.pump(await worker.request_names(width), width)
                            if "DONE.json" in entries:
                                await pool.drain()
                                await worker.transfer_call(lambda: transfer.download(
                                    args.channel + "/DONE.json", args.output / "DONE.json"))
                                marker = bounded_json(args.output / "DONE.json")
                                if marker.get("session_id") != args.session_id:
                                    raise InfrastructureError("Unrelated forest completion marker")
                                await worker.flush_diagnostics(deadline=math.inf)
                                return 0 if marker.get("pipeline_complete") else 1
                        else:
                            for name in sorted(await worker.request_names()):
                                done = await worker.handle(name)
                                if done and args.once:
                                    return 0
                        await asyncio.sleep(args.poll_seconds)
            finally:
                await pool.close()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--codex-config", type=Path, required=True)
    parser.add_argument("--dependency-receipt", type=Path)
    parser.add_argument("--required-jobs", nargs="+", default=[])
    parser.add_argument("--executable", default="codex")
    parser.add_argument("--transport-smoke", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--mother-trees", action="store_true",
                        help="Follow Mother's controller-owned N-tree plan; run all N concurrently")
    parser.add_argument("--max-seconds", type=int, default=72000)
    parser.add_argument("--poll-seconds", type=float, default=2)
    args = parser.parse_args()
    if args.mother_trees and args.once:
        parser.error("--mother-trees must serve the complete N-tree forest, not one request")
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.transport_smoke and (not args.dependency_receipt or not args.required_jobs):
        parser.error("Model calls require a dependency receipt and explicit completed job IDs")
    if args.max_seconds <= 0 or args.poll_seconds <= 0:
        parser.error("Worker time limits must be positive")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
