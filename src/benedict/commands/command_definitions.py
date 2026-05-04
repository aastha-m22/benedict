"""Command Definitions

Declarative definitions of all Benedict commands with intent patterns.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import re
from enum import Enum


class CommandType(Enum):
    """Types of commands Benedict supports."""
    
    # System commands
    ONBOARD = "onboard"
    STATUS = "status"
    UPDATE_INDEX = "update_index"
    
    # File operations
    READ_FILE = "read_file"
    LIST_FILES = "list_files"
    SEARCH_FILES = "search_files"
    
    # Method file operations
    READ_METHOD = "read_method"
    UPDATE_METHOD = "update_method"
    CREATE_METHOD = "create_method"
    
    # Metadata operations
    READ_METADATA = "read_metadata"
    GENERATE_METADATA = "generate_metadata"
    
    # General queries (not a command, but classified)
    QUERY = "query"


@dataclass
class CommandIntent:
    """Represents a detected command intent."""
    
    command_type: CommandType
    confidence: float  # 0.0 to 1.0
    parameters: Dict[str, Any]  # Extracted parameters
    matched_pattern: Optional[str] = None  # Which pattern matched


@dataclass
class CommandDefinition:
    """Definition of a command with patterns and metadata."""
    
    command_type: CommandType
    name: str
    description: str
    patterns: List[str]  # Regex patterns or keywords
    required_params: List[str] = field(default_factory=list)  # Required parameters
    optional_params: List[str] = field(default_factory=list)  # Optional parameters
    examples: List[str] = field(default_factory=list)  # Example user inputs
    compiled_patterns: List = field(default_factory=list, init=False)  # Compiled regex patterns


# Command definitions
COMMAND_DEFINITIONS: List[CommandDefinition] = [
    # System commands
    CommandDefinition(
        command_type=CommandType.ONBOARD,
        name="onboard",
        description="Onboard a channel to a repository",
        patterns=[
            r"onboard\s+(?:repo\s+)?([^\s]+)",
            r"link\s+(?:channel\s+)?to\s+([^\s]+)",
            r"connect\s+(?:channel\s+)?to\s+([^\s]+)",
        ],
        required_params=["repo"],
        examples=[
            "onboard repo mkarots/benedict",
            "link channel to benedict",
            "connect to my-repo",
        ],
    ),
    
    CommandDefinition(
        command_type=CommandType.STATUS,
        name="status",
        description="Show channel status and configuration",
        patterns=[
            r"status",
            r"show\s+status",
            r"channel\s+status",
            r"what'?s?\s+the\s+status",
            r"how\s+are\s+we\s+configured",
        ],
        examples=[
            "status",
            "show status",
            "what's the channel status?",
        ],
    ),
    
    CommandDefinition(
        command_type=CommandType.UPDATE_INDEX,
        name="update_index",
        description="Update the semantic search index",
        patterns=[
            r"update\s+index(?:\s+force)?",
            r"reindex",
            r"refresh\s+index",
            r"rebuild\s+index",
        ],
        optional_params=["force"],
        examples=[
            "update index",
            "update index force",
            "reindex the repository",
        ],
    ),
    
    # File operations
    CommandDefinition(
        command_type=CommandType.READ_FILE,
        name="read_file",
        description="Read/show contents of a specific file",
        patterns=[
            r"read\s+([^\s]+)",
            r"show\s+(?:me\s+)?(?:the\s+)?(?:contents?\s+of\s+)?([^\s]+)",
            r"tell\s+me\s+(?:the\s+)?(?:contents?\s+of\s+)?([^\s]+)",
            r"what'?s?\s+in\s+([^\s]+)",
            r"display\s+([^\s]+)",
            r"open\s+([^\s]+)",
            r"contents?\s+of\s+([^\s]+)",
        ],
        required_params=["file_path"],
        examples=[
            "read .benedict.method.yaml",
            "show me the contents of README.md",
            "what's in agent.py",
        ],
    ),
    
    CommandDefinition(
        command_type=CommandType.LIST_FILES,
        name="list_files",
        description="List files in repository or directory",
        patterns=[
            r"list\s+files",
            r"show\s+files",
            r"what\s+files\s+are\s+there",
            r"files\s+in\s+([^\s]+)",
        ],
        optional_params=["path"],
        examples=[
            "list files",
            "show files in src/",
            "what files are in the repo?",
        ],
    ),
    
    # Method file operations
    CommandDefinition(
        command_type=CommandType.READ_METHOD,
        name="read_method",
        description="Read the method file",
        patterns=[
            r"read\s+method",
            r"show\s+method",
            r"method\s+file",
            r"what'?s?\s+in\s+the\s+method\s+file",
            r"show\s+me\s+the\s+method",
        ],
        examples=[
            "read method file",
            "show me the method",
            "what's in the method file?",
        ],
    ),
    
    CommandDefinition(
        command_type=CommandType.UPDATE_METHOD,
        name="update_method",
        description="Update method file (phase, concerns, etc.)",
        patterns=[
            r"update\s+method",
            r"change\s+method",
            r"update\s+phase",
            r"change\s+phase",
            r"set\s+phase\s+to\s+([^\s]+)",
            r"update\s+concern",
            r"change\s+concern",
            r"set\s+([^\s]+)\s+to\s+([^\s]+)",  # Generic set X to Y
        ],
        optional_params=["phase", "concern", "state", "iteration", "step"],
        examples=[
            "update phase to sprint",
            "set documentation concern to complete",
            "change method file",
        ],
    ),
    
    CommandDefinition(
        command_type=CommandType.CREATE_METHOD,
        name="create_method",
        description="Create a new method file",
        patterns=[
            r"create\s+method",
            r"generate\s+method",
            r"setup\s+method",
            r"initialize\s+method",
            r"new\s+method\s+file",
        ],
        examples=[
            "create method file",
            "generate method",
            "setup method file",
        ],
    ),
    
    # Metadata operations
    CommandDefinition(
        command_type=CommandType.READ_METADATA,
        name="read_metadata",
        description="Read repository metadata",
        patterns=[
            r"read\s+metadata",
            r"show\s+metadata",
            r"metadata\s+file",
        ],
        examples=[
            "read metadata",
            "show metadata",
        ],
    ),
    
    CommandDefinition(
        command_type=CommandType.GENERATE_METADATA,
        name="generate_metadata",
        description="Generate metadata file",
        patterns=[
            r"generate\s+metadata",
            r"create\s+metadata",
            r"setup\s+metadata",
        ],
        examples=[
            "generate metadata",
            "create metadata file",
        ],
    ),
]
