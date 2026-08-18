"""Tests for LLM implementations.

Tests the LLM protocol and mock implementation.
"""

import pytest

from benedict.llm import MockLLM


class TestMockLLM:
    """Tests for MockLLM implementation."""

    def test_initialization(self):
        """Test mock LLM initialization."""
        llm = MockLLM()
        assert llm is not None

    def test_generate_default_response(self):
        """Test generating a default response."""
        llm = MockLLM()
        response = llm.generate(
            system_prompt="You are a helpful assistant.",
            user_message="What is the architecture?",
        )
        
        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0

    def test_generate_with_history(self):
        """Test generating response with conversation history."""
        llm = MockLLM()
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        
        response = llm.generate(
            system_prompt="You are a helpful assistant.",
            user_message="How are you?",
            conversation_history=history,
        )
        
        assert response is not None
        assert isinstance(response, str)

    def test_generate_with_context(self):
        """Test generating response with additional context."""
        llm = MockLLM()
        context = "Repository: example-org/repo\nLanguage: Python"
        
        response = llm.generate(
            system_prompt="You are a helpful assistant.",
            user_message="What language is used?",
            context=context,
        )
        
        assert response is not None

    def test_set_response(self):
        """Test setting a custom response."""
        llm = MockLLM()
        custom_response = "This is a custom response"
        llm.set_response(custom_response)
        
        response = llm.generate(
            system_prompt="System",
            user_message="Message",
        )
        
        assert response == custom_response

    def test_multiple_generations(self):
        """Test generating multiple responses."""
        llm = MockLLM()
        
        response1 = llm.generate(
            system_prompt="System",
            user_message="Message 1",
        )
        response2 = llm.generate(
            system_prompt="System",
            user_message="Message 2",
        )
        
        assert response1 is not None
        assert response2 is not None

    def test_max_tokens_parameter(self):
        """Test that max_tokens parameter is accepted."""
        llm = MockLLM()
        
        response = llm.generate(
            system_prompt="System",
            user_message="Message",
            max_tokens=100,
        )
        
        assert response is not None
