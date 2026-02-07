"""Workspace Manager

Manages workspace lifecycle and resource operations for each context.
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Resource:
    """Represents a resource in a workspace."""
    name: str
    resource_type: str
    workspace_path: str
    source_path: Optional[str] = None
    content_type: Optional[str] = None


class WorkspaceManager:
    """Manages workspace lifecycle and resource operations."""
    
    def __init__(self, workspaces_dir: str = "./workspaces", copy_mode: str = "symlink"):
        """Initialize workspace manager.
        
        Args:
            workspaces_dir: Base directory for workspaces
            copy_mode: "symlink" or "copy" (default: "symlink")
        """
        self.workspaces_dir = Path(workspaces_dir).resolve()
        self.copy_mode = copy_mode
        
        # Ensure workspaces directory exists
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized WorkspaceManager with workspaces_dir={self.workspaces_dir}, copy_mode={copy_mode}")
    
    def create_workspace(self, context_id: str) -> Path:
        """Create workspace directory for context.
        
        Args:
            context_id: Context identifier (e.g., Slack channel_id, Discord channel_id)
            
        Returns:
            Path to workspace directory
        """
        workspace_path = self.workspaces_dir / context_id
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Created workspace for context {context_id} at {workspace_path}")
        return workspace_path
    
    def get_workspace_path(self, context_id: str) -> Path:
        """Get workspace path for context.
        
        Args:
            context_id: Context identifier
            
        Returns:
            Path to workspace directory (creates if doesn't exist)
        """
        workspace_path = self.workspaces_dir / context_id
        if not workspace_path.exists():
            return self.create_workspace(context_id)
        return workspace_path
    
    def add_resource(
        self,
        context_id: str,
        resource_type: str,
        source_path: str,
        name: str,
        content_type: Optional[str] = None
    ) -> str:
        """Add resource to workspace (symlink or copy).
        
        Args:
            context_id: Context identifier
            resource_type: Type of resource (e.g., "repository", "data", "documentation")
            source_path: Path to source resource
            name: Name for resource in workspace
            content_type: Optional content type (e.g., "code", "conversation_history")
            
        Returns:
            Workspace-relative path to resource
        """
        workspace_path = self.get_workspace_path(context_id)
        target_path = workspace_path / name
        
        source = Path(source_path).resolve()
        
        if not source.exists():
            raise FileNotFoundError(f"Source path does not exist: {source_path}")
        
        # Create parent directories if name contains slashes (e.g., "mkarots/hookedllm")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove existing target if it exists
        if target_path.exists() or target_path.is_symlink():
            if target_path.is_symlink():
                target_path.unlink()
            else:
                import shutil
                shutil.rmtree(target_path)
        
        # Create symlink or copy
        if self.copy_mode == "symlink":
            target_path.symlink_to(source)
            logger.info(f"Created symlink: {target_path} -> {source}")
        else:
            if source.is_dir():
                import shutil
                shutil.copytree(source, target_path)
            else:
                import shutil
                shutil.copy2(source, target_path)
            logger.info(f"Copied resource: {source} -> {target_path}")
        
        # Return workspace-relative path
        return name
    
    def list_resources(self, context_id: str) -> List[Resource]:
        """List resources in workspace.
        
        Args:
            context_id: Context identifier
            
        Returns:
            List of Resource objects
        """
        workspace_path = self.get_workspace_path(context_id)
        resources = []
        
        for item in workspace_path.iterdir():
            # Skip workspace_log.json
            if item.name == "workspace_log.json":
                continue
            
            # Determine resource type and content type
            resource_type = "unknown"
            content_type = None
            
            if item.is_symlink() or item.is_dir():
                # Try to detect content type
                if (item / ".git").exists():
                    resource_type = "repository"
                    content_type = "code"
                elif item.name == "conversation_history":
                    resource_type = "conversation_history"
                    content_type = "conversation_history"
                else:
                    resource_type = "directory"
            
            source_path = None
            if item.is_symlink():
                source_path = str(item.readlink())
            
            resources.append(Resource(
                name=item.name,
                resource_type=resource_type,
                workspace_path=str(item.relative_to(workspace_path)),
                source_path=source_path,
                content_type=content_type
            ))
        
        return resources
    
    def resource_exists(self, context_id: str, resource_name: str) -> bool:
        """Check if resource exists in workspace.
        
        Args:
            context_id: Context identifier
            resource_name: Name of resource
            
        Returns:
            True if resource exists
        """
        workspace_path = self.get_workspace_path(context_id)
        resource_path = workspace_path / resource_name
        return resource_path.exists() or resource_path.is_symlink()
