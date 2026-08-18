"""Tests for RepoAgent.

Tests the core agent logic including command parsing and conversation handling.
"""

import json
import re
from pathlib import Path

import pytest

from benedict.agent import RepoAgent, REPO_PATTERN
from benedict.models import Conversation


class TestRepoPattern:
    """Tests for repository pattern matching."""

    def test_valid_repo_patterns(self):
        """Test that valid repository patterns are matched."""
        valid_repos = [
            "owner/repo",
            "my-org/my-repo",
            "org_name/repo_name",
            "org123/repo456",
            "a/b",
        ]
        
        for repo in valid_repos:
            match = REPO_PATTERN.search(repo)
            assert match is not None, f"Failed to match: {repo}"
            assert match.group(0) == repo

    def test_invalid_repo_patterns(self):
        """Test that invalid repository patterns are not matched."""
        invalid_repos = [
            "just-a-name",
            "owner/",
            "/repo",
            "owner//repo",
            "",
        ]
        
        for repo in invalid_repos:
            match = REPO_PATTERN.search(repo)
            if match:
                assert match.group(0) != repo, f"Should not fully match: {repo}"

    def test_repo_pattern_in_text(self):
        """Test extracting repository from text."""
        text = "Please onboard repo example-org/example-repo for this channel"
        match = REPO_PATTERN.search(text)
        
        assert match is not None
        assert match.group(0) == "example-org/example-repo"


class TestRepoAgent:
    """Tests for RepoAgent class."""

    def test_initialization_minimal(self, temp_state_file):
        """Test agent initialization with minimal dependencies."""
        agent = RepoAgent(state_file=str(temp_state_file))
        
        assert agent.state_file == temp_state_file
        assert agent.llm is None
        assert agent.repo_reader is None
        assert agent.semantic_indexer is None
        assert agent.conversation_manager is not None

    def test_initialization_with_dependencies(
        self,
        temp_state_file,
        mock_llm,
        mock_repo_reader,
        mock_semantic_indexer,
        mock_conversation_repository,
    ):
        """Test agent initialization with all dependencies."""
        agent = RepoAgent(
            state_file=str(temp_state_file),
            llm=mock_llm,
            repo_reader=mock_repo_reader,
            semantic_indexer=mock_semantic_indexer,
            conversation_repository=mock_conversation_repository,
        )
        
        assert agent.llm is mock_llm
        assert agent.repo_reader is mock_repo_reader
        assert agent.semantic_indexer is mock_semantic_indexer

    def test_load_empty_state(self, temp_state_file):
        """Test loading state from non-existent file."""
        agent = RepoAgent(state_file=str(temp_state_file))
        state = agent.load_state()
        
        assert state == {}

    def test_load_existing_state(self, temp_state_file, sample_state_data):
        """Test loading state from existing file."""
        # Write state file
        with open(temp_state_file, "w") as f:
            json.dump(sample_state_data, f)
        
        agent = RepoAgent(state_file=str(temp_state_file))
        state = agent.load_state()
        
        assert state == sample_state_data
        assert "channels" in state

    def test_save_state(self, temp_state_file):
        """Test saving state to file."""
        agent = RepoAgent(state_file=str(temp_state_file))
        
        state = {
            "channels": {
                "C123456": {
                    "repo": "example-org/repo",
                    "onboarded_at": "2026-08-01T10:00:00Z",
                }
            }
        }
        
        agent.save_state(state)
        
        # Verify file was written
        assert temp_state_file.exists()
        with open(temp_state_file, "r") as f:
            loaded = json.load(f)
        assert loaded == state

    def test_get_channel_repo_existing(self, temp_state_file, sample_state_data):
        """Test getting repository for a channel that exists."""
        with open(temp_state_file, "w") as f:
            json.dump(sample_state_data, f)
        
        agent = RepoAgent(state_file=str(temp_state_file))
        repo = agent.get_channel_repo("C123456")
        
        assert repo == "example-org/example-repo"

    def test_get_channel_repo_nonexistent(self, temp_state_file):
        """Test getting repository for a channel that doesn't exist."""
        agent = RepoAgent(state_file=str(temp_state_file))
        repo = agent.get_channel_repo("C999999")
        
        assert repo is None

    def test_set_channel_repo(self, temp_state_file):
        """Test setting repository for a channel."""
        agent = RepoAgent(state_file=str(temp_state_file))
        
        agent.set_channel_repo(
            channel_id="C123456",
            repo="example-org/repo",
            user_id="U123456",
        )
        
        # Verify it was saved
        repo = agent.get_channel_repo("C123456")
        assert repo == "example-org/repo"
        
        # Verify state file was updated
        with open(temp_state_file, "r") as f:
            state = json.load(f)
        assert state["channels"]["C123456"]["repo"] == "example-org/repo"

    def test_is_onboard_command(self, temp_state_file):
        """Test detecting onboard commands."""
        agent = RepoAgent(state_file=str(temp_state_file))
        
        valid_commands = [
            "onboard repo example-org/repo",
            "onboard example-org/repo",
            "  onboard  repo  example-org/repo  ",
            "ONBOARD REPO example-org/repo",
        ]
        
        for cmd in valid_commands:
            assert agent.is_onboard_command(cmd), f"Should detect: {cmd}"

    def test_is_not_onboard_command(self, temp_state_file):
        """Test that non-onboard commands are not detected."""
        agent = RepoAgent(state_file=str(temp_state_file))
        
        invalid_commands = [
            "status",
            "what is the architecture",
            "onboard",  # Missing repo
            "board repo example-org/repo",
        ]
        
        for cmd in invalid_commands:
            assert not agent.is_onboard_command(cmd), f"Should not detect: {cmd}"

    def test_is_status_command(self, temp_state_file):
        """Test detecting status commands."""
        agent = RepoAgent(state_file=str(temp_state_file))
        
        valid_commands = [
            "status",
            "  status  ",
            "STATUS",
            "Status",
        ]
        
        for cmd in valid_commands:
            assert agent.is_status_command(cmd), f"Should detect: {cmd}"

    def test_extract_repo_name(self, temp_state_file):
        """Test extracting repository name from command."""
        agent = RepoAgent(state_file=str(temp_state_file))
        
        test_cases = [
            ("onboard repo example-org/repo", "example-org/repo"),
            ("onboard example-org/repo", "example-org/repo"),
            ("  onboard  repo  my-org/my-repo  ", "my-org/my-repo"),
            ("ONBOARD REPO Example-Org/Example-Repo", "Example-Org/Example-Repo"),
        ]
        
        for text, expected_repo in test_cases:
            repo = agent.extract_repo_name(text)
            assert repo == expected_repo, f"Failed for: {text}"

    def test_extract_repo_name_invalid(self, temp_state_file):
        """Test extracting repo name from invalid command."""
        agent = RepoAgent(state_file=str(temp_state_file))
        
        invalid_commands = [
            "onboard repo",  # No repo name
            "status",
            "what is the architecture",
        ]
        
        for cmd in invalid_commands:
            repo = agent.extract_repo_name(cmd)
            assert repo is None, f"Should return None for: {cmd}"


