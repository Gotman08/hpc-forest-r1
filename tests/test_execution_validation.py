import copy
import json

import pytest

from hpc_forest.core import ForestError, InfrastructureError, Outcome, file_digest
from hpc_forest.evaluator import Evaluator
from hpc_forest.execution_validation import (
    allocation_evidence,
    assess_parallelism,
    environment,
    read_probe,
    requirements,
)


def contract(threads=4):
    return requirements({"cpus_per_task": threads, "required_threads": threads,
                         "sockets_per_node": 2, "parallelism": "gnu_openmp_required"})


def allocation(threads=4):
    topology = [{"cpu": i, "core": i % (threads // 2), "socket": i // (threads // 2)}
                for i in range(threads)]
    return allocation_evidence(contract(threads), affinity=list(range(threads)), topology=topology,
                               environ={"SLURM_JOB_ID": "123", "SLURM_JOB_NUM_NODES": "1"})


def region(threads=4):
    return {"schema": "forest-gomp-region-v1", "error": 0, "threads": [
        {"tid": 100+i, "index": i, "team": threads, "cpu": i, "end_cpu": i,
         "affinity_count": 1, "work_cpu_ns": 600000, "start_ns": 1000, "end_ns": 1001000}
        for i in range(threads)]}


@pytest.mark.parametrize("threads", [4, 32, 192])
def test_contract_scales_without_fixed_cpu_count(threads):
    c = contract(threads)
    assert environment(c)["OMP_NUM_THREADS"] == str(threads)
    observed = allocation(threads)
    assert observed["status"] == "passed"
    assert assess_parallelism(c, [region(threads)], observed)["status"] == "passed"


@pytest.mark.parametrize("change", [
    {"cpus_per_task": True}, {"nodes": 2}, {"required_threads": 5},
    {"sockets_per_node": False}, {"parallelism": "invented"}, {"unknown": 1},
    {"min_parallel_cpu_ratio": float("nan")}, {"omp_places": "anything"},
])
def test_invalid_or_unsupported_contract_fails_closed(change):
    with pytest.raises(ForestError):
        requirements(contract() | change)


def test_historical_contract_is_not_retroactively_verified():
    assert requirements(None) is None
    assert environment(None) == {}


def test_controller_rechecks_allocation_without_freezing_observation_time(
        monkeypatch, tmp_path, config, need_compiler):
    import hpc_forest.evaluator as module
    from hpc_forest.controller import Controller, create_workspace

    evidence = allocation()
    observed_times = []

    def observe(_):
        result = copy.deepcopy(evidence)
        result["observed_at"] = 1000.0 + len(observed_times)
        observed_times.append(result["observed_at"])
        return result

    monkeypatch.setattr(module, "allocation_evidence", observe)
    config["execution_validation"] = contract()
    root = create_workspace(tmp_path / "campaign", config)
    with Controller(root) as controller:
        controller._start()
        assert controller.db.get("started") is not None
        assert module.target_identity(controller.config) == controller.db.get("identity")
    assert len(set(observed_times)) >= 3


@pytest.mark.parametrize("field,value", [
    ("allowed_cpus", [4, 5, 6, 7]), ("job_id", "124"),
    ("physical_cores", 2), ("sockets", [0]),
])
def test_controller_still_rejects_changed_allocation(
        monkeypatch, tmp_path, config, need_compiler, field, value):
    import hpc_forest.evaluator as module
    from hpc_forest.controller import Controller, create_workspace

    evidence = allocation()
    monkeypatch.setattr(module, "allocation_evidence", lambda _: copy.deepcopy(evidence))
    config["execution_validation"] = contract()
    root = create_workspace(tmp_path / "campaign", config)
    evidence[field] = value
    with Controller(root) as controller, pytest.raises(InfrastructureError, match="Target changed"):
        controller._start()


def test_public_mission_exposes_only_normalized_validation_requirements():
    from hpc_forest.webapp.execution import public_mission

    record = {"id": "prepared", "launch": {"execution_validation": contract(),
              "dsh_romeo": {"api_key_file": "/private/key"}}, "connection": {"secret": "hidden"}}
    public = public_mission(record)
    assert public["execution_validation"] == contract()
    assert not {"launch", "connection"} & public.keys()
    assert "private/key" not in json.dumps(public)
    record["launch"]["execution_validation"]["unexpected_secret"] = "hidden"
    public = public_mission(record)
    assert public["execution_validation"] is None and public["execution_validation_error"]
    assert "hidden" not in json.dumps(public)


def test_allocation_uses_real_affinity_and_socket_topology():
    assert allocation_evidence(contract(), affinity=[0, 1], topology=[
        {"cpu": 0, "core": 0, "socket": 0}, {"cpu": 1, "core": 1, "socket": 0}],
        environ={"SLURM_JOB_ID": "123", "SLURM_JOB_NUM_NODES": "1"})["status"] == "failed"
    assert allocation_evidence(contract(), affinity=[0, 1, 2, 3], topology=allocation()["topology"],
                               environ={})["status"] == "failed"


@pytest.mark.parametrize("case", ["serial", "empty", "master_only", "undersized", "repeated_tid",
                                  "same_cpu", "unpinned", "runtime_only", "not_simultaneous"])
def test_idle_or_wrong_workers_do_not_satisfy_required_parallelism(case):
    r = region()
    if case == "serial":
        records = []
    else:
        records = [r]
        if case == "empty":
            for row in r["threads"]:
                row["work_cpu_ns"] = 100
        elif case in {"master_only", "runtime_only"}:
            for row in r["threads"][1:]:
                row["work_cpu_ns"] = 0
        elif case == "undersized":
            r["threads"] = r["threads"][:2]
        elif case == "repeated_tid":
            r["threads"][1]["tid"] = r["threads"][0]["tid"]
        elif case == "same_cpu":
            r["threads"][1].update(cpu=0, end_cpu=0)
        elif case == "unpinned":
            r["threads"][1]["affinity_count"] = 4
        elif case == "not_simultaneous":
            for row in r["threads"]:
                row["end_ns"] = 10000000
    assert assess_parallelism(contract(), records, allocation())["status"] == "failed"


def test_malformed_probe_and_wrong_allocation_are_infrastructure_failures():
    malformed = region()
    malformed["threads"][0]["work_cpu_ns"] = "claimed"
    for records, observed in (([malformed], allocation()), ([region()], {"status": "failed"}),
                               ([region() | {"error": 1}], allocation())):
        with pytest.raises(InfrastructureError):
            assess_parallelism(contract(), records, observed)


def test_probe_receipt_is_tied_to_unchanged_executable(tmp_path):
    binary, trace = tmp_path / "binary", tmp_path / "trace.jsonl"
    binary.write_bytes(b"original executable")
    sha = file_digest(binary)
    trace.write_text(json.dumps({"schema": "forest-gomp-probe-v1", "loaded": True}) + "\n" +
                     json.dumps(region()) + "\n", encoding="utf-8")
    evidence = read_probe(contract(), trace, allocation(), binary, sha, tmp_path / "proof.json")
    assert evidence["status"] == "passed"
    binary.write_bytes(b"different executable")
    with pytest.raises(InfrastructureError, match="changed"):
        read_probe(contract(), trace, allocation(), binary, sha, tmp_path / "proof.json")


def test_smt_placement_follows_configured_physical_core_capacity():
    c = contract() | {"threads_per_core": 2}
    topology = [{"cpu": i, "core": 0, "socket": i // 2} for i in range(4)]
    a = allocation_evidence(c, affinity=list(range(4)), topology=topology,
                           environ={"SLURM_JOB_ID": "123", "SLURM_JOB_NUM_NODES": "1"})
    r = region()
    for i, row in enumerate(r["threads"]):
        row.update(cpu=2*(i//2), end_cpu=2*(i//2)+1, affinity_count=2)
    assert assess_parallelism(c, [r], a)["status"] == "passed"
    assert assess_parallelism(c | {"omp_places": "threads"}, [r], a)["status"] == "failed"
    r["threads"][2].update(cpu=0, end_cpu=1)
    assert assess_parallelism(c, [r], a)["status"] == "failed"


def test_truncated_observation_is_not_scored_as_incorrect(tmp_path):
    binary, trace = tmp_path / "binary", tmp_path / "trace"
    binary.write_bytes(b"executable")
    records = [{"schema": "forest-gomp-probe-v1", "loaded": True},
               {"schema": "forest-gomp-limit-v1"}]
    trace.write_text("\n".join(map(json.dumps, records)), encoding="utf-8")
    with pytest.raises(InfrastructureError, match="observation limit"):
        read_probe(contract(), trace, allocation(), binary, file_digest(binary), tmp_path / "proof")
    trace.write_text("\n".join(map(json.dumps, records + [region()])), encoding="utf-8")
    result = read_probe(contract(), trace, allocation(), binary, file_digest(binary), tmp_path / "proof")
    assert result["status"] == "passed" and result["trace_truncated"]


@pytest.mark.parametrize("other_region", [False, True])
def test_unsupported_runtime_cannot_be_scored_or_hidden_by_another_region(tmp_path, other_region):
    binary, trace = tmp_path / "binary", tmp_path / "trace"
    binary.write_bytes(b"executable")
    records = [{"schema": "forest-gomp-probe-v1", "loaded": True},
               {"schema": "forest-gomp-unsupported-v1", "api": "GOMP_parallel_reductions"}]
    if other_region:
        records.append(region())
    trace.write_text("\n".join(map(json.dumps, records)), encoding="utf-8")
    with pytest.raises(InfrastructureError, match="Unsupported GNU OpenMP"):
        read_probe(contract(), trace, allocation(), binary, file_digest(binary), tmp_path / "proof")
    assert not (tmp_path / "proof").exists()


def test_baseline_is_explicit_reference_and_never_probe_pass(monkeypatch, tmp_path):
    import hpc_forest.evaluator as module

    monkeypatch.setattr(module, "allocation_evidence", lambda _: allocation())
    evaluator = object.__new__(Evaluator)
    evaluator.config = {"execution_validation": contract()}
    outcome = Outcome("pending", correct=True)
    evaluator._execution_check(outcome, {"_baseline_reference": True}, tmp_path)
    assert outcome.correct is True
    assert outcome.execution_validation["parallelism"]["status"] == "reference_only"


def test_web_contract_changes_resources_without_editing_old_project():
    from hpc_forest.webapp.projects import infer_contract, validate_contract

    original = infer_contract([("main.c", b"int main(){return 0;}")])
    retained = copy.deepcopy(original)
    value = validate_contract(original | {"execution_validation": contract(192)})
    assert value["execution_validation"]["required_threads"] == 192
    assert original == retained
    assert validate_contract(original)["execution_validation"] is None


def test_web_launch_uses_configured_cpu_count():
    from hpc_forest.webapp.execution import job_arguments

    launch = {"target": "cpu", "allocation_seconds": 10800, "execution_validation": contract(192)}
    settings = {"base_dir": "/project/test", "codex_home": "/project/native", "profiles": {
        "cpu": {"python": "/usr/bin/python3"}}}
    result = job_arguments({"id": "abcd"}, settings, launch, "a" * 64)
    assert result["nodes"] == 1 and result["cpus_per_task"] == 192
    assert result["time_limit"] == "03:00:00"


def test_confirmation_cannot_promote_faster_sequential_program_or_baseline():
    from hpc_forest.controller import select_confirmed_program

    def item(name, seconds, status):
        return {"experiment_id": name, "outcome": {"correct": True, "mean_seconds": seconds,
                "execution_validation": {"parallelism": {"status": status}}}}

    rows = [item("baseline-e1", .001, "reference_only"),
            item("sequential", .0001, "failed"), item("parallel", .01, "passed")]
    c = {"execution_validation": contract(), "minimum_gain": .03}
    reference, winner, gain = select_confirmed_program(rows, "baseline-e1", c)
    assert reference is rows[0] and winner is rows[2] and gain == -9
    with pytest.raises(ForestError, match="parallel execution contract"):
        select_confirmed_program(rows[:2], "baseline-e1", c)
    rows[0]["outcome"]["execution_validation"]["parallelism"]["status"] = "passed"
    with pytest.raises(ForestError, match="parallel execution contract"):
        select_confirmed_program(rows[:1], "baseline-e1", c)


def test_budget_shortened_observation_retains_no_score(monkeypatch, tmp_path):
    from types import SimpleNamespace

    import hpc_forest.evaluator as module

    monkeypatch.setattr(module, "allocation_evidence", lambda _: allocation())
    monkeypatch.setattr(module, "build_probe", lambda _: tmp_path / "probe.so")
    monkeypatch.setattr(module, "run_process", lambda *args: SimpleNamespace(
        timed_out=True, returncode=-1, log=str(tmp_path / "run.log")))
    e = object.__new__(Evaluator)
    e.config = {"execution_validation": contract()}
    e.protocol = {"environment": {}, "benchmark": ["{binary}"], "timeout_seconds": 100}
    e.deadline = 1
    monkeypatch.setattr(e, "_timeout", lambda: .01)
    o = Outcome("pending", correct=True)
    e._execution_check(o, {"binary": str(tmp_path / "binary"), "worktree": str(tmp_path)}, tmp_path)
    assert o.status == "cancelled_budget" and o.score is None and o.correct is None
