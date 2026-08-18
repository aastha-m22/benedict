"""Tests for MCP server tool wiring."""

import asyncio
from unittest.mock import MagicMock

from benedict.mcp.server import create_mcp_server
from benedict.mcp.service import BenedictMcpService


def _service() -> BenedictMcpService:
    service = MagicMock(spec=BenedictMcpService)
    service.list_projects.return_value = {"ok": True, "projects": [], "count": 0}
    service.get_repository_summary.return_value = {"ok": True, "summary": "demo"}
    service.search_code.return_value = {"ok": True, "results": []}
    service.get_recent_actions.return_value = {"ok": True, "actions": []}
    service.ask.return_value = {"ok": True, "answer": "because tests"}
    return service


def _structured(result) -> dict:
    if getattr(result, "structured_content", None):
        return result.structured_content
    if getattr(result, "data", None):
        return result.data
    content = result.content[0]
    text = getattr(content, "text", None)
    if text:
        import json

        return json.loads(text)
    raise AssertionError(f"Unexpected tool result: {result!r}")


def test_mcp_tools_delegate_to_service():
    service = _service()
    mcp = create_mcp_server(service)

    async def _run():
        from mcp import Client

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = (
                {tool.name for tool in tools.tools}
                if hasattr(tools, "tools")
                else {tool.name for tool in tools}
            )
            assert names == {
                "list_projects",
                "get_repository_summary",
                "search_code",
                "get_recent_actions",
                "ask_benedict",
            }

            listed = _structured(await client.call_tool("list_projects", {}))
            assert listed["ok"] is True
            service.list_projects.assert_called_once()

            asked = _structured(
                await client.call_tool(
                    "ask_benedict", {"question": "what does this repo do?", "repo": "acme/example"}
                )
            )
            assert asked["answer"] == "because tests"
            service.ask.assert_called_once()
            kwargs = service.ask.call_args.kwargs
            assert kwargs["question"] == "what does this repo do?"
            assert kwargs["repo"] == "acme/example"

    asyncio.run(_run())
