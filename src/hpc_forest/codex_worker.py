"""Local Codex worker; use the existing ROMEO MCP only for verified file transfer."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from contextlib import AsyncExitStack
from pathlib import Path, PurePosixPath

from .codex_mailbox import (
    EFFORT,
    MAX_REQUEST_BYTES,
    MODEL,
    PROTOCOL,
    TOKEN_CEILING,
    bounded_json,
    json_bytes,
    response_envelope,
    sha256,
)
from .codex_process import check_dependencies, run_codex
from .core import FileLock, InfrastructureError, atomic_json


class RomeoFiles:
    """A private local MCP connection, never passed to the model."""
    def __init__(self, config: Path):
        self.config = config
        self.stack = AsyncExitStack()

    async def __aenter__(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        cfg = tomllib.loads(self.config.read_text(encoding="utf8"))
        server = cfg["mcp_servers"]["romeo"]
        # The SDK default whitelist drops ProgramData. Windows scp then exits 255
        # before authentication; retain the process environment for this local relay.
        parameters = StdioServerParameters(command=server["command"], args=server.get("args", []),
                                           env={**os.environ, **server.get("env", {})})
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

    async def call(self, name, **arguments):
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
            raise InfrastructureError("A remote request download was not verified")
        return receipt

    async def upload(self, local: Path, remote: str):
        receipt = await self.call("upload_to_romeo", local_path=str(local.resolve()),
                                  remote_path=remote, verify=True)
        if receipt.get("verifie") is not True:
            raise InfrastructureError("A remote response upload was not verified")
        return receipt

    async def requests(self, channel: str):
        listing = await self.call("list_dir", path=channel + "/requests", limit=500)
        if listing.get("truncated"):
            raise InfrastructureError("Mailbox request listing is truncated")
        return [item["name"] for item in listing["entries"]
                if not item.get("is_dir") and not item.get("is_symlink")
                and re.fullmatch(r"[0-9a-f]{32}\.request\.json", item["name"])]


def validate_remote_channel(channel: str):
    path = PurePosixPath(channel)
    if (not path.is_absolute() or ".." in path.parts or path.name != "mailbox"
            or not re.fullmatch(r"results-[0-9]+", path.parent.name)
            or not any(p.startswith("hpc-forest-gpt61sol-max-") for p in path.parts)):
        raise InfrastructureError("Expected this campaign's owned ROMEO mailbox")


def validate_request(request: dict, session_id: str, nonce: str):
    expected = {"protocol": PROTOCOL, "session_id": session_id, "nonce": nonce,
                "model": MODEL, "reasoning_effort": EFFORT}
    if any(request.get(k) != v for k, v in expected.items()):
        raise InfrastructureError("Downloaded request belongs to another session or model")
    if request.get("kind") not in {"source-proposal", "transport-smoke"}:
        raise InfrastructureError("Unsupported mailbox request kind")


class Worker:
    def __init__(self, transfer, channel: str, session_id: str, output: Path,
                 dependency_receipt: Path | None, required_jobs: set[str],
                 transport_smoke=False, executable="codex", *, defer_diagnostics=False):
        validate_remote_channel(channel)
        self.transfer, self.channel, self.session_id = transfer, channel, session_id
        self.output, self.dependency_receipt, self.required_jobs = output, dependency_receipt, required_jobs
        self.transport_smoke, self.executable = transport_smoke, executable
        self.defer_diagnostics = defer_diagnostics
        self.output.mkdir(parents=True, exist_ok=True)
        self.completed = set()

    async def _upload_diagnostics(self, local: Path, nonce: str):
        marker = local / "diagnostics-delivered.json"
        if marker.exists():
            return
        uploaded = []
        for name in ("codex.jsonl", "invocation.json"):
            if (local / name).exists():
                await self.transfer.upload(local / name, self.channel + f"/logs/{nonce}.{name}")
                uploaded.append(name)
        atomic_json(marker, {"nonce": nonce, "files": uploaded, "delivered_at": time.time()})

    async def flush_diagnostics(self):
        """Transfer preserved logs after deadline-sensitive responses have been delivered."""
        for nonce in sorted(self.completed):
            await self._upload_diagnostics(self.output / nonce, nonce)

    async def hello(self):
        native = {}
        if not self.transport_smoke:
            if self.dependency_receipt is None:
                raise InfrastructureError("A verified DeepSeek dependency receipt is required")
            check_dependencies(self.dependency_receipt, self.required_jobs)
            self.executable = shutil.which(self.executable)
            if not self.executable:
                raise InfrastructureError("Codex is unavailable on this PC")
            version = await asyncio.to_thread(subprocess.run, [self.executable, "--version"],
                capture_output=True, text=True, timeout=30, check=True)
            auth = await asyncio.to_thread(subprocess.run, [self.executable, "login", "status"],
                capture_output=True, text=True, timeout=30, check=True)
            if "Logged in using ChatGPT" not in auth.stdout + auth.stderr:
                raise InfrastructureError("This experiment requires the existing ChatGPT authentication")
            native = {"codex_executable": self.executable, "codex_cli_version": version.stdout.strip(),
                      "authentication": "existing-local-ChatGPT", "weight_digest_available": False}
        await self.transfer.download(self.channel + "/OWNER.json", self.output / "OWNER.json")
        marker = bounded_json(self.output / "OWNER.json", 4096)
        expected = {"protocol": PROTOCOL, "session_id": self.session_id,
                    "model": MODEL, "reasoning_effort": EFFORT}
        if any(marker.get(k) != v for k, v in expected.items()):
            raise InfrastructureError("The remote channel owner does not match")
        ready = {**expected, "mode": "transport-smoke" if self.transport_smoke else "codex",
                 "pid": os.getpid(), "started_at": time.time(), "local_python": sys.executable,
                 "model_weights_on_romeo": False, **native}
        atomic_json(self.output / "worker-ready.json", ready)
        await self.transfer.upload(self.output / "worker-ready.json", self.channel + "/worker-ready.json")

    async def handle(self, filename: str):
        if not re.fullmatch(r"[0-9a-f]{32}\.request\.json", filename):
            raise InfrastructureError("Unsafe request filename")
        nonce = filename.split(".")[0]
        if nonce in self.completed:
            return False
        local = self.output / nonce
        local.mkdir(exist_ok=True)
        request_file = local / "downloaded-request.json"
        receipt = await self.transfer.download(self.channel + "/requests/" + filename, request_file)
        atomic_json(local / "download-receipt.json", receipt)
        request = bounded_json(request_file, MAX_REQUEST_BYTES)
        validate_request(request, self.session_id, nonce)
        request_sha = sha256(request_file.read_bytes())
        response_file = local / "response.json"
        claim = local / "generation-claimed.json"
        if response_file.exists():
            response = bounded_json(response_file)
            if response.get("request_sha256") != request_sha:
                raise InfrastructureError("Cached response differs from the downloaded request")
        elif claim.exists():
            # A crash may have lost the end of a charged model request. Never regenerate it.
            response = response_envelope(request, request_sha,
                error="Worker interrupted after claiming this request; not replayed",
                infrastructure_error=True,
                usage={"tokens": TOKEN_CEILING, "token_accounting": "upper_bound", "llm_calls": 1})
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
                response = await asyncio.to_thread(run_codex, request, request_sha, local,
                    self.dependency_receipt, self.required_jobs, self.executable)
            except Exception as exc:
                response = response_envelope(request, request_sha,
                    error=f"Local Codex interface failed: {type(exc).__name__}: {exc}",
                    infrastructure_error=True,
                    usage={"tokens": TOKEN_CEILING, "token_accounting": "upper_bound", "llm_calls": 1})
        # Keep byte-identical results for interrupted uploads; a later run only resends them.
        raw = json_bytes(response)
        response_file.write_bytes(raw)
        await self.transfer.upload(response_file, self.channel + f"/responses/{nonce}.response.json")
        atomic_json(local / "response-ready.json", {"sha256": sha256(raw), "bytes": len(raw)})
        await self.transfer.upload(local / "response-ready.json", self.channel + f"/responses/{nonce}.ready.json")
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
                            args.executable)
            await worker.hello()
            end = time.monotonic() + args.max_seconds
            while time.monotonic() < end:
                for name in sorted(await transfer.requests(args.channel)):
                    done = await worker.handle(name)
                    if done and args.once:
                        return 0
                await asyncio.sleep(args.poll_seconds)
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
    parser.add_argument("--max-seconds", type=int, default=72000)
    parser.add_argument("--poll-seconds", type=float, default=2)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.transport_smoke and (not args.dependency_receipt or not args.required_jobs):
        parser.error("Model calls require a dependency receipt and explicit completed job IDs")
    if args.max_seconds <= 0 or args.poll_seconds <= 0:
        parser.error("Worker time limits must be positive")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
