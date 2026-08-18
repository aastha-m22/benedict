# Benedict

A Slack bot that links a channel to a local git repository and answers questions about that repo with Claude, semantic search, and project metadata files.

Use Benedict when a Slack channel is the working surface for a codebase and you want an agent that already knows the repo and the thread history.

## Current status

Benedict is a working Slack Socket Mode bot (Python 3.10+, version 0.5.0). It is not a remote GitHub-hosted reader. Onboarding resolves a **local** checkout, then isolates it per channel in a workspace.

**In production use today:**

- Slack `@mentions` and thread replies, with conversation history persisted in `state.json`
- Channel → repository mapping (onboard, offboard, status)
- Claude 3.5 Sonnet (override with `ANTHROPIC_MODEL`) plus a stub mode if the API key is missing
- Semantic code search with ChromaDB and sentence-transformers; git-based incremental reindex
- Per-channel workspaces (symlink or copy of the local repo)
- `.metadata.benedict` directory summaries that boost search
- Architect channel for cross-project questions
- Slack conversation history indexing into the workspace
- GitHub CLI (`gh`) during conversations, when `gh` is installed and authenticated on the host
- MCP server (`benedict-mcp`) so Cursor and Claude Code can query onboarded projects

**Not implemented:** GitHub API as a `RepoReader`, Notion, Google Docs, Cursor session logs, and a background git/file watcher process. Changelog entries for a watcher describe work that is no longer in the tree. `GitChangeDetector` remains and is used for incremental indexing.

## How it works

1. You invite Benedict to a Slack channel and onboard a local repository.
2. Benedict creates a workspace for that channel and indexes the repo on first use.
3. A mention or a reply in an existing Benedict thread builds context (README, metadata, semantic hits, recent actions) and asks Claude.
4. Explicit commands (onboard, status, index) skip the general Q&A path and run dedicated handlers.

```
Slack event → slack_app.py → RepoAgent
  → workspace + semantic index + metadata context
  → Claude (optional tools) → formatted Slack reply
```

## Commands

Mention `@benedict` (or `@agent`) in the channel.

| Command | What it does |
| --- | --- |
| `onboard repo org/repo` | Links the channel to a local checkout. Also accepts `this channel is for org/repo` or an absolute path. |
| `offboard` | Removes the channel mapping. |
| `status` | Shows the linked repo and when it was onboarded. |
| `update index` | Incremental reindex. Add `force` for a full rebuild. |
| `onboard architect` | Marks the channel as the architect channel for cross-project questions. |
| Any other question | Repo-scoped conversation with search and LLM. |

There is no method-file command. A `.benedict.method.yaml` in a repository is an ordinary file, not a runtime feature.

### Onboard a channel

```
@benedict onboard repo acme/widget
```

Benedict looks for the checkout in this order:

1. The text as an absolute path
2. Directories in `BENEDICT_REPO_SOURCE_DIRS` (comma-separated), as `org/repo` and as the repo name alone
3. `~/Projects/<repo>` if `BENEDICT_REPO_SOURCE_DIRS` is unset
4. The current working directory

It does not clone from GitHub. The directory must already exist on the machine that runs the bot.

### Ask a question

```
@benedict what files handle authentication?
```

Benedict searches the index, reads relevant files from the workspace, and replies in the thread. Later replies in that thread are treated as continuation even without a mention, once Benedict has already participated.

### GitHub CLI

If GitHub CLI is installed and authenticated on the host, Benedict can run `gh` in the onboarded workspace repo (list PRs, inspect issues, and similar). Mutating GitHub (create, merge, close, comment) is supposed to be confirmed with you first. This is not a general shell.

## Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A Slack workspace where you can create apps
- An Anthropic API key for LLM answers (`ANTHROPIC_API_KEY`)
- Optional: [GitHub CLI](https://cli.github.com/) (`gh`) for GitHub tools
- Optional: local git checkouts of the repos you want to onboard

## Slack app setup

See [docs/SLACK_SETUP.md](docs/SLACK_SETUP.md) for the full walkthrough.

Short version:

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps).
2. Enable Socket Mode and create an app token (`xapp-...`).
3. Add bot scopes: `chat:write`, `channels:history`, `channels:read`.
4. Subscribe to `app_mention` (and `message.channels` / `message.groups` if you want thread replies without a mention).
5. Install the app and copy the bot token (`xoxb-...`).
6. Put both tokens in `.env`.

## Installation

```bash
git clone https://github.com/mkarots/benedict.git
cd benedict
```

