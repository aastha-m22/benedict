# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.6] - 2026-02-08

### Fixed
- Fixed code block truncation and splitting issues in Slack message formatting
- Code blocks are now never split across message chunks or Slack blocks
- Truncation now respects code block boundaries - never truncates inside a code block
- Added code-aware splitting logic that extends to end of code blocks when necessary
- Fixed issue where code blocks would be cut in half, leaving unclosed code fences

## [0.3.5] - 2026-02-08

### Fixed
- Fixed bug where bot wouldn't respond immediately to channel messages without @mentions
- Fixed duplicate responses when @mentioning the bot (message handler now skips messages with bot mentions)
- Fixed threading issue where responses to channel messages weren't properly linked (now uses `conversation_ts` instead of `thread_ts`)

## [0.3.4] - 2026-02-08

### Changed
- Repository source paths are now configurable via `BENEDICT_REPO_SOURCE_DIRS` environment variable
- Format: comma-separated paths, e.g., `BENEDICT_REPO_SOURCE_DIRS=/Users/name/Projects,/opt/repos`
- Defaults to `~/Projects` if not configured
- Error messages now show all tried paths including configured source directories

## [0.3.3] - 2026-02-08

### Added
- Smart message detection - Benedict now responds to messages in channels that appear to be directed at it
- Detects questions, help requests, and messages mentioning "benedict", "agent", or bot-related terms
- Responds to channel messages without requiring @mention when message seems directed at the bot

## [0.3.2] - 2026-02-08

### Fixed
- Fixed ChromaDB metadata error when indexing Slack messages - now filters out `None` values from metadata before indexing
- Messages with missing `thread_ts` or `user` fields now index correctly

## [0.3.1] - 2026-02-08

### Added
- Thread-aware conversation detection - Benedict now responds to messages in threads where it has already participated, without requiring @mention
- Automatic detection of thread context to understand when users are talking to Benedict

## [0.3.0] - 2026-02-08

### Changed
- Removed manual `@agent index slack history` command - indexing now happens automatically in the background
- Slack conversation history indexing is now fully automatic:
  - Indexes from channel start when channel is onboarded
  - Automatically indexes new messages as they arrive via message events
  - Creates embeddings for all messages in ChromaDB for semantic search
- Messages are now indexed with embeddings for semantic search capabilities

### Added
- Automatic background indexing of new Slack messages via message event handler
- Proper embedding generation for Slack messages in semantic indexer
- `index_new_slack_messages()` method for automatic incremental updates

## [0.2.9] - 2026-02-08

### Added
- Automatic Slack conversation history indexing when a channel is onboarded
- Channel history is now indexed from the beginning when `@agent onboard` is run
- Users are notified that conversation history indexing is in progress during onboarding

## [0.2.8] - 2026-02-08

### Changed
- Conversation summarization is now a normal query, not a special command
- When users ask about conversations (e.g., "summarise today's conversations"), the LLM automatically receives conversation history in context
- Removed special command routing for conversation summarization - it's handled naturally by the LLM

## [0.2.7] - 2026-02-08

### Fixed
- Improved command detection for summarize conversations command to handle British spelling ("summarise") and typos
- Command now properly recognizes variations like "summarise todays conversastions"

## [0.2.6] - 2026-02-08

### Added
- Command to gather and summarize today's conversations via `@agent summarize today` or `@agent gather today's conversations`
- Automatic LLM-powered summarization for conversations with 3+ threads or 20+ messages
- Conversation filtering by date (today) and channel
- Support for extracting key topics, decisions, and action items from conversation history

## [0.2.5] - 2026-02-08

### Added
- Slack conversation history indexing via `@agent index slack history` command
- Full implementation of `SlackConversationHistoryIndexer` with Slack API integration
- Support for fetching channel history using `conversations.history` API with pagination
- Support for fetching thread replies using `conversations.replies` API
- Incremental updates for Slack history indexing (only fetches new messages since last index)
- Message filtering to exclude bot messages and system messages
- Conversation history stored as JSON files in workspace `conversation_history/` directory
- Integration with workspace manager and action logger for tracking indexing operations

### Changed
- Updated `create_conversation_history_indexer()` factory to accept `slack_client` parameter
- Enhanced `RepoAgent` to support conversation history indexing via new `conversation_history_indexer` parameter

## [0.2.4] - 2026-02-08

### Changed
- Renamed metadata files from `METADATA` to `.metadata.benedict` for better specificity and to avoid conflicts
- Updated system prompt to include comprehensive documentation on `.metadata.benedict` files
- Enhanced benedict's ability to discover and read `.metadata.benedict` files through the repo_reader interface

### Breaking Changes
- Existing `METADATA` files will no longer be recognized. Regenerate metadata files to create new `.metadata.benedict` files.

## [0.2.3] - 2026-02-07

### Added
- Configurable chunk size via `BENEDICT_CHUNK_SIZE` environment variable (default: 2000 characters)
- Diagnostic logging for chunking statistics showing:
  - Total files indexed
  - Total chunks created
  - Average chunks per file
  - Average file size
  - Top 10 files by chunk count
- Path-based filtering to exclude common build/cache directories from indexing:
  - Virtual environments (`.venv`, `venv`, `env`, etc.)
  - Dependencies (`node_modules`)
  - Build artifacts (`build`, `dist`, `target`)
  - Cache directories (`__pycache__`, `.pytest_cache`, `.mypy_cache`, etc.)
  - Version control directories (`.git`, `.hg`, `.svn`)
  - IDE directories (`.idea`, `.vscode`, `.vs`)
  - And more (see `_filter_code_files` for complete list)

### Changed
- Increased default chunk size from 1000 to 2000 characters for better semantic context
- Improved file filtering to exclude virtual environment and build artifact directories

### Fixed
- Prevented indexing of `.venv` and other virtual environment directories
- Reduced unnecessary chunk generation from third-party dependencies
- Fixed `AttributeError` when accessing `SlackFormatter.MAX_MESSAGE_LENGTH` by adding it as a class attribute

## [0.2.2]

### Added
- Semantic code search using ChromaDB and sentence-transformers
- Workspace management for multi-channel repository access
- Metadata generation and overlays for enhanced context
- Repository change detection (Git-based and file watcher)
- Incremental index updates for changed files only
- Conversation history tracking per thread
- Protocol-based architecture for testability
- Mock implementations for all protocols

### Changed
- Refactored to SOLID principles with dependency injection
- Improved context building with semantic search integration
- Enhanced file filtering for better code indexing

## [0.2.0] - LLM Integration

### Added
- LLM protocol definition with Claude 3.5 Sonnet implementation
- Repository reader protocol with local filesystem implementation
- Context builder that intelligently selects relevant files
- Composition root pattern for dependency management
- Conversation repository pattern for persistence abstraction
- Thread-based conversations with full history tracking

### Changed
- Refactored from monolithic to protocol-based architecture
- Improved error handling and graceful degradation

## [0.1.0] - Initial Release

### Added
- Slack bot with Socket Mode support
- Channel → Repository mapping via `onboard` command
- Status command to show channel mappings
- State persistence across restarts (JSON-based)
- Thread-based conversation handling
- Basic command parsing and routing

## [0.0.1] - Proof of Concept

### Added
- Initial Slack bot infrastructure
- Basic mention handling
- State management

---

## Types of Changes

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes
