"""Tool Generator

Generates LLM tool schemas from method and metadata files.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MethodMetadataTools:
    """Tools derived from method and metadata files."""
    
    method_tools: List[Dict[str, Any]]
    metadata_tools: List[Dict[str, Any]]
    
    def to_function_schema(self) -> List[Dict[str, Any]]:
        """Convert to OpenAI/Anthropic function calling format.
        
        Returns:
            List of function schemas compatible with OpenAI/Anthropic APIs
        """
        all_tools = []
        
        for tool in self.method_tools:
            all_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"]
            })
        
        for tool in self.metadata_tools:
            all_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"]
            })
        
        return all_tools
    
    def to_openai_functions(self) -> List[Dict[str, Any]]:
        """Convert to OpenAI function calling format.
        
        Returns:
            List of function definitions for OpenAI API
        """
        functions = []
        
        for tool in self.method_tools + self.metadata_tools:
            functions.append({
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"]
            })
        
        return functions
    
    def to_anthropic_tools(self) -> List[Dict[str, Any]]:
        """Convert to Anthropic tool format.
        
        Returns:
            List of tool definitions for Anthropic API
        """
        tools = []
        
        for tool in self.method_tools + self.metadata_tools:
            tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"]
            })
        
        return tools


class MethodMetadataToolGenerator:
    """Generates LLM tool schemas from method and metadata files."""
    
    def __init__(self, method_reader=None, metadata_reader=None):
        """Initialize tool generator.
        
        Args:
            method_reader: Optional MethodReader instance
            metadata_reader: Optional MetadataReader instance
        """
        self.method_reader = method_reader
        self.metadata_reader = metadata_reader
    
    def generate_tools(self, repo_path: Path) -> MethodMetadataTools:
        """Generate tools from method and metadata files.
        
        Args:
            repo_path: Path to repository directory
            
        Returns:
            MethodMetadataTools with generated tools
        """
        method_tools = []
        metadata_tools = []
        
        # Generate tools from method file
        if self.method_reader:
            try:
                method_data = self.method_reader.read_method(repo_path)
                if method_data:
                    method_tools = self._generate_method_tools(method_data)
                    logger.debug(f"Generated {len(method_tools)} tools from method file")
            except Exception as e:
                logger.warning(f"Error generating method tools: {e}")
        
        # Generate tools from metadata file
        if self.metadata_reader:
            try:
                metadata_data = self.metadata_reader.read_metadata(repo_path)
                if metadata_data:
                    metadata_tools = self._generate_metadata_tools(metadata_data)
                    logger.debug(f"Generated {len(metadata_tools)} tools from metadata file")
            except Exception as e:
                logger.warning(f"Error generating metadata tools: {e}")
        
        return MethodMetadataTools(
            method_tools=method_tools,
            metadata_tools=metadata_tools
        )
    
    def _generate_method_tools(self, method_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate tools from method file structure.
        
        Args:
            method_data: Parsed method file data
            
        Returns:
            List of tool definitions
        """
        tools = []
        method = method_data.get("method", {})
        
        # Generate update_pc tool
        if "pc" in method:
            sequence = method.get("sequence", {})
            phases = list(sequence.keys()) if sequence else []
            
            tools.append({
                "name": "update_pc",
                "description": "Update program counter (current phase, iteration, step). The program counter tracks where the project is in its methodology.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phase": {
                            "type": "string",
                            "enum": phases if phases else None,
                            "description": f"Phase name. Valid phases: {', '.join(phases) if phases else 'any'}"
                        },
                        "iteration": {
                            "type": "integer",
                            "description": "Iteration number (e.g., 1, 2, 3)"
                        },
                        "step": {
                            "type": "string",
                            "description": "Step name within the phase"
                        }
                    }
                }
            })
        
        # Generate update_concern tool
        if "concern_definitions" in method:
            concern_defs = method["concern_definitions"]
            concerns = list(concern_defs.keys())
            
            # Build state enum from all concern definitions
            all_states = set()
            concern_states_map = {}
            for concern_name, concern_def in concern_defs.items():
                states = concern_def.get("states", [])
                all_states.update(states)
                concern_states_map[concern_name] = states
            
            tools.append({
                "name": "update_concern",
                "description": "Update a concern's current state. Concerns track different aspects of the project (scope, documentation, development, etc.).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concern": {
                            "type": "string",
                            "enum": concerns,
                            "description": f"Concern name. Valid concerns: {', '.join(concerns)}"
                        },
                        "state": {
                            "type": "string",
                            "description": f"New state value. Valid states depend on concern type. Common states: {', '.join(sorted(all_states))}"
                        }
                    },
                    "required": ["concern", "state"]
                }
            })
        
        # Generate get_method_state tool
        tools.append({
            "name": "get_method_state",
            "description": "Get current method file state including phase, iteration, step, and all concern states. Use this to understand the project's current methodology state.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        })
        
        # Generate update_sequence_phase tool
        if "sequence" in method:
            sequence = method["sequence"]
            phases = list(sequence.keys())
            statuses = ["complete", "active", "pending"]
            
            tools.append({
                "name": "update_sequence_phase",
                "description": "Update a sequence phase's status and iteration. Sequence phases are the main stages of the methodology (conception, design, sprint, review).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phase": {
                            "type": "string",
                            "enum": phases,
                            "description": f"Phase name. Valid phases: {', '.join(phases)}"
                        },
                        "status": {
                            "type": "string",
                            "enum": statuses,
                            "description": f"Status. Valid statuses: {', '.join(statuses)}"
                        },
                        "iteration": {
                            "type": "integer",
                            "description": "Iteration number for this phase"
                        }
                    },
                    "required": ["phase", "status"]
                }
            })
        
        return tools
    
    def _generate_metadata_tools(self, metadata_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate tools from metadata file structure.
        
        Args:
            metadata_data: Parsed metadata file data
            
        Returns:
            List of tool definitions
        """
        tools = []
        
        if "files" in metadata_data:
            tools.append({
                "name": "get_file_metadata",
                "description": "Get metadata for a specific file including its purpose, key functions, and key classes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to file relative to repository root"
                        }
                    },
                    "required": ["file_path"]
                }
            })
            
            tools.append({
                "name": "list_key_files",
                "description": "List all files with metadata and their purposes. Use this to understand what files exist and what they do.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            })
        
        if "summary" in metadata_data:
            tools.append({
                "name": "get_repository_summary",
                "description": "Get repository summary, purpose, and high-level overview.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            })
        
        return tools
