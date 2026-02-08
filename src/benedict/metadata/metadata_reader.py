"""Metadata Reader

Reads and searches .metadata.benedict files.
"""

import logging
import yaml
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class MetadataReader:
    """Reads and searches metadata overlays."""

    def read_metadata(self, directory: Path) -> Optional[Dict[str, Any]]:
        """Read metadata from directory.

        Args:
            directory: Directory path

        Returns:
            Metadata dictionary or None if not found
        """
        directory = Path(directory)
        metadata_file = directory / ".metadata.benedict"

        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = yaml.safe_load(f)
            logger.debug(f"Read .metadata.benedict from {metadata_file}")
            return metadata
        except Exception as e:
            logger.warning(f"Error reading .metadata.benedict from {metadata_file}: {e}")
            return None

    def search_metadata(
        self, workspace_path: Path, query: str, content_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search metadata files in workspace.

        Args:
            workspace_path: Workspace root path
            query: Search query string
            content_type: Optional content type filter

        Returns:
            List of matching metadata dictionaries with path information
        """
        workspace_path = Path(workspace_path)
        results = []
        query_lower = query.lower()

        # Walk through workspace and read all .metadata.benedict files
        for metadata_file in workspace_path.rglob(".metadata.benedict"):
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
                results.append(
                    {
                        "path": str(metadata_file.parent.relative_to(workspace_path)),
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
        return list(workspace_path.rglob(".metadata.benedict"))
