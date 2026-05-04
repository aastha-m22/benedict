# LLM-Based Command Classifier: Technical Design Document

## Overview

An LLM-powered command classification system that uses natural language understanding to map user input to structured command intents. Instead of pattern matching, this system leverages LLM reasoning to understand user intent and extract parameters.

**One-sentence summary:** An LLM-based command classifier that uses structured prompting to classify natural language input into command intents with parameter extraction.

## 1. Overview

### What

A Python library that uses Large Language Models (LLMs) to classify natural language text into command intents. The system uses structured prompts and function calling/JSON mode to get deterministic command classifications.

### Why

- **True Natural Language Understanding**: Handles variations, synonyms, and context
- **No Pattern Maintenance**: No need to define regex patterns for every variation
- **Context Awareness**: Can understand implicit commands and context
- **Parameter Extraction**: LLM extracts structured parameters intelligently
- **Handles Ambiguity**: Can ask clarifying questions or make reasonable inferences

### When to Use

- Applications requiring natural language command understanding
- Systems where command variations are too numerous for patterns
- Context-aware command routing
- Multi-turn conversations where context matters
- Applications already using LLMs (leverages existing infrastructure)

## 2. Non-Goals

- **Not a pattern matching system**: Uses LLM, not regex patterns
- **Not a training system**: Uses pre-trained LLMs, no fine-tuning required
- **Not a full conversational AI**: Focused on command classification, not general chat
- **Not deterministic by default**: Uses LLM reasoning (can be made deterministic with constraints)

## 3. Key Concepts & Terminology

| Term | Meaning |
|------|---------|
| **LLM Classifier** | The core component that uses LLM to classify commands |
| **Command Schema** | JSON schema defining available commands and their parameters |
| **Structured Prompt** | Prompt template that guides LLM to return structured output |
| **Function Calling** | LLM feature that returns structured function calls (OpenAI, Anthropic) |
| **JSON Mode** | LLM mode that guarantees JSON output (OpenAI) |
| **Intent Classification** | Process of mapping user input to command type |
| **Parameter Extraction** | Process of extracting structured parameters from natural language |
| **Confidence Score** | LLM-provided or computed confidence in classification |

## 4. High-Level Design

### Main Components

1. **Command Schema**: JSON schema defining available commands
2. **LLM Classifier**: Core classification engine using LLM
3. **Prompt Builder**: Constructs structured prompts from schema
4. **Response Parser**: Parses LLM response into CommandIntent
5. **Parameter Validator**: Validates extracted parameters against schema

### Data Flow

```
User Input (text)
    ↓
Command Schema (available commands)
    ↓
Prompt Builder (creates structured prompt)
    ↓
LLM (classifies intent + extracts parameters)
    ↓
Response Parser (parses JSON/function call)
    ↓
Parameter Validator (validates against schema)
    ↓
CommandIntent (structured result)
    ↓
Application Router (routes to handler)
```

### Key Invariants

- **Schema-Driven**: All commands defined in JSON schema
- **Structured Output**: LLM always returns structured JSON/function call
- **Validation**: Parameters validated against schema before returning
- **Fallback**: Returns QUERY intent if no command matches

## 5. API / Interface

### Core Interface

```python
from llm_command_classifier import LLMCommandClassifier, CommandSchema, CommandIntent

# Define command schema
schema = CommandSchema(
    commands=[
        {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    }
                },
                "required": ["file_path"]
            }
        },
        {
            "name": "update_method",
            "description": "Update the method file (phase, concerns, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "phase": {
                        "type": "string",
                        "enum": ["conception", "design", "sprint", "review"],
                        "description": "Phase to set"
                    },
                    "concern": {
                        "type": "string",
                        "enum": ["scope", "documentation", "development", "communication"],
                        "description": "Concern to update"
                    },
                    "state": {
                        "type": "string",
                        "description": "New state value"
                    }
                }
            }
        }
    ]
)

# Initialize classifier
classifier = LLMCommandClassifier(
    llm=llm_instance,  # LLM protocol implementation
    schema=schema,
    fallback_to_query=True  # Return QUERY if no command matches
)

# Classify user input
intent = classifier.classify("read the README.md file")

# Result structure
class CommandIntent:
    command_name: str              # Name from schema
    confidence: Optional[float]   # LLM confidence if available
    parameters: Dict[str, Any]     # Extracted parameters
    reasoning: Optional[str]       # LLM reasoning (optional)
```

