import copy
import hashlib
import io
import json
import socket
import time
from email.message import Message

import pytest

from hpc_forest.core import CandidateRejected, InfrastructureError, atomic_json
from hpc_forest.harness_research import DocumentationReader, extract_research, research_contract
from hpc_forest.ollama_backend import SOURCE_SCHEMA


def action(**changes):
    return {"hypothesis": "documentation read fixture", "notes": "fixture", "transformations": [],
            "sources_kept": [], "files": [], "research": {"queries": ["fixture"], "urls": []}, **changes}


def test_mixed_contract_is_explicit_and_default_contract_is_unchanged():
    original = copy.deepcopy(SOURCE_SCHEMA)
    system, schema = research_contract("neutral", original, {})
    assert system == "neutral" and schema == SOURCE_SCHEMA
    _, mixed = research_contract("neutral", original, {"node_research": {"enabled": True}})
    assert "research" in mixed["required"] and "research" not in SOURCE_SCHEMA["required"]
    candidate, request = extract_research(action(), {"node_research": {"enabled": True}})
    assert request["queries"] == ["fixture"] and "research" not in candidate


def test_schema_declares_the_documentation_bounds_enforced_by_the_validator():
    _, mixed = research_contract("neutral", SOURCE_SCHEMA, {"node_research": {"enabled": True}})
    fields = mixed["properties"]["research"]["properties"]
    for name, maximum in (("queries", 300), ("urls", 2000)):
        assert fields[name]["maxItems"] == 2
        assert fields[name]["items"]["minLength"] == 1
        assert fields[name]["items"]["maxLength"] == maximum


@pytest.mark.parametrize("change", [
    {"files": [{"path": "src/x.c", "content": "int x;"}]},
    {"research": {"queries": ["a", "b", "c"], "urls": []}},
    {"research": {"queries": ["x" * 301], "urls": []}},
    {"research": {"commands": ["shell"]}},
    {"sources_kept": ["old-candidate"]},
])
def test_research_action_cannot_hide_edits_or_exceed_its_contract(change):
    with pytest.raises(CandidateRejected):
        extract_research(action(**change), {"node_research": {"enabled": True}})


def test_frozen_corpus_rejects_changed_text(tmp_path):
    path = tmp_path / "corpus.json"
    document = {"title": "Fixture", "version": "1", "url": "https://example.org/manual", "text": "fixture"}
    document["sha256"] = hashlib.sha256(document["text"].encode()).hexdigest()
    atomic_json(path, {"documents": [document]})
    settings = {"corpus": str(path), "corpus_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    reader = DocumentationReader(settings, tmp_path / "reads", time.time() + 10)
    hit = reader.read({"queries": ["fixture"], "urls": []}, 1)[0]["hits"][0]
    assert hit["sha256"] == document["sha256"]
    document["text"] = "changed"
    atomic_json(path, {"documents": [document]})
    with pytest.raises(InfrastructureError, match="SHA-256"):
        DocumentationReader(settings, tmp_path / "reads", time.time() + 10)
    settings["corpus_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(InfrastructureError, match="provenance"):
        DocumentationReader(settings, tmp_path / "reads", time.time() + 10)


@pytest.mark.parametrize("url", [
    "http://docs.example.org/file", "https://other.example.org/file",
    "https://user:password@docs.example.org/file", "https://docs.example.org:444/file",
    "https://127.0.0.1/file", "file:///tmp/code", "https://docs.example.org/file#fragment",
])
def test_disallowed_url_never_opens_a_connection(tmp_path, monkeypatch, url):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: pytest.fail("Unexpected DNS request"))
    reader = DocumentationReader({"allowed_hosts": ["docs.example.org"]}, tmp_path, time.time() + 10)
    result = reader.read({"queries": [], "urls": [url]}, 1)
    assert result[0]["evidence_type"] == "read_error"


def test_even_an_allowed_hostname_cannot_resolve_to_private_addresses(tmp_path, monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(socket.AF_INET, 1, 6, "", ("127.0.0.1", 443))])
    reader = DocumentationReader({"allowed_hosts": ["docs.example.org"]}, tmp_path, time.time() + 10)
    result = reader.read({"queries": [], "urls": ["https://docs.example.org/file"]}, 1)
    assert "public addresses" in result[0]["error"]


def test_public_document_is_read_archived_hashed_and_returned_as_data(tmp_path, monkeypatch):
    raw = b"<h1>Fixture</h1><script>execute_shell()</script><p>Reference data.</p>"
    headers = Message()
    headers["Content-Type"] = "text/html; charset=utf-8"

    class Response(io.BytesIO):
        pass

    response = Response(raw)
    response.headers = headers

    class Opener:
        def open(self, request, timeout):
            assert request.full_url == "https://docs.example.org/file" and timeout <= 5
            return response

    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(socket.AF_INET, 1, 6, "", ("1.1.1.1", 443))])
    monkeypatch.setattr("urllib.request.build_opener", lambda *a: Opener())
    reader = DocumentationReader({"allowed_hosts": ["docs.example.org"]}, tmp_path, time.time() + 10)
    result = reader.read({"queries": [], "urls": ["https://docs.example.org/file"]}, 1)[0]
    sha = hashlib.sha256(raw).hexdigest()
    assert result["sha256"] == sha and "Reference data." in result["excerpt"]
    assert "execute_shell" not in result["excerpt"]
    assert (tmp_path / (sha + ".raw")).read_bytes() == raw
    assert json.loads((tmp_path / "research-action-01.json").read_text())["results"][0] == result
