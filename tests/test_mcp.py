import sys

import pytest

from hpc_forest.controller import create_workspace


def test_real_stdio_server_exposes_only_documentation_and_status(tmp_path, config):
    pytest.importorskip("mcp")
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    root = create_workspace(tmp_path / "mcp-campaign", config)

    async def check():
        parameters = StdioServerParameters(
            command=sys.executable, args=["-m", "hpc_forest", "mcp", str(root)]
        )
        async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            catalog = await session.list_tools()
            assert {tool.name for tool in catalog.tools} == {
                "search_documentation",
                "campaign_status",
            }
            status = await session.call_tool("campaign_status", {})
            assert not status.isError
            assert "ready" in "".join(c.text for c in status.content if hasattr(c, "text"))
            docs = await session.call_tool(
                "search_documentation", {"query": "OpenMP", "max_chars": 2000}
            )
            assert not docs.isError
            assert "documentation" in "".join(c.text for c in docs.content if hasattr(c, "text"))

    anyio.run(check)
