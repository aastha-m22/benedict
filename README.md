# Slack Repo Agent

A Slack bot that links channels to repositories and provides intelligent, repo-scoped AI agent conversations.

## Overview

This bot provides:
- ✅ Slack bot responding to @mentions
- ✅ Channel → Repository mapping
- ✅ Persistent state across restarts
- ✅ Thread-based conversations with history
- ✅ LLM integration (Claude 3.5 Sonnet)
- ✅ Semantic code search (ChromaDB + sentence-transformers)
- ✅ Local repository access
- ❌ GitHub API integration (coming in M2)
- ❌ Notion/GDocs access (coming in v2)

## Features

### Commands

1. **Onboard a channel**
   ```
   @benedict onboard repo foo/bar
   ```
   Links the current channel to a repository.

2. **Check status**
   ```
   @benedict status
   ```
   Shows which repository the channel is linked to.

3. **Update the semantic index**
   ```
   @benedict update index
   ```
   Rebuilds the search index for the linked repository. Add `force` for a full reindex.

4. **Ask questions**
   ```
   @benedict what's the architecture?
   ```
   The bot uses semantic search and LLM to provide intelligent answers. There is no method-file command; `.benedict.method.yaml` is not a runtime feature.

## Prerequisites

- Python 3.8 or higher
- A Slack workspace where you can create apps
- Admin access to install apps to the workspace

## Slack App Setup

**📖 See [SLACK_SETUP.md](SLACK_SETUP.md) for complete step-by-step setup instructions.**

Quick summary:
1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps)
2. Enable Socket Mode and create app token (`xapp-...`)
3. Add bot scopes: `chat:write`, `channels:history`, `channels:read`
4. Subscribe to `app_mention` event
5. Install app to workspace and get bot token (`xoxb-...`)
6. Add both tokens to `.env` file

## Installation

### 1. Clone or Download

```bash
git clone <your-repo-url>
cd slack-repo-agent
```

Or download the files directly.

### 2. Install uv (if not already installed)

`uv` is a fast Python package installer and resolver. Install it with:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or using Homebrew (macOS):
```bash
brew install uv
```

### 3. Install Dependencies

**Using Make (recommended):**
```bash
make sync
```

Or:
```bash
make install
```

**Or manually with uv:**
```bash
uv pip install -e .
```

**Using a virtual environment (recommended):**
```bash
make venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
make sync
```

### 4. Configure Environment Variables

Create a `.env` file in the project directory:

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
```

Replace the values with your actual tokens from the Slack App setup (see [SLACK_SETUP.md](SLACK_SETUP.md)).

### 5. Run the Bot

**Using Make:**
```bash
make run
```

**Or manually:**
```bash
python -m benedict.main
```

You should see:
```
✅ Bot is running! Press Ctrl+C to stop.
```

### Quick Start with Make

```bash
# Create virtual environment and install dependencies
make setup
source .venv/bin/activate  # uv creates .venv by default

# Sync dependencies (uv's recommended way)
make sync

# Check dependencies
make deps

# Run the bot
make run
```

## Usage

### 1. Invite the Bot to a Channel

In any Slack channel, type:
```
/invite @benedict
```

### 2. Onboard the Channel

Tell the bot which repository this channel is about:
```
@benedict onboard repo foo/bar
```

The bot will confirm:
```
✅ Onboarded! This channel is now linked to `foo/bar`.
I'll remember this repo for all our conversations here.
```

### 3. Check Status

```
@benedict status
```

Response:
```
📊 Channel Status
━━━━━━━━━━━━━━━
📺 Channel: #proj-foo
🔗 Repository: foo/bar
⏰ Onboarded: 2026-02-01 20:30 UTC
👤 By: @michael
```

### 4. Ask Questions

```
@benedict what files handle authentication?
```

The bot will:
1. Use semantic search to find relevant files
2. Build context from repository code
3. Generate intelligent responses using Claude LLM
4. Maintain conversation history in the thread

## Testing Checklist

Use this checklist to verify everything works:

### Basic Setup
- [ ] Completed Slack app setup (see [SLACK_SETUP.md](SLACK_SETUP.md))
- [ ] Created `.env` file with tokens
- [ ] Installed Python dependencies (`make sync` or `make install`)
- [ ] Started bot successfully (`make run`)

### Single Channel Test
- [ ] Created test channel `#test-foo`
- [ ] Invited bot to channel
- [ ] Tried talking without onboarding (should get prompt)
- [ ] Onboarded: `@benedict onboard repo foo/bar`
- [ ] Got success confirmation
- [ ] Checked status: `@benedict status`
- [ ] Asked question: `@benedict what's the code structure?`
- [ ] Got stub response mentioning the repo

### Multiple Channels Test
- [ ] Created second channel `#test-bar`
- [ ] Invited bot to second channel
- [ ] Onboarded: `@benedict onboard repo baz/qux`
- [ ] Verified status shows different repo
- [ ] Went back to first channel
- [ ] Verified status still shows `foo/bar`

### Persistence Test
- [ ] Stopped bot (Ctrl+C)
- [ ] Verified `state.json` file exists
- [ ] Checked `state.json` contains channel mappings
- [ ] Restarted bot
- [ ] Checked status in channel (should still show repo)

### Edge Cases
- [ ] Onboarded same channel twice (should update)
- [ ] Tried invalid repo format (should show error)
- [ ] Tried status in non-onboarded channel (should prompt)

## File Structure

