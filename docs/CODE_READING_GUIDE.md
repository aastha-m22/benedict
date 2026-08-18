# Code Reading Guide

One-sentence summary:
A guide for engineers to understand how to read, navigate, and understand the benedict codebase architecture and implementation.

## 1. Overview

**What:**
This document explains how to read and understand the benedict codebase—a Slack bot that provides repository-scoped AI agent conversations with semantic code search capabilities.

**Why:**
The codebase follows SOLID principles with protocol-based architecture, dependency injection, and root composition. Understanding these patterns is essential for effective navigation and contribution.

**When to use:**
- When starting to work on the codebase
- When trying to understand how a feature works
- When debugging issues
- When adding new features or modifying existing ones

## 2. Non-Goals

This guide does not:
- Provide API documentation (see code docstrings)
- Explain deployment or operations (see README.md)
- Cover all implementation details (see ARCHITECTURE.md for high-level design)

## 3. Key Concepts & Terminology

| Term | Meaning |
|------|---------|
| **Protocol** | Python Protocol (interface) defining a contract without implementation |
| **Composition Root** | `main.py` where all concrete classes are instantiated |
| **Dependency Injection** | Dependencies passed to classes rather than created internally |
| **Workspace** | Isolated directory per Slack channel containing repository resources |
| **Metadata** | `.metadata.benedict` files providing directory summaries and context |
| **Semantic Indexer** | Component that indexes code for semantic similarity search |
| **Repo Reader** | Abstraction for reading repository files (local filesystem or workspace) |
| **Conversation Repository** | Abstraction for persisting conversation state |

## 4. High-Level Design

### Main Components

The codebase is organized into these layers:

1. **Entry Point** (`main.py`): Composition root that wires all dependencies
2. **Protocols** (`protocols/`): Interface definitions (no implementations)
3. **Implementations** (`llm/`, `repo_reader/`, `semantic_indexer/`, etc.): Concrete implementations
4. **Core Logic** (`agent.py`, `slack_app.py`): Business logic using protocols
5. **Supporting Systems** (`workspace/`, `metadata/`, `commands/`): Feature-specific modules

### Data Flow

1. **Startup**: `main.py` creates all dependencies and wires them together
2. **Event Handling**: Slack events trigger handlers in `slack_app.py`
3. **Command Processing**: `agent.py` routes commands and builds context
4. **Context Building**: Uses semantic search or keyword matching to find relevant files
5. **LLM Interaction**: Sends context + query to LLM for intelligent responses
6. **Response**: Formats and sends response back to Slack

### Key Invariants

- All concrete classes instantiated only in `main.py` (root composition)
- Dependencies injected via constructor, never created internally
- Protocols define contracts; implementations live in separate modules
- Optional dependencies gracefully degrade (system works without LLM, indexer, etc.)

## 5. Reading Strategy: Where to Start

### Step 1: Understand the Entry Point

**Start here:** `src/benedict/main.py` (Slack) or `src/benedict/mcp/server.py` (MCP)

**Questions to answer:**
- What dependencies does the system need?
- How are they created and wired together?
- What happens if optional dependencies fail?

**Key sections:**
- `main.py` `main()` function shows the Slack dependency graph
- `mcp/server.py` `build_mcp_service()` shows the MCP dependency graph

**What you'll learn:**
- The complete system architecture in one place
- How optional components are handled
- Configuration via environment variables
- How the MCP server reuses the same data directory without starting Slack

### Step 2: Understand the Core Agent

**Next:** `src/benedict/agent.py`

**Questions to answer:**
- How does the agent handle different types of commands?
- How is context built for LLM queries?
- How are conversations managed?

**Key sections:**
- Lines 38-90: `RepoAgent.__init__()` shows all dependencies
- Lines 136-250: Command handlers (`handle_onboard`, `handle_status`, etc.)
- Lines 400-600: `handle_conversation()` shows context building and LLM interaction

**What you'll learn:**
- How business logic is organized
- How dependencies are used (not created)
- How commands flow through the system

### Step 3: Understand Protocols (Interfaces)

**Next:** `src/benedict/protocols/`

**Questions to answer:**
- What contracts do components follow?
- What methods must implementations provide?
- How are protocols used vs. implementations?

**Key files:**
- `protocols/llm.py`: LLM interface
- `protocols/repo_reader.py`: Repository access interface
- `protocols/semantic_indexer.py`: Semantic search interface
- `protocols/conversation_repository.py`: Persistence interface

**What you'll learn:**
- System boundaries and abstractions
- What can be swapped out (different LLM, storage, etc.)
- How to add new implementations

### Step 4: Understand Implementations

**Next:** Pick an implementation module (e.g., `llm/llm_claude.py`)

**Questions to answer:**
- How does this implementation satisfy the protocol?
- What external dependencies does it have?
- How does it handle errors?

