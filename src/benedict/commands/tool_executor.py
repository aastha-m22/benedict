"""Tool Executor

Executes LLM tool calls against method and metadata files.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MethodMetadataToolExecutor:
    """Executes tool calls against method and metadata files."""
    
    def __init__(self, method_reader=None, method_writer=None, metadata_reader=None, workspace_path: Optional[Path] = None):
        """Initialize tool executor.
        
        Args:
            method_reader: MethodReader instance
            method_writer: MethodWriter instance
            metadata_reader: MetadataReader instance
            workspace_path: Workspace path for repository
        """
        self.method_reader = method_reader
        self.method_writer = method_writer
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
        # Handle both OpenAI format (arguments) and Anthropic format (input)
        arguments = tool_call.get("arguments") or tool_call.get("input", {})
        
        if not tool_name:
            return {
                "success": False,
                "error": "Tool call missing 'name' field"
            }
        
        try:
            # Route to appropriate handler
            if tool_name == "update_pc":
                return self._execute_update_pc(arguments)
            elif tool_name == "update_concern":
                return self._execute_update_concern(arguments)
            elif tool_name == "get_method_state":
                return self._execute_get_method_state()
            elif tool_name == "update_sequence_phase":
                return self._execute_update_sequence_phase(arguments)
            elif tool_name == "get_file_metadata":
                return self._execute_get_file_metadata(arguments)
            elif tool_name == "list_key_files":
                return self._execute_list_key_files()
            elif tool_name == "get_repository_summary":
                return self._execute_get_repository_summary()
            else:
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                }
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _execute_update_pc(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute update_pc tool."""
        if not self.method_writer or not self.workspace_path:
            return {"success": False, "error": "Method writer not available"}
        
        phase = arguments.get("phase")
        iteration = arguments.get("iteration")
        step = arguments.get("step")
        
        try:
            self.method_writer.update_pc(
                self.workspace_path,
                phase=phase,
                iteration=iteration,
                step=step
            )
            
            result = "Updated program counter"
            if phase:
                result += f" - Phase: {phase}"
            if iteration:
                result += f", Iteration: {iteration}"
            if step:
                result += f", Step: {step}"
            
            return {
                "success": True,
                "message": result
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _execute_update_concern(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute update_concern tool."""
        if not self.method_writer or not self.workspace_path:
            return {"success": False, "error": "Method writer not available"}
        
        concern = arguments.get("concern")
        state = arguments.get("state")
        
        if not concern or not state:
            return {"success": False, "error": "Missing required parameters: concern, state"}
        
        try:
            self.method_writer.update_concern(self.workspace_path, concern, state)
            return {
                "success": True,
                "message": f"Updated concern '{concern}' to state '{state}'"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _execute_get_method_state(self) -> Dict[str, Any]:
        """Execute get_method_state tool."""
        if not self.method_reader or not self.workspace_path:
            return {"success": False, "error": "Method reader not available"}
        
        try:
            method_data = self.method_reader.read_method(self.workspace_path)
            if not method_data:
                return {"success": False, "error": "Method file not found"}
            
            method = method_data.get("method", {})
            pc = method.get("pc", {})
            concerns = method.get("concerns", {})
            sequence = method.get("sequence", {})
            
            return {
                "success": True,
                "data": {
                    "pc": pc,
                    "concerns": concerns,
                    "sequence": {k: {"status": v.get("status"), "iteration": v.get("iteration")} 
                                for k, v in sequence.items()}
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _execute_update_sequence_phase(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute update_sequence_phase tool."""
        if not self.method_writer or not self.workspace_path:
            return {"success": False, "error": "Method writer not available"}
        
        phase = arguments.get("phase")
        status = arguments.get("status")
        iteration = arguments.get("iteration")
        
        if not phase or not status:
            return {"success": False, "error": "Missing required parameters: phase, status"}
        
        try:
            self.method_writer.update_sequence_phase_status(
                self.workspace_path,
                phase,
                status,
                iteration=iteration
            )
            
            result = f"Updated sequence phase '{phase}' to status '{status}'"
            if iteration:
                result += f", iteration {iteration}"
            
            return {
                "success": True,
                "message": result
            }
        except Exception as e:
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
            
            return {
                "success": True,
                "data": file_info
            }
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
            return {
                "success": True,
                "data": files
            }
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
                    "purpose": metadata_data.get("purpose")
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
