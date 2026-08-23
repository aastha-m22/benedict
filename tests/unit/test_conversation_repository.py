"""Tests for conversation repository implementations.

Tests the ConversationRepository protocol and implementations.
"""

import json
import pytest

from benedict.models import Conversation, Message
from benedict.conversation_repository import MockConversationRepository, JSONConversationRepository


class TestMockConversationRepository:
    """Tests for MockConversationRepository."""

    def test_initialization(self):
        """Test repository initialization."""
        repo = MockConversationRepository()
        assert repo is not None

    def test_save_conversation(self):
        """Test saving a conversation."""
        repo = MockConversationRepository()
        conv = Conversation(
            thread_ts="1234567890.123456",
            channel_id="C123456",
            repo="example-org/repo",
        )
        
        repo.save_conversation(conv)
        
        # Should be able to retrieve it
        retrieved = repo.get_conversation("1234567890.123456")
        assert retrieved is not None
        assert retrieved.thread_ts == "1234567890.123456"

    def test_get_nonexistent_conversation(self):
        """Test getting a conversation that doesn't exist."""
        repo = MockConversationRepository()
        conv = repo.get_conversation("nonexistent")
        assert conv is None

    def test_save_and_retrieve_with_messages(self):
        """Test saving and retrieving conversation with messages."""
        repo = MockConversationRepository()
        conv = Conversation(
            thread_ts="1234567890.123456",
            channel_id="C123456",
            repo="example-org/repo",
        )
        conv.add_message("user", "Question")
        conv.add_message("assistant", "Answer")
        
        repo.save_conversation(conv)
        
        retrieved = repo.get_conversation("1234567890.123456")
        assert len(retrieved.messages) == 2
        assert retrieved.messages[0].content == "Question"

    def test_update_conversation(self):
        """Test updating an existing conversation."""
        repo = MockConversationRepository()
        conv = Conversation(
            thread_ts="1234567890.123456",
            channel_id="C123456",
            repo="example-org/repo",
        )
        conv.add_message("user", "Question")
        repo.save_conversation(conv)
        
        # Add more messages and save again
        conv.add_message("assistant", "Answer")
        repo.save_conversation(conv)
        
        retrieved = repo.get_conversation("1234567890.123456")
        assert len(retrieved.messages) == 2

    def test_multiple_conversations(self):
        """Test managing multiple conversations."""
        repo = MockConversationRepository()
        
        conv1 = Conversation(
            thread_ts="1111111111.111111",
            channel_id="C111111",
            repo="org1/repo1",
        )
        conv2 = Conversation(
            thread_ts="2222222222.222222",
            channel_id="C222222",
            repo="org2/repo2",
        )
        
        repo.save_conversation(conv1)
        repo.save_conversation(conv2)
        
        retrieved1 = repo.get_conversation("1111111111.111111")
        retrieved2 = repo.get_conversation("2222222222.222222")
        
        assert retrieved1.repo == "org1/repo1"
        assert retrieved2.repo == "org2/repo2"


class TestJSONConversationRepository:
    """Tests for JSONConversationRepository."""

    def test_initialization(self, temp_state_file):
        """Test repository initialization with file."""
        repo = JSONConversationRepository(state_file=str(temp_state_file))
        assert repo is not None

    def test_save_conversation_to_file(self, temp_state_file):
        """Test that conversation is saved to file."""
        repo = JSONConversationRepository(state_file=str(temp_state_file))
        conv = Conversation(
            thread_ts="1234567890.123456",
            channel_id="C123456",
            repo="example-org/repo",
        )
        
        repo.save_conversation(conv)
        
        # Verify file was created
        assert temp_state_file.exists()

    def test_load_conversation_from_file(self, temp_state_file):
        """Test loading conversation from file."""
        repo = JSONConversationRepository(state_file=str(temp_state_file))
        conv = Conversation(
            thread_ts="1234567890.123456",
            channel_id="C123456",
            repo="example-org/repo",
        )
        conv.add_message("user", "Question")
        
        repo.save_conversation(conv)
        
        # Create new repository instance and load
        repo2 = JSONConversationRepository(state_file=str(temp_state_file))
        retrieved = repo2.get_conversation("1234567890.123456")
        
        assert retrieved is not None
        assert len(retrieved.messages) == 1

    def test_persistence_across_instances(self, temp_state_file):
        """Test that data persists across repository instances."""
        # First instance saves
        repo1 = JSONConversationRepository(state_file=str(temp_state_file))
        conv = Conversation(
            thread_ts="1234567890.123456",
            channel_id="C123456",
            repo="example-org/repo",
        )
        repo1.save_conversation(conv)
        
        # Second instance retrieves
        repo2 = JSONConversationRepository(state_file=str(temp_state_file))
        retrieved = repo2.get_conversation("1234567890.123456")
        
        assert retrieved is not None
        assert retrieved.thread_ts == "1234567890.123456"

    def test_empty_file_initialization(self, temp_state_file):
        """Test initializing with non-existent file."""
        repo = JSONConversationRepository(state_file=str(temp_state_file))
        conv = repo.get_conversation("nonexistent")
        assert conv is None
