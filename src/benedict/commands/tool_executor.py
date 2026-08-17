"""Tool Executor

Executes LLM tool calls against metadata files.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MetadataToolExecutor:
    """Executes tool calls against metadata files."""

    def __init__(self, metadata_reader=None, workspace_path: Optional[str] = None):
        """Initialize tool executor.

        Args:
            metadata_reader: MetadataReader instance
            workspace_path: Workspace path for repository
        """
        self.metadata_reader = metadata_reader
        self.workspace_path = workspace_path

    def execute(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call.

        Args:
            tool_call: Tool call from LLM in format:
                {
                    "name": "tool_name",
                    "arguments": {...}  # or "input" for Anthropic
                }

        Returns:
            Result dictionary with success status and message/data
        """
        tool_name = tool_call.get("name")
        arguments = tool_call.get("arguments") or tool_call.get("input", {})

        if not tool_name:
            return {"success": False, "error": "Tool call missing 'name' field"}

        try:
            if tool_name == "get_file_metadata":
                return self._execute_get_file_metadata(arguments)
            if tool_name == "list_key_files":
                return self._execute_list_key_files()
            if tool_name == "get_repository_summary":
                return self._execute_get_repository_summary()
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _execute_get_file_metadata(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute get_file_metadata tool."""
        if not self.metadata_reader or not self.workspace_path:
            return {"success": False, "error": "Metadata reader not available"}

        file_path = arguments.get("file_path")
        if not file_path:
            return {"success": False, "error": "Missing required parameter: file_path"}

        try:
            metadata_data = self.metadata_reader.read_metadata(self.workspace_path)
            if not metadata_data:
                return {"success": False, "error": "Metadata file not found"}

            files = metadata_data.get("files", [])
            file_info = next((f for f in files if f.get("name") == file_path), None)

            if not file_info:
                return {"success": False, "error": f"File '{file_path}' not found in metadata"}

            return {"success": True, "data": file_info}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_list_key_files(self) -> Dict[str, Any]:
        """Execute list_key_files tool."""
        if not self.metadata_reader or not self.workspace_path:
            return {"success": False, "error": "Metadata reader not available"}

        try:
            metadata_data = self.metadata_reader.read_metadata(self.workspace_path)
            if not metadata_data:
                return {"success": False, "error": "Metadata file not found"}

            files = metadata_data.get("files", [])
            return {"success": True, "data": files}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_get_repository_summary(self) -> Dict[str, Any]:
        """Execute get_repository_summary tool."""
        if not self.metadata_reader or not self.workspace_path:
            return {"success": False, "error": "Metadata reader not available"}

        try:
            metadata_data = self.metadata_reader.read_metadata(self.workspace_path)
            if not metadata_data:
                return {"success": False, "error": "Metadata file not found"}

            return {
                "success": True,
                "data": {
                    "summary": metadata_data.get("summary"),
                    "purpose": metadata_data.get("purpose"),
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
