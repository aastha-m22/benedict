"""Repository Change Detector Protocol

Abstract interface for detecting changes in repositories.
Supports git-based detection and file-watching.
"""

from typing import Protocol, List, Dict, Optional
from datetime import datetime
from pathlib import Path


class RepoChangeDetector(Protocol):
    """Protocol for detecting repository changes."""

    def detect_changes(
        self, repo_path: Path, since: Optional[datetime] = None, branch: str = "main"
    ) -> Dict[str, List[str]]:
        """Detect changes in repository.

        Args:
            repo_path: Path to repository
            since: Optional datetime to detect changes since
            branch: Git branch to check (default: "main")

        Returns:
            Dictionary with keys:
            - 'added': List of added file paths (relative to repo root)
            - 'modified': List of modified file paths (relative to repo root)
            - 'deleted': List of deleted file paths (relative to repo root)
            - 'diff': Optional diff text (if git-based)
        """
        ...

    def get_last_commit_time(self, repo_path: Path, branch: str = "main") -> Optional[datetime]:
        """Get timestamp of last commit on branch.

        Args:
            repo_path: Path to repository
            branch: Git branch to check

        Returns:
            Datetime of last commit, or None if not available
        """
        ...

    def supports_git(self, repo_path: Path) -> bool:
        """Check if repository is a git repository.

        Args:
            repo_path: Path to repository

        Returns:
            True if git repository, False otherwise
        """
        ...


def create_repo_change_detector(detector_type: str = "auto") -> RepoChangeDetector:
    """Factory function to create RepoChangeDetector instance.

    Args:
        detector_type: Type of detector ("git", "file_watcher", or "auto")

    Returns:
        RepoChangeDetector instance

    Raises:
        ValueError: If detector_type is unknown
    """
    if detector_type == "git":
        from benedict.repo_change_detector.git_change_detector import GitChangeDetector

        return GitChangeDetector()
    elif detector_type == "file_watcher":
        from benedict.repo_change_detector.file_watcher_detector import FileWatcherDetector

        return FileWatcherDetector()
    elif detector_type == "auto":
        # Try git first, fallback to file watcher
        from benedict.repo_change_detector.git_change_detector import GitChangeDetector

        return GitChangeDetector()  # Git detector can detect if repo is git or not
    else:
        raise ValueError(f"Unknown detector_type: {detector_type}")
