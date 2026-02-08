"""Workspace Repository Reader

Reads from workspace structure instead of direct repository paths.
Supports all content types uniformly.
"""

import logging
from pathlib import Path
from typing import List

from benedict.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class WorkspaceRepoReader:
    """Reads from workspace structure (all content types)."""

    def __init__(self, workspace_manager: WorkspaceManager):
        """Initialize workspace repo reader.

        Args:
            workspace_manager: WorkspaceManager instance
        """
        self.workspace_manager = workspace_manager
        logger.info("Initialized WorkspaceRepoReader")

    def read_file(self, context_id: str, resource_name: str, path: str) -> str:
        """Read file from workspace resource.

        Args:
            context_id: Context identifier (e.g., channel_id)
            resource_name: Resource name in workspace (e.g., repo name)
            path: File path relative to resource root

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        workspace_path = self.workspace_manager.get_workspace_path(context_id)
        resource_path = workspace_path / resource_name / path

        if not resource_path.exists():
            raise FileNotFoundError(
                f"File not found: {path} in resource {resource_name} for context {context_id}"
            )

        if not resource_path.is_file():
            raise ValueError(f"Path is not a file: {path} in resource {resource_name}")

        try:
            return resource_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Error reading file {path} in resource {resource_name}: {e}")
            raise

    def list_files(self, context_id: str, resource_name: str, path: str = "") -> List[str]:
        """List files in workspace resource directory.

        Args:
            context_id: Context identifier
            resource_name: Resource name in workspace
            path: Directory path relative to resource root (empty = root)

        Returns:
            List of file paths relative to the specified path
        """
        workspace_path = self.workspace_manager.get_workspace_path(context_id)
        full_path = workspace_path / resource_name / path

        if not full_path.exists():
            logger.warning(f"Path does not exist: {path} in resource {resource_name}")
            return []

        if not full_path.is_dir():
            # If path is a file, return just that file
            if full_path.is_file():
                return [str(Path(path).name)]
            return []

        files = []
        try:
            for p in full_path.rglob("*"):
                # Skip .metadata.benedict files (dotfiles are typically hidden anyway)
                if p.is_file() and p.name != ".metadata.benedict":
                    rel_path = p.relative_to(full_path)
                    files.append(str(rel_path))
            return sorted(files)
        except Exception as e:
            logger.error(f"Error listing files in {path} for resource {resource_name}: {e}")
            return []

    def file_exists(self, context_id: str, resource_name: str, path: str) -> bool:
        """Check if file exists in workspace resource.

        Args:
            context_id: Context identifier
            resource_name: Resource name in workspace
            path: File path relative to resource root

        Returns:
            True if file exists, False otherwise
        """
        workspace_path = self.workspace_manager.get_workspace_path(context_id)
        resource_path = workspace_path / resource_name / path
        return resource_path.exists() and resource_path.is_file()

    def list_resources(self, context_id: str) -> List[str]:
        """List all resources in workspace.

        Args:
            context_id: Context identifier

        Returns:
            List of resource names
        """
        resources = self.workspace_manager.list_resources(context_id)
        return [r.name for r in resources]
