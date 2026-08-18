"""Benedict MCP server: expose project memory to Cursor, Claude Code, and other MCP clients."""

from benedict.mcp.project import Project, ProjectResolutionError, ProjectResolver
from benedict.mcp.service import BenedictMcpService

__all__ = [
    "BenedictMcpService",
    "Project",
    "ProjectResolutionError",
    "ProjectResolver",
]
