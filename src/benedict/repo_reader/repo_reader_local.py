"""Local Repository Reader Implementation

Reads repository files from local filesystem.
"""

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class LocalRepoReader:
    """Local filesystem repository reader."""

    def __init__(self, base_path: str = "./repos"):
        """Initialize local repo reader.

        Args:
            base_path: Base directory containing repositories
        """
        self.base_path = Path(base_path).resolve()
        logger.info(f"Initialized LocalRepoReader with base_path: {self.base_path}")

    def read_file(self, repo: str, path: str) -> str:
        """Read file from repository.

        Args:
            repo: Repository name/identifier
            path: File path relative to repository root

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        full_path = self.base_path / repo / path

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path} in repo {repo}")

        if not full_path.is_file():
            raise ValueError(f"Path is not a file: {path} in repo {repo}")

        try:
            return full_path.read_text()
        except Exception as e:
            logger.error(f"Error reading file {path} in repo {repo}: {e}")
            raise

    def list_files(self, repo: str, path: str = "") -> List[str]:
        """List files in repository directory.

        Args:
            repo: Repository name/identifier
            path: Directory path relative to repository root (empty = root)

        Returns:
            List of file paths relative to the specified path
        """
        full_path = self.base_path / repo / path

        if not full_path.exists():
            logger.warning(f"Path does not exist: {path} in repo {repo}")
            return []

        if not full_path.is_dir():
            # If path is a file, return just that file
            if full_path.is_file():
                return [str(Path(path).name)]
            return []

        files = []
        try:
            # rglob("*") doesn't match dotfiles, so we need to handle them separately
            # First, get all regular files (non-dotfiles)
            for p in full_path.rglob("*"):
                if p.is_file():
                    rel_path = p.relative_to(full_path)
                    files.append(str(rel_path))
            
            # Also include .metadata.* files (dotfiles)
            # These need explicit globbing since rglob("*") skips them
            for pattern in [".metadata.*"]:
                # Check root level
                for p in full_path.glob(pattern):
                    if p.is_file():
                        rel_path = p.relative_to(full_path)
                        if str(rel_path) not in files:
                            files.append(str(rel_path))
                # Check subdirectories recursively
                for p in full_path.rglob(f"**/{pattern}"):
                    if p.is_file():
                        rel_path = p.relative_to(full_path)
                        if str(rel_path) not in files:
                            files.append(str(rel_path))
            
            return sorted(files)
        except Exception as e:
            logger.error(f"Error listing files in {path} for repo {repo}: {e}")
            return []

    def walk(self, repo: str, path: str = "") -> List[str]:
        """Walk through repository directory.

        Args:
            repo: Repository name/identifier
            path: Directory path relative to repository root
        """
        full_path = self.base_path / repo / path
        return full_path.walk()

    def walk_files(self, repo: str, path: str = "") -> List[str]:
        """Walk through repository directory and return only files.

        Args:
            repo: Repository name/identifier
            path: Directory path relative to repository root
        """
        return [p for p in self.walk(repo, path) if p.is_file()]

    def walk_dirs(self, repo: str, path: str = "") -> List[str]:
        """Walk through repository directory and return only directories.

        Args:
            repo: Repository name/identifier
            path: Directory path relative to repository root
        """
        return [p for p in self.walk(repo, path) if p.is_dir()]

    def file_exists(self, repo: str, path: str) -> bool:
        """Check if file exists in repository.

        Args:
            repo: Repository name/identifier
            path: File path relative to repository root

        Returns:
            True if file exists, False otherwise
        """
        full_path = self.base_path / repo / path
        return full_path.exists() and full_path.is_file()
