"""Tool Framework

Minimal framework for defining and executing tools.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result of tool execution."""
    
    success: bool
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class Tool(ABC):
    """Base class for tools."""
    
    def __init__(self, name: str, description: str):
        """Initialize tool.
        
        Args:
            name: Tool name (must be unique)
            description: Tool description for LLM
        """
        self.name = name
        self.description = description
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for LLM.
        
        Returns:
            Dictionary with name, description, and input_schema
        """
        pass
    
    @abstractmethod
    def execute(self, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Execute tool with given arguments.
        
        Args:
            arguments: Tool arguments from LLM
            context: Optional execution context (e.g., workspace_path, repo)
            
        Returns:
            ToolResult with success status and result data/message
        """
        pass
    
    def validate(self, arguments: Dict[str, Any]) -> Optional[str]:
        """Validate arguments before execution.
        
        Args:
            arguments: Tool arguments to validate
            
        Returns:
            Error message if invalid, None if valid
        """
        schema = self.get_schema()
        input_schema = schema.get("input_schema", {})
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        
        # Check required parameters
        for param in required:
            if param not in arguments:
                return f"Missing required parameter: {param}"
        
        # Check parameter types (basic validation)
        for param_name, param_value in arguments.items():
            if param_name in properties:
                param_def = properties[param_name]
                expected_type = param_def.get("type")
                
                # Type checking
                if expected_type == "string" and not isinstance(param_value, str):
                    return f"Parameter '{param_name}' must be a string"
                elif expected_type == "integer" and not isinstance(param_value, int):
                    return f"Parameter '{param_name}' must be an integer"
                elif expected_type == "boolean" and not isinstance(param_value, bool):
                    return f"Parameter '{param_name}' must be a boolean"
                
                # Enum checking
                enum_values = param_def.get("enum")
                if enum_values and param_value not in enum_values:
                    return f"Parameter '{param_name}' must be one of: {', '.join(enum_values)}"
        
        return None


class ToolRegistry:
    """Registry for managing tools."""
    
    def __init__(self):
        """Initialize tool registry."""
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool.
        
        Args:
            tool: Tool instance to register
        """
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, overwriting")
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")
    
    def get(self, name: str) -> Optional[Tool]:
        """Get tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)
    
    def list_tools(self) -> List[Tool]:
        """List all registered tools.
        
        Returns:
            List of all registered tools
        """
        return list(self._tools.values())
    
    def to_anthropic_tools(self) -> List[Dict[str, Any]]:
        """Convert all tools to Anthropic tool format.
        
        Returns:
            List of tool schemas for Anthropic API
        """
        return [tool.get_schema() for tool in self._tools.values()]
    
    def execute(self, tool_name: str, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Execute a tool by name.
        
        Args:
            tool_name: Name of tool to execute
            arguments: Tool arguments
            context: Optional execution context
            
        Returns:
            ToolResult
        """
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found"
            )
        
        # Validate arguments
        validation_error = tool.validate(arguments)
        if validation_error:
            return ToolResult(
                success=False,
                error=validation_error
            )
        
        # Execute tool
        try:
            return tool.execute(arguments, context)
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=str(e)
            )
