"""Mock Semantic Indexer Implementation

Mock semantic indexer for testing purposes.
"""

import logging
from typing import List, Dict, Any
from benedict.protocols.repo_reader import RepoReader

logger = logging.getLogger(__name__)


class MockSemanticIndexer:
    """Mock semantic indexer that simulates semantic search."""

    def __init__(self):
        """Initialize mock semantic indexer."""
        self.indexed_repos: set = set()
        logger.info("Initialized MockSemanticIndexer")

    def index_repository(self, repo: str, repo_reader: RepoReader) -> None:
        """Mock repository indexing.

        Args:
            repo: Repository identifier
            repo_reader: RepoReader instance (ignored)
        """
        self.indexed_repos.add(repo)
        logger.debug(f"Mock indexed repository {repo}")

    def search(self, repo: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Mock semantic search.

        Args:
            repo: Repository identifier
            query: Search query
            top_k: Number of results

        Returns:
            Mock results
        """
        if repo not in self.indexed_repos:
            return []

        # Return mock results based on query keywords
        keywords = query.lower().split()
        mock_files = [f"file_{kw}.py" for kw in keywords[:top_k] if len(kw) > 3]

        results = []
        for i, file_path in enumerate(mock_files[:top_k]):
            results.append(
                {
                    "file_path": file_path,
                    "content": f"[Mock content for {file_path} related to: {query}]",
                    "score": 0.9 - (i * 0.1),
                }
            )

        return results

    def is_indexed(self, repo: str) -> bool:
        """Check if repository is indexed.

        Args:
            repo: Repository identifier

        Returns:
            True if mock-indexed
        """
        return repo in self.indexed_repos
