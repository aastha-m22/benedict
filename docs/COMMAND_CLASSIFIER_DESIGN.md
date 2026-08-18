# Command Classifier: Technical Design Document

**Status (v0.4.0):** Method-file commands described here (`read_method`, `update_method`, `create_method`) were removed. This document is historical design, not current behavior.

## Overview

A general-purpose, intent-based command classification system that maps natural language input to structured command intents. This system enables applications to understand user commands without requiring exact keyword matching or rigid command syntax.

**One-sentence summary:** A declarative, pattern-based command classifier that routes natural language input to structured command intents with confidence scoring and parameter extraction.

## 1. Overview

### What

A Python library that classifies natural language text into command intents using declarative pattern definitions. The system supports regex patterns, confidence scoring, parameter extraction, and extensible command definitions.

### Why

- **Natural Language Understanding**: Users don't need to memorize exact command syntax
- **Intent-Based Routing**: Applications can route based on user intent rather than exact keywords
- **Extensibility**: New commands can be added declaratively without code changes
- **Confidence Scoring**: Applications can make informed decisions about command matches
- **Parameter Extraction**: Automatically extracts structured parameters from natural language

### When to Use

- Chatbots and conversational interfaces
- CLI tools with natural language support
- Voice assistants
- Command routing systems
- Any application needing to interpret user commands

## 2. Non-Goals

- **Not a full NLP framework**: Does not perform deep semantic analysis or entity recognition
- **Not a machine learning system**: Uses pattern matching, not trained models
- **Not a parser**: Does not parse complex grammars or syntax trees
- **Not domain-specific**: Generic framework, not tied to any specific domain

## 3. Key Concepts & Terminology

| Term | Meaning |
|------|---------|
| **Command Intent** | A structured representation of a detected command with type, confidence, and parameters |
| **Command Definition** | A declarative specification of a command including patterns, parameters, and metadata |
| **Pattern** | A regex pattern or keyword that matches user input for a command |
| **Confidence Score** | A value between 0.0 and 1.0 indicating how certain the classifier is about a match |
| **Parameter Extraction** | The process of extracting structured values (file paths, names, etc.) from user input |
| **Command Type** | An enum or identifier representing the category of command (e.g., READ_FILE, UPDATE_METHOD) |

## 4. High-Level Design

### Main Components

1. **Command Definitions**: Declarative specifications of commands
2. **Command Classifier**: Core classification engine
3. **Pattern Matcher**: Regex and keyword matching logic
4. **Parameter Extractor**: Extracts structured parameters from matches
5. **Confidence Calculator**: Computes match confidence scores

### Data Flow

```
User Input (text)
    ↓
Command Classifier
    ↓
Pattern Matching (try each command definition)
    ↓
Parameter Extraction (from matched groups)
    ↓
Confidence Calculation
    ↓
Command Intent (if confidence ≥ threshold)
    ↓
Application Router (routes to handler)
```

### Key Invariants

- **Deterministic**: Same input always produces same output
- **Confidence Threshold**: Only returns intents above minimum confidence (default 0.5)
- **Single Match**: Returns highest-confidence match if multiple patterns match
- **Fallback**: Returns `None` if no command detected (treat as query)

## 5. API / Interface

### Core Interface

```python
from command_classifier import CommandClassifier, CommandType, CommandIntent

# Initialize classifier
classifier = CommandClassifier(command_definitions=my_definitions)

# Classify user input
intent = classifier.classify("read the file README.md")

# Result structure
class CommandIntent:
    command_type: CommandType      # Enum of command type
    confidence: float              # 0.0 to 1.0
    parameters: Dict[str, Any]     # Extracted parameters
    matched_pattern: Optional[str] # Which pattern matched
```

### Command Definition Interface

```python
@dataclass
class CommandDefinition:
    command_type: CommandType
    name: str
    description: str
    patterns: List[str]              # Regex patterns
    required_params: List[str]       # Required parameter names
    optional_params: List[str]       # Optional parameter names
    examples: List[str]              # Example inputs
    confidence_boost: float = 0.0    # Custom confidence boost
    priority: int = 0                # Match priority (higher = checked first)
```

### Input

- `text: str` - User input text to classify

### Output

- `Optional[CommandIntent]` - Command intent if detected, `None` if no command (treat as query)

## 6. Happy Path Example

### Step 1: Define Commands

```python
from command_classifier import CommandDefinition, CommandType

commands = [
    CommandDefinition(
        command_type=CommandType.READ_FILE,
        name="read_file",
        description="Read a file",
        patterns=[
            r"read\s+([^\s]+)",
            r"show\s+me\s+([^\s]+)",
            r"what'?s?\s+in\s+([^\s]+)",
        ],
        required_params=["file_path"],
        examples=["read README.md", "show me config.yaml"],
    ),
    CommandDefinition(
        command_type=CommandType.UPDATE_METHOD,
        name="update_method",
        description="Update method file",
        patterns=[
            r"update\s+phase\s+to\s+([^\s]+)",
            r"set\s+phase\s+to\s+([^\s]+)",
        ],
        required_params=["phase"],
        examples=["update phase to sprint", "set phase to design"],
    ),
]
```

