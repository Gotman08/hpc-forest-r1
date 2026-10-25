"""Archive evidence must reach real control requests without broadening tree scope."""
import json

import pytest
from test_active_architecture import action, campaign, decision, trial  # noqa: F401

from hpc_forest import active_control as controls
from hpc_forest.active_analysis import packet
from hpc_forest.active_snapshot import freeze
from hpc_forest.active_state import apply
from hpc_forest.core import Outcome
from hpc_forest.evolution_archive import record


@pytest.mark.parametrize(("kind", "shared"), [("analyst", False), ("analyst", True), ("mother", False)])
def test_archive_reaches_control_request_and_can_be_read_outside_first_page(campaign, monkeypatch, kind, shared):  # noqa: F811
    campaign.config["evolution"] = {"enabled": True}
    campaign.db.set("config", campaign.config)
    monkeypatch.setattr("hpc_forest.tree_observer.PAGE_SIZE", 1)
    monkeypatch.setattr("hpc_forest.evolution_archive.committed_source_snapshot",
                        lambda root, commit: {"src/main.c": "int " + commit + ";"})
    slow, fast, other = trial(campaign, "T1", 14), trial(campaign, "T1", 8), trial(campaign, "T2", 6)
    for mission in (slow, fast, other):
        result = json.loads(campaign.db.one("SELECT result FROM trials WHERE id=?", (mission.id,))["result"])
        record(campaign, mission, Outcome(**result))
    if shared:
        snap = freeze(campaign, 1)
        apply(campaign.db, 1, "share", snap, decision(snap, action("share", "T1", [other.id])))
    job = controls.create(campaign, 1, kind, "T1" if kind == "analyst" else None)
    assert slow.id not in {r["id"] for r in job["history"][0]["view"]["items"]}
    request, _, _ = controls.begin_call(campaign, job)
    payload = json.loads(request["messages"][-1]["content"])
    entries = {item["id"] for item in payload["diverse_measured_sources"]["entries"]}
    expected = {slow.id, fast.id} | ({other.id} if shared or kind == "mother" else set())
    assert entries == expected
    assert entries <= set(payload["visible_evidence_ids"])
    if other.id not in expected:
        assert other.id not in payload["visible_evidence_ids"]
    source = controls.view(controls.snapshot(campaign, job), {
        "operation": "source", "evidence_id": slow.id, "path": "src/main.c", "offset": 0})
    assert "int T11;" in source["text"]
    assert request["model"] == "gpt-6-luna" and request["reasoning_effort"] == "max"


def test_code_packet_adds_archived_alternative_without_replacing_latest_or_importing_hidden_code():
    def evidence(identity, seconds, kind="trial"):
        return {"id": identity, "kind": kind, "mission": {"role": "T1", "parent_id": "baseline-e1"},
                "outcome": {"correct": True, "mean_seconds": seconds, "commit": identity},
                "source_files": {"src/main.c": "int " + identity.replace("-", "_") + ";\n"}}

    dossier = {"epoch": 1, "role": "T1", "records": [evidence("baseline-e1", 10, "baseline"),
        evidence("latest", 8), evidence("recent", 7), evidence("best", 1), evidence("oldslow", 14)]}
    assert "oldslow" not in packet(dossier)["selected_ids"]
    dossier["diverse_measured_sources"] = {"entries": [{"id": "hidden-other-tree"}, {"id": "oldslow"}]}
    value = packet(dossier)
    assert value["selected_ids"] == ["latest", "baseline-e1", "best", "oldslow"]
    assert any(page["evidence_id"] == "oldslow" and "int oldslow;" in page["text"] for page in value["sources"])
