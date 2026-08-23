"""Tests for BenedictMcpService."""

import json
from pathlib import Path

from benedict.llm.llm_mock import MockLLM
from benedict.mcp.project import ProjectResolver, load_channel_state
from benedict.mcp.service import BenedictMcpService
from benedict.metadata import MetadataReader
from benedict.operator_ui.recorder import JsonlRunRecorder
from benedict.semantic_indexer.semantic_indexer_mock import MockSemanticIndexer
from benedict.workspace.action_logger import ActionLogger
from benedict.workspace.workspace_manager import WorkspaceManager

METADATA_YAML = """\
summary: Example service
purpose: Demo repository for tests
files:
  - name: README.md
    purpose: Overview
"""


def _build_service(
    tmp_path: Path, *, with_llm: bool = True, index: bool = True, run_recorder=None
) -> BenedictMcpService:
    source = tmp_path / "src" / "example"
    source.mkdir(parents=True)
    (source / "README.md").write_text("# example\n", encoding="utf-8")
    (source / ".metadata.benedict").write_text(METADATA_YAML, encoding="utf-8")

    manager = WorkspaceManager(workspaces_dir=str(tmp_path / "workspaces"), copy_mode="symlink")
    manager.add_resource("C1", "repository", str(source), "acme/example", content_type="code")
    workspace = manager.get_workspace_path("C1")
    ActionLogger(workspace).log_action(
        action="symlink_repository",
        content_type="code",
        resource="acme/example",
    )

    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps({"channels": {"C1": {"repo": "acme/example"}}}),
        encoding="utf-8",
    )

    indexer = MockSemanticIndexer()
    if index:
        indexer.index_repository("acme/example", repo_reader=None)

    return BenedictMcpService(
        resolver=ProjectResolver(load_channel_state(state_file), tmp_path / "workspaces"),
        metadata_reader=MetadataReader(),
        semantic_indexer=indexer,
        llm=MockLLM() if with_llm else None,
        workspace_manager=manager,
        run_recorder=run_recorder,
    )


def test_list_projects(tmp_path: Path):
    service = _build_service(tmp_path)
    listed = service.list_projects()
    assert listed["ok"] is True
    assert listed["count"] == 1
    assert listed["projects"][0]["repo"] == "acme/example"


def test_repository_summary_and_actions(tmp_path: Path):
    service = _build_service(tmp_path)
    summary = service.get_repository_summary(repo="example")
    assert summary["ok"] is True
    assert summary["summary"] == "Example service"
    assert summary["purpose"] == "Demo repository for tests"

    actions = service.get_recent_actions(repo="acme/example", limit=5)
    assert actions["ok"] is True
    assert actions["actions"][0]["action"] == "symlink_repository"


def test_search_code_indexed_and_unindexed(tmp_path: Path):
    service = _build_service(tmp_path, index=True)
    hits = service.search_code("authentication flow", repo="acme/example")
    assert hits["ok"] is True
    assert hits["results"]
    assert hits["results"][0]["file_path"] == "file_authentication.py"

    empty = _build_service(tmp_path / "other", index=False)
    skipped = empty.search_code("anything", repo="acme/example")
    assert skipped["ok"] is True
    assert skipped["results"] == []
    assert "not indexed" in skipped["note"]


def test_search_requires_query(tmp_path: Path):
    service = _build_service(tmp_path)
    result = service.search_code("  ")
    assert result["ok"] is False
    assert "query" in result["error"]


def test_ask_with_and_without_llm(tmp_path: Path):
    service = _build_service(tmp_path, with_llm=True)
    answer = service.ask("What does this repo do?", repo="acme/example")
    assert answer["ok"] is True
    assert "answer" in answer
    assert answer["answer"]

    no_llm = _build_service(tmp_path / "nollm", with_llm=False)
    missing = no_llm.ask("hello", repo="acme/example")
    assert missing["ok"] is False
    assert "ANTHROPIC_API_KEY" in missing["error"]


def test_ask_records_operator_run(tmp_path: Path):
    recorder = JsonlRunRecorder(tmp_path / "runs.jsonl")
    service = _build_service(tmp_path, with_llm=True, run_recorder=recorder)
    answer = service.ask("What does this repo do?", repo="acme/example")
    assert answer["ok"] is True
    runs = recorder.list_runs(limit=10)
    assert len(runs) == 1
    assert runs[0]["source"] == "mcp"
    assert runs[0]["route"] == "BenedictMcpService.ask"
    assert "What does this repo do?" in runs[0]["query"]
    assert runs[0]["status"] == "ok"


def test_unknown_project_error(tmp_path: Path):
    service = _build_service(tmp_path)
    result = service.get_repository_summary(repo="nope")
    assert result["ok"] is False
    assert "No onboarded" in result["error"]
