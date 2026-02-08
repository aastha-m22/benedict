"""Workspace Repository Reader Adapter

Adapts WorkspaceRepoReader to the RepoReader protocol by binding to a channel_id.
"""

import logging
from typing import List

from benedict.repo_reader.repo_reader_workspace import WorkspaceRepoReader

logger = logging.getLogger(__name__)


class WorkspaceRepoReaderAdapter:
    """Adapter that makes WorkspaceRepoReader conform to RepoReader protocol.

    This adapter binds a channel_id (context_id) so that the standard RepoReader
    interface (repo, path) can be used with workspace-based reading.
    """

    def __init__(self, workspace_reader: WorkspaceRepoReader, channel_id: str):
        """Initialize adapter.

        Args:
            workspace_reader: WorkspaceRepoReader instance
            channel_id: Channel ID to bind to (used as context_id)
        """
        self.workspace_reader = workspace_reader
        self.channel_id = channel_id
        logger.info(f"Initialized WorkspaceRepoReaderAdapter for channel {channel_id}")

    def read_file(self, repo: str, path: str) -> str:
        """Read file from workspace resource.

        Args:
            repo: Repository identifier (resource name in workspace)
            path: File path relative to repository root

        Returns:
            File content as string
        """
        return self.workspace_reader.read_file(self.channel_id, repo, path)

    def list_files(self, repo: str, path: str = "") -> List[str]:
        """List files in workspace resource.

        Args:
            repo: Repository identifier (resource name in workspace)
            path: Directory path relative to resource root

        Returns:
            List of file paths
        """
        return self.workspace_reader.list_files(self.channel_id, repo, path)

    def file_exists(self, repo: str, path: str) -> bool:
        """Check if file exists in workspace resource.

        Args:
            repo: Repository identifier (resource name in workspace)
            path: File path relative to repository root

        Returns:
            True if file exists
        """
        return self.workspace_reader.file_exists(self.channel_id, repo, path)
