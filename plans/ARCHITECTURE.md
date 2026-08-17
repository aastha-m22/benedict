# Architecture Overview

## Entry Point

**`src/benedict/main.py`** is the application entry point. Run with:
```bash
python -m benedict.main
```

## File Structure

### Core Application
- **`main.py`** - Composition root (wires all dependencies together)
- **`slack_app.py`** - Slack Bolt app configuration and event handlers
- **`agent.py`** - Main agent logic (handles commands and conversations)

### Domain Models
- **`models/conversation.py`** - Conversation and Message models, ConversationManager

### Protocols (Interfaces)
- **`protocols/llm.py`** - LLM protocol definition
- **`protocols/repo_reader.py`** - Repository reader protocol
- **`protocols/semantic_indexer.py`** - Semantic code search protocol
- **`protocols/conversation_repository.py`** - Conversation persistence protocol
- **`protocols/repo_change_detector.py`** - Repository change detection protocol
- **`protocols/conversation_history_indexer.py`** - Conversation history indexing protocol

### Implementations

#### LLM
- **`llm/llm_claude.py`** - Claude 3.5 Sonnet implementation
- **`llm/llm_mock.py`** - Mock LLM for testing

#### Repository Reader
- **`repo_reader/repo_reader_local.py`** - Local filesystem implementation
- **`repo_reader/repo_reader_workspace.py`** - Workspace-aware repository reader
- **`repo_reader/repo_reader_workspace_adapter.py`** - Adapter for workspace reader
- **`repo_reader/repo_reader_mock.py`** - Mock repository reader for testing

#### Semantic Indexer
- **`semantic_indexer/semantic_indexer_chromadb.py`** - ChromaDB + sentence-transformers implementation
- **`semantic_indexer/semantic_indexer_mock.py`** - Mock semantic indexer for testing

#### Conversation Repository
- **`conversation_repository/conversation_repository_json.py`** - JSON file persistence
- **`conversation_repository/conversation_repository_mock.py`** - In-memory mock for testing

#### Repository Change Detection
- **`repo_change_detector/git_change_detector.py`** - Git-based change detection

#### Conversation History Indexing
- **`indexers/slack_history_indexer.py`** - Slack conversation history indexer

### Workspace System
- **`workspace/workspace_manager.py`** - Manages workspace lifecycle and resources
- **`workspace/action_logger.py`** - Logs workspace actions and operations

### Metadata System
- **`metadata/metadata_generator.py`** - Generates METADATA files for directories
- **`metadata/metadata_reader.py`** - Reads METADATA files
- **`metadata/content_handlers.py`** - Content-specific handlers for metadata generation

Benedict does not have a method-file subsystem. A `.benedict.method.yaml` in a repository is an ordinary file, not a runtime feature.

### Utilities
- **`utils/context.py`** - Context building functions (uses semantic search when available)

## Dependency Flow

```
main.py (entry point)
  ├─> Creates: LLM (optional)
  ├─> Creates: RepoReader (optional)
  ├─> Creates: WorkspaceManager (required)
  ├─> Creates: MetadataGenerator (for semantic indexer)
  ├─> Creates: RepoChangeDetector (for semantic indexer)
  ├─> Creates: SemanticIndexer (optional, with MetadataGenerator and RepoChangeDetector)
  ├─> Creates: ConversationRepository (required)
  └─> Creates: RepoAgent (with all dependencies)
       ├─> Creates: ConversationManager (with ConversationRepository)
       └─> Creates: MetadataGenerator (if workspace_manager available)
            └─> Creates: SlackApp (with RepoAgent)
                 └─> Starts: SocketModeHandler
```

## Component Interactions

### Workspace System
- Each Slack channel gets its own workspace directory
- Repositories are symlinked (or copied) into workspace on onboarding
- Workspace paths are used for:
  - Repository access (via WorkspaceRepoReader)
  - Metadata generation and reading
  - Action logging
  - Conversation history indexing

### Context Building Flow
1. User asks question in Slack thread
2. `RepoAgent.handle_conversation()` is called
3. Gets workspace path and creates ActionLogger
4. Creates WorkspaceRepoReader adapter (if workspace available)
5. Calls `build_context()` which:
   - Includes recent actions from action log
   - Includes repository metadata (if available)
   - Includes README.md
   - Uses semantic search (if available) or keyword matching
   - Reads relevant files via RepoReader

### Semantic Indexing Flow
1. On first query, repository is indexed if not already indexed
2. Uses RepoChangeDetector to detect changes for incremental updates
3. MetadataGenerator creates METADATA files for directories
4. Files are chunked and embedded into ChromaDB
5. Search queries use semantic similarity to find relevant files

### Conversation Management
- Each Slack thread has a unique `thread_ts` identifier
- Conversations are persisted via ConversationRepository
- ConversationManager handles conversation lifecycle
- Message history is maintained for context in LLM calls

## Design Principles

- **SOLID**: All components follow SOLID principles
- **Dependency Injection**: Dependencies injected, not created internally
- **Protocol-Based**: Uses Python Protocols for interfaces
- **Root Composition**: All concrete classes instantiated in `main.py`
- **Graceful Degradation**: Works even if optional components unavailable
- **Workspace Isolation**: Each channel has isolated workspace for resources
- **Incremental Updates**: Change detection enables efficient index updates

## Configuration

Environment variables:
- `SLACK_BOT_TOKEN` - Slack bot token (required)
- `SLACK_APP_TOKEN` - Slack app token (required)
- `BENEDICT_DATA_DIR` - Data directory (default: repo root)
- `BENEDICT_WORKSPACES_DIR` - Workspaces directory (default: `{data_dir}/workspaces`)
- `BENEDICT_WORKSPACE_COPY_MODE` - "symlink" or "copy" (default: "symlink")
- `BENEDICT_CHROMA_DB_DIR` - ChromaDB directory (default: `{data_dir}/.chroma_db`)
- `BENEDICT_STATE_FILE` - State file path (default: `{data_dir}/state.json`)
- `BENEDICT_ENV_FILE` - .env file path (default: repo root `.env`)

## Commands

- `@agent onboard repo <repo>` - Link channel to repository
- `@agent offboard` - Unlink the channel from its repository
- `@agent status` - Show channel status and repository info
- `@agent update index` - Update semantic index (incremental)
- `@agent update index force` - Force full reindex
- `@agent <question>` - Ask question about repository