```
slack-repo-agent/
├── src/
│   └── benedict/                    # Main package
│       ├── __init__.py
│       ├── main.py                  # Entry point (composition root)
│       ├── agent.py                 # Main agent logic
│       ├── slack_app.py             # Slack Bolt app configuration
│       ├── models/                  # Domain models
│       │   ├── __init__.py
│       │   └── conversation.py      # Conversation and Message models
│       ├── protocols/               # Protocol definitions (interfaces)
│       │   ├── __init__.py
│       │   ├── llm.py               # LLM protocol
│       │   ├── repo_reader.py       # Repository reader protocol
│       │   ├── semantic_indexer.py  # Semantic search protocol
│       │   └── conversation_repository.py  # Conversation repository protocol
│       ├── llm/                     # LLM implementations
│       │   ├── __init__.py
│       │   ├── llm_claude.py        # Claude implementation
│       │   └── llm_mock.py          # Mock implementation
│       ├── repo_reader/              # Repository reader implementations
│       │   ├── __init__.py
│       │   ├── repo_reader_local.py # Local filesystem implementation
│       │   └── repo_reader_mock.py  # Mock implementation
│       ├── semantic_indexer/         # Semantic indexer implementations
│       │   ├── __init__.py
│       │   ├── semantic_indexer_chromadb.py  # ChromaDB implementation
│       │   └── semantic_indexer_mock.py     # Mock implementation
│       ├── conversation_repository/   # Conversation repository implementations
│       │   ├── __init__.py
│       │   ├── conversation_repository_json.py  # JSON implementation
│       │   └── conversation_repository_mock.py  # Mock implementation
│       └── utils/                    # Utility functions
│           ├── __init__.py
│           └── context.py           # Context building utilities
├── Makefile                          # Development commands
├── pyproject.toml                    # Python project configuration and dependencies
├── README.md                  # This file
├── SLACK_SETUP.md             # Slack app setup guide
├── ARCHITECTURE.md            # Architecture documentation
├── CLEANUP_SUMMARY.md         # Cleanup documentation
├── .env                       # Your tokens (DO NOT COMMIT)
├── .gitignore                 # Git ignore rules
└── state.json                 # Runtime state (created automatically)
```

## State File

The bot stores channel mappings in `state.json`:

```json
{
  "channels": {
    "C12345ABC": {
      "repo": "foo/bar",
      "onboarded_at": "2026-02-01T20:30:00Z",
      "onboarded_by": "U123456"
    }
  }
}
```

This file is created automatically and persists across restarts.

## Troubleshooting

### Bot doesn't respond

**Check:**
1. Is the bot running? (`python -m benedict.main` or `benedict` should show "Bot is running!")
2. Is the bot invited to the channel? (`/invite @benedict`)
3. Are you @mentioning the bot? (Just typing won't work)
4. Check the terminal for error messages

### "Missing SLACK_BOT_TOKEN" or "Missing SLACK_APP_TOKEN" error

**Fix:**
See [SLACK_SETUP.md](SLACK_SETUP.md) for detailed troubleshooting steps.

### Bot responds but says "This channel hasn't been onboarded yet"

**Fix:**
1. Run the onboard command: `@benedict onboard repo your-org/your-repo`
2. Make sure you're using the format `org/repo` (e.g., `acme/widget`)

### State file gets corrupted

**Fix:**
1. Stop the bot
2. Delete `state.json`
3. Restart the bot (it will create a new empty state)
4. Re-onboard your channels

### Bot responds in channel instead of thread

This is expected behavior in v0. The bot replies in-thread to keep conversations organized.

## Development

### Makefile Commands

The project includes a Makefile for common tasks:

```bash
make help      # Show all available commands
make sync      # Sync dependencies with uv (recommended)
make install   # Install dependencies with uv
make deps      # Check if dependencies are installed
make run       # Run the bot
make clean     # Remove cache files
make lint      # Run linters (if installed)
make format    # Format code (if black is installed)
```

### Running in Development

```bash
# Activate virtual environment (uv creates .venv by default)
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Run with debug logging
make run
# or
python -m benedict.main
# or (after installation)
benedict
```

### Project Structure

- **State Management** (`load_state`, `save_state`, `get_channel_repo`, `set_channel_repo`)
  - Handles JSON persistence
  - Thread-safe for single-process use

- **Command Detection** (`is_onboard_command`, `is_status_command`, `extract_repo_name`)
  - Simple pattern matching
  - Flexible parsing for natural language

- **Event Handlers** (`handle_app_mention`, `handle_onboard`, `handle_status`, `handle_conversation`)
  - Routes @mentions to appropriate handlers
  - Always replies in thread

## Roadmap

### Current Features ✅
- Slack connection via Socket Mode
- Channel → Repo mapping
- Onboard & status commands
- LLM integration (Claude 3.5 Sonnet)
- Semantic code search (ChromaDB + sentence-transformers)
- Conversation history tracking
- Local repository access

### Next (M2)
- GitHub API: read repo files remotely
- Enhanced code understanding

### v2 (Future)
- Notion integration
- Google Docs access
- Cursor session logs
- Multi-repo context

### v3 (Advanced)
- Agent-to-agent communication
- RAG/vector search over codebase
- Proactive suggestions
- Code review automation

## Contributing

This is a proof-of-concept. Contributions welcome!

## License

MIT License - feel free to use and modify.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review Slack app configuration
3. Check terminal logs for error messages
4. Verify `.env` file is correctly formatted

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for current architecture overview.

See [`plans/slack-agent-architecture.md`](plans/slack-agent-architecture.md) for detailed architecture documentation.

