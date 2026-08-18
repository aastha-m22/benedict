"""Tool Generator

Generates LLM tool schemas from metadata files.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class MetadataTools:
    """Tools derived from metadata files."""

    metadata_tools: List[Dict[str, Any]]

    def to_function_schema(self) -> List[Dict[str, Any]]:
        """Convert to OpenAI/Anthropic function calling format."""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"],
            }
            for tool in self.metadata_tools
        ]

    def to_openai_functions(self) -> List[Dict[str, Any]]:
        """Convert to OpenAI function calling format."""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            }
            for tool in self.metadata_tools
        ]

    def to_anthropic_tools(self) -> List[Dict[str, Any]]:
        """Convert to Anthropic tool format."""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"],
            }
            for tool in self.metadata_tools
        ]


class MetadataToolGenerator:
    """Generates LLM tool schemas from metadata files."""

    def __init__(self, metadata_reader=None):
        """Initialize tool generator.

        Args:
            metadata_reader: Optional MetadataReader instance
        """
        self.metadata_reader = metadata_reader

    def generate_tools(self, repo_path: Path) -> MetadataTools:
        """Generate tools from metadata files.

        Args:
            repo_path: Path to repository directory

        Returns:
            MetadataTools with generated tools
        """
        metadata_tools: List[Dict[str, Any]] = []

        if self.metadata_reader:
            try:
                metadata_data = self.metadata_reader.read_metadata(repo_path)
                if metadata_data:
                    metadata_tools = self._generate_metadata_tools(metadata_data)
                    logger.debug(
                        f"Generated {len(metadata_tools)} tools from metadata file"
                    )
            except Exception as e:
                logger.warning(f"Error generating metadata tools: {e}")

        return MetadataTools(metadata_tools=metadata_tools)

    def _generate_metadata_tools(self, metadata_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate tools from metadata file structure."""
        tools: List[Dict[str, Any]] = []

        if "files" in metadata_data:
            tools.append(
                {
                    "name": "get_file_metadata",
                    "description": (
                        "Get metadata for a specific file including its purpose, "
                        "key functions, and key classes."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to file relative to repository root",
                            }
                        },
                        "required": ["file_path"],
                    },
                }
            )
            tools.append(
                {
                    "name": "list_key_files",
                    "description": (
                        "List all files with metadata and their purposes. "
                        "Use this to understand what files exist and what they do."
                    ),
                    "parameters": {"type": "object", "properties": {}},
                }
            )

        if "summary" in metadata_data:
            tools.append(
                {
                    "name": "get_repository_summary",
                    "description": "Get repository summary, purpose, and high-level overview.",
                    "parameters": {"type": "object", "properties": {}},
                }
            )

        return tools
