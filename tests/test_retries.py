import json
from pathlib import Path

from hpc_forest.backends import Generated
from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import ProcessResult
from hpc_forest.evaluator import Evaluator


def test_transient_infrastructure_retry_preserves_both_logs_and_one_observation(
    tmp_path, config, monkeypatch, need_compiler
):
    real = Evaluator._run
    failed = False

    def transient(self, name, variables, log, build=False, **kwargs):
        nonlocal failed
        if name == "build" and "baseline-e" not in str(log) and not failed:
            failed = True
            log.write_text("temporary compiler service failure", encoding="utf-8")
            return ProcessResult(["contract-fixture"], 70, 0.001, False, str(log))
        return real(self, name, variables, log, build, **kwargs)

    monkeypatch.setattr(Evaluator, "_run", transient)
    config["roles"] = ["A"]
    config["budget"].update(search_slots=2, infrastructure_retries=1)
    root = create_workspace(tmp_path / "retry", config)
    with Controller(root) as controller:
        controller.run()
        trials = controller.db.rows("SELECT * FROM trials")
        assert len(trials) == 1
        outcome = json.loads(trials[0]["result"])
        assert outcome["status"] == "valid"
        assert controller.db.costs()["slots"] == 2
        assert len(controller.db.archive(1, "A")) == 1
        history = root / "logs" / "e1" / trials[0]["id"] / "search"
        assert len(list(history.glob("attempt-*"))) == 2
        assert "temporary" in (history / "attempt-001" / "build.log").read_text()
        assert Path(outcome["logs"][0]).parent.name == "attempt-002"


def test_bounded_generation_abort_preserves_no_reward_and_allows_later_mission(tmp_path,config,need_compiler):
    config["roles"]=["A"]
    config["schedule"].update(trials_per_role_per_cycle=2,integrations_per_cycle=1)
    config["budget"].update(search_slots=4,tokens=100)
    root=create_workspace(tmp_path/"bounded-abort",config)
    calls=[]

    class Backend:
        def generate(self,mission,context,settings,folder):
            if mission.role=="G":
                return Generated(error="No admissible integration sources")
            calls.append(mission.id)
            if len(calls)==1:
                return Generated(80,{"llm_calls":1,"token_accounting":"upper_bound"},"prediction aborted",True,True)
            return Generated(15,{"llm_calls":1},"proposal rejected by result contract")

    with Controller(root) as controller:
        controller.backend=Backend()
        state=controller.run()
        assert state["status"]=="search_complete" and len(calls)==2
        assert state["costs"]["tokens_used"]==95
        assert state["costs"]["bounded_usage_calls"]==1 and state["costs"]["unknown_usage_calls"]==0
        row=controller.db.one("SELECT result FROM trials WHERE id=?",(calls[0],))
        outcome=json.loads(row["result"])
        assert outcome["status"]=="infrastructure_error" and outcome["score"] is None
        assert not controller.db.archive(1,"A")
