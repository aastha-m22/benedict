# Operator UI

A local debug console for Benedict.

One-sentence summary: Open a localhost page, pick a Slack mention or MCP call, and see the timed pipeline that produced the reply.

Decisions: [ADR 0001](adr/0001-local-operator-ui.md).

## 1. Overview

### What

A thin browser console that runs next to the Slack bot. It is a **request debugger**, not a health dashboard.

The primary object is a **run**: one Slack mention, thread reply, command, index job, or MCP tool call. Each run has a route, timed stages, payloads, and the reply that went out.

### Why

Today you debug Benedict by tailing Rich logs and correlating them with Slack. That fails when you need to answer:

- Why did this mention take the metadata shortcut instead of conversation?
- What did semantic search return?
- What context went into Claude?
- Which `run_github` / `run_notion` argv ran, and what came back?
- Why was the Slack reply empty or an error?

`workspace_log.json` records coarse workspace actions (onboard, index). It does not record a request. Issue [#22](https://github.com/mkarots/benedict/issues/22) asked for a thin operator console. The first draft of this design (PR [#23](https://github.com/mkarots/benedict/pull/23)) specified process health and tables. That does not answer the questions above.

### When to use

Use it while developing and dogfooding Benedict on your machine. Mention the bot in Slack, then inspect the run.

### Visual spec

The live page is `src/benedict/operator_ui/static/index.html`. Layout, density, and copy in section 12 are the UI contract.

## 2. Non-Goals

Not responsible for:

- Replacing Slack as the chat surface
- A hosted or multi-tenant product
- Authentication (bind to localhost)
- A full APM (Jaeger, Datadog)
- Historical analytics and charts
- Chat-without-Slack (later)

Out of scope for the first ship:

- macOS menu-bar wrapper
- Embedded trace waterfall
- WebSocket streaming
- OTel SDK work (issue #11 / Observability 1–3)

## 3. Key Concepts

| Term | Meaning |
|------|---------|
| Run | One inbound event and everything Benedict did for it |
| Stage | A timed step inside a run (`route`, `classify`, `search`, `context`, `llm`, `tool`, `reply`) |
| Activity | Newest-first list of runs |
| Inspector | Detail view for the selected run |
| Run log | Append-only JSONL file of runs (`$BENEDICT_DATA_DIR/runs.jsonl`) |
| Status strip | Compact process/config line. Not the main view. |

## 4. High-Level Design

The console has one job: **select a run, inspect the pipeline**.

```
Slack / MCP event
        │
        ▼
   RunRecorder.begin()
        │
        ├── route (command vs conversation vs architect vs MCP tool)
        ├── classify (metadata shortcut, if any)
        ├── search (Chroma hits)
        ├── context (files, README, metadata, actions)
        ├── llm (model, tokens, latency)
        ├── tool* (run_github / run_notion / metadata tools)
        └── reply (Slack text or MCP result)
        │
        ▼
   RunRecorder.end() → runs.jsonl
        │
        ▼
   GET /api/runs  →  Activity + Inspector
```

### Main components

1. **RunRecorder** — protocol + JSONL implementation. Agent, Slack handlers, and MCP service call it. Composition root (`main.py`, MCP server) injects it.
2. **Status API** — read-only HTTP on `127.0.0.1:8765`. Serves the UI and JSON for status, runs, and workspaces.
3. **Browser UI** — `src/benedict/operator_ui/static/index.html`. No SPA framework.

### Layout

Two panes. Status lives in a 40px header, not a card grid. The inspector splits pipeline vs context internally.

```
┌──────────────────────────────────────────────────────────────────┐
│ Benedict          Activity  Workspaces     live · slack · mcp    │
├────────────┬─────────────────────────────────────────────────────┤
│ Activity   │ query + route + duration                            │
│ newest     ├──────────────────────────────┬──────────────────────┤
│ first      │ Pipeline (timed stages)      │ Why this answer      │
│            │ click a stage for payload    │ hits, files, tools   │
│            ├──────────────────────────────┴──────────────────────┤
│            │ Reply that went to Slack / MCP                      │
└────────────┴─────────────────────────────────────────────────────┘
```

Workspaces is a second top-level view: channel → repo → index age. Use it to confirm onboarding, not to debug a reply.

### Key invariants

- Every inbound Slack mention, thread reply that Benedict answers, command, and MCP tool call writes exactly one run.
- Stages are append-only during the run. Failed stages stay in the record.
- The UI never writes. It only reads the run log and `state.json`.
- Missing optional components (LLM, Chroma, MCP) show as skipped stages or a dim status chip. The page still loads.

## 5. API / Interface

Bind to `127.0.0.1`. Default port `8765`. Enable with `BENEDICT_OPERATOR_UI=1`.

### `GET /api/status`

Input: none.

Output:

- `version`: package version
- `uptime_s`: Slack process uptime
- `data_dir`, `model`, `copy_mode`
- `components`: `{ slack, mcp, chroma, state }` each `{ ok: bool, detail: string }`
- `channels`: onboarded count
- `runs_today`: count

MCP health is best-effort (PID file or process name). If MCP is not running, the chip is dim, not an error. MCP is a separate process.

### `GET /api/runs?limit=50&source=&status=`

Input:

- `limit`: default 50, max 200
- `source`: optional `slack` | `mcp`
- `status`: optional `ok` | `error` | `running`

Output: `{ "runs": [ RunSummary, ... ] }` newest first.

`RunSummary`: `id`, `source`, `kind`, `status`, `started_at`, `duration_ms`, `channel_name`, `repo`, `query`, `route`.

### `GET /api/runs/{id}`

Output: full `Run`.

```json
{
  "id": "01JABC…",
  "source": "slack",
  "kind": "conversation",
  "status": "ok",
  "started_at": "2026-08-21T18:40:12.110Z",
  "ended_at": "2026-08-21T18:40:14.450Z",
  "duration_ms": 2340,
  "channel_id": "C123",
  "channel_name": "eng-backend",
  "user_id": "U456",
  "repo": "acme/backend",
  "thread_ts": "1692451200.123456",
  "query": "What files handle authentication?",
  "route": "handle_conversation",
  "reply": "*Auth lives in* `src/auth/…`",
  "error": null,
  "stages": [
    {
      "name": "route",
      "status": "ok",
      "duration_ms": 4,
      "detail": { "matched": "conversation" }
    }
  ]
}
```

`kind` values: `conversation` | `command` | `architect` | `index` | `mcp`.

`stage.name` values: `route` | `classify` | `search` | `context` | `llm` | `tool` | `reply`.

`detail` is stage-specific and must stay JSON-serializable. Truncate large blobs (tool stdout, system prompt) to 32 KiB with a `truncated: true` flag.

### `GET /api/workspaces`

Output: onboarded channels from `state.json` plus workspace path, last run, and whether a Chroma collection exists.

### `GET /`

Serves the console HTML.

## 6. Happy Path Example

1. Operator starts Benedict with `BENEDICT_OPERATOR_UI=1`.
2. Log line: `Operator UI http://127.0.0.1:8765`.
3. Operator asks in Slack: `@benedict what files handle authentication?`
4. Activity shows a new `conversation` run within 2 seconds.
5. Operator clicks it (or it auto-selects if it is the newest).
6. Inspector shows: route → search (8 hits) → context (4 files) → llm → `run_github` → reply.
7. Operator clicks `search` and sees hit paths and scores. Clicks `tool` and sees argv plus stdout.

Result: the operator knows why that answer appeared, without opening a terminal.

## 7. Edge Cases & Failure Modes

| Failure | Behavior |
|---------|----------|
| Run still in progress | `status: running`, stages partial, Activity shows a live pip. UI polls every 2s. |
| Handler throws | Run ends `error`. `error` holds the message. Stages recorded so far remain. |
| Channel not onboarded | Run still recorded. Route is `handle_conversation`, stage `reply` is the onboard error text. |
| Metadata shortcut fails and falls through | `classify` is `error` or `skip`; later stages are the conversation path. Both are visible. |
| LLM / indexer missing | Stages `llm` / `search` are `skip` with a reason. Stub reply is still a run. |
| `runs.jsonl` missing or corrupt | API returns empty list. Status chip for the run log is not-ok. UI stays up. |
| Payload over 32 KiB | Truncate; set `truncated`. Never block the Slack reply on recorder I/O. |
| Recorder I/O fails | Log a warning. Slack path continues. |

Guarantees:

- Recording must not raise into Slack handlers.
- The UI is read-only. It cannot onboard, index, or send Slack messages.

## 8. Constraints & Assumptions

- Local operator on the same machine as the bot. Bind `127.0.0.1` only.
- Same process as the Slack bot for v1 (background asyncio/thread). MCP writes to the same `runs.jsonl` because it shares `BENEDICT_DATA_DIR`.
- No new database. JSONL is grepable and enough for recent activity.
- Polling at 2s. Fast enough to watch a request; simple enough to skip WebSockets.
- UI: one HTML file, no React. Dense, dark, system/Plex fonts. Color only for status.
- Jaeger links are optional. If a `trace_id` exists on the run, show it. Do not require Observability 1–3 to ship this UI.
- API handlers should return in well under 500ms for the last 200 runs.

## 9. Alternatives Considered

**Health dashboard (PR #23)** — rejected as the primary UI. PID/uptime/Chroma-path tables do not explain a bad Slack reply. Status belongs in the header.

**Read only existing files** (`state.json`, `workspace_log.json`) — rejected. Those files do not contain search hits, prompts, or tool argv. A `RunRecorder` is required.

**Jaeger-first** — rejected for v1. OTel is a separate milestone. A local run log is useful the same day. Link out later.

**Sidecar process** — deferred. Same-process is enough. Split if the HTTP server ever contends with Socket Mode.

**Embedded chat** — deferred. Slack stays the input.

## 10. Open Questions

Q1: Should MCP runs appear in the same Activity list as Slack? Default: yes, one stream, filterable by source.

Q2: How long to retain `runs.jsonl`? Default: last 2,000 runs, rotate by truncating the oldest on write. Revisit if the file grows past ~20 MB.

Q3: Redact Slack user IDs in the UI? Default: show IDs. This is a local operator tool.

## 11. Implementation plan

Ship in this order. Do not build the HTTP server before runs exist.

1. **RunRecorder** — protocol, JSONL store, unit tests (write, read, truncate, failure isolation).
2. **Instrument** — `slack_app` handlers, `RepoAgent.handle_*`, `run_tool_loop`, MCP service methods.
3. **Status API** — stdlib or existing stack; prefer stdlib `http.server` or `aiohttp` if already justified. Avoid adding FastAPI unless something else needs it.
4. **UI** — serve `src/benedict/operator_ui/static/index.html` from `/`, wired to `/api/*`.
5. **Docs** — README env vars, CHANGELOG.

Done when: you can mention Benedict in Slack, open `http://127.0.0.1:8765`, and see that run’s stages, search hits, tool argv, and reply.

## 12. Visual design

Principles:

- One accent (warm sand). Green/red only on status.
- Flat surfaces. No gradients, no shadows, no emoji.
- 13px UI type. Monospace for IDs, argv, paths, JSON.
- Activity is scannable in under a second: pip, kind, query, duration.
- Inspector is a timeline, not a table of requests.
- The right column of the inspector answers “why this answer?” (hits, files, tools).

Keyboard: `j` / `k` move in Activity. `1` Activity, `2` Workspaces.

`src/benedict/operator_ui/static/index.html` is normative for layout, density, and copy.