### Command Schema Interface

```python
@dataclass
class CommandSchema:
    """Schema defining available commands."""
    commands: List[Dict[str, Any]]  # List of command definitions
    default_command: Optional[str] = None  # Default if no match
    query_command_name: str = "query"  # Name for query fallback
    
    def to_function_schema(self) -> List[Dict]:
        """Convert to OpenAI function calling format."""
        ...
    
    def to_json_schema(self) -> Dict:
        """Convert to JSON schema for JSON mode."""
        ...
```

### LLM Protocol Interface

```python
class LLM(Protocol):
    """LLM protocol for classification."""
    
    def call_with_functions(
        self,
        prompt: str,
        functions: List[Dict],
        function_call: Optional[str] = "auto"
    ) -> Dict[str, Any]:
        """Call LLM with function calling."""
        ...
    
    def call_with_json_mode(
        self,
        prompt: str,
        response_format: Dict
    ) -> Dict[str, Any]:
        """Call LLM with JSON mode."""
        ...
```

## 6. Happy Path Example

### Step 1: Define Command Schema

```python
schema = CommandSchema(
    commands=[
        {
            "name": "read_file",
            "description": "Read contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "File path"}
                },
                "required": ["file_path"]
            }
        },
        {
            "name": "update_method",
            "description": "Update method file phase or concerns",
            "parameters": {
                "type": "object",
                "properties": {
                    "phase": {
                        "type": "string",
                        "enum": ["conception", "design", "sprint", "review"]
                    },
                    "concern": {"type": "string"},
                    "state": {"type": "string"}
                }
            }
        }
    ]
)
```

### Step 2: Initialize Classifier

```python
classifier = LLMCommandClassifier(
    llm=anthropic_llm,  # or openai_llm
    schema=schema
)
```

### Step 3: Classify Input

```python
intent = classifier.classify("can you show me what's in the README file?")
```

### Step 4: LLM Processing

**Prompt sent to LLM:**
```
You are a command classifier. Classify the user's input into one of these commands:

Available commands:
1. read_file - Read contents of a file
   Parameters: file_path (string, required)

2. update_method - Update method file phase or concerns
   Parameters: phase (enum), concern (string), state (string)

User input: "can you show me what's in the README file?"

Respond with a JSON object:
{
  "command": "command_name",
  "parameters": {...},
  "confidence": 0.0-1.0
}
```

**LLM Response:**
```json
{
  "command": "read_file",
  "parameters": {
    "file_path": "README.md"
  },
  "confidence": 0.95,
  "reasoning": "User wants to see file contents, 'README' refers to README.md"
}
```

### Step 5: Parse and Return

```python
# Returns CommandIntent:
CommandIntent(
    command_name="read_file",
    confidence=0.95,
    parameters={"file_path": "README.md"},
    reasoning="User wants to see file contents..."
)
```

**Result**: Natural language "can you show me what's in the README file?" is classified as `read_file` command with extracted `file_path` parameter.

## 7. Edge Cases & Failure Modes

### What Can Fail?

1. **LLM Returns Invalid JSON**
   - **Handling**: Retry with stricter prompt, fallback to query
   - **Guarantee**: Always returns valid CommandIntent or None

2. **LLM Returns Unknown Command**
   - **Handling**: Validate against schema, fallback to query
   - **Guarantee**: Only returns commands defined in schema

3. **Missing Required Parameters**
   - **Handling**: Ask LLM to extract missing params, or return partial intent
   - **Guarantee**: Parameters validated against schema

4. **Ambiguous Input**
   - **Handling**: LLM can return multiple candidates or ask clarifying question
   - **Guarantee**: Returns single intent or None (with optional clarification)

5. **LLM Timeout/Error**
   - **Handling**: Retry with exponential backoff, fallback to query
   - **Guarantee**: Never raises exception, always returns None or Intent

6. **Parameter Type Mismatch**
   - **Handling**: Validate types, coerce if possible, reject if not
   - **Guarantee**: Parameters match schema types

