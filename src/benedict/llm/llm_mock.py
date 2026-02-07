"""Mock LLM Implementation

Mock LLM for testing purposes.
"""
import logging
from typing import Optional, List, Dict
from benedict.protocols.llm import LLM

logger = logging.getLogger(__name__)


class MockLLM:
    """Mock LLM that returns predefined responses."""
    
    def __init__(self, responses: dict = None):
        """Initialize mock LLM.
        
        Args:
            responses: Optional dict mapping prompts to responses.
                      If None, returns generic mock response.
        """
        self.responses = responses or {}
        logger.info("Initialized MockLLM")
    
    def generate(
        self, 
        messages: List[Dict[str, str]],
        system: str = "",
        max_tokens: int = 2000
    ) -> str:
        """Generate mock response.
        
        Args:
            messages: Conversation history as list of {"role": "user|assistant", "content": "..."}
            system: System message/instructions (ignored)
            max_tokens: Maximum tokens (ignored)
            
        Returns:
            Mock response text
        """
        if not messages:
            return "[Mock LLM Response] No messages provided"
        
        # Get the last user message
        last_user_msg = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break
        
        if not last_user_msg:
            return "[Mock LLM Response] No user message found"
        
        # Check if we have a predefined response
        if last_user_msg in self.responses:
            return self.responses[last_user_msg]
        
        # Include conversation context in mock response
        context_note = f" (with {len(messages)} messages in conversation)"
        
        # Default mock response
        return f"[Mock LLM Response{context_note}] You asked: {last_user_msg[:100]}"