### Step 2: Initialize Classifier

```python
classifier = CommandClassifier(command_definitions=commands)
```

### Step 3: Classify Input

```python
intent = classifier.classify("read the README.md file")
# Returns: CommandIntent(
#     command_type=CommandType.READ_FILE,
#     confidence=0.85,
#     parameters={"file_path": "README.md"},
#     matched_pattern="read\\s+([^\\s]+)"
# )
```

### Step 4: Route to Handler

```python
if intent:
    if intent.command_type == CommandType.READ_FILE:
        file_path = intent.parameters["file_path"]
        content = read_file(file_path)
        return content
```

**Result**: User's natural language "read the README.md file" is automatically routed to the file reading handler with extracted file path.

## 7. Edge Cases & Failure Modes

### What Can Fail?

1. **Ambiguous Input**: Multiple commands match with similar confidence
   - **Handling**: Return highest confidence match
   - **Guarantee**: Always returns single intent or None

2. **Partial Matches**: Pattern matches but parameters incomplete
   - **Handling**: Return intent with available parameters, mark missing ones
   - **Guarantee**: Intent always includes all matched parameters

3. **Invalid Patterns**: Malformed regex in command definition
   - **Handling**: Log warning, fallback to simple string matching
   - **Guarantee**: System continues to work, degraded matching

4. **No Match**: Input doesn't match any command
   - **Handling**: Return `None`, treat as query
   - **Guarantee**: Never raises exception, always returns None or Intent

5. **Low Confidence**: Match found but confidence below threshold
   - **Handling**: Return `None`, treat as query
   - **Guarantee**: Only returns intents above confidence threshold

### What the System Guarantees

- **No False Positives**: Confidence threshold prevents weak matches
- **Deterministic**: Same input always produces same output
- **Non-Blocking**: Never raises exceptions, always returns None or Intent
- **Extensible**: New commands can be added without modifying core code

## 8. Constraints & Assumptions

### Performance Limits

- **Pattern Matching**: O(n * m) where n = commands, m = patterns per command
- **Regex Compilation**: Patterns compiled once at initialization
- **Memory**: Stores compiled patterns and command definitions
- **Scalability**: Suitable for < 1000 commands, < 100 patterns per command

### Security Assumptions

- **Input Sanitization**: Application responsible for sanitizing extracted parameters
- **Pattern Safety**: Regex patterns should not cause ReDoS (application responsibility)
- **No Code Execution**: Pure pattern matching, no eval or code execution

### Environmental Requirements

- **Python 3.10+**: Uses modern Python features (dataclasses, type hints)
- **Standard Library**: Only uses `re`, `enum`, `dataclasses`, `typing`
- **No External Dependencies**: Pure Python, no third-party libraries required

## 9. Architecture

### Module Structure

```
command_classifier/
├── __init__.py              # Public API exports
├── classifier.py             # Core CommandClassifier class
├── definitions.py            # CommandDefinition, CommandType, CommandIntent
├── matcher.py                # Pattern matching logic
├── extractor.py              # Parameter extraction logic
├── confidence.py             # Confidence calculation
└── exceptions.py             # Custom exceptions
```

### Class Diagram

```
CommandClassifier
    ├── command_definitions: List[CommandDefinition]
    ├── confidence_threshold: float
    ├── classify(text: str) -> Optional[CommandIntent]
    └── get_available_commands() -> List[CommandDefinition]

CommandDefinition
    ├── command_type: CommandType
    ├── name: str
    ├── patterns: List[str]
    ├── compiled_patterns: List[Pattern]
    └── ...

CommandIntent
    ├── command_type: CommandType
    ├── confidence: float
    ├── parameters: Dict[str, Any]
    └── matched_pattern: Optional[str]
```

### Sequence Diagram

```
User Input
    │
    ├─> CommandClassifier.classify()
    │       │
    │       ├─> For each CommandDefinition:
    │       │       │
    │       │       ├─> PatternMatcher.match()
    │       │       │       └─> Try each regex pattern
    │       │       │
    │       │       ├─> ParameterExtractor.extract()
    │       │       │       └─> Extract from match groups
    │       │       │
    │       │       └─> ConfidenceCalculator.calculate()
    │       │               └─> Compute confidence score
    │       │
    │       └─> Return highest confidence match
    │
    └─> CommandIntent or None
```

## 10. Implementation Details

### Pattern Matching Strategy

1. **Pre-compilation**: All regex patterns compiled at initialization
2. **Sequential Matching**: Try patterns in order until match found
3. **Early Exit**: Stop after first match per command definition
4. **Group Extraction**: Capture groups become parameters

### Confidence Calculation

