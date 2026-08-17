"""Command Classification System

Provides intent-based command routing for Benedict.
Commands are declaratively defined and automatically classified from user input.
"""

from .command_classifier import CommandClassifier, CommandIntent, CommandType
from .command_definitions import COMMAND_DEFINITIONS
from .github_tools import RunGithubTool
from .llm_classifier import LLMCommandClassifier
from .metadata_tools import (
    GetFileMetadataTool,
    GetRepositorySummaryTool,
    ListKeyFilesTool,
)
from .tool_framework import Tool, ToolRegistry, ToolResult
from .tool_loop import run_tool_loop
from .tool_registry_factory import create_tool_registry

__all__ = [
    "CommandClassifier",
    "CommandType",
    "CommandIntent",
    "COMMAND_DEFINITIONS",
    "Tool",
    "ToolResult",
    "ToolRegistry",
    "create_tool_registry",
    "GetFileMetadataTool",
    "ListKeyFilesTool",
    "GetRepositorySummaryTool",
    "LLMCommandClassifier",
    "RunGithubTool",
    "run_tool_loop",
]
