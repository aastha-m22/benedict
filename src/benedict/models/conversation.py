"""Conversation Model

Tracks message history for a conversation thread.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Single message in a conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp}

    def to_json(self) -> str:
        """Convert to JSON."""
        return json.dumps(self.to_dict())

    def from_json(self, json_str: str) -> "Message":
        """Create from JSON."""
        return self.from_dict(json.loads(json_str))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create from dictionary."""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
        )


@dataclass
class Conversation:
    """Conversation thread with message history."""

    thread_ts: str  # Slack thread timestamp (unique identifier)
    channel_id: str
    repo: str
    messages: List[Message] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation.

        Args:
            role: Message role ("user" or "assistant")
            content: Message content
        """
        message = Message(role=role, content=content)
        self.messages.append(message)
        self.updated_at = datetime.utcnow().isoformat() + "Z"
        logger.debug(f"Added {role} message to conversation {self.thread_ts}")

    def get_messages(self, max_messages: Optional[int] = None) -> List[Message]:
        """Get conversation messages.

        Args:
            max_messages: Optional limit on number of messages (returns most recent)

        Returns:
            List of messages
        """
        if max_messages is None:
            return self.messages.copy()

        # Return most recent messages
        return (
            self.messages[-max_messages:]
            if len(self.messages) > max_messages
            else self.messages.copy()
        )

    def get_message_history(self, max_messages: Optional[int] = None) -> List[Dict[str, str]]:
        """Get message history in format suitable for LLM.

        Args:
            max_messages: Optional limit on number of messages

        Returns:
            List of message dicts with "role" and "content"
        """
        messages = self.get_messages(max_messages)
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "thread_ts": self.thread_ts,
            "channel_id": self.channel_id,
            "repo": self.repo,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_json(self) -> str:
        """Convert to JSON."""
        return json.dumps(self.to_dict())

    def from_json(self, json_str: str) -> "Conversation":
        """Create from JSON."""
        return self.from_dict(json.loads(json_str))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Conversation":
        """Create from dictionary."""
        return cls(
            thread_ts=data["thread_ts"],
            channel_id=data["channel_id"],
            repo=data["repo"],
            messages=[Message.from_dict(msg) for msg in data.get("messages", [])],
            created_at=data.get("created_at", datetime.utcnow().isoformat() + "Z"),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat() + "Z"),
        )


class ConversationManager:
    """Manages conversations across threads.

    Business logic layer that uses ConversationRepository for persistence.
    """

    def __init__(self, repository):
        """Initialize conversation manager.

        Args:
            repository: ConversationRepository instance for persistence
        """
        self.repository = repository
        logger.debug("Initialized ConversationManager")

    def get_conversation(self, thread_ts: str, channel_id: str, repo: str) -> Conversation:
        """Get or create conversation for thread.

        Args:
            thread_ts: Thread timestamp
            channel_id: Channel ID
            repo: Repository name

        Returns:
            Conversation instance
        """
        # Try to find existing conversation
        conv = self.repository.find_by_thread_ts(thread_ts)

        if conv:
            # Update repo if it changed (e.g., channel was re-onboarded)
            if conv.repo != repo:
                conv.repo = repo
                self.repository.save(conv)
            return conv

        # Create new conversation
        conv = Conversation(thread_ts=thread_ts, channel_id=channel_id, repo=repo)
        self.repository.save(conv)
        return conv

    def save_conversation(self, conversation: Conversation) -> None:
        """Save a conversation.

        Args:
            conversation: Conversation to save
        """
        self.repository.save(conversation)
