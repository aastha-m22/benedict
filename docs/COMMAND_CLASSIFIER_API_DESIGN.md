# Command Classifier API Design: Multi-Agent Support

**Status (v0.4.0):** Method-file command examples in this document (`update_method`) are not part of the runtime. This document is historical API design.

## Overview

**One-sentence summary:** A registry-based API that enables multiple agents/tools to each define their own command sets, with unified classification and context-aware routing.

## 1. Overview

### What

An API layer that extends the core `CommandClassifier` to support multiple agents, each with their own command definitions. Provides a registry pattern for managing agent-specific classifiers and a unified interface for classification.

### Why

- **Multi-Agent Support**: Different agents/tools need different command sets
- **Isolation**: Agent commands don't interfere with each other
- **Flexibility**: Agents can register/unregister commands dynamically
- **Unified Interface**: Single API for all agents
- **Context-Aware**: Route classification based on agent context

### When to Use

- Multi-agent systems where each agent has distinct capabilities
- Plugin architectures where tools register their own commands
- Systems requiring agent-specific command routing
- Applications needing to support multiple command sets simultaneously

## 2. Non-Goals

- **Not a command router**: Only classifies, doesn't execute commands
- **Not a command discovery system**: Doesn't auto-discover agent capabilities
- **Not a permission system**: Doesn't handle authorization
- **Not a command composition system**: Doesn't chain or combine commands

## 3. Key Concepts & Terminology

| Term | Meaning |
|------|---------|
| **Agent** | A tool or service with its own set of commands |
| **Agent ID** | Unique identifier for an agent (e.g., "repo_agent", "deploy_agent") |
| **Command Registry** | Central registry managing agent-specific classifiers |
| **Context** | Information about which agent should handle classification |
| **Unified Classification** | Classification across all agents, returning agent + intent |
| **Agent-Specific Classification** | Classification within a single agent's command set |

## 4. High-Level Design

### Main Components

1. **CommandRegistry**: Central registry for managing agent classifiers
2. **AgentClassifier**: Wrapper around CommandClassifier with agent metadata
3. **ClassificationResult**: Extended result including agent information
4. **CommandBuilder**: Fluent API for building command definitions

### Data Flow

```
User Input (text)
    ↓
[Option A: Unified Classification]
    ├─> CommandRegistry.classify_all(text)
    │       ├─> Try each agent's classifier
    │       └─> Return best match across all agents
    │
[Option B: Agent-Specific Classification]
    ├─> CommandRegistry.classify_for_agent(agent_id, text)
    │       └─> Use only that agent's classifier
    │
[Option C: Context-Aware Classification]
    ├─> CommandRegistry.classify_with_context(context, text)
    │       ├─> Determine agent from context
    │       └─> Classify using that agent's commands
```

### Key Invariants

- **Agent Isolation**: Each agent's commands don't affect others
- **Deterministic**: Same input + agent always produces same output
- **Fallback**: Returns None if no command detected
- **Priority**: Unified classification returns highest confidence match

## 5. API / Interface

### Core API Structure

```python
from command_classifier import (
    CommandRegistry,
    AgentClassifier,
    ClassificationResult,
    CommandBuilder,
    CommandDefinition,
    CommandType,
    CommandIntent
)
```

### CommandRegistry Interface

```python
class CommandRegistry:
    """Central registry for managing agent-specific command classifiers."""
    
    def register_agent(
        self,
        agent_id: str,
        command_definitions: List[CommandDefinition],
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentClassifier:
        """Register an agent with its command definitions.
        
        Args:
            agent_id: Unique identifier for the agent
            command_definitions: List of command definitions for this agent
            metadata: Optional metadata (name, description, version, etc.)
            
        Returns:
            AgentClassifier instance for this agent
            
        Raises:
            ValueError: If agent_id already registered
        """
    
    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent and remove its commands."""
    
    def get_agent_classifier(self, agent_id: str) -> Optional[AgentClassifier]:
        """Get classifier for a specific agent."""
    
    def classify_all(
        self,
        text: str,
        agent_ids: Optional[List[str]] = None
    ) -> Optional[ClassificationResult]:
        """Classify across all agents (or specified agents).
        
        Args:
            text: User input text
            agent_ids: Optional list of agent IDs to consider.
                     If None, considers all registered agents.
        
        Returns:
            ClassificationResult with agent_id and intent, or None
        """
    
    def classify_for_agent(
        self,
        agent_id: str,
        text: str
    ) -> Optional[CommandIntent]:
        """Classify using only a specific agent's commands.
        
        Args:
            agent_id: Agent to use for classification
            text: User input text
            
        Returns:
            CommandIntent if detected, None otherwise
        """
    
    def classify_with_context(
        self,
        context: Dict[str, Any],
        text: str
    ) -> Optional[ClassificationResult]:
        """Classify using context to determine agent.
        
        Args:
            context: Context dict with 'agent_id' or routing logic
            text: User input text
            
        Returns:
            ClassificationResult with agent_id and intent, or None
        """
    
    def list_agents(self) -> List[str]:
        """List all registered agent IDs."""
    
    def get_agent_commands(self, agent_id: str) -> List[CommandDefinition]:
        """Get command definitions for an agent."""
```