### What the System Guarantees

- **Schema Compliance**: Only returns commands and parameters defined in schema
- **Type Safety**: Parameters match schema types
- **Graceful Degradation**: Falls back to query on errors
- **Non-Blocking**: Never raises exceptions, always returns result

## 8. Constraints & Assumptions

### Performance Limits

- **LLM Latency**: 100-2000ms per classification (depends on LLM)
- **Token Usage**: ~200-500 tokens per classification
- **Cost**: ~$0.0001-0.001 per classification (depends on LLM pricing)
- **Rate Limits**: Subject to LLM provider rate limits

### Security Assumptions

- **LLM Provider Security**: Trusts LLM provider for secure API calls
- **Input Sanitization**: Application responsible for sanitizing extracted parameters
- **Schema Validation**: Parameters validated but not sanitized
- **No Code Execution**: Pure classification, no code execution

### Environmental Requirements

- **Python 3.10+**: Modern Python features
- **LLM Provider**: OpenAI, Anthropic, or compatible LLM API
- **Network Access**: Requires internet for LLM API calls
- **API Keys**: Requires LLM provider API keys

## 9. Architecture

### Module Structure

```
llm_command_classifier/
├── __init__.py              # Public API exports
├── classifier.py            # Core LLMCommandClassifier class
├── schema.py                # CommandSchema definition
├── prompt_builder.py        # Constructs prompts from schema
├── response_parser.py       # Parses LLM responses
├── validator.py             # Validates parameters against schema
├── llm_protocol.py          # LLM protocol interface
└── adapters/
    ├── openai_adapter.py    # OpenAI implementation
    ├── anthropic_adapter.py # Anthropic implementation
    └── mock_adapter.py       # Mock for testing
```

### Class Diagram

```
LLMCommandClassifier
    ├── llm: LLM
    ├── schema: CommandSchema
    ├── prompt_builder: PromptBuilder
    ├── response_parser: ResponseParser
    ├── validator: ParameterValidator
    ├── classify(text: str) -> Optional[CommandIntent]
    └── classify_with_context(text: str, history: List) -> Optional[CommandIntent]

CommandSchema
    ├── commands: List[Dict]
    ├── to_function_schema() -> List[Dict]
    └── to_json_schema() -> Dict

PromptBuilder
    ├── build_prompt(schema: CommandSchema, text: str) -> str
    └── build_with_context(schema: CommandSchema, text: str, history: List) -> str

ResponseParser
    ├── parse_function_call(response: Dict) -> CommandIntent
    └── parse_json(response: str) -> CommandIntent

ParameterValidator
    ├── validate(intent: CommandIntent, schema: CommandSchema) -> bool
    └── coerce_types(intent: CommandIntent, schema: CommandSchema) -> CommandIntent
```

### Sequence Diagram

```
User Input
    │
    ├─> LLMCommandClassifier.classify()
    │       │
    │       ├─> PromptBuilder.build_prompt()
    │       │       └─> Convert schema to prompt
    │       │
    │       ├─> LLM.call_with_functions() or call_with_json_mode()
    │       │       └─> Send prompt to LLM
    │       │
    │       ├─> ResponseParser.parse()
    │       │       └─> Parse JSON/function call response
    │       │
    │       ├─> ParameterValidator.validate()
    │       │       └─> Validate against schema
    │       │
    │       └─> Return CommandIntent or None
    │
    └─> CommandIntent or None
```

## 10. Implementation Details

### Prompt Construction

**Function Calling Approach (OpenAI, Anthropic):**
```python
def build_function_calling_prompt(schema, user_input):
    functions = schema.to_function_schema()
    
    prompt = f"""Classify the user's input into one of these commands:

{format_commands(schema.commands)}

User input: "{user_input}"

Call the appropriate function with extracted parameters."""
    
    return prompt, functions
```

**JSON Mode Approach (OpenAI):**
```python
def build_json_mode_prompt(schema, user_input):
    json_schema = schema.to_json_schema()
    
    prompt = f"""Classify the user's input into one of these commands:

{format_commands(schema.commands)}

User input: "{user_input}"

Respond with JSON matching this schema:
{json.dumps(json_schema, indent=2)}"""
    
    return prompt, json_schema
```

