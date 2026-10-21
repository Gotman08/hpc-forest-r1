"""Official source boundaries, extraction, shared snapshots and native MCP wiring."""
import asyncio
import hashlib
import io
import json
import socket
import zipfile
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from hpc_forest import codex_process, documentation_fetch, documentation_store
from hpc_forest.documentation_fetch import (
    CATALOGUE_SHA256,
    INTEL_ARCHIVE_URL,
    SOURCES,
    _PinnedHTTPS,
    documentation_redirect,
    extract_document,
    official_url,
)
from hpc_forest.documentation_mcp import DOCUMENTATION_POLICY, DocumentationMCP
from hpc_forest.documentation_store import DocumentationStore

URL = "https://gcc.gnu.org/onlinedocs/test-reference.html"


def fetched(url, text="Official fixture: vectorization and SIMD reductions."):
    raw = text.encode()
    url, source_id = official_url(url)
    return {"url": url, "resolved_url": url, "source_id": source_id, "title": "Reference fixture",
            "text": text, "links": [], "pdf_pages": None, "media_type": "text/plain",
            "raw_sha256": hashlib.sha256(raw).hexdigest(), "text_sha256": hashlib.sha256(raw).hexdigest(),
            "retrieved_at": 1234.0, "raw": raw}


@pytest.mark.parametrize("url", [
    "http://gcc.gnu.org/onlinedocs/test", "file:///etc/passwd", "https://localhost/docs/",
    "https://127.0.0.1/", "https://gcc.gnu.org.evil.invalid/onlinedocs/test",
    "https://other.invalid/?next=https://gcc.gnu.org/onlinedocs/",
    "https://user:password@gcc.gnu.org/onlinedocs/test", "https://gcc.gnu.org:444/onlinedocs/test",
    "https://gcc.gnu.org/onlinedocs/../private", "https://gcc.gnu.org/onlinedocs/%2e%2e/private",
    "https://gcc.gnu.org/onlinedocs/%252e%252e/private", "https://gcc.gnu.org/onlinedocs/%0d%0aheader",
    "https://gcc.gnu.org/onlinedocs/test?download=yes", "https://gcc.gnu.org/onlinedocs\\private",
    "https://arm-software.github.io/unrelated-project/", "https://raw.githubusercontent.com/user/repo/doc.md",
])
def test_only_official_reference_paths_are_allowed(url):
    with pytest.raises(ValueError):
        official_url(url)


def test_all_requested_families_have_valid_official_entrypoints():
    assert {"cuda", "openmp", "mpi-standard", "arm-simd", "intel-simd", "gcc", "clang"} <= SOURCES.keys()
    for identifier, source in SOURCES.items():
        for url in source["roots"]:
            assert official_url(url)[1] == identifier
    assert official_url(URL + "#section") == (URL, "gcc")
    with pytest.raises(ValueError):
        official_url(URL, "cuda")


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.8", "169.254.169.254", "::1"])
def test_dns_resolution_cannot_redirect_to_a_private_address(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 443))])
    monkeypatch.setattr(socket, "socket", lambda *args: pytest.fail("Must reject before opening a socket"))
    with pytest.raises(ValueError, match="public IP"):
        _PinnedHTTPS("gcc.gnu.org").connect()


def test_cross_publisher_redirect_is_rejected_before_second_request(monkeypatch):
    requested = []
    class Connection:
        def __init__(self, host, **kwargs):
            requested.append(host)
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            return SimpleNamespace(status=302, getheader=lambda *args: "https://127.0.0.1/private")
        def close(self):
            pass
    monkeypatch.setattr(documentation_fetch, "_PinnedHTTPS", Connection)
    with pytest.raises(ValueError):
        documentation_fetch.fetch_document(URL)
    assert requested == ["gcc.gnu.org"]


def test_html_and_intrinsic_xml_are_text_only_with_navigation():
    document = extract_document(
        b'<html><title>Manual</title><script>do_not_execute()</script><h1>SIMD</h1>'
        b'<a href="reduction.html">reduction rules</a><p>vectorize safely</p></html>', "text/html")
    assert "do_not_execute" not in document["text"]
    assert document["title"] == "Manual" and "vectorize safely" in document["text"]
    assert document["links"] == [{"url": "reduction.html", "title": "reduction rules"}]
    xml = extract_document(b'<intrinsics><intrinsic name="_mm_add_ps"><return type="__m128"/>'
                           b'<parameter type="__m128" varname="a"/><description>'
                           b'Add packed values</description></intrinsic></intrinsics>', "application/xml")
    assert "_mm_add_ps" in xml["text"] and "Add packed values" in xml["text"]
    assert "return: type=__m128" in xml["text"] and "varname=a" in xml["text"]


def test_pdf_text_is_searchable_and_preserves_page_numbers():
    pypdf = pytest.importorskip("pypdf")
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({
        NameObject("/F1"): font})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 10 100 Td (MPI_Allreduce official PDF fixture) Tj ET")
    page[NameObject("/Contents")] = stream
    buffer = io.BytesIO()
    writer.write(buffer)
    document = extract_document(buffer.getvalue(), "application/pdf")
    assert document["pdf_pages"] == 1 and "[PDF page 1]" in document["text"]
    assert "MPI_Allreduce" in document["text"]