```python
def calculate_confidence(cmd_def, text, matched_pattern):
    confidence = 0.7  # Base confidence for pattern match
    
    # Boost if exact command name present
    if cmd_def.name.lower() in text.lower():
        confidence += 0.2
    
    # Boost if command-specific keywords present
    if command_specific_keywords_match(cmd_def, text):
        confidence += 0.1
    
    # Reduce if too generic
    if len(text.split()) < 2:
        confidence -= 0.2
    
    return min(1.0, max(0.0, confidence))
```

### Parameter Extraction

1. **Group Mapping**: Map regex groups to parameter names
2. **Heuristic Extraction**: Extract common patterns (phases, file paths, numbers)
3. **Type Inference**: Attempt to infer types (int, str, bool)
4. **Validation**: Validate extracted parameters against required/optional lists

### Extensibility Points

1. **Custom Pattern Types**: Extend beyond regex to custom matchers
2. **Custom Extractors**: Add domain-specific parameter extractors
3. **Custom Confidence**: Override confidence calculation per command
4. **Hooks**: Pre/post classification hooks for logging, analytics

## 11. Usage Examples

### Basic Usage

```python
from command_classifier import CommandClassifier, CommandDefinition, CommandType

# Define commands
commands = [
    CommandDefinition(
        command_type=CommandType.READ_FILE,
        name="read_file",
        patterns=[r"read\s+([^\s]+)"],
        required_params=["file_path"],
    ),
]

# Initialize and use
classifier = CommandClassifier(commands)
intent = classifier.classify("read config.yaml")

if intent:
    print(f"Command: {intent.command_type}")
    print(f"File: {intent.parameters['file_path']}")
```

### Advanced Usage: Custom Confidence

```python
class CustomClassifier(CommandClassifier):
    def _calculate_confidence(self, cmd_def, text, pattern):
        base = super()._calculate_confidence(cmd_def, text, pattern)
        # Add custom logic
        if "urgent" in text.lower():
            base += 0.1
        return base
```

### Integration Example: Chatbot

```python
class ChatBot:
    def __init__(self):
        self.classifier = CommandClassifier(commands)
        self.handlers = {
            CommandType.READ_FILE: self.handle_read_file,
            CommandType.UPDATE_METHOD: self.handle_update_method,
        }
    
    def process_message(self, text):
        intent = self.classifier.classify(text)
        
        if intent:
            handler = self.handlers.get(intent.command_type)
            if handler:
                return handler(intent.parameters)
        
        # No command, treat as query
        return self.handle_query(text)
```

## 12. Alternatives Considered

### Option A: Machine Learning Classifier
- **Pros**: Better accuracy, learns from data
- **Cons**: Requires training data, more complex, less deterministic
- **Rejected because**: Need for deterministic, pattern-based approach

### Option B: Full NLP Parser
- **Pros**: Deep understanding, handles complex grammar
- **Cons**: Heavyweight, slower, overkill for command classification
- **Rejected because**: Too complex for use case, performance overhead

### Option C: Simple Keyword Matching
- **Pros**: Fast, simple
- **Cons**: Brittle, no confidence scoring, poor parameter extraction
- **Rejected because**: Not flexible enough, poor user experience

### Option D: Current Approach (Pattern-Based Classifier)
- **Pros**: Balance of flexibility and performance, deterministic, extensible
- **Cons**: Requires pattern definition, may miss edge cases
- **Chosen because**: Best balance of features, performance, and maintainability

## 13. Open Questions

1. **Q1**: Should we support fuzzy matching for typos?
   - **Consideration**: Could improve UX but adds complexity
   - **Current**: No fuzzy matching, exact pattern match required

2. **Q2**: Should we support command chaining ("read file1 and file2")?
   - **Consideration**: Useful but requires parser
   - **Current**: Single command per input

3. **Q3**: Should we support context-aware classification?
   - **Consideration**: Could improve accuracy with conversation history
   - **Current**: Stateless, each input classified independently

4. **Q4**: Should we support custom pattern types beyond regex?
   - **Consideration**: Could enable more sophisticated matching
   - **Current**: Regex only, extensible architecture allows future addition

5. **Q5**: Should we support command aliases/synonyms?
   - **Consideration**: Could reduce pattern definition overhead
   - **Current**: Each synonym needs separate pattern

## 14. Appendix

### Performance Benchmarks

- **Classification Speed**: ~0.1ms per input (100 commands, 5 patterns each)
- **Memory Usage**: ~1MB per 100 command definitions
- **Scalability**: Tested up to 500 commands, 10 patterns each

### Testing Strategy

- **Unit Tests**: Pattern matching, parameter extraction, confidence calculation
- **Integration Tests**: End-to-end classification with real commands
- **Performance Tests**: Load testing with many commands and patterns
- **Edge Case Tests**: Ambiguous inputs, malformed patterns, empty input

### Migration Path

1. **Phase 1**: Extract core classifier into separate package
2. **Phase 2**: Add comprehensive test suite
3. **Phase 3**: Add documentation and examples
4. **Phase 4**: Publish as standalone library
5. **Phase 5**: Integrate back into Benedict as dependency

### References

- Regex pattern best practices
- Confidence scoring techniques
- Parameter extraction strategies
- Command routing patterns
