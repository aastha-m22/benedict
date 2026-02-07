"""JSON Conversation Repository Implementation

Persists conversations to JSON file.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional
from benedict.models.conversation import Conversation
from benedict.protocols.conversation_repository import ConversationRepository

logger = logging.getLogger(__name__)


class JsonConversationRepository:
    """JSON file-based conversation repository."""
    
    def __init__(self, state_file: str = "state.json"):
        """Initialize JSON conversation repository.
        
        Args:
            state_file: Path to state JSON file
        """
        self.state_file = Path(state_file)
        logger.debug(f"Initialized JsonConversationRepository with state_file={state_file}")
    
    def find_by_thread_ts(self, thread_ts: str) -> Optional[Conversation]:
        """Find conversation by thread timestamp.
        
        Args:
            thread_ts: Thread timestamp identifier
            
        Returns:
            Conversation if found, None otherwise
        """
        conversations = self.find_all()
        return conversations.get(thread_ts)
    
    def find_all(self) -> Dict[str, Conversation]:
        """Find all conversations.
        
        Returns:
            Dict mapping thread_ts to Conversation
        """
        if not self.state_file.exists():
            return {}
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            conversations_data = state.get("conversations", {})
            conversations = {}
            for thread_ts, conv_data in conversations_data.items():
                try:
                    conversations[thread_ts] = Conversation.from_dict(conv_data)
                except Exception as e:
                    logger.warning(f"Error loading conversation {thread_ts}: {e}")
                    continue
            
            logger.debug(f"Loaded {len(conversations)} conversations")
            return conversations
        except Exception as e:
            logger.error(f"Error loading conversations: {e}")
            return {}
    
    def save(self, conversation: Conversation) -> None:
        """Save or update conversation.
        
        Args:
            conversation: Conversation to save
        """
        # Load existing state
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
            except Exception:
                state = {}
        else:
            state = {}
        
        # Ensure conversations dict exists
        if "conversations" not in state:
            state["conversations"] = {}
        
        # Save conversation
        state["conversations"][conversation.thread_ts] = conversation.to_dict()
        
        # Write back
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            logger.debug(f"Saved conversation {conversation.thread_ts}")
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
