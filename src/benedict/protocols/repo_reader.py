"""RepoReader Protocol Definition

Defines the interface for repository file readers.
"""
from typing import Protocol, List, Optional


class RepoReader(Protocol):
    """Protocol for repository file readers."""
    
    def read_file(self, repo: str, path: str) -> str:
        """Read single file content from repository.
        
        Args:
            repo: Repository identifier/name
            path: File path relative to repository root
            
        Returns:
            File content as string
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        ...
    
    def list_files(self, repo: str, path: str = "") -> List[str]:
        """List files in repository directory.
        
        Args:
            repo: Repository identifier/name
            path: Directory path relative to repository root (empty = root)
            
        Returns:
            List of file paths relative to the specified path
        """
        ...
    
    def file_exists(self, repo: str, path: str) -> bool:
        """Check if file exists in repository.
        
        Args:
            repo: Repository identifier/name
            path: File path relative to repository root
            
        Returns:
            True if file exists, False otherwise
        """
        ...


def create_repo_reader(source: str = "local") -> RepoReader:
    """Factory function to create RepoReader instance.
    
    Args:
        source: Source type ("local" or "mock")
        
    Returns:
        RepoReader instance
        
    Raises:
        ValueError: If source is unknown
    """
    if source == "local":
        from benedict.repo_reader.repo_reader_local import LocalRepoReader
        return LocalRepoReader()
    elif source == "mock":
        from benedict.repo_reader.repo_reader_mock import MockRepoReader
        return MockRepoReader()
    else:
        raise ValueError(f"Unknown source: {source}")