**Pattern to follow:**
1. Read the protocol first (understand the contract)
2. Read one implementation (see how contract is fulfilled)
3. Compare with mock implementation (see testability pattern)

**What you'll learn:**
- How protocols are implemented
- How external libraries are integrated
- How to create testable code

### Step 5: Understand Feature Modules

**Next:** Explore feature-specific modules (`commands/`, `workspace/`, `metadata/`)

**Questions to answer:**
- How does this feature integrate with the core system?
- What protocols or core components does it use?
- How is it tested?

**Key modules:**
- `commands/`: Command classification and tool execution
- `workspace/`: Workspace lifecycle management
- `metadata/`: Metadata generation and reading

## 6. Guiding Questions for Reading Code

### When Reading a New File

1. **What is this file's responsibility?**
   - Check the module docstring
   - Look at class names and method names
   - Identify if it's a protocol, implementation, or core logic

2. **What does it depend on?**
   - Check imports (especially from `protocols/`)
   - Look at constructor parameters
   - Identify if dependencies are injected or created

3. **What depends on it?**
   - Search for imports of this module
   - Check where it's instantiated (should be `main.py` for concrete classes)
   - See how it's used in tests

4. **How does it fit into the data flow?**
   - Trace from `main.py` → `slack_app.py` → `agent.py` → this file
   - Understand what triggers this code
   - Understand what this code triggers

### When Understanding a Feature

1. **Where is the feature entry point?**
   - Usually in `agent.py` or `slack_app.py`
   - May be in `commands/` for command-specific features

2. **What protocols does it use?**
   - Check what abstractions it depends on
   - Understand why those abstractions exist

3. **How is it tested?**
   - Look for mock implementations
   - Check test files (if they exist)
   - See how dependencies are mocked

4. **What are the failure modes?**
   - Check error handling
   - See how optional dependencies are handled
   - Understand graceful degradation

### When Debugging an Issue

1. **Where does the user action start?**
   - Slack event → `slack_app.py`
   - Command → `agent.py` command handler
   - Conversation → `agent.py.handle_conversation()`

2. **What path does the code take?**
   - Trace from entry point through dependencies
   - Check logs at each step
   - Identify where behavior diverges from expected

3. **What dependencies are involved?**
   - Check if optional dependencies are available
   - Verify dependency configuration
   - See if mocks are being used instead of real implementations

## 7. Code Organization Patterns

### Protocol-Based Architecture

**Pattern:**
```python
# protocols/llm.py - Interface definition
class LLM(Protocol):
    def generate(self, prompt: str) -> str: ...

# llm/llm_claude.py - Implementation
class ClaudeLLM:
    def generate(self, prompt: str) -> str:
        # Actual implementation
```

**Why:**
- Enables swapping implementations
- Makes testing easier (use mocks)
- Clear separation of concerns

**Where to see it:**
- All protocol files in `protocols/`
- All implementations in their respective modules
- Factory functions in `protocols/__init__.py`

### Dependency Injection

**Pattern:**
```python
class RepoAgent:
    def __init__(self, llm: Optional[LLM], repo_reader: Optional[RepoReader]):
        self.llm = llm  # Injected, not created
        self.repo_reader = repo_reader  # Injected, not created
```

**Why:**
- Testability (inject mocks)
- Flexibility (swap implementations)
- Clear dependencies

**Where to see it:**
- All classes in `agent.py`
- All implementations
- `main.py` shows injection points

### Root Composition

**Pattern:**
```python
# main.py - Only place concrete classes are instantiated
def main():
    llm = create_llm(provider="claude")
    repo_reader = create_repo_reader(source="local")
    agent = RepoAgent(llm=llm, repo_reader=repo_reader)
```

**Why:**
- Single place to see all dependencies
- Easy to swap implementations
- Clear dependency graph

**Where to see it:**
- `main.py` lines 95-217
- Factory functions in `protocols/__init__.py`

### Graceful Degradation

**Pattern:**
```python
# main.py
try:
    llm = create_llm(provider="claude")
except Exception as e:
    logger.warning(f"LLM not available: {e}")
    llm = None  # System continues without LLM
```

**Why:**
- System works even if optional components fail
- Easier development (don't need all services)
- Better error messages

**Where to see it:**
- `main.py` for optional components
- `agent.py` checks for None before using dependencies

## 8. Common Code Paths

### Path 1: User Asks a Question

```
Slack Event → slack_app.py (event handler)
  → agent.py.handle_conversation()
    → build_context() (utils/context.py)
      → semantic_indexer.search() OR keyword matching
      → repo_reader.read_file()
    → llm.generate() (with context)
    → Format response → Slack
```

**Files to read:**
1. `slack_app.py`: Event handling
2. `agent.py.handle_conversation()`: Main conversation logic
3. `utils/context.py`: Context building
4. `semantic_indexer/semantic_indexer_chromadb.py`: Semantic search
5. `repo_reader/repo_reader_workspace.py`: File reading

### Path 2: Onboarding a Channel

```
Slack Command → slack_app.py
  → agent.py.handle_onboard()
    → workspace_manager.create_workspace()
    → workspace_manager.add_resource()
    → Save channel → repo mapping
```

**Files to read:**
1. `slack_app.py`: Command routing
2. `agent.py.handle_onboard()`: Onboarding logic
3. `workspace/workspace_manager.py`: Workspace creation
4. `conversation_repository/conversation_repository_json.py`: State persistence

### Path 3: Semantic Indexing

```
First Query → agent.py.handle_conversation()
  → semantic_indexer.search() (not indexed yet)
    → semantic_indexer.index_repository()
      → metadata_generator.generate_metadata()
      → Change detector detects files
      → Files chunked and embedded
      → Stored in ChromaDB
```

**Files to read:**
1. `agent.py`: Triggers indexing
2. `semantic_indexer/semantic_indexer_chromadb.py`: Indexing logic
3. `metadata/metadata_generator.py`: Metadata generation
4. `repo_change_detector/git_change_detector.py`: Change detection

## 9. Reading Checklist

When reading a new part of the codebase:

- [ ] Read the module docstring
- [ ] Identify if it's a protocol, implementation, or core logic
- [ ] Check what it depends on (imports, constructor params)
- [ ] Check what depends on it (search for imports)
- [ ] Understand its place in the data flow
- [ ] Look for error handling patterns
- [ ] Check if it's optional (graceful degradation)
- [ ] Find related test files or mocks
- [ ] Trace a code path that uses it

## 10. Key Files Reference

### Entry Points
- `main.py`: Application entry point and composition root
- `slack_app.py`: Slack event handlers and app configuration

### Core Logic
- `agent.py`: Main agent logic, command handlers, conversation management
- `models/conversation.py`: Conversation and message models

### Protocols (Interfaces)
- `protocols/llm.py`: LLM interface
- `protocols/repo_reader.py`: Repository access interface
- `protocols/semantic_indexer.py`: Semantic search interface
- `protocols/conversation_repository.py`: Persistence interface
- `protocols/repo_change_detector.py`: Change detection interface
- `protocols/conversation_history_indexer.py`: History indexing interface

### Implementations
- `llm/llm_claude.py`: Claude LLM implementation
- `repo_reader/repo_reader_local.py`: Local filesystem reader
- `repo_reader/repo_reader_workspace.py`: Workspace-aware reader
- `semantic_indexer/semantic_indexer_chromadb.py`: ChromaDB indexer
- `conversation_repository/conversation_repository_json.py`: JSON persistence
- `repo_change_detector/git_change_detector.py`: Git-based change detection

### Feature Modules
- `commands/`: Command classification and tool execution
- `workspace/`: Workspace management
- `metadata/`: Metadata generation and reading
- `utils/`: Utility functions (context building, formatting)

## 11. Debugging Tips

### Enable Debug Logging

Set log level to DEBUG to see detailed execution flow:
```python
# In main.py or via environment variable
logging.getLogger("benedict").setLevel(logging.DEBUG)
```

### Trace Execution Flow

1. Start from `slack_app.py` event handler
2. Follow method calls through `agent.py`
3. Check which implementations are being used
4. Verify optional dependencies are available

### Common Issues

**Issue: LLM not responding**
- Check if `llm` is None in `agent.py`
- Verify API key in environment
- Check `main.py` error handling

**Issue: Repository not found**
- Check workspace creation in `workspace_manager.py`
- Verify repository path in channel mapping
- Check `repo_reader` implementation

**Issue: Semantic search not working**
- Check if `semantic_indexer` is None
- Verify ChromaDB initialization
- Check indexing logs

## 12. Next Steps

After reading this guide:

1. **Start with `main.py`**: Understand the complete system
2. **Read `agent.py`**: Understand core business logic
3. **Explore protocols**: Understand abstractions
4. **Pick an implementation**: See how protocols are implemented
5. **Trace a code path**: Follow a user action through the system
6. **Read feature modules**: Understand specific features

## 13. Additional Resources

- `plans/ARCHITECTURE.md`: High-level architecture overview
- `README.md`: Setup and usage instructions
- `CHANGELOG.md`: Version history and changes
- `docs/`: Feature-specific design documents

## 14. Open Questions

When reading code, if you encounter:

- **Unclear abstractions**: Check the protocol definition
- **Missing implementations**: Look for mocks or graceful degradation
- **Complex logic**: Break it down by following the data flow
- **Unclear dependencies**: Trace from `main.py` composition root
