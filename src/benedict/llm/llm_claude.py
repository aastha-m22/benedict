"""Claude LLM Implementation

Anthropic Claude 3.5 Sonnet implementation of LLM protocol.
"""
import os
import logging
from typing import Optional, List, Dict
from anthropic import Anthropic
from benedict.protocols.llm import LLM

logger = logging.getLogger(__name__)


class ClaudeLLM:
    """Claude 4.5 Sonnet LLM implementation."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Claude client.
        
        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
        """
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-4-5-sonnet-20260207"
        logger.info(f"Initialized Claude LLM with model {self.model}")
    
    def generate(
        self, 
        messages: List[Dict[str, str]],
        system: str = "",
        max_tokens: int = 2000
    ) -> str:
        """Generate response from conversation messages.
        
        Args:
            messages: Conversation history as list of {"role": "user|assistant", "content": "..."}
                     Must include at least one "user" message.
            system: System message/instructions
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated text response
            
        Raises:
            Exception: If API call fails
        """
        try:
            if not messages:
                raise ValueError("messages list cannot be empty")
            
            # Ensure at least one user message
            if not any(msg.get("role") == "user" for msg in messages):
                raise ValueError("messages must include at least one user message")
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system if system else None,
                messages=messages
            )
            
            # Extract text from response
            if response.content and len(response.content) > 0:
                return response.content[0].text
            else:
                return ""
                
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise
