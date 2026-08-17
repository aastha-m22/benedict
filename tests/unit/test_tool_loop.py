"""Tests for the LLM tool-call loop."""

from typing import Any, Dict, List, Optional, Union

from benedict.commands.tool_framework import Tool, ToolRegistry, ToolResult
from benedict.commands.tool_loop import format_tool_result, run_tool_loop


class StubTool(Tool):
    def __init__(self):
        super().__init__(name="stub", description="stub tool")
        self.calls: List[Dict[str, Any]] = []

    def get_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
        }

    def execute(
        self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        self.calls.append({"arguments": arguments, "context": context})
        return ToolResult(success=True, message=f"ran:{arguments.get('q')}")


class ScriptedLLM:
    def __init__(self, responses: List[Union[str, Dict[str, Any]]]):
        self.responses = list(responses)
        self.calls: List[Dict[str, Any]] = []

    def generate(
        self,
        messages: List[Dict[str, Any]],
        system: str = "",
        max_tokens: int = 2000,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Union[str, Dict[str, Any]]:
        self.calls.append({"messages": messages, "tools": tools, "system": system})
        if not self.responses:
            return "empty script"
        return self.responses.pop(0)


def _registry_with_stub():
    registry = ToolRegistry()
    tool = StubTool()
    registry.register(tool)
    return registry, tool


def test_format_tool_result():
    assert format_tool_result(ToolResult(success=False, error="nope")) == "nope"
    assert format_tool_result(ToolResult(success=True, message="ok")) == "ok"
    assert '"a": 1' in format_tool_result(ToolResult(success=True, data={"a": 1}))
    assert format_tool_result(ToolResult(success=True)) == "OK"


def test_loop_returns_text_without_tools():
    llm = ScriptedLLM(["hello"])
    registry, tool = _registry_with_stub()
    text = run_tool_loop(
        llm,
        messages=[{"role": "user", "content": "hi"}],
        system="sys",
        tool_registry=registry,
    )
    assert text == "hello"
    assert tool.calls == []
    assert llm.calls[0]["tools"][0]["name"] == "stub"


def test_loop_executes_tool_and_feeds_result_back():
    llm = ScriptedLLM(
        [
            {"tool_calls": [{"id": "call_1", "name": "stub", "input": {"q": "prs"}}]},
            "There is 1 PR",
        ]
    )
    registry, tool = _registry_with_stub()
    text = run_tool_loop(
        llm,
        messages=[{"role": "user", "content": "open prs?"}],
        system="sys",
        tool_registry=registry,
        context={"workspace_path": "/tmp/repo"},
    )
    assert text == "There is 1 PR"
    assert tool.calls == [{"arguments": {"q": "prs"}, "context": {"workspace_path": "/tmp/repo"}}]
    second = llm.calls[1]["messages"]
    assert second[-2]["role"] == "assistant"
    assert second[-1]["role"] == "user"
    assert second[-1]["content"][0]["type"] == "tool_result"
    assert second[-1]["content"][0]["tool_use_id"] == "call_1"
    assert "ran:prs" in second[-1]["content"][0]["content"]


def test_loop_stops_at_max_iterations():
    tool_response = {"tool_calls": [{"id": "call_x", "name": "stub", "input": {"q": "again"}}]}
    llm = ScriptedLLM([tool_response, tool_response, tool_response])
    registry, tool = _registry_with_stub()
    text = run_tool_loop(
        llm,
        messages=[{"role": "user", "content": "loop"}],
        system="sys",
        tool_registry=registry,
        max_iterations=2,
    )
    assert "tool-call limit" in text
    assert len(tool.calls) == 2
    assert len(llm.calls) == 2