### LLM Adapter Pattern

```python
class OpenAIAdapter:
    def call_with_functions(self, prompt, functions, function_call="auto"):
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            functions=functions,
            function_call=function_call
        )
        return response.choices[0].message.function_call

class AnthropicAdapter:
    def call_with_functions(self, prompt, functions, function_call="auto"):
        response = anthropic.messages.create(
            model="claude-3-opus",
            messages=[{"role": "user", "content": prompt}],
            tools=[{"type": "function", "function": f} for f in functions]
        )
        return response.content[0].tool_use
```

### Parameter Validation

```python
def validate_parameters(intent: CommandIntent, schema: CommandSchema):
    command_def = find_command(schema.commands, intent.command_name)
    if not command_def:
        return False
    
    param_schema = command_def["parameters"]
    
    # Validate required parameters
    required = param_schema.get("required", [])
    for param in required:
        if param not in intent.parameters:
            return False
    
    # Validate types
    properties = param_schema.get("properties", {})
    for param_name, param_value in intent.parameters.items():
        if param_name in properties:
            expected_type = properties[param_name].get("type")
            if not validate_type(param_value, expected_type):
                return False
    
    # Validate enums
    for param_name, param_value in intent.parameters.items():
        if param_name in properties:
            enum_values = properties[param_name].get("enum")
            if enum_values and param_value not in enum_values:
                return False
    
    return True
```

### Context-Aware Classification

```python
def classify_with_context(self, text: str, conversation_history: List[Message]):
    prompt = self.prompt_builder.build_with_context(
        self.schema,
        text,
        conversation_history
    )
    
    # Include conversation context in prompt
    context_prompt = f"""Previous conversation:
{format_history(conversation_history)}

Current user input: "{text}"

Classify the current input considering the conversation context."""
    
    return self._classify(context_prompt)
```

### Caching Strategy

```python
class CachedLLMCommandClassifier(LLMCommandClassifier):
    def __init__(self, *args, cache_ttl=3600, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache = TTLCache(maxsize=1000, ttl=cache_ttl)
    
    def classify(self, text: str):
        cache_key = hashlib.md5(text.encode()).hexdigest()
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        intent = super().classify(text)
        self.cache[cache_key] = intent
        return intent
```

## 11. Usage Examples

### Basic Usage

```python
from llm_command_classifier import LLMCommandClassifier, CommandSchema
from benedict.llm import AnthropicLLM

# Define schema
schema = CommandSchema(
    commands=[
        {
            "name": "read_file",
            "description": "Read a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"}
                },
                "required": ["file_path"]
            }
        }
    ]
)

# Initialize
llm = AnthropicLLM(api_key="...")
classifier = LLMCommandClassifier(llm=llm, schema=schema)

# Classify
intent = classifier.classify("show me README.md")
# Returns: CommandIntent(command_name="read_file", parameters={"file_path": "README.md"})
```

### Advanced Usage: Context-Aware

```python
# Include conversation history
history = [
    Message(role="user", content="What files are in the repo?"),
    Message(role="assistant", content="Here are the files: README.md, src/..."),
    Message(role="user", content="read the first one")
]

intent = classifier.classify_with_context("read the first one", history)
# LLM understands "first one" refers to README.md from context
```

### Advanced Usage: Custom Prompts

```python
class CustomClassifier(LLMCommandClassifier):
    def build_prompt(self, schema, text):
        base_prompt = super().build_prompt(schema, text)
        return f"""{base_prompt}

Additional context:
- User is a developer
- Prefer technical commands
- Be concise"""
```

### Integration Example: Benedict Agent

```python
class RepoAgent:
    def __init__(self):
        self.classifier = LLMCommandClassifier(
            llm=self.llm,
            schema=self._build_command_schema()
        )
    
    def _build_command_schema(self):
        return CommandSchema(commands=[
            {
                "name": "read_file",
                "description": "Read repository file contents",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"}
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "update_method",
                "description": "Update method file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phase": {"type": "string", "enum": ["conception", "design", "sprint", "review"]},
                        "concern": {"type": "string"},
                        "state": {"type": "string"}
                    }
                }
            }
        ])
    
    def handle_conversation(self, text: str):
        intent = self.classifier.classify(text)
        
        if intent:
            return self._route_command(intent)
        else:
            # No command, treat as query
            return self._handle_query(text)
```