### AgentClassifier Interface

```python
class AgentClassifier:
    """Classifier wrapper for a specific agent."""
    
    def __init__(
        self,
        agent_id: str,
        command_definitions: List[CommandDefinition],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Initialize agent classifier."""
    
    @property
    def agent_id(self) -> str:
        """Agent identifier."""
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Agent metadata."""
    
    def classify(self, text: str) -> Optional[CommandIntent]:
        """Classify using this agent's commands."""
    
    def add_command(self, command_def: CommandDefinition) -> None:
        """Add a command definition dynamically."""
    
    def remove_command(self, command_type: CommandType) -> None:
        """Remove a command definition."""
```

### ClassificationResult Interface

```python
@dataclass
class ClassificationResult:
    """Extended classification result with agent information."""
    
    agent_id: str
    intent: CommandIntent
    confidence: float  # Same as intent.confidence, for convenience
    
    @property
    def command_type(self) -> CommandType:
        """Convenience accessor."""
        return self.intent.command_type
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """Convenience accessor."""
        return self.intent.parameters
```

### CommandBuilder Interface

```python
class CommandBuilder:
    """Fluent API for building command definitions."""
    
    def __init__(self, command_type: CommandType, name: str):
        """Start building a command definition."""
    
    def with_description(self, description: str) -> 'CommandBuilder':
        """Set command description."""
    
    def with_pattern(self, pattern: str) -> 'CommandBuilder':
        """Add a regex pattern."""
    
    def with_patterns(self, patterns: List[str]) -> 'CommandBuilder':
        """Add multiple patterns."""
    
    def with_required_param(self, param: str) -> 'CommandBuilder':
        """Add required parameter."""
    
    def with_optional_param(self, param: str) -> 'CommandBuilder':
        """Add optional parameter."""
    
    def with_example(self, example: str) -> 'CommandBuilder':
        """Add example usage."""
    
    def with_confidence_boost(self, boost: float) -> 'CommandBuilder':
        """Set custom confidence boost."""
    
    def with_priority(self, priority: int) -> 'CommandBuilder':
        """Set match priority."""
    
    def build(self) -> CommandDefinition:
        """Build the command definition."""
```

## 6. Happy Path Examples

### Example 1: Registering Multiple Agents

```python
from command_classifier import CommandRegistry, CommandBuilder, CommandType

# Create registry
registry = CommandRegistry()

# Register Repo Agent
repo_commands = [
    CommandBuilder(CommandType.READ_FILE, "read_file")
        .with_description("Read a file")
        .with_pattern(r"read\s+([^\s]+)")
        .with_required_param("file_path")
        .with_example("read README.md")
        .build(),
    CommandBuilder(CommandType.UPDATE_METHOD, "update_method")
        .with_description("Update method file")
        .with_pattern(r"update\s+phase\s+to\s+([^\s]+)")
        .with_required_param("phase")
        .build(),
]

registry.register_agent(
    agent_id="repo_agent",
    command_definitions=repo_commands,
    metadata={"name": "Repository Agent", "version": "1.0"}
)

# Register Deploy Agent
deploy_commands = [
    CommandBuilder(CommandType.DEPLOY, "deploy")
        .with_description("Deploy application")
        .with_pattern(r"deploy\s+to\s+([^\s]+)")
        .with_required_param("environment")
        .with_example("deploy to production")
        .build(),
]

registry.register_agent(
    agent_id="deploy_agent",
    command_definitions=deploy_commands,
    metadata={"name": "Deploy Agent", "version": "1.0"}
)
```

