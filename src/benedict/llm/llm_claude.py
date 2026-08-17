"""Claude LLM Implementation

Anthropic Claude 3.5 Sonnet implementation of LLM protocol.
"""

import os
import logging
from typing import Optional, List, Dict, Any, Union
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class ClaudeLLM:
    """Claude LLM implementation."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize Claude client.

        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
            model: Model name. If None, reads from ANTHROPIC_MODEL env var or uses default.
        """
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        # Default to claude-3-5-sonnet-20241022 (latest stable as of 2025)
        # Can be overridden via ANTHROPIC_MODEL environment variable
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

        self.client = Anthropic(api_key=api_key)
        logger.info(f"Initialized Claude LLM with model {self.model}")

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
                     Must include at least one "user" message.
                     Tool responses should have role "tool" with "tool_call_id" and "content".
            system: System message/instructions
            max_tokens: Maximum tokens in response
            tools: Optional list of tool definitions for function calling

        Returns:
            If LLM requests tool use:
                Dict with "tool_calls" key containing list of {"id": str, "name": str, "input": dict}
            Otherwise:
                Generated text response string

        Raises:
            Exception: If API call fails
        """
        try:
            if not messages:
                raise ValueError("messages list cannot be empty")

            # Ensure at least one user message
            if not any(msg.get("role") == "user" for msg in messages):
                raise ValueError("messages must include at least one user message")

            # Convert messages to Anthropic format
            anthropic_messages = []
            for msg in messages:
                role = msg.get("role")
                content = msg.get("content", "")

                if role == "tool":
                    # Tool responses need special handling
                    tool_call_id = msg.get("tool_call_id")
                    if not tool_call_id:
                        logger.warning("Tool message missing tool_call_id, skipping")
                        continue
                    anthropic_messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_call_id,
                                    "content": (
                                        str(content)
                                        if not isinstance(content, (list, dict))
                                        else content
                                    ),
                                }
                            ],
                        }
                    )
                elif role == "assistant" and isinstance(content, list):
                    # Assistant message with tool_use blocks (from tool call loop)
                    anthropic_messages.append({"role": role, "content": content})
                else:
                    # Regular text message
                    anthropic_messages.append({"role": role, "content": content})

            # Prepare API call
            api_kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": anthropic_messages,
            }

            if system:
                api_kwargs["system"] = system

            if tools:
                api_kwargs["tools"] = tools

            response = self.client.messages.create(**api_kwargs)

            # Check if response contains tool use (may follow a text block)
            if response.content and len(response.content) > 0:
                tool_calls = []
                assistant_content = []
                for content_item in response.content:
                    item_type = getattr(content_item, "type", None)
                    if item_type == "tool_use":
                        tool_call = {
                            "id": content_item.id,
                            "name": content_item.name,
                            "input": content_item.input,
                        }
                        tool_calls.append(tool_call)
                        assistant_content.append(
                            {
                                "type": "tool_use",
                                "id": content_item.id,
                                "name": content_item.name,
                                "input": content_item.input,
                            }
                        )
                    elif item_type == "text":
                        assistant_content.append({"type": "text", "text": content_item.text})

                if tool_calls:
                    return {
                        "tool_calls": tool_calls,
                        "assistant_content": assistant_content,
                    }

                first_content = response.content[0]
                return first_content.text if hasattr(first_content, "text") else str(first_content)
            else:
                return ""

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise
