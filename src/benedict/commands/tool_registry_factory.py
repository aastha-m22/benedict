"""Tool Registry Factory

Creates tool registries from method and metadata files.
"""

import logging
from pathlib import Path
from typing import Optional
from .tool_framework import ToolRegistry
from .method_tools import (
    UpdatePCTool,
    UpdateConcernTool,
    GetMethodStateTool,
    UpdateSequencePhaseTool,
    CreateMethodTool,
)
from .metadata_tools import (
    GetFileMetadataTool,
    ListKeyFilesTool,
    GetRepositorySummaryTool,
)

logger = logging.getLogger(__name__)


def create_tool_registry(
    method_reader=None,
    method_writer=None,
    metadata_reader=None,
    repo_path: Optional[Path] = None,
) -> ToolRegistry:
    """Create tool registry with tools from method/metadata files.
    
    Args:
        method_reader: MethodReader instance
        method_writer: MethodWriter instance
        metadata_reader: MetadataReader instance
        repo_path: Optional repository path to validate tools against
        
    Returns:
        ToolRegistry with registered tools
    """
    registry = ToolRegistry()
    
    # Register method tools
    # Always register GetMethodStateTool (for reading), even if file doesn't exist
    if method_reader:
        registry.register(GetMethodStateTool(method_reader))
        logger.debug("Registered get_method_state tool")
    
    # Always register CreateMethodTool when method_writer is available
    # This allows creating the method file even when it doesn't exist
    if method_writer:
        registry.register(CreateMethodTool(method_writer))
        logger.debug("Registered create_method tool")
    
    # Register write tools only if method_writer available
    if method_reader and method_writer:
        # Check if method file exists before registering write tools
        if not repo_path or (method_reader and method_reader.method_exists(repo_path)):
            registry.register(UpdatePCTool(method_reader, method_writer))
            registry.register(UpdateConcernTool(method_reader, method_writer))
            registry.register(UpdateSequencePhaseTool(method_reader, method_writer))
            logger.debug("Registered method write tools")
    
    # Register metadata tools
    if metadata_reader:
        # Check if metadata file exists before registering tools
        if not repo_path or (metadata_reader and metadata_reader.metadata_exists(repo_path)):
            registry.register(GetFileMetadataTool(metadata_reader))
            registry.register(ListKeyFilesTool(metadata_reader))
            registry.register(GetRepositorySummaryTool(metadata_reader))
            logger.debug("Registered metadata tools")
    
    return registry


def create_tool_registry_from_method_data(
    method_data: dict,
    method_reader=None,
    method_writer=None,
    metadata_reader=None,
) -> ToolRegistry:
    """Create tool registry and enhance tool schemas with actual method data.
    
    This allows tools to have enums derived from actual method file content.
    
    Args:
        method_data: Parsed method file data
        method_reader: MethodReader instance
        method_writer: MethodWriter instance
        metadata_reader: MetadataReader instance
        
    Returns:
        ToolRegistry with enhanced tools
    """
    registry = ToolRegistry()
    
    # Always register GetMethodStateTool (for reading), even if file doesn't exist
    if method_reader:
        registry.register(GetMethodStateTool(method_reader))
        logger.debug("Registered get_method_state tool")
    
    # Always register CreateMethodTool when method_writer is available
    # This allows creating the method file even when it doesn't exist
    if method_writer:
        registry.register(CreateMethodTool(method_writer))
        logger.debug("Registered create_method tool")
    
    # Register method tools with enhanced schemas
    if method_reader and method_writer and method_data:
        method = method_data.get("method", {})
        
        # Enhance UpdatePCTool with phase enum
        sequence = method.get("sequence", {})
        phases = list(sequence.keys()) if sequence else None
        
        update_pc_tool = UpdatePCTool(method_reader, method_writer)
        if phases:
            # Enhance schema with phase enum
            schema = update_pc_tool.get_schema()
            schema["input_schema"]["properties"]["phase"]["enum"] = phases
            schema["input_schema"]["properties"]["phase"]["description"] += f" Valid phases: {', '.join(phases)}"
        registry.register(update_pc_tool)
        
        # Enhance UpdateConcernTool with concern and state enums
        concern_defs = method.get("concern_definitions", {})
        concerns = list(concern_defs.keys()) if concern_defs else None
        all_states = set()
        for concern_def in concern_defs.values():
            states = concern_def.get("states", [])
            all_states.update(states)
        
        update_concern_tool = UpdateConcernTool(method_reader, method_writer)
        if concerns:
            schema = update_concern_tool.get_schema()
            schema["input_schema"]["properties"]["concern"]["enum"] = concerns
            schema["input_schema"]["properties"]["concern"]["description"] += f" Valid concerns: {', '.join(concerns)}"
            if all_states:
                schema["input_schema"]["properties"]["state"]["enum"] = list(all_states)
                schema["input_schema"]["properties"]["state"]["description"] += f" Valid states: {', '.join(sorted(all_states))}"
        registry.register(update_concern_tool)
        
        # Enhance UpdateSequencePhaseTool with phase enum
        update_sequence_tool = UpdateSequencePhaseTool(method_reader, method_writer)
        if phases:
            schema = update_sequence_tool.get_schema()
            schema["input_schema"]["properties"]["phase"]["enum"] = phases
            schema["input_schema"]["properties"]["phase"]["description"] += f" Valid phases: {', '.join(phases)}"
        registry.register(update_sequence_tool)
    
    # Register metadata tools
    if metadata_reader:
        registry.register(GetFileMetadataTool(metadata_reader))
        registry.register(ListKeyFilesTool(metadata_reader))
        registry.register(GetRepositorySummaryTool(metadata_reader))
    
    return registry
