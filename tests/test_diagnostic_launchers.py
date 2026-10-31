"""Regression checks for profiler placement; synthetic profilers are explicit."""
import subprocess
import sys

import pytest

from hpc_forest import diagnostic_collectors as collectors


def test_nsys_executes_python_protocol_and_its_child_without_rewriting_arguments(tmp_path):
    """Execute the real wrapper/child; the shim only imitates Nsight's CLI boundary."""
    binary = tmp_path / "program.py"
    marker = tmp_path / "executed.txt"
    binary.write_text("import pathlib,sys\npathlib.Path(sys.argv[1]).write_text('child executed')\n")
    wrapper = tmp_path / "protocol.py"
    wrapper.write_text(
        "import argparse,subprocess,sys\n"
        "p=argparse.ArgumentParser()\n"
        "p.add_argument('action',choices=['benchmark'])\n"
        "p.add_argument('binary')\n"
        "p.add_argument('phase',choices=['search'])\n"
        "a=p.parse_args()\n"
        f"subprocess.run([sys.executable,a.binary,{str(marker)!r}],check=True)\n")
    shim = tmp_path / "synthetic_nsys.py"
    shim.write_text(
        "import pathlib,subprocess,sys\n"
        "args=sys.argv[1:]\nassert args[0]=='profile'\n"
        "start=next(i for i in range(1,len(args)) if not args[i].startswith('--'))\n"
        "subprocess.run(args[start:],check=True)\n"
        "out=next(a.split('=',1)[1] for a in args[1:start] if a.startswith('--output='))\n"
        "pathlib.Path(out+'.nsys-rep').write_text('synthetic CLI test, not a GPU profile')\n"
        "pathlib.Path(out+'.sqlite').touch()\n")
    workload = [sys.executable, str(wrapper), "benchmark", str(binary), "search"]
    calls = []

    def run(argv, name, **kwargs):
        calls.append(argv)
        if name == "nsys-profile":
            assert argv[0] == "nsys"
            subprocess.run([sys.executable, str(shim), *argv[1:]], check=True, timeout=15)

    collectors.collect("nsys", {}, workload, binary, tmp_path, run, {"nsys": "nsys"})
    assert marker.read_text() == "child executed"
    assert calls[0][-len(workload):] == workload
    assert "--output=" + str(tmp_path / "timeline") in calls[0]


@pytest.mark.parametrize("prefix", [
    ["srun", "-n", "2"],
    ["/opt/mpi/bin/mpirun", "--map-by", "node", "-np2"],
    ["mpiexec", "--hostfile=hosts.txt", "-n", "2", "--"],
])
def test_rank_instrumentation_precedes_the_rank_wrapper_not_its_binary_argument(tmp_path, prefix):
    binary = tmp_path / "solution.json"
    rank = [sys.executable, "protocol.py", "benchmark", str(binary), "search"]
    calls = []
    collectors.collect("hpctoolkit", {}, prefix + rank, binary, tmp_path,
                       lambda argv, name, **kw: calls.append(argv),
                       {"hpcrun": "hpcrun", "hpcstruct": "hpcstruct", "hpcprof": "hpcprof"})
    assert calls[0][:len(prefix) + 1] == prefix + ["hpcrun"]
    assert calls[0][-len(rank):] == rank
    with pytest.raises(ValueError, match="MPI kernel replay"):
        collectors.collect("ncu", {}, prefix + rank, binary, tmp_path,
                           lambda *a, **kw: pytest.fail("Must not start MPI replay"), {"ncu": "ncu"})


def test_ncu_profiles_the_python_process_tree_instead_of_misclassifying_it_as_mpi(tmp_path):
    binary = tmp_path / "solution.json"
    workload = [sys.executable, "protocol.py", "benchmark", str(binary), "search"]
    calls = []
    collectors.collect("ncu", {}, workload, binary, tmp_path,
                       lambda argv, name, **kw: calls.append(argv), {"ncu": "ncu"})
    assert calls[0][:3] == ["ncu", "--target-processes", "all"]
    assert calls[0][-len(workload):] == workload


@pytest.mark.parametrize("workload", [
    ["mpirun", "--unknown-option", "some-value", "program"],
    ["mpirun", "-n", "2"],
    ["mpirun", "--"],
    ["mpirun", "-n", "1", "first", ":", "-n", "1", "second"],
    ["env", "OMP_NUM_THREADS=1", "srun", "-n", "2", "program"],
])
def test_ambiguous_mpi_syntax_is_rejected_before_any_profiler_runs(tmp_path, workload):
    with pytest.raises(ValueError, match="MPI|MPMD"):
        collectors.collect("nsys", {}, workload, tmp_path / "program", tmp_path,
                           lambda *a, **kw: pytest.fail("Must not guess a launcher boundary"),
                           {"nsys": "nsys"})
