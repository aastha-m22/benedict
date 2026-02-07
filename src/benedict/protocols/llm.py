"""LLM Protocol Definition

Defines the interface for Large Language Model providers.
"""
from typing import Protocol, Optional, List, Dict


class LLM(Protocol):
    """Protocol for LLM providers."""
    
    def generate(
        self, 
        messages: List[Dict[str, str]],
        system: str = "",
        max_tokens: int = 2000
    ) -> str:
        """Generate response from conversation messages.
        
        Args:
            messages: Conversation history as list of {"role": "user|assistant", "content": "..."}
                     Must include at least one "user" message. Last message should be the current user question.
            system: System message/instructions
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated text response
        """
        ...


def create_llm(provider: str = "claude", model: Optional[str] = None) -> LLM:
    """Factory function to create LLM instance.
    
    Args:
        provider: Provider name ("claude" or "mock")
        model: Optional model name (for Claude, defaults to ANTHROPIC_MODEL env var or claude-3-5-sonnet-20241022)
        
    Returns:
        LLM instance
        
    Raises:
        ValueError: If provider is unknown
    """
    if provider == "claude":
        from benedict.llm.llm_claude import ClaudeLLM
        return ClaudeLLM(model=model)
    elif provider == "mock":
        from benedict.llm.llm_mock import MockLLM
        return MockLLM()
    else:
        raise ValueError(f"Unknown provider: {provider}")