class TestRepoAgentConversations:
    """Tests for conversation handling in RepoAgent."""

    def test_create_conversation(
        self,
        temp_state_file,
        mock_conversation_repository,
    ):
        """Test creating a conversation through the agent."""
        agent = RepoAgent(
            state_file=str(temp_state_file),
            conversation_repository=mock_conversation_repository,
        )
        
        # Set up channel
        agent.set_channel_repo("C123456", "example-org/repo", "U123456")
        
        # Create conversation
        conv = agent.conversation_manager.create_conversation(
            thread_ts="1234567890.123456",
            channel_id="C123456",
            repo="example-org/repo",
        )
        
        assert conv is not None
        assert conv.repo == "example-org/repo"

    def test_get_conversation(
        self,
        temp_state_file,
        mock_conversation_repository,
    ):
        """Test retrieving a conversation."""
        agent = RepoAgent(
            state_file=str(temp_state_file),
            conversation_repository=mock_conversation_repository,
        )
        
        # Create conversation
        agent.conversation_manager.create_conversation(
            thread_ts="1234567890.123456",
            channel_id="C123456",
            repo="example-org/repo",
        )
        
        # Retrieve it
        conv = agent.conversation_manager.get_conversation("1234567890.123456")
        assert conv is not None


class TestRepoAgentStateManagement:
    """Tests for state management in RepoAgent."""

    def test_state_persistence_across_instances(self, temp_state_file):
        """Test that state persists across agent instances."""
        # First agent sets up channel
        agent1 = RepoAgent(state_file=str(temp_state_file))
        agent1.set_channel_repo("C123456", "example-org/repo", "U123456")
        
        # Second agent should see the channel
        agent2 = RepoAgent(state_file=str(temp_state_file))
        repo = agent2.get_channel_repo("C123456")
        
        assert repo == "example-org/repo"

    def test_multiple_channels(self, temp_state_file):
        """Test managing multiple channels."""
        agent = RepoAgent(state_file=str(temp_state_file))
        
        agent.set_channel_repo("C111111", "org1/repo1", "U123456")
        agent.set_channel_repo("C222222", "org2/repo2", "U123456")
        
        assert agent.get_channel_repo("C111111") == "org1/repo1"
        assert agent.get_channel_repo("C222222") == "org2/repo2"

    def test_update_channel_repo(self, temp_state_file):
        """Test updating repository for existing channel."""
        agent = RepoAgent(state_file=str(temp_state_file))
        
        # Initial onboard
        agent.set_channel_repo("C123456", "org1/repo1", "U123456")
        assert agent.get_channel_repo("C123456") == "org1/repo1"
        
        # Update to different repo
        agent.set_channel_repo("C123456", "org2/repo2", "U123456")
        assert agent.get_channel_repo("C123456") == "org2/repo2"