### Example 2: Unified Classification

```python
# Classify across all agents
result = registry.classify_all("read README.md")

if result:
    print(f"Agent: {result.agent_id}")  # "repo_agent"
    print(f"Command: {result.command_type}")  # CommandType.READ_FILE
    print(f"Parameters: {result.parameters}")  # {"file_path": "README.md"}
    print(f"Confidence: {result.confidence}")  # 0.85
```

### Example 3: Agent-Specific Classification

```python
# Classify using only repo agent
intent = registry.classify_for_agent("repo_agent", "read config.yaml")

if intent:
    print(f"Command: {intent.command_type}")
    print(f"File: {intent.parameters['file_path']}")
```

### Example 4: Context-Aware Classification

```python
# Classify with context (e.g., from Slack channel metadata)
context = {
    "channel": "C12345",
    "agent_id": "repo_agent",  # Determined from channel config
    "user_id": "U67890"
}

result = registry.classify_with_context(context, "update phase to sprint")

if result:
    # Route to repo_agent handler
    route_to_handler(result.agent_id, result.intent)
```

### Example 5: Dynamic Command Registration

```python
# Get agent classifier
agent_classifier = registry.get_agent_classifier("repo_agent")

# Add new command dynamically
new_command = CommandBuilder(CommandType.SEARCH_CODE, "search_code")
    .with_description("Search code")
    .with_pattern(r"search\s+for\s+(.+)")
    .with_required_param("query")
    .build()

agent_classifier.add_command(new_command)

# Now it's available for classification
intent = agent_classifier.classify("search for authentication")
```

## 7. Edge Cases & Failure Modes

### What Can Fail?

1. **Duplicate Agent ID**: Registering same agent_id twice
   - **Handling**: Raise ValueError with clear message
   - **Guarantee**: Each agent_id is unique

2. **Unknown Agent**: Classifying for non-existent agent
   - **Handling**: Return None or raise KeyError (configurable)
   - **Guarantee**: Never crashes, returns None by default

3. **Conflicting Commands**: Same command type across agents
   - **Handling**: Allowed, unified classification returns highest confidence
   - **Guarantee**: No interference between agents

4. **Empty Command Set**: Agent with no commands
   - **Handling**: Classification always returns None
   - **Guarantee**: System continues to work

5. **Context Without Agent**: Context doesn't specify agent_id
   - **Handling**: Fall back to unified classification
   - **Guarantee**: Always returns result or None

### What the System Guarantees

- **Agent Isolation**: Commands don't leak between agents
- **Thread Safety**: Safe for concurrent access (if implemented)
- **Deterministic**: Same input + agent = same output
- **Non-Blocking**: Never raises exceptions (except registration errors)

## 8. Constraints & Assumptions

### Performance Limits

- **Registry Lookup**: O(1) for agent lookup, O(n) for unified classification
- **Memory**: Each agent stores its own classifier and patterns
- **Scalability**: Suitable for < 100 agents, < 1000 commands total

### Security Assumptions

- **Agent IDs**: Should be validated (no injection)
- **Command Definitions**: Trusted source (application responsibility)
- **Context**: Application validates context before passing

### Environmental Requirements

- **Python 3.10+**: Uses modern Python features
- **Standard Library**: Only uses standard library (re, enum, dataclasses, typing)

## 9. Architecture

### Module Structure

```
command_classifier/
├── __init__.py              # Public API exports
├── classifier.py            # Core CommandClassifier (existing)
├── registry.py              # CommandRegistry, AgentClassifier
├── result.py                 # ClassificationResult
├── builder.py                # CommandBuilder
├── definitions.py            # CommandDefinition, CommandType, CommandIntent (existing)
└── context.py                # Context routing utilities
```

### Class Diagram

