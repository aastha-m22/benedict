"""Tests for the operator-UI run recorder and HTTP API."""

import json
from datetime import datetime, timezone
from pathlib import Path

from benedict.operator_ui.recorder import JsonlRunRecorder, NullRunRecorder, record_stage
from benedict.operator_ui.server import StatusMonitor, _Handler


def test_recorder_write_read_and_list(tmp_path: Path):
    recorder = JsonlRunRecorder(tmp_path / "runs.jsonl")
    run = recorder.begin(source="slack", kind="conversation", query="hello", repo="acme/x")
    run.add_stage("route", label="conversation", detail={"matched": "handle_conversation"})
    run.finish(status="ok", reply="hi")

    listed = recorder.list_runs(limit=10)
    assert len(listed) == 1
    assert listed[0]["query"] == "hello"
    assert listed[0]["status"] == "ok"
    assert listed[0]["reply"] == "hi"
    assert listed[0]["stages"][0]["name"] == "route"

    loaded = recorder.get(run.id)
    assert loaded is not None
    assert loaded["id"] == run.id
    assert (tmp_path / "runs.jsonl").exists()


def test_recorder_isolates_io_failure(tmp_path: Path):
    blocked = tmp_path / "missing" / "runs.jsonl"
    recorder = JsonlRunRecorder(blocked)
    parent = blocked.parent
    parent.mkdir()
    parent.chmod(0o400)
    try:
        run = recorder.begin(query="x")
        run.finish(status="ok", reply="ok")
    finally:
        parent.chmod(0o700)
    # begin must not raise even if persist later fails
    assert run.id


def test_recorder_sees_writes_from_another_process(tmp_path: Path):
    """Slack UI and MCP are separate processes sharing one JSONL file."""
    path = tmp_path / "runs.jsonl"
    slack_view = JsonlRunRecorder(path)
    mcp_writer = JsonlRunRecorder(path)
    run = mcp_writer.begin(
        source="mcp",
        kind="mcp",
        query="ask_benedict  issue 42",
        repo="acme/x",
        route="BenedictMcpService.ask",
    )
    run.finish(status="ok", reply="batch chroma deletes")

    listed = slack_view.list_runs(limit=10)
    assert any(row["id"] == run.id for row in listed)
    loaded = slack_view.get(run.id)
    assert loaded is not None
    assert loaded["source"] == "mcp"
    assert loaded["query"] == "ask_benedict  issue 42"
    assert slack_view.runs_today() == 1


def test_recorder_persist_keeps_other_process_runs(tmp_path: Path):
    path = tmp_path / "runs.jsonl"
    slack = JsonlRunRecorder(path)
    mcp = JsonlRunRecorder(path)
    mcp_run = mcp.begin(source="mcp", query="ask")
    mcp_run.finish(status="ok", reply="yes")
    slack_run = slack.begin(source="slack", query="hi")
    slack_run.finish(status="ok", reply="there")

    ids = {row["id"] for row in slack.list_runs()}
    assert {mcp_run.id, slack_run.id} <= ids
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_null_recorder_is_safe():
    recorder = NullRunRecorder()
    run = recorder.begin(query="nope")
    run.add_stage("route")
    run.finish(status="ok", reply="x")
    assert recorder.list_runs() == []
    assert recorder.get("abc") is None
    record_stage("search")  # no current run


def test_record_stage_attaches_to_current_run(tmp_path: Path):
    recorder = JsonlRunRecorder(tmp_path / "runs.jsonl")
    run = recorder.begin(query="search me")
    record_stage("search", label="2 hits", detail={"hits": [["a.py", 0.9]]})
    run.finish(status="ok", reply="done")
    loaded = recorder.get(run.id)
    assert loaded["stages"][-1]["name"] == "search"
    assert loaded["stages"][-1]["detail"]["hits"][0][0] == "a.py"


def test_status_and_runs_endpoints(tmp_path: Path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"channels": {"C1": {"repo": "acme/x"}}}), encoding="utf-8")
    recorder = JsonlRunRecorder(tmp_path / "runs.jsonl")
    run = recorder.begin(
        source="slack",
        kind="conversation",
        query="auth?",
        channel_id="C1",
        repo="acme/x",
        route="handle_conversation",
    )
    run.finish(status="ok", reply="here")
    monitor = StatusMonitor(
        data_dir=tmp_path,
        recorder=recorder,
        state_file=state,
        workspaces_dir=tmp_path / "workspaces",
        chroma_path=tmp_path / ".chroma_db",
        started_at=datetime.now(timezone.utc),
        model="claude-test",
        copy_mode="symlink",
    )
    status = monitor.status()
    assert status["channels"] == 1
    assert status["components"]["slack"]["ok"] is True
    assert status["components"]["state"]["ok"] is True
    assert status["runs_today"] == 1

    workspaces = monitor.workspaces()
    assert workspaces["workspaces"][0]["repository"] == "acme/x"

    _Handler.monitor = monitor
    summaries = [_summary_via_api(recorder)]
    assert summaries[0]["query"] == "auth?"


def _summary_via_api(recorder):
    from benedict.operator_ui.server import _summary

    return _summary(recorder.list_runs(limit=1)[0])


def test_conversation_records_not_onboarded(tmp_path: Path):
    from benedict.agent import RepoAgent
    from benedict.conversation_repository.conversation_repository_mock import (
        MockConversationRepository,
    )

    recorder = JsonlRunRecorder(tmp_path / "runs.jsonl")
    agent = RepoAgent(
        state_file=str(tmp_path / "state.json"),
        conversation_repository=MockConversationRepository(),
        run_recorder=recorder,
    )
    run = recorder.begin(query="what's in auth?", channel_id="Cnone")
    success, message = agent.handle_conversation("Cnone", "what's in auth?", "1.2")
    run.finish(status="ok" if success else "error", reply=message)
    assert success is False
    loaded = recorder.get(run.id)
    assert any(stage["label"] == "not onboarded" for stage in loaded["stages"])
