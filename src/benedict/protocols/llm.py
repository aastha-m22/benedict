"""LLM Protocol Definition

Defines the interface for Large Language Model providers.
"""

from typing import Protocol, Optional, List, Dict, Any, Union


class LLM(Protocol):
    """Protocol for LLM providers."""

    def generate(
        self,
        messages: List[Dict[str, Any]],
        system: str = "",
        max_tokens: int = 2000,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Union[str, Dict[str, Any]]:
        """Generate response from conversation messages.

        Args:
            messages: Conversation history as list of {"role": "user|assistant|tool", "content": "..."}
                     Must include at least one "user" message. Last message should be the current user question.
                     Tool responses should have role "tool" with "tool_call_id" and "content".
            system: System message/instructions
            max_tokens: Maximum tokens in response
            tools: Optional list of tool definitions for function calling

        Returns:
            If tools are provided and LLM requests tool use:
                Dict with "tool_calls" key containing list of tool call requests
            Otherwise:
                Generated text response string
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
