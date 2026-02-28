"""Metadata Reader

Reads and searches .metadata.benedict files.
"""

import logging
import os
import yaml
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

# Directories to exclude when searching for metadata files
# (virtual environments, dependencies, build artifacts, etc.)
_EXCLUDE_DIRS = {
    ".venv",
    "venv",
    "env",
    ".env",
    "ENV",
    "virtualenv",
    "build-env",
    "env-build",
    "node_modules",
    ".node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".git",
    ".hg",
    ".svn",
    "build",
    "dist",
    ".build",
    ".dist",
    ".tox",
    ".coverage",
    "htmlcov",
    ".eggs",
    ".idea",
    ".vscode",
    ".vs",
    ".DS_Store",
    "target",
    ".cargo",
    ".gradle",
    ".maven",
    ".next",
    ".nuxt",
    ".cache",
    ".parcel-cache",
    "coverage",
    ".nyc_output",
    ".sass-cache",
    "site-packages",  # Python package installation directory
}


class MetadataReader:
    """Reads and searches metadata overlays."""

    def __init__(self, metadata_file_path: Optional[str] = None):
        """Initialize metadata reader.

        Args:
            metadata_file_path: Optional path to metadata file (from env var or explicit)
                               If None, uses BENEDICT_METADATA_FILE env var or defaults to .metadata.benedict
        """
        self.metadata_file_path = metadata_file_path or os.environ.get("BENEDICT_METADATA_FILE")

    @staticmethod
    def _should_exclude_path(path: Path) -> bool:
        """Check if a path should be excluded from metadata scanning.

        Args:
            path: Path to check

        Returns:
            True if path should be excluded, False otherwise
        """
        # Check if any part of the path is in excluded directories
        path_parts = path.parts
        if any(
            part in _EXCLUDE_DIRS
            or part.endswith(".egg-info")
            or part.endswith(".dist-info")
            for part in path_parts
        ):
            return True
        return False

    def read_metadata(self, directory: Path) -> Optional[Dict[str, Any]]:
        """Read metadata from directory.

        If BENEDICT_METADATA_FILE env var is set, uses that path.
        Otherwise looks for .metadata.benedict in the directory.

        Args:
            directory: Directory path

        Returns:
            Metadata dictionary or None if not found
        """
        directory = Path(directory)

        # Check for env var or explicit metadata file path
        if self.metadata_file_path:
            metadata_file = Path(self.metadata_file_path)
            # If path is relative, resolve relative to directory
            if not metadata_file.is_absolute():
                metadata_file = directory / metadata_file
        else:
            metadata_file = directory / ".metadata.benedict"

        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = yaml.safe_load(f)
            logger.debug(f"Read .metadata.benedict from {metadata_file}")
            return metadata
        except Exception as e:
            logger.warning(f"Error reading metadata file from {metadata_file}: {e}")
            return None

    def metadata_exists(self, directory: Path) -> bool:
        """Check if metadata file exists for directory.

        Args:
            directory: Directory path

        Returns:
            True if metadata file exists, False otherwise
        """
        directory = Path(directory)

        if self.metadata_file_path:
            metadata_file = Path(self.metadata_file_path)
            if not metadata_file.is_absolute():
                metadata_file = directory / metadata_file
        else:
            metadata_file = directory / ".metadata.benedict"

        return metadata_file.exists()

    def search_metadata(
        self, workspace_path: Path, query: str, content_type: Optional[str] = None, repo: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search metadata files in workspace.

        Args:
            workspace_path: Workspace root path
            query: Search query string
            content_type: Optional content type filter
            repo: Optional repository name to scope search to specific repo only

        Returns:
            List of matching metadata dictionaries with path information
        """
        workspace_path = Path(workspace_path)
        results = []
        query_lower = query.lower()

        # If repo is specified, only search within that repo directory
        if repo:
            search_root = workspace_path / repo
            if not search_root.exists():
                return []
        else:
            search_root = workspace_path

        # Walk through workspace and read all .metadata.benedict files (scoped to repo if specified)
        for metadata_file in search_root.rglob(".metadata.benedict"):
            # Skip files in excluded directories (virtual environments, build artifacts, etc.)
            if self._should_exclude_path(metadata_file):
                continue

            metadata = self.read_metadata(metadata_file.parent)
            if not metadata:
                continue

            # Filter by content type if specified
            if content_type and metadata.get("content_type") != content_type:
                continue

            # Search in summary, purpose, and file names
            matches = False

            summary = str(metadata.get("summary", "")).lower()
            purpose = str(metadata.get("purpose", "")).lower()

            if query_lower in summary or query_lower in purpose:
                matches = True

            # Check file names
            files = metadata.get("files", [])
            for file_info in files:
                file_name = str(file_info.get("name", "")).lower()
                file_purpose = str(file_info.get("purpose", "")).lower()
                if query_lower in file_name or query_lower in file_purpose:
                    matches = True
                    break

            if matches:
                # Calculate relative path from workspace root
                rel_path = str(metadata_file.parent.relative_to(workspace_path))
                results.append(
                    {
                        "path": rel_path,
                        "metadata": metadata,
                    }
                )

        logger.debug(f"Found {len(results)} metadata matches for query '{query}'")
        return results

    def get_directory_summary(self, directory: Path) -> Optional[str]:
        """Get summary for a directory from its .metadata.benedict file.

        Args:
            directory: Directory path

        Returns:
            Summary string or None
        """
        metadata = self.read_metadata(directory)
        if metadata:
            return metadata.get("summary")
        return None

    def list_metadata_files(self, workspace_path: Path) -> List[Path]:
        """List all .metadata.benedict files in workspace.

        Args:
            workspace_path: Workspace root path

        Returns:
            List of .metadata.benedict file paths
        """
        workspace_path = Path(workspace_path)
        metadata_files = []
        for metadata_file in workspace_path.rglob(".metadata.benedict"):
            # Skip files in excluded directories (virtual environments, build artifacts, etc.)
            if not self._should_exclude_path(metadata_file):
                metadata_files.append(metadata_file)
        return metadata_files
