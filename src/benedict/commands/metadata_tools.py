"""Metadata File Tools

Tools for operating on metadata files.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from .tool_framework import Tool, ToolResult

logger = logging.getLogger(__name__)


class GetFileMetadataTool(Tool):
    """Tool for getting file metadata."""
    
    def __init__(self, metadata_reader=None):
        """Initialize tool.
        
        Args:
            metadata_reader: MetadataReader instance
        """
        super().__init__(
            name="get_file_metadata",
            description="Get metadata for a specific file including its purpose, key functions, and key classes."
        )
        self.metadata_reader = metadata_reader
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to file relative to repository root"
                    }
                },
                "required": ["file_path"]
            }
        }
    
    def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Execute tool."""
        if not self.metadata_reader or not context:
            return ToolResult(
                success=False,
                error="Metadata reader or context not available"
            )
        
        workspace_path = context.get("workspace_path")
        if not workspace_path:
            return ToolResult(
                success=False,
                error="workspace_path not provided in context"
            )
        
        file_path = arguments.get("file_path")
        if not file_path:
            return ToolResult(
                success=False,
                error="Missing required parameter: file_path"
            )
        
        try:
            metadata_data = self.metadata_reader.read_metadata(Path(workspace_path))
            if not metadata_data:
                return ToolResult(
                    success=False,
                    error="Metadata file not found"
                )
            
            files = metadata_data.get("files", [])
            file_info = next((f for f in files if f.get("name") == file_path), None)
            
            if not file_info:
                return ToolResult(
                    success=False,
                    error=f"File '{file_path}' not found in metadata"
                )
            
            return ToolResult(
                success=True,
                data=file_info
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )


class ListKeyFilesTool(Tool):
    """Tool for listing key files."""
    
    def __init__(self, metadata_reader=None):
        """Initialize tool.
        
        Args:
            metadata_reader: MetadataReader instance
        """
        super().__init__(
            name="list_key_files",
            description="List all files with metadata and their purposes. Use this to understand what files exist and what they do."
        )
        self.metadata_reader = metadata_reader
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {}
            }
        }
    
    def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Execute tool."""
        if not self.metadata_reader or not context:
            return ToolResult(
                success=False,
                error="Metadata reader or context not available"
            )
        
        workspace_path = context.get("workspace_path")
        if not workspace_path:
            return ToolResult(
                success=False,
                error="workspace_path not provided in context"
            )
        
        try:
            metadata_data = self.metadata_reader.read_metadata(Path(workspace_path))
            if not metadata_data:
                return ToolResult(
                    success=False,
                    error="Metadata file not found"
                )
            
            files = metadata_data.get("files", [])
            return ToolResult(
                success=True,
                data={"files": files}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )


class GetRepositorySummaryTool(Tool):
    """Tool for getting repository summary."""
    
    def __init__(self, metadata_reader=None):
        """Initialize tool.
        
        Args:
            metadata_reader: MetadataReader instance
        """
        super().__init__(
            name="get_repository_summary",
            description="Get repository summary, purpose, and high-level overview."
        )
        self.metadata_reader = metadata_reader
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {}
            }
        }
    
    def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Execute tool."""
        if not self.metadata_reader or not context:
            return ToolResult(
                success=False,
                error="Metadata reader or context not available"
            )
        
        workspace_path = context.get("workspace_path")
        if not workspace_path:
            return ToolResult(
                success=False,
                error="workspace_path not provided in context"
            )
        
        try:
            metadata_data = self.metadata_reader.read_metadata(Path(workspace_path))
            if not metadata_data:
                return ToolResult(
                    success=False,
                    error="Metadata file not found"
                )
            
            return ToolResult(
                success=True,
                data={
                    "summary": metadata_data.get("summary"),
                    "purpose": metadata_data.get("purpose")
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )
