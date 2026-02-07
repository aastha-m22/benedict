"""Git-based Repository Change Detector

Uses git commands to detect changes in repositories.
"""
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

from benedict.protocols.repo_change_detector import RepoChangeDetector

logger = logging.getLogger(__name__)


class GitChangeDetector:
    """Git-based change detector for repositories."""
    
    def supports_git(self, repo_path: Path) -> bool:
        """Check if repository is a git repository.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            True if git repository, False otherwise
        """
        git_dir = Path(repo_path) / ".git"
        return git_dir.exists() or git_dir.is_dir()
    
    def detect_changes(
        self,
        repo_path: Path,
        since: Optional[datetime] = None,
        branch: str = "main"
    ) -> Dict[str, List[str]]:
        """Detect changes in git repository.
        
        Args:
            repo_path: Path to repository
            since: Optional datetime to detect changes since
            branch: Git branch to check (default: "main")
            
        Returns:
            Dictionary with keys: 'added', 'modified', 'deleted', 'diff'
        """
        repo_path = Path(repo_path).resolve()
        
        if not self.supports_git(repo_path):
            logger.warning(f"Repository {repo_path} is not a git repository")
            return {
                "added": [],
                "modified": [],
                "deleted": [],
                "diff": None
            }
        
        try:
            # Get current branch or use provided branch
            current_branch = self._get_current_branch(repo_path) or branch
            
            # Fetch latest changes
            self._git_fetch(repo_path)
            
            # Check if branch has moved forward
            local_commit = self._get_commit_hash(repo_path, current_branch)
            remote_commit = self._get_commit_hash(repo_path, f"origin/{current_branch}")
            
            if local_commit == remote_commit:
                logger.debug(f"Branch {current_branch} is up to date")
                return {
                    "added": [],
                    "modified": [],
                    "deleted": [],
                    "diff": None
                }
            
            # Get diff between local and remote
            diff_output = self._git_diff(repo_path, local_commit, remote_commit)
            
            # Parse diff to get changed files
            changed_files = self._parse_diff_files(diff_output)
            
            # Filter by since datetime if provided
            if since:
                # Normalize since to UTC for comparison
                since_utc = self._normalize_to_utc(since)
                
                # Get commit timestamps and filter
                filtered_files = {
                    "added": [],
                    "modified": [],
                    "deleted": []
                }
                
                for file_type in ["added", "modified", "deleted"]:
                    for file_path in changed_files.get(file_type, []):
                        file_commit_time = self._get_file_last_commit_time(repo_path, file_path, remote_commit)
                        if file_commit_time and file_commit_time > since_utc:
                            filtered_files[file_type].append(file_path)
                
                changed_files = filtered_files
            
            logger.info(f"Detected changes in {repo_path}: "
                       f"{len(changed_files['added'])} added, "
                       f"{len(changed_files['modified'])} modified, "
                       f"{len(changed_files['deleted'])} deleted")
            
            return {
                **changed_files,
                "diff": diff_output
            }
            
        except Exception as e:
            logger.error(f"Error detecting git changes: {e}", exc_info=True)
            return {
                "added": [],
                "modified": [],
                "deleted": [],
                "diff": None
            }
    
    def get_last_commit_time(self, repo_path: Path, branch: str = "main") -> Optional[datetime]:
        """Get timestamp of last commit on branch.
        
        Args:
            repo_path: Path to repository
            branch: Git branch to check
            
        Returns:
            Datetime of last commit, or None if not available
        """
        try:
            repo_path = Path(repo_path).resolve()
            if not self.supports_git(repo_path):
                return None
            
            # Try origin/branch first, fallback to local branch
            refs = [f"origin/{branch}", branch]
            
            for ref in refs:
                try:
                    result = subprocess.run(
                        ["git", "log", "-1", "--format=%ct", ref],
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    if result.stdout.strip():
                        timestamp = int(result.stdout.strip())
                        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
                except (subprocess.CalledProcessError, ValueError):
                    continue
            
            return None
            
        except Exception as e:
            logger.warning(f"Error getting last commit time: {e}")
            return None
    
    def _get_current_branch(self, repo_path: Path) -> Optional[str]:
        """Get current git branch."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
    
    def _git_fetch(self, repo_path: Path) -> None:
        """Fetch latest changes from remote."""
        try:
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=repo_path,
                capture_output=True,
                check=False  # Don't fail if no remote
            )
        except Exception as e:
            logger.debug(f"Error fetching: {e}")
    
    def _get_commit_hash(self, repo_path: Path, ref: str) -> Optional[str]:
        """Get commit hash for ref."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", ref],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
    
    def _git_diff(self, repo_path: Path, from_ref: str, to_ref: str) -> str:
        """Get diff between two refs."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-status", from_ref, to_ref],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error getting diff: {e}")
            return ""
    
    def _parse_diff_files(self, diff_output: str) -> Dict[str, List[str]]:
        """Parse git diff output to extract changed files.
        
        Git diff --name-status format:
        A <file>  - Added
        M <file>  - Modified
        D <file>  - Deleted
        """
        added = []
        modified = []
        deleted = []
        
        for line in diff_output.strip().split('\n'):
            if not line.strip():
                continue
            
            parts = line.split('\t', 1)
            if len(parts) != 2:
                continue
            
            status = parts[0].strip()
            file_path = parts[1].strip()
            
            if status.startswith('A'):
                added.append(file_path)
            elif status.startswith('M'):
                modified.append(file_path)
            elif status.startswith('D'):
                deleted.append(file_path)
        
        return {
            "added": added,
            "modified": modified,
            "deleted": deleted
        }
    
    def _get_file_last_commit_time(self, repo_path: Path, file_path: str, ref: str) -> Optional[datetime]:
        """Get last commit time for a specific file."""
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ct", ref, "--", file_path],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            if result.stdout.strip():
                timestamp = int(result.stdout.strip())
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (subprocess.CalledProcessError, ValueError):
            pass
        return None
    
    def _normalize_to_utc(self, dt: datetime) -> datetime:
        """Normalize datetime to UTC for comparison.
        
        Args:
            dt: Datetime to normalize (may be timezone-aware or naive)
            
        Returns:
            Timezone-aware datetime in UTC
        """
        if dt.tzinfo is None:
            # Naive datetime - assume UTC
            return dt.replace(tzinfo=timezone.utc)
        else:
            # Timezone-aware datetime - convert to UTC
            return dt.astimezone(timezone.utc)