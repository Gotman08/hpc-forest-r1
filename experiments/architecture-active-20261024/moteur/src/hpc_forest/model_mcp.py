"""Bind native models to the user's existing stdio ROMEO server.

This file also runs as a standalone stdio launcher. Configuration values stay
on the local PC; credentials are never embedded in Codex arguments or receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

MODEL_MCP_POLICY = {"server": "romeo", "profile": "existing-user", "policy": "romeo-tools-v1"}
# The forest controller alone launches models. ROMEO experiments do not grant
# Mother (or a child) a second route to create or restart LLM workers.
DISABLED_MODEL_TOOLS = (
    "romeollm_launch_prepare", "romeollm_launch", "romeollm_chat",
    "romeollm_gateway_start", "romeollm_gateway_stop", "romeollm_stop",
)
RUNTIME_INSTRUCTIONS = """

ROMEO MCP access is enabled for this run through the user's existing server,
SSH identity and tool profile. Local shell execution remains disabled. You may
use ROMEO tools to inspect documentation, software, resources and diagnostics,
and to conduct remote experiments within this campaign's authorized scope.
Use allocated compute nodes for compilation and computation, never the login
node. Keep experimental files in a separate directory belonging to your mission.
Never modify official tests, oracle, compiler, target, controller, mailbox,
authorization or another mission's files. Only controller measurements and its
independent confirmation determine official scores; tool results are evidence,
not replacement scores. Return the requested JSON proposal as your final answer.
Never launch or contact other LLM workers through ROMEO. Only the controller
starts the N research trees. In Mother's assembly phase research is permanently
closed: continue the same conversation, assemble G and do not restart any tree.
"""


def load_server(config: Path, expected_sha256: str | None = None) -> tuple[dict, str]:
    raw = config.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("The bound ROMEO MCP configuration changed")
    if len(raw) > 1024 * 1024:
        raise ValueError("ROMEO MCP configuration is too large")
    try:
        server = tomllib.loads(raw.decode("utf-8"))["mcp_servers"]["romeo"]
    except (KeyError, UnicodeError, tomllib.TOMLDecodeError):
        # TOML decoder errors may contain secret configuration values.
        raise ValueError("Expected a valid local mcp_servers.romeo configuration") from None
    if (not isinstance(server, dict) or not isinstance(server.get("command"), str)
            or not server["command"].strip() or "url" in server or server.get("enabled") is False
            or not isinstance(server.get("args", []), list)
            or not all(isinstance(arg, str) for arg in server.get("args", []))
            or not isinstance(server.get("env", {}), dict)
            or not all(isinstance(k, str) and isinstance(v, str) for k, v in server.get("env", {}).items())
            or ("cwd" in server and not isinstance(server["cwd"], str))):
        raise ValueError("ROMEO MCP requires an enabled local stdio server")
    for key in ("enabled_tools", "disabled_tools"):
        if key in server and (not isinstance(server[key], list)
                              or not all(isinstance(item, str) for item in server[key])):
            raise ValueError("Invalid ROMEO MCP tool selection")
    for key in ("startup_timeout_sec", "tool_timeout_sec"):
        if key in server and (type(server[key]) not in {int, float}
                              or not math.isfinite(server[key]) or server[key] <= 0):
            raise ValueError("Invalid ROMEO MCP timeout")
    return server, digest


@dataclass(frozen=True)
class RomeoMCP:
    config: Path
    sha256: str

    @classmethod
    def bind(cls, config: Path) -> RomeoMCP:
        config = config.resolve(strict=True)
        _, digest = load_server(config)
        return cls(config, digest)

    def receipt(self) -> dict:
        return {**MODEL_MCP_POLICY, "config_sha256": self.sha256,
                "disabled_model_tools": list(DISABLED_MODEL_TOOLS)}

    def overrides(self) -> dict:
        server, _ = load_server(self.config, self.sha256)
        values = {
            "command": sys.executable,
            "args": [str(Path(__file__).resolve()), "--config", str(self.config), "--sha256", self.sha256],
            "env_vars": sorted(os.environ),
            "enabled": True, "required": True,
            "default_tools_approval_mode": "approve",
            "startup_timeout_sec": server.get("startup_timeout_sec", 60),
            "tool_timeout_sec": server.get("tool_timeout_sec", 120),
            "disabled_tools": sorted(set(server.get("disabled_tools", [])) | set(DISABLED_MODEL_TOOLS)),
        }
        if "enabled_tools" in server:
            values["enabled_tools"] = server["enabled_tools"]
        return {"mcp_servers.romeo." + key: value for key, value in values.items()}

    def instructions(self, system: str) -> str:
        return system.replace("Do not execute commands", "Do not execute local commands") + RUNTIME_INSTRUCTIONS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        server, _ = load_server(args.config, args.sha256)
        # Preserve HOME/LOCALAPPDATA, SSH_AUTH_SOCK and Windows ProgramData just
        # as the existing file relay does. The user's saved ROMEO profile applies.
        process = subprocess.run([server["command"], *server.get("args", [])],
                                 cwd=server.get("cwd"), env={**os.environ, **server.get("env", {})})
        return process.returncode
    except (OSError, ValueError):
        print("The bound local ROMEO MCP server could not start; check its configuration", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
