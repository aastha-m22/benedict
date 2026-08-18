"""Integration tests for RepoAgent.

Tests the agent with multiple components working together.
"""

import pytest

from benedict.agent import RepoAgent
from benedict.models import Conversation


class TestRepoAgentIntegration:
    """Integration tests for RepoAgent with dependencies."""

    def test_agent_with_llm_and_repo_reader(
        self,
        temp_state_file,
        mock_llm,
        populated_mock_repo_reader,
        mock_conversation_repository,
    ):
        """Test agent with LLM and repository reader."""
        agent = RepoAgent(
            state_file=str(temp_state_file),
            llm=mock_llm,
            repo_reader=populated_mock_repo_reader,
            conversation_repository=mock_conversation_repository,
        )
        
        assert agent.llm is not None
        assert agent.repo_reader is not None

    def test_full_conversation_flow(
        self,
        temp_state_file,
        mock_llm,
        populated_mock_repo_reader,
        mock_conversation_repository,
    ):
        """Test complete conversation flow from onboarding to question."""
        agent = RepoAgent(
            state_file=str(temp_state_file),
            llm=mock_llm,
            repo_reader=populated_mock_repo_reader,
            conversation_repository=mock_conversation_repository,
        )
        
        # 1. Onboard channel
        agent.set_channel_repo("C123456", "example-org/repo", "U123456")
        
        # 2. Verify channel is onboarded
        repo = agent.get_channel_repo("C123456")
        assert repo == "example-org/repo"
        
        # 3. Create conversation
        conv = agent.conversation_manager.create_conversation(
            thread_ts="1234567890.123456",
            channel_id="C123456",
            repo="example-org/repo",
        )
        
        # 4. Add user message
        agent.conversation_manager.add_message(
            "1234567890.123456",
            "user",
            "What is the architecture?",
        )
        
        # 5. Verify conversation state
        retrieved = agent.conversation_manager.get_conversation("1234567890.123456")
        assert retrieved is not None
        assert len(retrieved.messages) == 1

    def test_multiple_conversations_same_channel(
        self,
        temp_state_file,
        mock_llm,
        populated_mock_repo_reader,
        mock_conversation_repository,
    ):
        """Test multiple conversations in the same channel."""
        agent = RepoAgent(
            state_file=str(temp_state_file),
            llm=mock_llm,
            repo_reader=populated_mock_repo_reader,
            conversation_repository=mock_conversation_repository,
        )
        
        # Onboard channel
        agent.set_channel_repo("C123456", "example-org/repo", "U123456")
        
        # Create two conversations
        conv1 = agent.conversation_manager.create_conversation(
            thread_ts="1111111111.111111",
            channel_id="C123456",
            repo="example-org/repo",
        )
        conv2 = agent.conversation_manager.create_conversation(
            thread_ts="2222222222.222222",
            channel_id="C123456",
            repo="example-org/repo",
        )
        
        # Add different messages to each
        agent.conversation_manager.add_message("1111111111.111111", "user", "Question 1")
        agent.conversation_manager.add_message("2222222222.222222", "user", "Question 2")
        
        # Verify they're separate
        retrieved1 = agent.conversation_manager.get_conversation("1111111111.111111")
        retrieved2 = agent.conversation_manager.get_conversation("2222222222.222222")
        
        assert retrieved1.messages[0].content == "Question 1"
        assert retrieved2.messages[0].content == "Question 2"

    def test_agent_with_semantic_indexer(
        self,
        temp_state_file,
        mock_llm,
        populated_mock_repo_reader,
        mock_semantic_indexer,
        mock_conversation_repository,
    ):
        """Test agent with semantic indexer for intelligent file selection."""
        agent = RepoAgent(
            state_file=str(temp_state_file),
            llm=mock_llm,
            repo_reader=populated_mock_repo_reader,
            semantic_indexer=mock_semantic_indexer,
            conversation_repository=mock_conversation_repository,
        )
        
        assert agent.semantic_indexer is not None
        
        # Semantic indexer should be able to find relevant files
        relevant_files = mock_semantic_indexer.search("architecture", top_k=5)
        assert len(relevant_files) > 0

    def test_conversation_persistence(
        self,
        temp_state_file,
        mock_llm,
        populated_mock_repo_reader,
        mock_conversation_repository,
    ):
        """Test that conversations persist across agent restarts."""
        # First agent creates conversation
        agent1 = RepoAgent(
            state_file=str(temp_state_file),
            llm=mock_llm,
            repo_reader=populated_mock_repo_reader,
            conversation_repository=mock_conversation_repository,
        )
        
        agent1.set_channel_repo("C123456", "example-org/repo", "U123456")
        agent1.conversation_manager.create_conversation(
            thread_ts="1234567890.123456",
            channel_id="C123456",
            repo="example-org/repo",
        )
        agent1.conversation_manager.add_message(
            "1234567890.123456",
            "user",
            "Question",
        )
        
        # Second agent retrieves conversation
        agent2 = RepoAgent(
            state_file=str(temp_state_file),
            llm=mock_llm,
            repo_reader=populated_mock_repo_reader,
            conversation_repository=mock_conversation_repository,
        )
        
        conv = agent2.conversation_manager.get_conversation("1234567890.123456")
        assert conv is not None
        assert len(conv.messages) == 1
        assert conv.messages[0].content == "Question"
