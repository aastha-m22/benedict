# ADR 0001: Local operator UI

Status: Accepted

Date: 2026-08-23

One-sentence summary:
Ship a localhost request debugger next to the Slack bot, not a health dashboard and not a second chat surface.

## Context

Debugging Benedict meant tailing Rich logs and guessing which mention they belonged to. Operators could not answer:

- Why did this mention take the metadata shortcut?
- What did semantic search return?
- Which files went into Claude?
- What tool argv ran, and what came back?

`workspace_log.json` records coarse workspace actions (onboard, index). It does not record a request.

Issue [#22](https://github.com/mkarots/benedict/issues/22) asked for a thin operator console. PR [#23](https://github.com/mkarots/benedict/pull/23) drafted a health dashboard (PIDs, uptime, tables). That does not explain a bad Slack reply.

## Decision

1. **The primary object is a run.** One Slack mention, thread reply, command, index job, or MCP tool call. Stages are `route`, `classify`, `search`, `context`, `llm`, `tool`, `reply`.
2. **Slack stays the chat surface.** The console is read-only. It does not onboard repos or send messages.
3. **Record into `$BENEDICT_DATA_DIR/runs.jsonl`.** No new database. Rotate at 2,000 rows.
4. **Serve a single static HTML page** from the Slack process on `127.0.0.1:8765` using stdlib `ThreadingHTTPServer`. No React, no FastAPI, no extra runtime dependency. The shipped page is `src/benedict/operator_ui/static/index.html`.
5. **Recording and HTTP must not raise into Slack or MCP.** `begin` / `record_stage` / `finish` swallow exceptions. Bind failure leaves the bot running. The HTTP server is a daemon thread.
6. **On by default.** Set `BENEDICT_OPERATOR_UI=0` to use `NullRunRecorder` and skip the server.
7. **Keep the decision and the spec in `docs/`.** Do not keep HTML mocks or walkthroughs under `plans/`. Spec: [OPERATOR_UI_DESIGN.md](../OPERATOR_UI_DESIGN.md).

## Consequences

### What we get

- Mention Benedict, open `http://127.0.0.1:8765`, and inspect that run within about two seconds (poll interval).
- MCP writes the same JSONL when it shares `BENEDICT_DATA_DIR`. The Slack process serves the UI. MCP writes `mcp.pid` for the header chip.

### What we give up

- No component model, TypeScript, or UI tests. The page is one HTML file with string templates.
- No WebSockets. A live run can lag by up to two seconds.
- The UI shares the Slack process (GIL and the recorder lock). A slow list of runs can delay a mention slightly. It must not crash Slack.
- `ThreadingHTTPServer` is not a production web stack. Bind stays on loopback. No auth.

### Failure modes

- Port in use: log a warning, continue without the console.
- JSONL unwritable or corrupt: log a warning, Slack still replies.
- Browser cannot reach the API: the page shows an empty state. The bot is unchanged.

## Alternatives considered

**Health dashboard (PR #23)** — rejected as the primary UI. PID and uptime tables do not explain a reply.

**Read only `state.json` and `workspace_log.json`** — rejected. Those files do not contain search hits, prompts, or tool argv.

**Jaeger / OpenTelemetry first** — deferred. A local run log is useful the same day. Link a `trace_id` later.

**Sidecar process** — deferred. Same-process is enough until the HTTP server contends with Socket Mode.

**Embedded chat** — out of scope. Slack stays the input.

**SPA framework or FastAPI** — rejected for v1. Extra toolchain and dependency for a localhost debugger.

## References

- Spec: [OPERATOR_UI_DESIGN.md](../OPERATOR_UI_DESIGN.md)
- Live UI: `src/benedict/operator_ui/static/index.html`
- Issue [#22](https://github.com/mkarots/benedict/issues/22), draft [#23](https://github.com/mkarots/benedict/pull/23)
