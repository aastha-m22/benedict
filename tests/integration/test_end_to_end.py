"""End-to-end integration tests.

Tests complete workflows from user interaction to response.
"""

import pytest

from benedict.agent import RepoAgent


class TestEndToEnd:
    """End-to-end workflow tests."""

    def test_onboard_and_status_workflow(
        self,
        temp_state_file,
        mock_conversation_repository,
    ):
        """Test complete onboard and status check workflow."""
        agent = RepoAgent(
            state_file=str(temp_state_file),
            conversation_repository=mock_conversation_repository,
        )
        
        # Step 1: User onboards channel
        text = "onboard repo example-org/example-repo"
        
        # Agent detects onboard command
        assert agent.is_onboard_command(text)
        
        # Extract repository name
        repo = agent.extract_repo_name(text)
        assert repo == "example-org/example-repo"
        
        # Set channel repository
        agent.set_channel_repo(
            channel_id="C123456",
            repo=repo,
            user_id="U123456",
        )
        
        # Step 2: User checks status
        status_text = "status"
        assert agent.is_status_command(status_text)
        
        # Agent retrieves channel info
        channel_repo = agent.get_channel_repo("C123456")
        assert channel_repo == "example-org/example-repo"

    def test_complete_conversation_workflow(
        self,
        temp_state_file,
        mock_llm,
        populated_mock_repo_reader,
        mock_conversation_repository,
    ):
        """Test complete conversation workflow."""
        agent = RepoAgent(
            state_file=str(temp_state_file),
            llm=mock_llm,
            repo_reader=populated_mock_repo_reader,
            conversation_repository=mock_conversation_repository,
        )
        
        # Step 1: Onboard channel
        agent.set_channel_repo("C123456", "example-org/repo", "U123456")
        
        # Step 2: User asks question
        thread_ts = "1234567890.123456"
        channel_id = "C123456"
        user_message = "What files are in the repository?"
        
        # Step 3: Get or create conversation
        conv = agent.conversation_manager.get_or_create_conversation(
            thread_ts=thread_ts,
            channel_id=channel_id,
            repo="example-org/repo",
        )
        
        # Step 4: Add user message
        agent.conversation_manager.add_message(thread_ts, "user", user_message)
        
        # Step 5: Get repository files (for context)
        if agent.repo_reader:
            files = agent.repo_reader.list_files()
            assert len(files) > 0
        
        # Step 6: Generate response (LLM would be called here)
        # In real flow, this would involve context building and LLM generation
        
        # Step 7: Add assistant response
        agent.conversation_manager.add_message(
            thread_ts,
            "assistant",
            "The repository contains several files including README.md and source files.",
        )
        
        # Verify final state
        final_conv = agent.conversation_manager.get_conversation(thread_ts)
        assert len(final_conv.messages) == 2
        assert final_conv.messages[0].role == "user"
        assert final_conv.messages[1].role == "assistant"

    def test_multi_turn_conversation(
        self,
        temp_state_file,
        mock_llm,
        populated_mock_repo_reader,
        mock_conversation_repository,
    ):
        """Test multi-turn conversation with context."""
        agent = RepoAgent(
            state_file=str(temp_state_file),
            llm=mock_llm,
            repo_reader=populated_mock_repo_reader,
            conversation_repository=mock_conversation_repository,
        )
        
        # Setup
        thread_ts = "1234567890.123456"
        agent.set_channel_repo("C123456", "example-org/repo", "U123456")
        
        conv = agent.conversation_manager.get_or_create_conversation(
            thread_ts=thread_ts,
            channel_id="C123456",
            repo="example-org/repo",
        )
        
        # Turn 1
        agent.conversation_manager.add_message(thread_ts, "user", "What is in README?")
        agent.conversation_manager.add_message(
            thread_ts,
            "assistant",
            "The README describes an example project.",
        )
        
        # Turn 2
        agent.conversation_manager.add_message(thread_ts, "user", "What about src/main.py?")
        agent.conversation_manager.add_message(
            thread_ts,
            "assistant",
            "The main.py file contains the entry point.",
        )
        
        # Turn 3 - Follow-up question
        agent.conversation_manager.add_message(thread_ts, "user", "Can you explain more?")
        
        # Get conversation history for context
        history = conv.get_message_history()
        assert len(history) == 5  # 3 user + 2 assistant messages
        
        # Assistant would use history to understand "more" refers to main.py
        agent.conversation_manager.add_message(
            thread_ts,
            "assistant",
            "Sure, main.py is the entry point that prints 'Hello, World!'",
        )
        
        # Verify complete conversation
        final_conv = agent.conversation_manager.get_conversation(thread_ts)
        assert len(final_conv.messages) == 6

    def test_multiple_channels_workflow(
        self,
        temp_state_file,
        mock_llm,
        populated_mock_repo_reader,
        mock_conversation_repository,
    ):
        """Test managing multiple channels simultaneously."""
        agent = RepoAgent(
            state_file=str(temp_state_file),
            llm=mock_llm,
            repo_reader=populated_mock_repo_reader,
            conversation_repository=mock_conversation_repository,
        )
        
        # Onboard two different channels to different repos
        agent.set_channel_repo("C111111", "org1/repo1", "U123456")
        agent.set_channel_repo("C222222", "org2/repo2", "U123456")
        
        # Create conversations in each channel
        conv1 = agent.conversation_manager.create_conversation(
            thread_ts="1111111111.111111",
            channel_id="C111111",
            repo="org1/repo1",
        )
        conv2 = agent.conversation_manager.create_conversation(
            thread_ts="2222222222.222222",
            channel_id="C222222",
            repo="org2/repo2",
        )
        
        # Add messages to each
        agent.conversation_manager.add_message(
            "1111111111.111111",
            "user",
            "Question about repo1",
        )
        agent.conversation_manager.add_message(
            "2222222222.222222",
            "user",
            "Question about repo2",
        )
        
        # Verify channels are independent
        repo1 = agent.get_channel_repo("C111111")
        repo2 = agent.get_channel_repo("C222222")
        
        assert repo1 == "org1/repo1"
        assert repo2 == "org2/repo2"
        
        # Verify conversations are separate
        retrieved1 = agent.conversation_manager.get_conversation("1111111111.111111")
        retrieved2 = agent.conversation_manager.get_conversation("2222222222.222222")
        
        assert retrieved1.repo == "org1/repo1"
        assert retrieved2.repo == "org2/repo2"
        assert retrieved1.messages[0].content == "Question about repo1"
        assert retrieved2.messages[0].content == "Question about repo2"
