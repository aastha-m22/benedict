"""Mock Repository Reader Implementation

Mock repository reader for testing purposes.
"""
import logging
from typing import List, Dict
from benedict.protocols.repo_reader import RepoReader

logger = logging.getLogger(__name__)


class MockRepoReader:
    """Mock repository reader with in-memory file storage."""
    
    def __init__(self, repos: Dict[str, Dict[str, str]] = None):
        """Initialize mock repo reader.
        
        Args:
            repos: Dict mapping repo names to dicts of {path: content}
                   If None, creates empty structure.
        """
        self.repos = repos or {}
        logger.info(f"Initialized MockRepoReader with {len(self.repos)} repos")
    
    def read_file(self, repo: str, path: str) -> str:
        """Read file from mock repository.
        
        Args:
            repo: Repository name
            path: File path relative to repository root
            
        Returns:
            File content
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if repo not in self.repos:
            raise FileNotFoundError(f"Repository not found: {repo}")
        
        if path not in self.repos[repo]:
            raise FileNotFoundError(f"File not found: {path} in repo {repo}")
        
        return self.repos[repo][path]
    
    def list_files(self, repo: str, path: str = "") -> List[str]:
        """List files in mock repository.
        
        Args:
            repo: Repository name
            path: Directory path (ignored in mock, returns all files)
            
        Returns:
            List of file paths
        """
        if repo not in self.repos:
            return []
        
        return list(self.repos[repo].keys())
    
    def walk(self, repo: str, path: str = "") -> List[str]:
        """Walk through mock repository directory.
        
        Args:
            repo: Repository name
            path: Directory path (ignored in mock, returns all files)
            
        Returns:
            List of file paths
        """
        return list(self.repos[repo].keys())
    
    def walk_files(self, repo: str, path: str = "") -> List[str]:
        """Walk through mock repository directory and return only files.
        
        Args:
            repo: Repository name
            path: Directory path (ignored in mock, returns all files)
            
        Returns:
            List of file paths
        """
        return list(self.repos[repo].keys())
    
    def walk_dirs(self, repo: str, path: str = "") -> List[str]:
        """Walk through mock repository directory and return only directories.
        
        Args:
            repo: Repository name
            path: Directory path (ignored in mock, returns all directories)
            
        Returns:
            List of directory paths
        """
        return []
    
    def file_exists(self, repo: str, path: str) -> bool:
        """Check if file exists in mock repository.
        
        Args:
            repo: Repository name
            path: File path
            
        Returns:
            True if file exists
        """
        return repo in self.repos and path in self.repos[repo]
