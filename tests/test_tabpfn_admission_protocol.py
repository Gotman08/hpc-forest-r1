"""A timed-out candidate fails the unchanged checks; it cannot pass or train as fast."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("case", ["utf8", "mandelbrot"])
def test_candidate_timeout_is_not_an_infrastructure_failure(tmp_path, monkeypatch, capsys, case):
    source = Path(__file__).resolve().parents[1] / f"experiments/tabpfn-admission-20261025/inputs/{case}/validation"
    config = json.loads((source / "case.json").read_text())
    config["suite"] = str(tmp_path)
    config["trusted_files"] = {}
    (tmp_path / "case.json").write_text(json.dumps(config))
    (tmp_path / "protocol.py").write_text((source / "protocol.py").read_text())
    spec = importlib.util.spec_from_file_location("new_timeout_protocol", tmp_path / "protocol.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys, "argv", ["protocol.py", "check", "solution", "search"])
    def timeout(cmd, **kwargs):
        assert kwargs["timeout"] == 180
        raise subprocess.TimeoutExpired(cmd, 180)
    monkeypatch.setattr(module.subprocess, "run", timeout)
    assert module.main() == 1
    data = json.loads(capsys.readouterr().out)
    assert data["correct"] is False and data["details"][0]["error"] == "candidate_timeout"
    assert "seconds" not in data
