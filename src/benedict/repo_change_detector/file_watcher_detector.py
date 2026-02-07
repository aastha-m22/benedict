"""File Watcher-based Change Detector

Uses file system watching to detect changes (fallback for non-git repos).
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from benedict.protocols.repo_change_detector import RepoChangeDetector

logger = logging.getLogger(__name__)


class FileWatcherDetector:
    """File system watcher-based change detector (fallback for non-git repos)."""
    
    def supports_git(self, repo_path: Path) -> bool:
        """Check if repository is a git repository.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            False (this detector is for non-git repos)
        """
        return False
    
    def detect_changes(
        self,
        repo_path: Path,
        since: Optional[datetime] = None,
        branch: str = "main"
    ) -> Dict[str, List[str]]:
        """Detect changes by comparing file modification times.
        
        Note: This is a simple implementation. For production, consider using
        watchdog library for real-time file watching.
        
        Args:
            repo_path: Path to repository
            since: Optional datetime to detect changes since
            branch: Not used for file watcher (kept for interface compatibility)
            
        Returns:
            Dictionary with keys: 'added', 'modified', 'deleted', 'diff'
        """
        repo_path = Path(repo_path).resolve()
        
        if not repo_path.exists():
            return {
                "added": [],
                "modified": [],
                "deleted": [],
                "diff": None
            }
        
        if not since:
            # Without a timestamp, we can't detect changes
            logger.warning("FileWatcherDetector requires 'since' parameter")
            return {
                "added": [],
                "modified": [],
                "deleted": [],
                "diff": None
            }
        
        added = []
        modified = []
        deleted = []
        
        # Walk through repository and check modification times
        try:
            for file_path in repo_path.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    try:
                        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        rel_path = str(file_path.relative_to(repo_path))
                        
                        if file_mtime > since:
                            # File was modified after 'since'
                            # We can't distinguish between added and modified without tracking
                            # So we'll mark as modified (can be refined later)
                            modified.append(rel_path)
                    except (OSError, ValueError) as e:
                        logger.debug(f"Error checking file {file_path}: {e}")
                        continue
            
            logger.info(f"Detected changes in {repo_path}: "
                       f"{len(modified)} modified files")
            
        except Exception as e:
            logger.error(f"Error detecting file changes: {e}", exc_info=True)
        
        return {
            "added": added,
            "modified": modified,
            "deleted": deleted,
            "diff": None  # File watcher doesn't provide diff
        }
    
    def get_last_commit_time(self, repo_path: Path, branch: str = "main") -> Optional[datetime]:
        """Get last modification time of repository.
        
        Args:
            repo_path: Path to repository
            branch: Not used (kept for interface compatibility)
            
        Returns:
            Last modification time of any file in repository
        """
        repo_path = Path(repo_path).resolve()
        
        if not repo_path.exists():
            return None
        
        latest_mtime = None
        
        try:
            for file_path in repo_path.rglob("*"):
                if file_path.is_file():
                    try:
                        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if latest_mtime is None or file_mtime > latest_mtime:
                            latest_mtime = file_mtime
                    except (OSError, ValueError):
                        continue
        except Exception as e:
            logger.debug(f"Error getting last modification time: {e}")
        
        return latest_mtime
