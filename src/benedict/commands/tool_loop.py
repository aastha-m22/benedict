"""LLM tool-call loop.

Feeds tool results back to the model so it can interpret output or call again.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from .tool_framework import ToolRegistry, ToolResult
from benedict.operator_ui.recorder import record_stage

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 5


def format_tool_result(result: ToolResult) -> str:
    """Turn a ToolResult into text the model can read."""
    if not result.success:
        return result.error or "Tool failed"
    if result.message:
        return result.message
    if result.data is not None:
        try:
            return json.dumps(result.data, default=str)
        except (TypeError, ValueError):
            return str(result.data)
    return "OK"


def _assistant_content_from_tool_calls(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rebuild Anthropic tool_use blocks if the LLM did not return assistant_content."""
    blocks = []
    for call in tool_calls:
        call_id = call.get("id")
        name = call.get("name")
        if not call_id or not name:
            continue
        blocks.append(
            {
                "type": "tool_use",
                "id": call_id,
                "name": name,
                "input": call.get("input") or call.get("arguments") or {},
            }
        )
    return blocks


def run_tool_loop(
    llm,
    messages: List[Dict[str, Any]],
    system: str,
    tool_registry: ToolRegistry,
    context: Optional[Dict[str, Any]] = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    max_tokens: int = 2000,
) -> str:
    """Call the LLM, execute requested tools, and repeat until text is returned.

    Args:
        llm: LLM instance (must support tools=)
        messages: Conversation messages
        system: System prompt
        tool_registry: Tools the model may call
        context: Passed to each tool execute()
        max_iterations: Safety cap on tool rounds
        max_tokens: Per-call token limit

    Returns:
        Final assistant text
    """
    tools = tool_registry.to_anthropic_tools()
    working_messages: List[Dict[str, Any]] = list(messages)
    model = os.environ.get("ANTHROPIC_MODEL", "claude")

    for iteration in range(max_iterations):
        llm_started = time.perf_counter()
        response = llm.generate(
            messages=working_messages,
            system=system,
            tools=tools,
            max_tokens=max_tokens,
        )
        record_stage(
            "llm",
            duration_ms=int((time.perf_counter() - llm_started) * 1000),
            label=model,
            detail={"iteration": iteration + 1},
        )

        if isinstance(response, str):
            return response

        if not isinstance(response, dict) or not response.get("tool_calls"):
            return str(response) if response else ""

        tool_calls = response["tool_calls"]
        assistant_content = response.get("assistant_content") or _assistant_content_from_tool_calls(
            tool_calls
        )
        if not assistant_content:
            logger.warning("Tool calls missing ids/content; stopping loop")
            return "Tool call was missing an id; cannot continue."

        working_messages.append({"role": "assistant", "content": assistant_content})

        tool_results = []
        for call in tool_calls:
            name = call.get("name")
            arguments = call.get("input") or call.get("arguments") or {}
            call_id = call.get("id")
            logger.info("Tool loop iteration %s: %s(%s)", iteration + 1, name, arguments)
            tool_started = time.perf_counter()
            result = tool_registry.execute(name, arguments, context)
            argv = arguments.get("argv") if isinstance(arguments, dict) else arguments
            record_stage(
                "tool",
                status="ok" if result.success else "error",
                duration_ms=int((time.perf_counter() - tool_started) * 1000),
                label=f"{name}  {argv}" if argv else (name or "tool"),
                detail={"name": name, "arguments": arguments, "error": result.error},
                child=True,
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call_id,
                    "content": format_tool_result(result),
                }
            )

        working_messages.append({"role": "user", "content": tool_results})

    logger.warning("Tool loop hit max iterations (%s)", max_iterations)
    return "I reached the tool-call limit before finishing. " "Try a more specific question."
