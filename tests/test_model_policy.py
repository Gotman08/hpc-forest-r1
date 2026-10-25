"""The current series cannot silently fall back to a host-selected model/effort."""
import copy
import json
from types import SimpleNamespace

import pytest

from hpc_forest import backends
from hpc_forest.codex_mailbox import publish_request
from hpc_forest.config import load_config, validate
from hpc_forest.core import InfrastructureError, Mission
from hpc_forest.model_policy import EFFORT, MODEL


@pytest.mark.parametrize("model,effort", [(None, "max"), ("unknown", "max"),
                                        ("gpt-6-luna", "ultra"), ("gpt-6-luna", None)])
def test_config_and_mailbox_refuse_identity_drift(tmp_path, model, effort):
    config = load_config()
    config["backend"] = "codex"
    config["codex"].update(model=model, reasoning_effort=effort)
    with pytest.raises(InfrastructureError, match="Unsupported Forest"):
        validate(config)
    with pytest.raises(InfrastructureError, match="Unsupported Forest"):
        publish_request(tmp_path, {"nonce": "a" * 32, "model": model, "reasoning_effort": effort})


@pytest.mark.parametrize("model,effort", [(MODEL, EFFORT), ("gpt-6.1-sol", "ultra"), ("gpt-6-astra", "high")])
def test_direct_backend_passes_model_and_effort_explicitly(tmp_path, monkeypatch, model, effort):
    config = load_config()
    config["backend"] = "codex"
    config["codex"].update(model=model, reasoning_effort=effort)
    mission = Mission("m", "t", "trial", 1, "A", "base", None, "mother", 0, 1, str(tmp_path))
    monkeypatch.setattr(backends.shutil, "which", lambda _: "codex.exe")
    def process(argv, cwd, log, timeout, **kwargs):
        assert argv[argv.index("--model") + 1] == model
        assert f'model_reasoning_effort="{effort}"' in argv
        log.write_text(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 2}}))
        (log.parent / "agent-result.json").write_text(json.dumps({
            "hypothesis": "test", "transformations": [], "sources_kept": [], "notes": "test"}))
        return SimpleNamespace(returncode=0, timed_out=False, log=str(log))
    monkeypatch.setattr(backends, "run_process", process)
    result = backends.CodexBackend().generate(mission, {"deadline_policy": "finish-started"},
                                             copy.deepcopy(config), tmp_path)
    assert result.error is None and result.usage["reasoning_effort_requested"] == effort
