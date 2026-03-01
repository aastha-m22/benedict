"""Command Classification System

Provides intent-based command routing for Benedict.
Commands are declaratively defined and automatically classified from user input.
"""

from .command_classifier import CommandClassifier, CommandType, CommandIntent
from .command_definitions import COMMAND_DEFINITIONS
from .tool_framework import Tool, ToolResult, ToolRegistry
from .tool_registry_factory import create_tool_registry, create_tool_registry_from_method_data
from .method_tools import (
    UpdatePCTool,
    UpdateConcernTool,
    GetMethodStateTool,
    UpdateSequencePhaseTool,
)
from .metadata_tools import (
    GetFileMetadataTool,
    ListKeyFilesTool,
    GetRepositorySummaryTool,
)
from .llm_classifier import LLMCommandClassifier

__all__ = [
    "CommandClassifier",
    "CommandType",
    "CommandIntent",
    "COMMAND_DEFINITIONS",
    "Tool",
    "ToolResult",
    "ToolRegistry",
    "create_tool_registry",
    "create_tool_registry_from_method_data",
    "UpdatePCTool",
    "UpdateConcernTool",
    "GetMethodStateTool",
    "UpdateSequencePhaseTool",
    "GetFileMetadataTool",
    "ListKeyFilesTool",
    "GetRepositorySummaryTool",
    "LLMCommandClassifier",
]
