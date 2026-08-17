"""LLM-Based Command Classifier

Uses LLM with tool calling to classify user input into command intents.
"""

import logging
from typing import Optional, List, Dict, Any
from .tool_framework import ToolRegistry

logger = logging.getLogger(__name__)


class LLMCommandClassifier:
    """LLM-based command classifier using tool calling."""
    
    def __init__(self, llm, tool_registry: ToolRegistry, fallback_to_query: bool = True):
        """Initialize LLM command classifier.
        
        Args:
            llm: LLM instance (must support tool calling)
            tool_registry: ToolRegistry instance with available tools
            fallback_to_query: If True, returns None when no command matches (treat as query)
        """
        self.llm = llm
        self.tool_registry = tool_registry
        self.fallback_to_query = fallback_to_query
    
    def classify(self, text: str, conversation_history: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """Classify user input using LLM with tools.
        
        Args:
            text: User input text
            conversation_history: Optional conversation history for context
            
        Returns:
            Dictionary with tool calls if command detected, None if query
        """
        available_tools = self.tool_registry.list_tools()
        if not available_tools:
            # No tools available, treat as query
            if self.fallback_to_query:
                return None
            return {"tool_calls": []}
        
        try:
            # Build prompt with explicit tool descriptions
            prompt = self._build_prompt(text, conversation_history, available_tools)
            
            # Get tool schema (use Anthropic format)
            tools = self.tool_registry.to_anthropic_tools()
            
            logger.debug(f"Classifying '{text}' with {len(tools)} tools available")
            
            # Call LLM with tools
            response = self._call_llm_with_tools(prompt, tools, text)
            
            # Parse response
            tool_calls = self._parse_response(response)
            
            if tool_calls:
                logger.info(f"LLM returned {len(tool_calls)} tool calls: {[tc.get('name') for tc in tool_calls]}")
                return {"tool_calls": tool_calls}
            
            # No tool calls - treat as query if fallback enabled
            logger.info(f"No tool calls detected for '{text}', treating as query. Response was: {str(response)[:200]}")
            if self.fallback_to_query:
                return None
            
            return {"tool_calls": []}
            
        except Exception as e:
            logger.error(f"Error in LLM classification: {e}", exc_info=True)
            # On error, fallback to query
            if self.fallback_to_query:
                return None
            return {"tool_calls": []}
    
    def _build_prompt(self, text: str, conversation_history: Optional[List[Dict[str, Any]]] = None, available_tools: Optional[List] = None) -> str:
        """Build prompt for LLM.
        
        Args:
            text: User input
            conversation_history: Optional conversation history
            available_tools: Optional list of available tools for context
            
        Returns:
            Prompt string
        """
        prompt_parts = []
        
        # Add context if available
        if conversation_history:
            prompt_parts.append("Previous conversation context:")
            for msg in conversation_history[-3:]:  # Last 3 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_parts.append(f"{role}: {content}")
            prompt_parts.append("")
        
        # List available tools
        if available_tools:
            tool_names = [tool.name for tool in available_tools]
            prompt_parts.append(f"Available tools: {', '.join(tool_names)}")
            prompt_parts.append("")
        
        # Add instruction with explicit examples - be very direct
        prompt_parts.append(
            "You MUST call tools when the user requests specific operations. Do NOT try to answer from context.\n\n"
            "MANDATORY tool calls:\n"
            "- User says 'get file metadata' or 'show metadata for file' → CALL get_file_metadata tool\n"
            "- User says 'list files' → CALL list_key_files tool\n"
            "- User says 'get repository summary' → CALL get_repository_summary tool\n\n"
            "Only skip tool calls if the input is a general question that doesn't request a specific operation."
        )
        
        prompt_parts.append("")
        prompt_parts.append(f"User input: {text}")
        
        return "\n".join(prompt_parts)
    
    def _call_llm_with_tools(self, prompt: str, functions: List[Dict], user_text: str) -> Dict[str, Any]:
        """Call LLM with tool calling.
        
        Args:
            prompt: System prompt
            functions: Function definitions
            user_text: User input text
            
        Returns:
            LLM response
        """
        # Use LLM.generate with tools parameter
        messages = [{"role": "user", "content": user_text}]
        
        try:
            response = self.llm.generate(
                messages=messages,
                system=prompt,
                tools=functions,
                max_tokens=2000
            )
            
            # Handle different response formats
            if isinstance(response, dict):
                return response
            elif isinstance(response, str):
                # LLM returned text, try to parse as JSON
                import json
                try:
                    # Try to extract JSON from response
                    if "[" in response or "{" in response:
                        # Find JSON in response
                        json_start = response.find("[")
                        if json_start == -1:
                            json_start = response.find("{")
                        if json_start != -1:
                            json_end = response.rfind("]") + 1
                            if json_end == 0:
                                json_end = response.rfind("}") + 1
                            if json_end > json_start:
                                json_str = response[json_start:json_end]
                                parsed = json.loads(json_str)
                                if isinstance(parsed, list):
                                    return {"tool_calls": parsed}
                                elif isinstance(parsed, dict):
                                    return {"tool_calls": [parsed]}
                    return {"content": response}
                except Exception:
                    return {"content": response}
            else:
                return {"content": str(response)}
        except Exception as e:
            logger.error(f"Error calling LLM with tools: {e}", exc_info=True)
            # Fallback to text response
            return {"content": ""}
    
    def _parse_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse LLM response into tool calls.
        
        Args:
            response: LLM response
            
        Returns:
            List of tool calls in format: [{"name": str, "arguments": dict}]
        """
        tool_calls = []
        
        # Handle Anthropic format: {"tool_calls": [{"id": str, "name": str, "input": dict}]}
        if "tool_calls" in response:
            for tool_call in response["tool_calls"]:
                tool_calls.append({
                    "name": tool_call.get("name"),
                    "arguments": tool_call.get("input", {})  # Anthropic uses "input"
                })
        
        # Handle OpenAI format: {"tool_calls": [{"function": {"name": str, "arguments": str}}]}
        elif isinstance(response, dict) and "tool_calls" in response:
            for tool_call in response["tool_calls"]:
                func = tool_call.get("function", {})
                name = func.get("name")
                arguments_str = func.get("arguments", "{}")
                
                # Parse arguments if string
                if isinstance(arguments_str, str):
                    import json
                    try:
                        arguments = json.loads(arguments_str)
                    except Exception:
                        arguments = {}
                else:
                    arguments = arguments_str
                
                tool_calls.append({
                    "name": name,
                    "arguments": arguments
                })
        
        # Handle OpenAI function_call format (legacy)
        elif "function_call" in response:
            func_call = response["function_call"]
            arguments_str = func_call.get("arguments", "{}")
            if isinstance(arguments_str, str):
                import json
                try:
                    arguments = json.loads(arguments_str)
                except Exception:
                    arguments = {}
            else:
                arguments = arguments_str
            
            tool_calls.append({
                "name": func_call.get("name"),
                "arguments": arguments
            })
        
        return tool_calls
