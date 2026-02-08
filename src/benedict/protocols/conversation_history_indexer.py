"""Conversation History Indexer Protocol

Abstract interface for indexing conversation history from any platform.
"""

from typing import Protocol, Optional
from datetime import datetime
from pathlib import Path


class ConversationReader(Protocol):
    """Protocol for reading conversations."""

    def read_conversations(
        self, context_id: str, since: Optional[datetime] = None, limit: Optional[int] = None
    ) -> list:
        """Read conversations.

        Args:
            context_id: Context identifier
            since: Optional datetime to get conversations since
            limit: Optional limit on number of conversations

        Returns:
            List of conversation dictionaries
        """
        ...


class ConversationHistoryIndexer(Protocol):
    """Protocol for indexing conversation history from any platform."""

    def index_conversations(
        self,
        context_id: str,
        workspace_path: Path,
        since: Optional[datetime] = None,
        semantic_indexer=None,
    ) -> None:
        """Index conversations into workspace.

        Args:
            context_id: Context identifier
            workspace_path: Path to workspace directory
            since: Optional datetime to index conversations since (for incremental updates)
            semantic_indexer: Optional semantic indexer to also index conversations for search
        """
        ...

    def update_index(
        self,
        context_id: str,
        workspace_path: Path,
        since: Optional[datetime] = None,
        semantic_indexer=None,
    ) -> None:
        """Incrementally update conversation index with new messages.

        Args:
            context_id: Context identifier
            workspace_path: Path to workspace directory
            since: Datetime to index conversations since (required for incremental updates)
            semantic_indexer: Optional semantic indexer to also index conversations for search
        """
        ...

    def get_conversation_reader(self, workspace_path: Path) -> ConversationReader:
        """Get reader for accessing conversations.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            ConversationReader instance
        """
        ...


def create_conversation_history_indexer(
    platform: str = "slack", slack_client=None
) -> ConversationHistoryIndexer:
    """Factory function to create ConversationHistoryIndexer instance.

    Args:
        platform: Platform name ("slack", "discord", "mock", etc.)
        slack_client: Optional Slack client for Slack platform

    Returns:
        ConversationHistoryIndexer instance

    Raises:
        ValueError: If platform is unknown
    """
    if platform == "slack":
        from benedict.indexers.slack_history_indexer import SlackConversationHistoryIndexer

        return SlackConversationHistoryIndexer(slack_client=slack_client)
    elif platform == "mock":
        from benedict.indexers.slack_history_indexer import MockConversationHistoryIndexer

        return MockConversationHistoryIndexer()
    else:
        raise ValueError(f"Unknown platform: {platform}")
