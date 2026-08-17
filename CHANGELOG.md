# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.20] - 2026-08-17

### Changed
- **README**: Rewrote the project README to match the current system. It now describes workspaces, method and metadata files, architect channel, semantic indexing, GitHub CLI, configuration, and the real command surface. Removed stale v0 stub checklists, broken root doc links, and the claim that GitHub API integration was the next unstarted milestone without mentioning what already shipped.

### Fixed
- Package `__version__` in `src/benedict/__init__.py` now matches `pyproject.toml`.

## [0.3.17] - 2026-04-28

### Removed
- **`FileWatcherDetector`**: Removed unused mtime-based change detector. It was wired into the `create_repo_change_detector` factory under `detector_type="file_watcher"` but never instantiated at runtime — the `"auto"` branch always returned `GitChangeDetector`. Deleted `src/benedict/repo_change_detector/file_watcher_detector.py`, removed exports from `repo_change_detector/__init__.py`, simplified the factory to only support `"git"`, and updated `main.py` to pass `detector_type="git"` explicitly.

### Changed
- Updated `docs/FILE_AND_GIT_WATCHING.md` and `plans/ARCHITECTURE.md` to reflect that `GitChangeDetector` is now the only `RepoChangeDetector` implementation.

## [0.3.16] - 2026-03-13

### Added
- **Documentation**: Added `docs/FILE_AND_GIT_WATCHING.md` describing how file watching, git watching, and change detection work in Benedict.

## [0.3.15] - 2026-02-09

### Changed
- **Disabled documentation file detection**: The automatic detection and notification of new .md files has been disabled as it was making Slack channels too noisy. Commit detection and notifications remain active.

## [0.3.14] - 2026-02-09

### Fixed
- **Critical Bug Fixes in Slack Formatter:**
  - Fixed placeholder collision vulnerability (Bug #1): Replaced simple numeric placeholders with UUID-based placeholders to prevent collisions with actual code content
  - Fixed infinite loop in `split_message()` (Bug #5): Added progress check and maximum iteration limit to prevent hangs
  - Fixed unsafe string replacement (Bug #3): Replaced `str.replace()` with position-based removal to avoid substring collisions
  - Fixed unclosed code blocks in truncation (Bug #6): Added code block balance verification before truncating
  - Fixed heading detection in code blocks (Bug #4): Headings inside code blocks are now correctly excluded from section splitting
  - Fixed language identifier regex (Bug #2): Now supports language identifiers with hyphens, dots, plus signs, and hash (e.g., `python-3`, `c++`, `c#`, `tsx.js`)
  - Fixed Mermaid/code block overlap (Bug #7): Mermaid blocks are now excluded from code block extraction using negative lookahead
  - Fixed field truncation issue (Bug #8): Field chunks are now used directly instead of being truncated again
- **Edge Case Improvements:**
  - Added handling for very long single-line code blocks: splits at whitespace/punctuation boundaries
  - Added URL length validation for Mermaid rendering: prevents extremely long URLs (>2000 chars)
- **Code Quality:**
  - Extracted magic numbers to named constants: `PARAGRAPH_SEARCH_WINDOW`, `NEWLINE_SEARCH_WINDOW`, `TRUNCATION_THRESHOLD_RATIO`, `CODE_BLOCK_BUFFER`, `MAX_ITERATIONS_SPLIT`
  - Improved error handling and logging throughout the formatter

## [0.3.13] - 2026-02-08

### Added
- Git file watcher that monitors all onboarded repositories for new commits and new .md files
- Background service that periodically checks repositories and sends notifications to Slack channels
- Watcher state persistence to track last checked commit time per repository
- Configurable check interval via `BENEDICT_WATCHER_INTERVAL` environment variable (default: 300 seconds)
- Automatic detection of new commits with file change details (added, modified, deleted files)
- Automatic detection of new documentation files (.md files) in repositories
- Graceful shutdown handling for the watcher service
- Git file watcher now saves git patches to files in `.benedict/patches/` directory
- LLM-based change analysis that understands what changed in commits
- Automatic roadmap linking: changes are analyzed and linked to roadmap items
- Semantic search integration to find related roadmap items based on changed files
- Comprehensive change summaries that connect code changes to project roadmap
- Roadmap file detection (ROADMAP.md, roadmap.md, docs/ROADMAP.md)
- Change analysis includes: summary of changes, roadmap relationships, and affected roadmap items

## [0.3.12] - 2026-02-08

### Added
- Automatic creation of default `.benedict.method.yaml` file when onboarding empty directories
- Method file is automatically created during onboarding if directory is empty or method file doesn't exist
- Helper method `_create_default_method_data()` to generate default method file structure
- Helper method `_is_directory_empty()` to detect empty directories (ignoring system files like .git, .venv, etc.)

### Fixed
- Fixed method file creation failing when repository directory doesn't exist
- `MethodWriter.write_method()` now creates parent directories before writing the method file
- Prevents `FileNotFoundError` when creating method files in new repository paths
- Improved error handling: method file write failures now raise exceptions instead of silently returning
- Added file creation verification to ensure method files are actually written
- Enhanced logging: success messages now use INFO level instead of DEBUG for better visibility

## [0.3.11] - 2026-02-08

### Added
- Comprehensive features overview document (`docs/FEATURES_OVERVIEW.md`) documenting all implemented features
- Complete feature inventory covering commands, LLM integration, semantic search, method files, metadata, and more
- Usage examples and integration points documentation

## [0.3.10] - 2026-02-08

### Added
- Code reading guide (`docs/CODE_READING_GUIDE.md`) explaining how to read and understand the codebase
- Comprehensive documentation covering architecture patterns, reading strategies, and debugging tips
- Guiding questions for engineers to navigate the codebase effectively

## [0.3.9] - 2026-02-08

### Fixed
- Prevented metadata reader from scanning `.metadata.benedict` files in virtual environments and excluded directories
- Added path filtering to exclude common build/cache directories (`.venv`, `venv`, `node_modules`, `site-packages`, etc.) from metadata scanning
- Reduced unnecessary debug log noise from reading metadata files in third-party package directories

## [0.3.8] - 2026-02-08

### Added
- Method file support for reading and updating `.benedict.method.yaml` files
- `MethodReader` class to read and parse method files with project phases, concerns, and rules
- `MethodWriter` class to write and update method files
- Environment variable `BENEDICT_METHOD_FILE` to specify custom method file path
- Automatic detection of missing method files with proactive guidance
- Method file creation handler that generates complete method files with all concern definitions and sequence phases
- Integration of method file information into context building for better project awareness
- System prompt prioritization: method file creation is marked as FIRST PRIORITY when missing
- Method file update detection and confirmation flow for phase, iteration, step, and concern updates
- Support for parsing method file update requests (e.g., "set phase to sprint", "set documentation to complete")

### Changed
- Method file information is now included in repository context when available
- System prompt now instructs LLM to prioritize method file creation when missing (marked as CRITICAL)

## [0.3.7] - 2026-02-08

### Added
- Mermaid diagram rendering support for Slack messages
- Automatic detection and rendering of Mermaid code blocks to images using mermaid.ink API
- Mermaid diagrams are rendered as image blocks in Block Kit messages
- Fallback to code block display if image rendering fails
- Mermaid source code is included below rendered images for editing/copying

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
