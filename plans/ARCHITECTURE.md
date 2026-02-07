# Architecture Overview

## Entry Point

**`main.py`** is the application entry point. Run with:
```bash
python main.py
```

## File Structure

### Core Application
- **`main.py`** - Composition root (wires all dependencies together)
- **`slack_app.py`** - Slack Bolt app configuration and event handlers
- **`agent.py`** - Main agent logic (handles commands and conversations)

### Domain Models
- **`conversation.py`** - Conversation and Message models, ConversationManager

### Protocols (Interfaces)
- **`llm.py`** - LLM protocol definition
- **`repo_reader.py`** - Repository reader protocol
- **`semantic_indexer.py`** - Semantic code search protocol
- **`conversation_repository.py`** - Conversation persistence protocol

### Implementations

#### LLM
- **`llm_claude.py`** - Claude 3.5 Sonnet implementation
- **`llm_mock.py`** - Mock LLM for testing

#### Repository Reader
- **`repo_reader_local.py`** - Local filesystem implementation
- **`repo_reader_mock.py`** - Mock repository reader for testing

#### Semantic Indexer
- **`semantic_indexer_chromadb.py`** - ChromaDB + sentence-transformers implementation
- **`semantic_indexer_mock.py`** - Mock semantic indexer for testing

#### Conversation Repository
- **`conversation_repository_json.py`** - JSON file persistence
- **`conversation_repository_mock.py`** - In-memory mock for testing

### Utilities
- **`context.py`** - Context building functions (uses semantic search when available)

## Dependency Flow

```
main.py (entry point)
  ├─> Creates: LLM, RepoReader, SemanticIndexer, ConversationRepository
  └─> Creates: RepoAgent (with all dependencies)
       └─> Creates: ConversationManager (with ConversationRepository)
            └─> Creates: SlackApp (with RepoAgent)
```

## Design Principles

- **SOLID**: All components follow SOLID principles
- **Dependency Injection**: Dependencies injected, not created internally
- **Protocol-Based**: Uses Python Protocols for interfaces
- **Root Composition**: All concrete classes instantiated in `main.py`
- **Graceful Degradation**: Works even if optional components unavailable

## Deprecated Files

- **`app.py`** - Old v0 skeleton (superseded by refactored architecture)