def test_official_intel_archive_reads_constant_data_without_executing_javascript():
    buffer = io.BytesIO()
    xml = '<intrinsics_list version="3.6.9"><intrinsic name="_mm_add_ps">Add packed floats</intrinsic></intrinsics_list>'
    data = "var data_js = " + json.dumps(xml).replace(">", ">\\\n", 1) + ";"
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Intel Intrinsics Guide/files/data.js", data)
        archive.writestr("Intel Intrinsics Guide/viewer.js", "throw new Error('Never execute viewer');")
    document = extract_document(buffer.getvalue(), "application/zip")
    assert "_mm_add_ps" in document["text"] and "3.6.9" in document["title"]
    assert "Never execute" not in document["text"]
    invalid = io.BytesIO()
    with zipfile.ZipFile(invalid, "w") as archive:
        archive.writestr("data.js", 'var data_js = "<intrinsics_list/>"; run_a_command();')
    with pytest.raises(ValueError):
        extract_document(invalid.getvalue(), "application/zip")


def test_signed_delivery_is_allowed_only_from_the_fixed_official_download():
    signed = ("https://d2pgu9s4sfmw1s.cloudfront.net/UAM/Prod/Done/test-id/test-file"
              "?Expires=1&Key-Pair-Id=test&Signature=fake-secret")
    assert documentation_redirect(INTEL_ARCHIVE_URL, signed, INTEL_ARCHIVE_URL, "intel-simd") == signed
    with pytest.raises(ValueError):
        official_url(signed)
    with pytest.raises(ValueError):
        documentation_redirect(URL, signed, URL, "gcc")
    with pytest.raises(ValueError):
        official_url(INTEL_ARCHIVE_URL + "anything")


def test_concurrent_initial_fetches_share_the_first_committed_snapshot(tmp_path, monkeypatch):
    import threading
    import time

    store = DocumentationStore(tmp_path / "docs", "campaign")
    barrier = threading.Barrier(2, timeout=5)
    fetches = []
    def fetch(url):
        fetches.append(url)
        time.sleep(0.1)  # A simulated network read lets both clients request this URL.
        return fetched(url, "revision " + threading.current_thread().name)
    monkeypatch.setattr(documentation_store, "fetch_document", fetch)
    def read(_):
        barrier.wait()
        return store.read(URL)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(read, range(2)))
    assert results[0] == results[1] and fetches == [URL]


def test_shared_campaign_snapshots_keep_the_first_version_and_detect_corruption(tmp_path, monkeypatch):
    store = DocumentationStore(tmp_path / "docs", "campaign")
    monkeypatch.setattr(documentation_store, "fetch_document", fetched)
    original = store.read(URL)
    monkeypatch.setattr(documentation_store, "fetch_document", lambda url: pytest.fail("Must use shared cache"))
    assert DocumentationStore(store.root, "campaign").read(URL) == original
    with pytest.raises(ValueError, match="campaign"):
        DocumentationStore(store.root, "another-campaign")
    with store.connection() as db:
        document = json.loads(db.execute("SELECT payload FROM documents WHERE url=?", (URL,)).fetchone()[0])
        document["text"] = "changed"
        db.execute("UPDATE documents SET payload=? WHERE url=?", (json.dumps(document), URL))
    with pytest.raises(ValueError, match="changed"):
        store.read(URL)


