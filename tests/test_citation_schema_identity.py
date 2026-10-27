"""Regression: native constrained generation must emit citations we can accept."""
import copy

import pytest

from hpc_forest.active_analysis import citation_exposed, citation_schema, schema
from hpc_forest.active_contract import decision_schema
from hpc_forest.codex_process import wire_schema


@pytest.fixture
def pages():
    return [{"evidence_id": "trial-a", "path": "src/a.cpp", "sha256": "a" * 64,
             "start_line": 2, "end_line": 8},
            {"evidence_id": "baseline-e1", "path": "src/b.cpp", "sha256": "b" * 64,
             "start_line": 20, "end_line": 25}]


@pytest.mark.parametrize("role", ["analyst", "mother"])
def test_native_schema_citations_are_accepted_by_the_source_validator(pages, role):
    payload = {"code_packet": {"sources": pages}, "closure_code_packet": {"sources": pages},
               "trees": {"T1": {}}, "snapshot_id": "snapshot", "plan_revision": 0, "closure_guard": True,
               "visible_evidence_ids": [p["evidence_id"] for p in pages]}
    if role == "analyst":
        native = wire_schema(schema(True, payload))
        references = native["properties"]["code_findings"]["items"]["properties"]["citations"]["items"]
    else:
        native = wire_schema(decision_schema(True, payload))
        closing = next(v for v in native["properties"]["decisions"]["items"]["anyOf"]
                       if v["properties"]["kind"]["enum"] == ["close"])
        references = closing["properties"]["hypothesis_review"]["items"]["properties"]["source_citations"]["items"]
    for branch in references["anyOf"]:
        fields = branch["properties"]
        # A constrained model can only return these identities. The runtime must
        # accept that citation for the exact supplied page and reject substitutions.
        ref = {k: fields[k]["enum"][0] for k in ("evidence_id", "path", "sha256")}
        ref.update(start_line=fields["start_line"]["minimum"], end_line=fields["end_line"]["maximum"])
        assert citation_exposed(ref, pages), ref
        assert not citation_exposed({**ref, "path": "unseen.cpp"}, pages)


def test_schema_generation_cannot_cross_contaminate_fields_pages_or_later_requests(pages):
    first = citation_schema(pages)
    saved = copy.deepcopy(first)
    later = citation_schema([{**pages[0], "evidence_id": "new-trial", "path": "src/new.cpp"}])
    assert first == saved
    for page, branch in zip(pages, first["anyOf"], strict=True):
        for field in ("evidence_id", "path", "sha256"):
            assert branch["properties"][field]["enum"] == [page[field]]
    assert later["anyOf"][0]["properties"]["evidence_id"]["enum"] == ["new-trial"]
