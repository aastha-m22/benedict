# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

## [0.2.2] - Current

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