```
CommandRegistry
    ├── agents: Dict[str, AgentClassifier]
    ├── register_agent() -> AgentClassifier
    ├── unregister_agent()
    ├── classify_all() -> Optional[ClassificationResult]
    ├── classify_for_agent() -> Optional[CommandIntent]
    └── classify_with_context() -> Optional[ClassificationResult]

AgentClassifier
    ├── agent_id: str
    ├── classifier: CommandClassifier
    ├── metadata: Dict[str, Any]
    ├── classify() -> Optional[CommandIntent]
    ├── add_command()
    └── remove_command()

ClassificationResult
    ├── agent_id: str
    ├── intent: CommandIntent
    └── confidence: float

CommandBuilder
    ├── command_type: CommandType
    ├── name: str
    └── build() -> CommandDefinition
```

### Sequence Diagram: Unified Classification

```
User Input
    │
    ├─> CommandRegistry.classify_all(text)
    │       │
    │       ├─> For each AgentClassifier:
    │       │       │
    │       │       ├─> AgentClassifier.classify(text)
    │       │       │       └─> CommandClassifier.classify(text)
    │       │       │
    │       │       └─> Return CommandIntent or None
    │       │
    │       ├─> Collect all matches
    │       │
    │       └─> Return ClassificationResult with highest confidence
    │
    └─> ClassificationResult or None
```

## 10. Implementation Strategy

### Phase 1: Core Registry

1. Implement `CommandRegistry` with basic agent registration
2. Implement `AgentClassifier` wrapper
3. Implement `ClassificationResult`
4. Add unified classification

### Phase 2: Builder Pattern

1. Implement `CommandBuilder` fluent API
2. Add validation and error handling
3. Update documentation with builder examples

### Phase 3: Context-Aware Routing

1. Implement context routing logic
2. Add context utilities
3. Support context-based agent selection

### Phase 4: Advanced Features

1. Dynamic command registration/unregistration
2. Command priority and ordering
3. Agent metadata and introspection
4. Performance optimizations

## 11. Usage Patterns

### Pattern 1: Plugin Architecture

```python
# Each plugin registers its commands
class DeployPlugin:
    def register(self, registry: CommandRegistry):
        commands = self._build_commands()
        registry.register_agent("deploy", commands)
```

### Pattern 2: Agent Factory

```python
def create_repo_agent(registry: CommandRegistry) -> AgentClassifier:
    commands = load_repo_commands()
    return registry.register_agent("repo_agent", commands)
```

### Pattern 3: Middleware Pattern

```python
def classification_middleware(registry: CommandRegistry):
    def middleware(text: str, context: Dict):
        result = registry.classify_with_context(context, text)
        if result:
            return route_to_agent(result.agent_id, result.intent)
        return handle_query(text)
    return middleware
```

## 12. Alternatives Considered

### Option A: Single Classifier with Namespace Prefixes
- **Pros**: Simpler, single classifier
- **Cons**: Commands interfere, harder to isolate
- **Rejected because**: Need agent isolation

### Option B: Separate Classifiers Per Agent (No Registry)
- **Pros**: Simple, direct
- **Cons**: No unified classification, manual management
- **Rejected because**: Need unified interface

### Option C: Current Approach (Registry Pattern)
- **Pros**: Isolation + unified interface, extensible
- **Cons**: More complex, additional abstraction
- **Chosen because**: Best balance of features and flexibility

## 13. Open Questions

1. **Q1**: Should we support command aliases across agents?
   - **Consideration**: Could enable command reuse
   - **Current**: Each agent defines its own commands

2. **Q2**: Should we support command inheritance/composition?
   - **Consideration**: Could reduce duplication
   - **Current**: No inheritance, each agent independent

3. **Q3**: Should we support command versioning?
   - **Consideration**: Could enable command evolution
   - **Current**: No versioning, replace commands

4. **Q4**: Should we support command permissions?
   - **Consideration**: Could enable access control
   - **Current**: No permissions, application responsibility

5. **Q5**: Should we support command statistics/metrics?
   - **Consideration**: Could enable analytics
   - **Current**: No built-in metrics

## 14. Migration Path

### For Existing Users

1. **Backward Compatible**: Existing `CommandClassifier` still works
2. **Gradual Migration**: Can migrate agents one at a time
3. **Wrapper Support**: Registry can wrap existing classifiers

### Migration Steps

1. Create `CommandRegistry` instance
2. Register agents with their command definitions
3. Replace direct `CommandClassifier` usage with registry calls
4. Update routing logic to use `ClassificationResult`
