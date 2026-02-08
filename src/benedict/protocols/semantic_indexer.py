"""Semantic Indexer Protocol

Defines interface for semantic code search and indexing.
"""

from datetime import datetime
from typing import Protocol, List, Dict, Optional


class SemanticIndexer(Protocol):
    """Protocol for semantic code indexing and search."""

    def index_repository(
        self, repo: str, repo_reader, workspace_path=None, force: bool = False
    ) -> None:
        """Index a repository for semantic search.

        Args:
            repo: Repository identifier
            repo_reader: RepoReader instance to read files
            workspace_path: Optional workspace path for generating metadata overlays
            force: If True, reindex even if already indexed (default: False, incremental update)
        """
        ...

    def update_index(
        self, repo: str, repo_reader, workspace_path=None, since: Optional[datetime] = None
    ) -> None:
        """Incrementally update index with new/changed content.

        Args:
            repo: Repository identifier
            repo_reader: RepoReader instance to read files
            workspace_path: Optional workspace path for generating metadata overlays
            since: Optional datetime to only index files modified since this time
        """
        ...

    def search(self, repo: str, query: str, top_k: int = 5) -> List[Dict[str, any]]:
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


def create_semantic_indexer(
    provider: str = "chromadb",
    persist_directory: Optional[str] = None,
    metadata_generator=None,
    change_detector=None,
) -> SemanticIndexer:
    """Factory function to create SemanticIndexer instance.

    Args:
        provider: Provider name ("chromadb" or "mock")
        persist_directory: Optional directory path for ChromaDB persistence
        metadata_generator: Optional metadata generator for creating METADATA overlays
        change_detector: Optional change detector for git-based incremental updates

    Returns:
        SemanticIndexer instance

    Raises:
        ValueError: If provider is unknown
    """
    if provider == "chromadb":
        from benedict.semantic_indexer.semantic_indexer_chromadb import ChromaDBSemanticIndexer

        if persist_directory:
            return ChromaDBSemanticIndexer(
                persist_directory=persist_directory,
                metadata_generator=metadata_generator,
                change_detector=change_detector,
            )
        return ChromaDBSemanticIndexer(
            metadata_generator=metadata_generator, change_detector=change_detector
        )
    elif provider == "mock":
        from benedict.semantic_indexer.semantic_indexer_mock import MockSemanticIndexer

        return MockSemanticIndexer()
    else:
        raise ValueError(f"Unknown provider: {provider}")