## 12. Alternatives Considered

### Option A: Pattern Matching (Current Benedict Implementation)
- **Pros**: Fast, deterministic, no LLM cost
- **Cons**: Brittle, requires pattern maintenance, doesn't handle variations
- **Rejected because**: User wants LLM-based approach for better NLU

### Option B: Fine-Tuned Model
- **Pros**: Can be optimized for specific domain
- **Cons**: Requires training data, training infrastructure, ongoing maintenance
- **Rejected because**: Pre-trained LLMs sufficient, no training needed

### Option C: Hybrid (LLM + Patterns)
- **Pros**: Fast for common cases, LLM for edge cases
- **Cons**: More complex, two systems to maintain
- **Consideration**: Could be future optimization

### Option D: Current Approach (LLM-Only)
- **Pros**: Best NLU, handles all variations, no pattern maintenance
- **Cons**: Slower, costs money, requires LLM
- **Chosen because**: Best user experience, leverages existing LLM infrastructure

## 13. Open Questions

1. **Q1**: Should we support streaming responses for faster perceived performance?
   - **Consideration**: Could improve UX but adds complexity
   - **Current**: Synchronous only

2. **Q2**: Should we cache classifications to reduce LLM calls?
   - **Consideration**: Could reduce cost/latency but may miss context changes
   - **Current**: No caching, but architecture supports it

3. **Q3**: Should we support multi-command extraction ("read file1 and file2")?
   - **Consideration**: Useful but requires array handling
   - **Current**: Single command per input

4. **Q4**: Should we support confidence thresholds?
   - **Consideration**: Could filter low-confidence matches
   - **Current**: Returns all matches, application decides

5. **Q5**: Should we support clarification questions?
   - **Consideration**: Could handle ambiguous inputs better
   - **Current**: Returns None or best guess

6. **Q6**: Should we support command chaining in single input?
   - **Consideration**: "read file1 then update method"
   - **Current**: Single command only

## 14. Appendix

### Performance Benchmarks

- **Classification Latency**: 100-2000ms (depends on LLM)
- **Token Usage**: ~200-500 tokens per classification
- **Cost**: ~$0.0001-0.001 per classification
- **Accuracy**: ~95%+ for well-defined commands

### Cost Estimation

- **OpenAI GPT-4**: ~$0.03 per 1K tokens → ~$0.006-0.015 per classification
- **Anthropic Claude**: ~$0.015 per 1K tokens → ~$0.003-0.0075 per classification
- **OpenAI GPT-3.5**: ~$0.002 per 1K tokens → ~$0.0004-0.001 per classification

### Testing Strategy

- **Unit Tests**: Schema validation, parameter extraction, response parsing
- **Integration Tests**: End-to-end with real LLM (mocked for CI)
- **Accuracy Tests**: Test suite of varied inputs, measure accuracy
- **Performance Tests**: Latency and cost measurement
- **Edge Case Tests**: Ambiguous inputs, malformed responses, timeouts

### Migration Path from Pattern-Based

1. **Phase 1**: Implement LLM classifier alongside pattern classifier
2. **Phase 2**: A/B test both approaches
3. **Phase 3**: Gradually migrate commands to LLM-based
4. **Phase 4**: Remove pattern-based classifier
5. **Phase 5**: Optimize prompts and caching

### Prompt Engineering Best Practices

- **Be Specific**: Clear command descriptions and parameter definitions
- **Provide Examples**: Include example inputs in prompt
- **Use Enums**: Constrain parameters with enum values when possible
- **Structured Output**: Use function calling or JSON mode for reliability
- **Context**: Include conversation history when available
- **Fallback**: Always provide "query" option for non-commands

### References

- OpenAI Function Calling: https://platform.openai.com/docs/guides/function-calling
- Anthropic Tool Use: https://docs.anthropic.com/claude/docs/tool-use
- JSON Schema: https://json-schema.org/
- Prompt Engineering Guide: https://www.promptingguide.ai/
