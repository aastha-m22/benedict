"""Mock Conversation Repository Implementation

In-memory conversation repository for testing.
"""
import logging
from typing import Dict, Optional
from benedict.models.conversation import Conversation
from benedict.protocols.conversation_repository import ConversationRepository

logger = logging.getLogger(__name__)


class MockConversationRepository:
    """In-memory mock conversation repository."""
    
    def __init__(self):
        """Initialize mock conversation repository."""
        self.conversations: Dict[str, Conversation] = {}
        logger.info("Initialized MockConversationRepository")
    
    def find_by_thread_ts(self, thread_ts: str) -> Optional[Conversation]:
        """Find conversation by thread timestamp.
        
        Args:
            thread_ts: Thread timestamp identifier
            
        Returns:
            Conversation if found, None otherwise
        """
        return self.conversations.get(thread_ts)
    
    def find_all(self) -> Dict[str, Conversation]:
        """Find all conversations.
        
        Returns:
            Dict mapping thread_ts to Conversation
        """
        return self.conversations.copy()
    
    def save(self, conversation: Conversation) -> None:
        """Save or update conversation.
        
        Args:
            conversation: Conversation to save
        """
        self.conversations[conversation.thread_ts] = conversation
        logger.debug(f"Mock saved conversation {conversation.thread_ts}")