def test_concurrent_readers_return_one_snapshot_and_keep_separate_access_receipts(tmp_path, monkeypatch):
    store = DocumentationStore(tmp_path / "docs", "campaign")
    monkeypatch.setattr(documentation_store, "fetch_document", fetched)
    store.read(URL)
    def read(index):
        reader = DocumentationStore(store.root, "campaign")
        result = reader.read(URL)
        reader.audit(str(index), "read", result)
        return result["raw_sha256"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        hashes = list(pool.map(read, range(16)))
    assert len(set(hashes)) == 1
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM accesses").fetchone()[0] == 16


def test_search_follows_relevant_official_links_and_finds_text_beyond_the_prefix(tmp_path, monkeypatch):
    store = DocumentationStore(tmp_path / "docs", "campaign")
    visited = []
    def fetch(url):
        visited.append(url)
        document = fetched(url, "Overview\n" * 500 + "vectorization alignment requirements\n")
        if url.endswith("/"):
            document["links"] = [{"url": URL, "title": "vectorization alignment"}]
        return document
    monkeypatch.setattr(documentation_store, "fetch_document", fetch)
    result = store.search("vectorization alignment", "gcc")
    assert URL in visited and result["results"]
    assert all(hit["start_line"] > 400 and "alignment" in hit["excerpt"] for hit in result["results"])
    assert all("raw_sha256" in hit and "retrieved_at" in hit for hit in result["results"])
    assert store.catalogue()["queries_leave_client"] is False


def test_read_pagination_does_not_lose_long_publisher_lines(tmp_path, monkeypatch):
    store = DocumentationStore(tmp_path / "docs", "campaign")
    text = extract_document(("A" * 30000).encode(), "text/plain")["text"]
    monkeypatch.setattr(documentation_store, "fetch_document", lambda url: fetched(url, text))
    parts, start = [], 1
    while start is not None:
        result = store.read(URL, start_line=start, line_count=3)
        parts.append(result["text"])
        start = result["next_line"]
    assert "".join(parts).replace("\n", "") == "A" * 30000


def test_native_docs_remain_enabled_after_resume_without_enabling_other_tools(tmp_path, monkeypatch):
    from test_mother_conversation import complete_turn, request_for

    from hpc_forest.codex_conversation import first_turn, next_turn

    pytest.importorskip("mcp")
    pytest.importorskip("pypdf")
    binding = DocumentationMCP.bind(tmp_path / "references", "a" * 32)
    monkeypatch.setattr(codex_process, "shutil", SimpleNamespace(which=lambda _: "codex.exe"))
    request = request_for(first_turn())
    request.update(nonce="b" * 32, messages=[{"role": "system", "content": "Planning"},
                                           {"role": "user", "content": "Subject"}],
                   schema={"type": "object"}, token_policy="observe-only")
    first = complete_turn(request, "1" * 64, tmp_path / "first")
    request["conversation"] = next_turn(first["conversation"])
    command = codex_process.command_for(request, tmp_path / "assembly", documentation_mcp=binding)
    assert command[command.index("resume") + 1] == first["conversation"]["thread_id"]
    assert command.index("mcp_servers.hpc_docs.required=true") > command.index("resume")
    assert "features.multi_agent=false" in command and "features.shell_tool=false" in command
    assert "features.code_mode_host=true" in command
    assert not any("model_context_window" in part for part in command)
    assert "ROMEO's existing MCP" in (tmp_path / "assembly/instructions.txt").read_text()


@pytest.mark.parametrize("server,tool,enabled,forbidden", [
    ("hpc_docs", "read_documentation", True, False), ("hpc_docs", "search_documentation", True, False),
    ("hpc_docs", "documentation_catalog", True, False), ("hpc_docs", "job_prepare", True, True),
    ("hpc_docs", "read_documentation", False, True), ("other", "read_documentation", True, True),
])
def test_only_the_three_documentation_tools_are_authorized(tmp_path, server, tool, enabled, forbidden):
    log = tmp_path / "native.jsonl"
    log.write_text("\n".join(json.dumps(event) for event in [
        {"type": "item.completed", "item": {"id": "call", "type": "mcp_tool_call", "server": server,
                                            "tool": tool, "status": "completed"}},
        {"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 3}},
    ]))
    usage, bad = codex_process.usage_from_events(log, allow_documentation=enabled)
    assert bad is forbidden and usage["tokens"] == 15


def test_real_stdio_clients_share_references_during_planning_research_and_assembly(tmp_path, monkeypatch):
    mcp = pytest.importorskip("mcp")
    pytest.importorskip("pypdf")
    from mcp.client.stdio import stdio_client

    root, session = tmp_path / "references", "a" * 32
    binding = DocumentationMCP.bind(root, session)
    store = DocumentationStore(root, session)
    monkeypatch.setattr(documentation_store, "fetch_document", fetched)
    store.read(URL)
    for url in SOURCES["gcc"]["roots"]:
        store.read(url)
    async def read(request_id):
        overrides = binding.overrides(request_id)
        parameters = mcp.StdioServerParameters(command=overrides["mcp_servers.hpc_docs.command"],
                                               args=overrides["mcp_servers.hpc_docs.args"])
        async with stdio_client(parameters) as streams, mcp.ClientSession(*streams) as client:
            await client.initialize()
            tools = await client.list_tools()
            assert {tool.name for tool in tools.tools} == {
                "documentation_catalog", "search_documentation", "read_documentation"}
            assert all(tool.annotations.readOnlyHint for tool in tools.tools)
            catalogue = await client.call_tool("documentation_catalog", {})
            assert catalogue.structuredContent["ok"] and catalogue.structuredContent["cached_documents"] == 3
            search = await client.call_tool("search_documentation", {"query": "vectorization", "source_id": "gcc"})
            assert search.structuredContent["ok"] and search.structuredContent["results"]
            response = await client.call_tool("read_documentation", {"url": URL})
            assert not response.isError and response.structuredContent["ok"]
            return response.structuredContent["raw_sha256"]
    async def run():
        original = await read("mother-planning")
        children = await asyncio.gather(*(read(f"T{i}") for i in range(1, 4)))
        final = await read("mother-assembly")
        return [original, *children, final]
    assert len(set(asyncio.run(run()))) == 1
    with store.connection() as db:
        assert {row[0] for row in db.execute("SELECT request_id FROM accesses")} == {
            "mother-planning", "T1", "T2", "T3", "mother-assembly"}
    assert binding.receipt()["catalogue_sha256"] == DOCUMENTATION_POLICY["catalogue_sha256"] == CATALOGUE_SHA256
