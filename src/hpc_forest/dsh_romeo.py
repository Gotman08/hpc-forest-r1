"""Use an already running dsh-romeo gateway; never launch or stop model jobs."""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .core import InfrastructureError
from .model_policy import DSH_MODEL, generator_pool

DEFAULT_URL = "http://127.0.0.1:11318/v1"
KEY_ENV = "ROMEO_LLM_KEY"


def required(settings: dict) -> bool:
    return any(item["model"] == DSH_MODEL for item in generator_pool(settings))


def base_url(settings: dict | None = None) -> str:
    value = (settings.get("base_url") if settings is not None else
             os.environ.get("DSH_ROMEO_BASE_URL", DEFAULT_URL))
    try:
        parsed = urlsplit(value)
        valid = (isinstance(value, str) and value.isascii()
                 and not any(c.isspace() or ord(c) < 32 for c in value)
                 and parsed.scheme in {"http", "https"} and parsed.hostname
                 and parsed.username is None and parsed.password is None
                 and not parsed.query and not parsed.fragment and parsed.path.rstrip("/") == "/v1"
                 and parsed.port != 0)
    except (TypeError, ValueError, AttributeError):
        valid = False
    if not valid:
        raise InfrastructureError("dsh-romeo requires an HTTP(S) base_url ending in /v1 without credentials")
    return value.rstrip("/")


def validate_remote(settings: dict) -> dict:
    """Only a remote endpoint and a private key-file path may enter a frozen bundle."""
    if not isinstance(settings, dict) or set(settings) != {"base_url", "api_key_file"}:
        raise InfrastructureError("Configure dsh_romeo.base_url and dsh_romeo.api_key_file in romeo.json")
    url = base_url(settings)
    host = urlsplit(url).hostname
    try:
        local = ipaddress.ip_address(host).is_loopback or ipaddress.ip_address(host).is_unspecified
    except ValueError:
        local = host.rstrip(".").lower() == "localhost"
    if local:
        raise InfrastructureError("dsh-romeo on ROMEO needs the gateway host reachable from compute nodes, not the PC tunnel")
    path = settings["api_key_file"]
    if (not isinstance(path, str) or not PurePosixPath(path).is_absolute()
            or ".." in PurePosixPath(path).parts or any(ord(c) < 32 for c in path)):
        raise InfrastructureError("dsh_romeo.api_key_file must be an absolute ROMEO path")
    return {"base_url": url, "api_key_file": path}


def environment(settings: dict | None = None) -> dict[str, str]:
    """Read credentials at invocation time. Never serialize them into requests or argv."""
    base_url(settings)
    if settings is not None:
        path = settings.get("api_key_file")
        try:
            with Path(path).open(encoding="utf8") as stream:
                key = stream.read(8193).strip()
        except (OSError, TypeError, ValueError):
            raise InfrastructureError("The private dsh-romeo API key file is unavailable") from None
    else:
        key = os.environ.get(KEY_ENV, "")
    if not key or len(key) > 8192 or not key.isascii() or any(c.isspace() or ord(c) < 32 for c in key):
        raise InfrastructureError("dsh-romeo requires ROMEO_LLM_KEY or a readable private api_key_file")
    return {KEY_ENV: key, "OPENAI_API_KEY": "", "CODEX_API_KEY": ""}


def overrides(settings: dict | None = None) -> dict:
    return {
        "model_provider": "romeo",
        "model_providers.romeo.name": "ROMEO (dsh-romeo)",
        "model_providers.romeo.base_url": base_url(settings),
        "model_providers.romeo.env_key": KEY_ENV,
        "model_providers.romeo.wire_api": "responses",
        "model_providers.romeo.requires_openai_auth": False,
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_available(settings: dict | None = None) -> None:
    """A bounded, read-only check of the existing gateway's served model list."""
    request = Request(base_url(settings) + "/models",
                      headers={"Authorization": "Bearer " + environment(settings)[KEY_ENV]})
    try:
        with build_opener(_NoRedirect).open(request, timeout=15) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("oversized model catalogue")
        data = json.loads(raw)
        models = data.get("data") if isinstance(data, dict) else None
        if not isinstance(models, list):
            raise ValueError("invalid model catalogue")
    except (HTTPError, URLError, OSError, ValueError):
        raise InfrastructureError("dsh-romeo gateway unavailable or unauthorized; check its existing service and key") from None
    if not any(isinstance(item, dict) and item.get("id") == DSH_MODEL for item in models):
        raise InfrastructureError("The selected DeepSeek model is absent from the dsh-romeo gateway")
