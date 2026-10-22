"""Local inference only: structured source files, never model-provided shell commands."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

from .backends import Generated
from .core import CandidateRejected, InfrastructureError, Mission, atomic_json
from .harness_research import extract_research
from .proposal_contract import SOURCE_SCHEMA
from .source_request import proposal_messages
from .support.budgets import expired, generation_deadline, time_left, unlimited_tokens


class RepetitionAborted(InfrastructureError):
    """The pinned local engine aborted this one prediction for repeated tokens."""


def local_url(base_url: str) -> str:
    value = urllib.parse.urlsplit(base_url)
    if (
        value.scheme != "http"
        or value.hostname not in {"localhost", "127.0.0.1", "::1"}
        or value.username
        or value.password
        or value.query
        or value.fragment
        or value.path not in {"", "/"}
    ):
        raise InfrastructureError(
            "Ollama must use an explicit loopback HTTP endpoint on the execution node"
        )
    return base_url.rstrip("/")


def request_json(base_url: str, endpoint: str, payload: dict | None, timeout: float | None) -> dict:
    if timeout is not None and timeout <= 0:
        raise InfrastructureError("No inference time remaining")
    request = urllib.request.Request(
        local_url(base_url) + endpoint,
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "HPC-Forest-local-models"},
    )
    try:
        # Do not route local inference through a proxy inherited from the login environment.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise InfrastructureError("Ollama response exceeds the controller limit")
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("error"):
            raise InfrastructureError("Ollama returned an invalid/error response")
        return data
    except urllib.error.HTTPError as exc:
        # A local server failure is not a bad candidate. Retain its bounded
        # diagnostic, without replaying a generation whose usage is unknown.
        try:
            detail = exc.read(4096).decode("utf-8", errors="replace")
        except OSError:
            detail = "Response body unavailable"
        try:
            repetition = json.loads(detail).get("error") == "prediction aborted, token repeat limit reached"
        except (ValueError, AttributeError):
            repetition = False
        error_type = RepetitionAborted if exc.code == 500 and endpoint == "/api/chat" and repetition else InfrastructureError
        raise error_type(
            f"Local Ollama HTTP {exc.code} at {endpoint}: {detail}"
        ) from exc
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise InfrastructureError(f"Local Ollama request failed: {exc}") from exc


def resolve_model(settings: dict) -> dict:
    tags = request_json(settings["base_url"], "/api/tags", None, 10)
    model = next(
        (m for m in tags.get("models", []) if settings["model"] in {m.get("name"), m.get("model")}),
        None,
    )
    if model is None:
        raise InfrastructureError(
            f"Model is not installed on the local Ollama server: {settings['model']}"
        )
    sha = str(model.get("digest", "")).removeprefix("sha256:")
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise InfrastructureError("A full model digest is required")
    expected = settings.get("model_digest")
    if expected and expected != sha:
        raise InfrastructureError("Installed model digest changed; start a new campaign")
    version = request_json(settings["base_url"], "/api/version", None, 10)
    return {
        **settings,
        "model_digest": sha,
        "server_version": version.get("version"),
        "model_details": model.get("details", {}),
    }


def validate_files(worktree: Path, data: dict, source_ids: list[str]) -> list[tuple[Path, str]]:
    if not isinstance(data, dict) or set(data) != set(SOURCE_SCHEMA["required"]):
        raise CandidateRejected("Local model response does not match the result contract")
    if not isinstance(data["hypothesis"], str) or not isinstance(data["notes"], str):
        raise CandidateRejected("Invalid hypothesis/notes")
    if not isinstance(data["transformations"], list) or not all(
        isinstance(x, str) for x in data["transformations"]
    ):
        raise CandidateRejected("Invalid transformation list")
    kept = data["sources_kept"]
    if (
        not isinstance(kept, list)
        or any(s not in source_ids for s in kept)
        or len(set(kept)) != len(kept)
    ):
        raise CandidateRejected("Unknown or repeated integration source")
    files = data["files"]
    if not isinstance(files, list) or not 1 <= len(files) <= 20:
        raise CandidateRejected("Expected one to twenty source files")
    result, seen, total = [], set(), 0
    if (worktree / "src").is_symlink():
        raise CandidateRejected("Source root must not be a symlink")
    src_root = (worktree / "src").resolve()
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "content"}:
            raise CandidateRejected("Invalid source file object")
        name, content = item["path"], item["content"]
        if not isinstance(name, str) or not isinstance(content, str):
            raise CandidateRejected("Source path and content must be text")
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or "\\" in name
            or ":" in name
            or "\0" in name
            or ".." in path.parts
            or len(path.parts) < 2
            or path.parts[0] != "src"
            or any(part.startswith(".") for part in path.parts)
        ):
            raise CandidateRejected("Local model attempted to write outside allowed source paths")
        destination = worktree.joinpath(*path.parts)
        if src_root not in destination.resolve().parents or destination.is_symlink():
            raise CandidateRejected("Source path escapes its worktree")
        if destination.exists() and not destination.is_file():
            raise CandidateRejected("Source destination is not a regular file")
        key = name.casefold()
        if key in seen:
            raise CandidateRejected("Repeated source destination")
        seen.add(key)
        total += len(content.encode("utf-8"))
        if total > 1024 * 1024:
            raise CandidateRejected("Source result exceeds one MiB")
        result.append((destination, content))
    return result


class OllamaBackend:
    supports_harness_research = True

    def generate(self, mission: Mission, context: dict, config: dict, root: Path) -> Generated:
        if mission.role == "G" and not context.get("sources"):
            return Generated(error="No admissible integration sources")
        deadline = generation_deadline(context, config["budget"]["generation_seconds"])
        if expired(deadline):
            return Generated(
                0, {"llm_calls": 0, "generation_not_started": "search_deadline"},
                error="Search generation deadline reached before invocation",
            )
        settings = config["ollama"]
        # Verify the installed weights before every proposal, without generating text.
        current = resolve_model(settings)
        if current["server_version"] != settings.get("server_version"):
            raise InfrastructureError("Ollama server version changed during the campaign")
        worktree = Path(mission.worktree)
        rendered = proposal_messages(worktree, mission, context)
        payload = {
            "model": settings["model"],
            "stream": False,
            "format": rendered["schema"],
            "messages": rendered["messages"],
            "keep_alive": "5m",
            "options": {
                "temperature": settings["temperature"],
                "seed": config["seed"] + mission.ordinal,
                "num_ctx": settings["context_tokens"],
                "num_predict": settings["max_output_tokens"],
                "num_thread": settings["num_threads"],
                **{key: settings[key] for key in ["repeat_penalty", "repeat_last_n"] if key in settings},
            },
        }
        if unlimited_tokens(config):
            payload["options"]["num_predict"] = -1
            payload["options"].pop("num_ctx")
        logs = root / "logs" / mission.id
        atomic_json(logs / "ollama-request.json", payload)
        start = time.monotonic()
        timeout = time_left(deadline)
        try:
            response = request_json(settings["base_url"], "/api/chat", payload, timeout)
        except RepetitionAborted as exc:
            # Legacy requests reserve num_ctx + num_predict. Uncapped requests
            # have no such bound; never invent exact usage or replay the request.
            ceiling = None if unlimited_tokens(config) else settings["context_tokens"] + settings["max_output_tokens"]
            usage = {
                "backend": "ollama", "llm_calls": 1, "model": settings["model"],
                "model_digest": current["model_digest"], "server_version": current["server_version"],
                "seconds": time.monotonic() - start,
                "token_accounting": "unknown" if ceiling is None else "upper_bound",
                "exact_tokens": None, "token_ceiling": ceiling, "done_reason": "repetition_abort",
            }
            atomic_json(logs / "ollama-error.json", {"error": str(exc), **usage})
            return Generated(ceiling, usage, str(exc), infrastructure_error=True,
                             tokens_upper_bound=ceiling is not None)
        atomic_json(logs / "ollama-response.json", response)
        keys = ["prompt_eval_count", "eval_count"]
        known = all(type(response.get(k)) is int and response[k] >= 0 for k in keys)
        generated = Generated(
            sum(response[k] for k in keys) if known else None,
            {
                "backend": "ollama",
                "llm_calls": 1,
                "model": settings["model"],
                "model_digest": current["model_digest"],
                "server_version": current["server_version"],
                "seconds": time.monotonic() - start,
                **{
                    k: response.get(k)
                    for k in [
                        *keys,
                        "total_duration",
                        "load_duration",
                        "eval_duration",
                        "done_reason",
                    ]
                },
            },
        )
        if response.get("model") != settings["model"] or response.get("done") is not True:
            generated.error = "Inference returned an unexpected model or incomplete result"
            return generated
        if response.get("done_reason") == "length":
            generated.error = "Model output token limit reached; truncated proposal was not applied"
            return generated
        try:
            data = json.loads(response["message"]["content"])
            from .memory_contract import extract_memory

            data, memory_read, lessons = extract_memory(data, context)
            data, research = extract_research(data, context)
            if context.get("memory", {}).get("enabled"):
                generated.usage["memory_lessons"] = lessons
            if memory_read is not None:
                generated.usage["memory_request"] = memory_read
                atomic_json(logs / "agent-memory-request.json", memory_read)
                return generated
            if research is not None:
                generated.usage["research_request"] = research
                atomic_json(logs / "agent-research-request.json", research)
                return generated
            edits = validate_files(worktree, data, mission.sources)
            # Validate the entire response before applying any source edit.
            for destination, content in edits:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content, encoding="utf-8", newline="")
            mission.hypothesis = data["hypothesis"][:3000]
            mission.transformations = {
                "retained": data["transformations"],
                "files": [p.relative_to(worktree).as_posix() for p, _ in edits],
            }
            source_map = dict(zip(mission.sources, mission.source_commits, strict=True))
            mission.sources = data["sources_kept"]
            mission.source_commits = [source_map[s] for s in mission.sources]
            atomic_json(logs / "agent-result.json", data)
        except (CandidateRejected, ValueError, KeyError, TypeError) as exc:
            generated.error = f"Invalid local model proposal: {exc}"
        return generated
