"""Pytest configuration and shared fixtures for Benedict tests.

This module provides reusable fixtures for testing all components.
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import Mock, MagicMock

import pytest

from benedict.models import Message, Conversation, ConversationManager
from benedict.protocols import (
    LLM,
    RepoReader,
    SemanticIndexer,
    ConversationRepository,
    RepoChangeDetector,
)
from benedict.llm import MockLLM
from benedict.repo_reader import MockRepoReader
from benedict.semantic_indexer import MockSemanticIndexer
from benedict.conversation_repository import MockConversationRepository
from benedict.workspace import WorkspaceManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_state_file(temp_dir):
    """Create a temporary state file path."""
    return temp_dir / "state.json"


@pytest.fixture
def sample_state_data() -> Dict[str, Any]:
    """Sample state data for testing."""
    return {
        "channels": {
            "C123456": {
                "repo": "example-org/example-repo",
                "onboarded_at": "2026-08-01T10:00:00Z",
                "onboarded_by": "U123456",
            }
        }
    }


@pytest.fixture
def mock_llm() -> LLM:
    """Create a mock LLM for testing."""
    return MockLLM()


@pytest.fixture
def mock_repo_reader() -> RepoReader:
    """Create a mock repository reader for testing."""
    reader = MockRepoReader()
    # Add some sample files
    reader.add_file("README.md", "# Example Repository\n\nThis is a test repository.")
    reader.add_file(
        "src/main.py",
        "def main():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    main()",
    )
    reader.add_file("src/utils.py", "def helper():\n    return True")
    return reader


@pytest.fixture
def mock_semantic_indexer() -> SemanticIndexer:
    """Create a mock semantic indexer for testing."""
    indexer = MockSemanticIndexer()
    # Pre-populate with some relevant files
    indexer.add_relevant_file("README.md", 0.9)
    indexer.add_relevant_file("src/main.py", 0.8)
    return indexer


@pytest.fixture
def mock_conversation_repository() -> ConversationRepository:
    """Create a mock conversation repository for testing."""
    return MockConversationRepository()


@pytest.fixture
def mock_workspace_manager(temp_dir) -> WorkspaceManager:
    """Create a mock workspace manager for testing."""
    return WorkspaceManager(base_dir=str(temp_dir))


@pytest.fixture
def sample_message() -> Message:
    """Create a sample message for testing."""
    return Message(role="user", content="What is the architecture?")


@pytest.fixture
def sample_conversation() -> Conversation:
    """Create a sample conversation for testing."""
    conv = Conversation(
        thread_ts="1234567890.123456",
        channel_id="C123456",
        repo="example-org/example-repo",
    )
    conv.add_message("user", "What is the architecture?")
    conv.add_message("assistant", "The architecture consists of...")
    return conv


@pytest.fixture
def conversation_manager(mock_conversation_repository) -> ConversationManager:
    """Create a conversation manager for testing."""
    return ConversationManager(mock_conversation_repository)


@pytest.fixture
def mock_slack_client():
    """Create a mock Slack client for testing."""
    client = MagicMock()
    client.chat_postMessage = Mock(
        return_value={
            "ok": True,
            "channel": "C123456",
            "ts": "1234567890.123456",
            "message": {"text": "Response", "user": "U987654"},
        }
    )
    return client


@pytest.fixture
def mock_slack_event():
    """Create a sample Slack event for testing."""
    return {
        "type": "app_mention",
        "user": "U123456",
        "text": "<@U987654> what is the architecture?",
        "ts": "1234567890.123456",
        "channel": "C123456",
        "event_ts": "1234567890.123456",
        "thread_ts": "1234567890.123456",
    }


@pytest.fixture
def sample_repo_files() -> Dict[str, str]:
    """Sample repository file contents for testing."""
    return {
        "README.md": """# Example Project

## Overview
This is an example project for testing.

## Architecture
The project uses a modular architecture with clear separation of concerns.
""",
        "src/main.py": """\"\"\"Main entry point.\"\"\"

def main():
    print('Hello, World!')

if __name__ == '__main__':
    main()
""",
        "src/utils.py": """\"\"\"Utility functions.\"\"\"

def helper():
    return True

def process_data(data):
    return data.upper()
""",
        "tests/test_main.py": """\"\"\"Tests for main module.\"\"\"

def test_main():
    assert True
""",
    }


@pytest.fixture
def populated_mock_repo_reader(sample_repo_files) -> RepoReader:
    """Create a populated mock repository reader."""
    reader = MockRepoReader()
    for path, content in sample_repo_files.items():
        reader.add_file(path, content)
    return reader


# Helper functions for tests


def create_mock_llm_with_response(response: str) -> LLM:
    """Create a mock LLM that returns a specific response.
    
    Args:
        response: The response to return
        
    Returns:
        Mock LLM instance
    """
    llm = MockLLM()
    llm.set_response(response)
    return llm


def create_test_state_file(path: Path, data: Dict[str, Any]) -> None:
    """Create a test state file with given data.
    
    Args:
        path: Path to state file
        data: Data to write
    """
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def assert_valid_conversation(conversation: Conversation) -> None:
    """Assert that a conversation object is valid.
    
    Args:
        conversation: Conversation to validate
    """
    assert conversation.thread_ts
    assert conversation.channel_id
    assert conversation.repo
    assert isinstance(conversation.messages, list)
    assert conversation.created_at
    assert conversation.updated_at


def assert_valid_message(message: Message) -> None:
    """Assert that a message object is valid.
    
    Args:
        message: Message to validate
    """
    assert message.role in ["user", "assistant"]
    assert message.content
    assert message.timestamp