Install [uv](https://docs.astral.sh/uv/) if needed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: brew install uv
```

Then:

```bash
make setup
source .venv/bin/activate
make sync-dev
```

Without Make:

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Configuration

Create `.env` in the project directory (or set `BENEDICT_ENV_FILE`):

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
ANTHROPIC_API_KEY=your-anthropic-api-key
# Optional
# ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
# BENEDICT_REPO_SOURCE_DIRS=/Users/you/Projects,/opt/repos
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `SLACK_BOT_TOKEN` | required | Slack bot token |
| `SLACK_APP_TOKEN` | required | Slack Socket Mode token |
| `ANTHROPIC_API_KEY` | optional | Claude. Without it, Benedict runs in stub mode. |
| `ANTHROPIC_MODEL` | `claude-3-5-sonnet-20241022` | Claude model id |
| `BENEDICT_DATA_DIR` | repo root | Root for state, workspaces, and ChromaDB |
| `BENEDICT_WORKSPACES_DIR` | `{data_dir}/workspaces` | Per-channel workspaces |
| `BENEDICT_WORKSPACE_COPY_MODE` | `symlink` | `symlink` or `copy` |
| `BENEDICT_CHROMA_DB_DIR` | `{data_dir}/.chroma_db` | Vector index |
| `BENEDICT_STATE_FILE` | `{data_dir}/state.json` | Channel mappings and conversations |
| `BENEDICT_ENV_FILE` | `{repo}/.env` | dotenv path |
| `BENEDICT_REPO_SOURCE_DIRS` | `~/Projects` | Comma-separated roots used during onboard |
| `BENEDICT_CHUNK_SIZE` | `2000` | Index chunk size in characters |
| `BENEDICT_METADATA_FILE` | `.metadata.benedict` | Override metadata file name/path |

## Run

```bash
make run
```

Or:

```bash
python -m benedict.main
# after install: benedict
```

You should see: `Bot is running! Press Ctrl+C to stop.`

### MCP server (Cursor / Claude Code)

After a channel is onboarded, the same data can be queried from an IDE without Slack running:

```bash
benedict-mcp
```

Or `make mcp` / `python -m benedict.mcp`. Setup is in [docs/MCP.md](docs/MCP.md). Point `BENEDICT_DATA_DIR` at the directory the Slack bot uses.

## Usage

1. Invite the bot: `/invite @benedict`
2. Onboard: `@benedict onboard repo acme/widget`
3. Confirm: `@benedict status`
4. Ask: `@benedict what's the architecture?`

## State and workspaces

Channel mappings and thread conversations live in `state.json`:

```json
{
  "channels": {
    "C12345ABC": {
      "repo": "acme/widget",
      "onboarded_at": "2026-02-01T20:30:00Z",
      "onboarded_by": "U123456"
    }
  },
  "conversations": {},
  "architect": {}
}
```

Each onboarded channel also gets a directory under `workspaces/<channel_id>/` containing a symlink (or copy) of the repo plus action logs and indexed Slack history. `state.json` and `.chroma_db/` are gitignored.

## Project layout

```
src/benedict/
  main.py                 # Composition root
  slack_app.py            # Slack Bolt handlers
  agent.py                # Commands and conversation loop
  architect/              # Cross-project architect prompts
  commands/               # Command classifier and LLM tools
  conversation_repository/
  indexers/               # Slack history indexer
  llm/                    # Claude + mock
  metadata/               # .metadata.benedict generate/read
  models/                 # Conversation models
  protocols/              # Interfaces and factories
  repo_change_detector/   # GitChangeDetector
  repo_reader/            # Local and workspace readers
  semantic_indexer/       # ChromaDB indexer
  utils/                  # Context builder and Slack formatting
  workspace/              # Per-channel workspaces
docs/                     # Setup and design notes
plans/                    # Architecture and milestone docs
tests/unit/               # Unit tests
```

## Development

```bash
make help       # List targets
make sync-dev   # Install runtime + dev dependencies
make test       # pytest
make format     # black + ruff
make check      # format + test
make run        # Start the bot
```

The composition root is `src/benedict/main.py`. Concrete classes are wired there and injected into `RepoAgent`. Optional pieces (LLM, indexer, Slack history) log a warning and continue if they fail to start.

## Troubleshooting

**Bot does not respond.** Confirm the process is running, the bot is in the channel, and you @mentioned it (or replied in a thread Benedict already joined). Check the terminal log.

**Missing `SLACK_BOT_TOKEN` or `SLACK_APP_TOKEN`.** See [docs/SLACK_SETUP.md](docs/SLACK_SETUP.md).

**Channel is not onboarded.** Run `@benedict onboard repo org/repo` against a directory that exists locally.

**Repository not found.** Set `BENEDICT_REPO_SOURCE_DIRS` to the parent of your checkouts, or pass an absolute path in the onboard command.

**LLM answers are stubs.** Set `ANTHROPIC_API_KEY`. Without it, Benedict acknowledges the repo but does not call Claude.

**GitHub tool fails.** Install `gh` on the host and run `gh auth login`. Benedict does not ship a GitHub token of its own.

**Corrupt state.** Stop the bot, delete `state.json`, restart, and re-onboard channels. Conversations in that file are lost.

## Roadmap

Shipped beyond the original v0/M1 plan: semantic search, workspaces, metadata, architect channel, Slack history indexing, and GitHub CLI during chat.

Still open:

- Remote GitHub `RepoReader` (original M2) so onboarding does not require a local checkout
- External knowledge sources (Notion, Google Docs)
- Stronger test coverage for `agent.py` and command routing
- Open-source packaging (LICENSE, CI, SECURITY.md). See [docs/OPEN_SOURCE_GUIDE_INDEX.md](docs/OPEN_SOURCE_GUIDE_INDEX.md).

## Documentation

| Doc | Use it for |
| --- | --- |
| [docs/SLACK_SETUP.md](docs/SLACK_SETUP.md) | Slack app configuration |
| [docs/CODE_READING_GUIDE.md](docs/CODE_READING_GUIDE.md) | How to read the codebase |
| [plans/ARCHITECTURE.md](plans/ARCHITECTURE.md) | Current architecture overview |
| [plans/MILESTONE_STATUS.md](plans/MILESTONE_STATUS.md) | Milestone tracker (some items are stale; trust this README and CHANGELOG first) |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

## License

MIT License. A `LICENSE` file is not yet in the repository.
