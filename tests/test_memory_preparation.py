"""The CUDA preparer freezes inputs without optimizing them or allocating HPC."""
import json
import runpy
import tarfile
from pathlib import Path

import pytest

from hpc_forest.core import file_digest


def test_fresh_cuda_memory_payload_has_original_source_and_exact_validator(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    prepare = runpy.run_path(str(repo / "examples/cuda_nbody/prepare_memory.py"))["prepare"]
    source = tmp_path / "input/nbody_naive.cu"
    source.parent.mkdir()
    original = ('#include <stdio.h>\n// Structure\nstruct Particle { float x; };\n'
                '__global__ void nbody_step_naive(const Particle* a, Particle* b, int n, float dt) {}\n'
                'int main() { return 0; }\n')
    source.write_text(original, encoding="utf8")
    optimizer = source.parent / "optimizer"
    (optimizer / "optimizer_agent").mkdir(parents=True)
    (optimizer / "optimizer_agent/use_harness.py").write_text("# offline transfer fixture\n")
    (optimizer / "SOURCE_COMMIT.txt").write_text("offline-fixture\n")
    (optimizer / "cuda_test_harness").mkdir()
    (optimizer / "cuda_test_harness/CMakeLists.txt").write_text("# never executed by preparation\n")
    destination = tmp_path / "prepared"
    state = prepare(source, destination, repo, wall_seconds=1800)
    assert state["allocation_submitted"] is False
    assert source.read_text(encoding="utf8") == original
    payload = destination / "payload"
    assert (payload / "validation/original.cu").read_text(encoding="utf8") == original
    kernel = (payload / "source/src/nbody_kernel.cu").read_text(encoding="utf8")
    assert kernel == original[original.index("// Structure"):original.index("int main()")].replace(
        "__global__ void nbody_step_naive(", 'extern "C" __global__ void nbody_step_naive(', 1)
    assert file_digest(payload / "validation/protocol.py") == file_digest(repo / "examples/cuda_nbody/protocol.py")
    config = json.loads((payload / "settings.json").read_text())
    assert config["codex"]["model"] == "gpt-6-luna" and config["codex"]["reasoning_effort"] == "max"
    assert config["memory"]["mode"] == "active"
    assert config["forest"]["integration"] == "memory-guided-v1"
    assert "children" not in config["forest"]  # Mother, not preparation, chooses N and the subjects.
    manifest = json.loads((payload / "runtime-manifest.json").read_text())
    assert all(file_digest(payload / name) == sha for name, sha in manifest.items())
    with tarfile.open(destination / "payload.tar.gz") as archive:
        assert "project/src/hpc_forest/memory_store.py" in archive.getnames()
        assert not any("experiments/" in name or "registry.sqlite3" in name for name in archive.getnames())
    with pytest.raises(FileExistsError):
        prepare(source, destination, repo)
