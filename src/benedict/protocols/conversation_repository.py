"""Conversation Repository Protocol

Defines interface for conversation persistence.
"""

from typing import Protocol, Dict, Optional
from benedict.models.conversation import Conversation


class ConversationRepository(Protocol):
    """Protocol for conversation persistence."""

    def find_by_thread_ts(self, thread_ts: str) -> Optional[Conversation]:
        """Find conversation by thread timestamp.

        Args:
            thread_ts: Thread timestamp identifier

        Returns:
            Conversation if found, None otherwise
        """
        ...

    def find_all(self) -> Dict[str, Conversation]:
        """Find all conversations.

        Returns:
            Dict mapping thread_ts to Conversation
        """
        ...

    def save(self, conversation: Conversation) -> None:
        """Save or update conversation.

        Args:
            conversation: Conversation to save
        """
        ...


def create_conversation_repository(
    provider: str = "json", state_file: str = "state.json"
) -> ConversationRepository:
    """Factory function to create ConversationRepository instance.

    Args:
        provider: Provider name ("json" or "mock")
        state_file: Path to state file (for JSON provider)

    Returns:
        ConversationRepository instance

    Raises:
        ValueError: If provider is unknown
    """
    if provider == "json":
        from benedict.conversation_repository.conversation_repository_json import (
            JsonConversationRepository,
        )

        return JsonConversationRepository(state_file=state_file)
    elif provider == "mock":
        from benedict.conversation_repository.conversation_repository_mock import (
            MockConversationRepository,
        )

        return MockConversationRepository()
    else:
        raise ValueError(f"Unknown provider: {provider}")
