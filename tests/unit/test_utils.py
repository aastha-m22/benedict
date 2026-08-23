"""Tests for utility functions.

Tests context building and other utility functions.
"""

import pytest

from benedict.utils.context import truncate_to_tokens


class TestContextUtilities:
    """Tests for context utility functions."""

    def test_truncate_to_tokens_short_text(self):
        """Test truncating text that's already under limit."""
        text = "This is a short text."
        result = truncate_to_tokens(text, max_tokens=1000)
        
        assert result == text

    def test_truncate_to_tokens_long_text(self):
        """Test truncating text that exceeds limit."""
        # Create text that's definitely over 100 tokens (400 chars)
        text = "word " * 100  # 500 chars
        result = truncate_to_tokens(text, max_tokens=100)
        
        # Result should be shorter than original
        assert len(result) < len(text)
        # Should contain truncation notice
        assert "truncated" in result.lower()

    def test_truncate_to_tokens_exact_limit(self):
        """Test truncating text at exact limit."""
        # 400 chars = approximately 100 tokens
        text = "x" * 400
        result = truncate_to_tokens(text, max_tokens=100)
        
        # Should be at or under limit
        assert len(result) <= 400 + 100  # Allow some margin for truncation message

    def test_truncate_to_tokens_empty_text(self):
        """Test truncating empty text."""
        result = truncate_to_tokens("", max_tokens=100)
        assert result == ""

    def test_truncate_to_tokens_preserves_start(self):
        """Test that truncation preserves the beginning of text."""
        text = "IMPORTANT: " + ("x" * 1000)
        result = truncate_to_tokens(text, max_tokens=50)
        
        # Should preserve the important prefix
        assert result.startswith("IMPORTANT:")


class TestSlackFormatter:
    """Tests for Slack message formatting utilities."""

    def test_format_basic_text(self):
        """Test formatting basic text for Slack."""
        # This would test slack_formatter if it has public functions
        # Placeholder for now
        pass

    def test_format_code_block(self):
        """Test formatting code blocks for Slack."""
        # Placeholder
        pass

    def test_escape_special_characters(self):
        """Test escaping Slack special characters."""
        # Placeholder
        pass
