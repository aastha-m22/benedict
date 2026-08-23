# Benedict MCP Server

One-sentence summary:
Benedict exposes its onboarded project memory over MCP so Cursor, Claude Code, and other MCP clients can query it without going through Slack.

## 1. Overview

**What:**
A stdio MCP server (`benedict-mcp`) that reads the same `state.json`, workspaces, metadata, and semantic index as the Slack bot.

**Why:**
You already talk to Benedict in Slack. When you are in Cursor or Claude Code, you still want indexed code, metadata, and project Q&A. MCP is the protocol those tools already speak.

**When to use:**
- Cursor or Claude Code needs Benedict's project memory
- You want repo-scoped answers from the IDE without a second Slack thread
- You do not want a second Notion/GitHub-style integration inside the IDE

The Slack bot does **not** need to be running. The MCP process must see the same data directory the bot uses.

## 2. Non-Goals

Not responsible for:

- Starting Slack or posting to Slack
- Writing metadata or GitHub state
- Sharing Slack conversation history
- Benedict calling other MCP servers (client mode)

Out of scope: a custom agent-to-agent protocol. This is MCP tools only.

## 3. Tools

| Tool | Purpose |
|------|---------|
| `list_projects` | Onboarded Slack channel → repo mappings |
| `get_repository_summary` | Root `.metadata.benedict` summary and purpose |
| `search_code` | Semantic search over Benedict's index |
| `get_recent_actions` | Recent workspace action log entries |
| `ask_benedict` | Question answered from repo context (no Slack history) |

If `repo` is omitted, the server uses the process working directory when it matches an onboarded clone. If several projects are onboarded and cwd does not match, call `list_projects` and pass `repo`.

`ask_benedict` and `list_projects` write a run to `$BENEDICT_DATA_DIR/runs.jsonl`. If the Slack bot is running, the operator console at `http://127.0.0.1:8765` reloads that file and shows the MCP call in Activity. `search_code`, `get_repository_summary`, and `get_recent_actions` are not recorded yet.

## 4. Configuration

Point the MCP process at the Slack bot's data:

```bash
BENEDICT_DATA_DIR=/path/to/benedict-data
```

Optional (same as the Slack bot):

- `BENEDICT_STATE_FILE`
- `BENEDICT_WORKSPACES_DIR`
- `BENEDICT_CHROMA_DB_DIR`
- `BENEDICT_ENV_FILE`
- `ANTHROPIC_API_KEY` (required for `ask_benedict`)

If you run from an editable checkout of this repo, the default data dir is the repo root (same as `make run`).

Run by hand:

```bash
benedict-mcp
```

Or:

```bash
python -m benedict.mcp
```

The process speaks MCP on stdin/stdout. Logs go to stderr.

## 5. Cursor

In Cursor MCP settings, add:

```json
{
  "mcpServers": {
    "benedict": {
      "command": "benedict-mcp",
      "env": {
        "BENEDICT_DATA_DIR": "/absolute/path/to/benedict-data",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

If `benedict-mcp` is not on `PATH`, use the venv binary:

```json
{
  "mcpServers": {
    "benedict": {
      "command": "/absolute/path/to/benedict/.venv/bin/benedict-mcp",
      "env": {
        "BENEDICT_DATA_DIR": "/absolute/path/to/benedict-data"
      }
    }
  }
}
```

From this checkout with uv:

```json
{
  "mcpServers": {
    "benedict": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/benedict", "benedict-mcp"],
      "env": {
        "BENEDICT_DATA_DIR": "/absolute/path/to/benedict-data"
      }
    }
  }
}
```

## 6. Claude Code

```bash
claude mcp add benedict -- benedict-mcp
```

Set `BENEDICT_DATA_DIR` in the environment Claude Code uses, or:

```bash
claude mcp add benedict --env BENEDICT_DATA_DIR=/absolute/path/to/benedict-data -- benedict-mcp
```

## 7. Happy Path

Step 1: Onboard a repo in Slack (`@benedict onboard repo org/name`).
Step 2: Add the MCP server in Cursor or Claude Code.
Step 3: In that repo, ask the IDE about architecture or recent work.
Step 4: The client calls `search_code`, `get_repository_summary`, or `ask_benedict`.

Result: the IDE answers from Benedict's index and metadata, not from a fresh uninformed chat.

## 8. Edge Cases & Failure Modes

| Case | Behavior |
|------|----------|
| No onboarded projects | Tools return an error telling you to onboard in Slack |
| Several projects, cwd unknown | Error lists repos; pass `repo` |
| Repo not indexed | `search_code` returns no hits and tells you to run `@benedict update index` |
| No `ANTHROPIC_API_KEY` | `ask_benedict` fails; other tools still work |
| Missing metadata file | `get_repository_summary` returns a clear error; others still work |
| Slack bot not running | MCP tools still work. Recorded runs stay on disk until the operator UI starts and reloads `runs.jsonl`. |

The server does not create workspaces or mutate Slack state.

## 9. Constraints & Assumptions

- stdio only (local subprocess). No HTTP transport in this version.
- Read-only tools.
- Same host and filesystem as the Slack bot, so workspace symlinks resolve.
- Slack history is not exposed.

## 10. Architecture

`benedict.mcp.server` is a second composition root. It wires `ProjectResolver` and `BenedictMcpService`, then wraps them in MCP tools. Domain logic does not import the MCP SDK. The Slack bot is unchanged aside from sharing `benedict.paths`. MCP and Slack append the same `runs.jsonl`; the Slack-side recorder reloads the file when MCP writes.
