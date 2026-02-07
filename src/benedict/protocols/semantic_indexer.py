"""Semantic Indexer Protocol

Defines interface for semantic code search and indexing.
"""
from typing import Protocol, List, Dict, Optional


class SemanticIndexer(Protocol):
    """Protocol for semantic code indexing and search."""
    
    def index_repository(self, repo: str, repo_reader) -> None:
        """Index a repository for semantic search.
        
        Args:
            repo: Repository identifier
            repo_reader: RepoReader instance to read files
        """
        ...
    
    def search(
        self, 
        repo: str, 
        query: str, 
        top_k: int = 5
    ) -> List[Dict[str, any]]:
        """Search repository using semantic similarity.
        
        Args:
            repo: Repository identifier
            query: Search query/question
            top_k: Number of results to return
            
        Returns:
            List of dicts with keys: 'file_path', 'content', 'score'
        """
        ...
    
    def is_indexed(self, repo: str) -> bool:
        """Check if repository is indexed.
        
        Args:
            repo: Repository identifier
            
        Returns:
            True if repository is indexed
        """
        ...


def create_semantic_indexer(provider: str = "chromadb") -> SemanticIndexer:
    """Factory function to create SemanticIndexer instance.
    
    Args:
        provider: Provider name ("chromadb" or "mock")
        
    Returns:
        SemanticIndexer instance
        
    Raises:
        ValueError: If provider is unknown
    """
    if provider == "chromadb":
        from benedict.semantic_indexer.semantic_indexer_chromadb import ChromaDBSemanticIndexer
        return ChromaDBSemanticIndexer()
    elif provider == "mock":
        from benedict.semantic_indexer.semantic_indexer_mock import MockSemanticIndexer
        return MockSemanticIndexer()
    else:
        raise ValueError(f"Unknown provider: {provider}")
