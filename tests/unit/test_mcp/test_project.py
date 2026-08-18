"""Tests for ProjectResolver."""

import json
from pathlib import Path

import pytest

from benedict.mcp.project import ProjectResolutionError, ProjectResolver, load_channel_state
from benedict.workspace.workspace_manager import WorkspaceManager


def _write_state(path: Path, channels: dict) -> None:
    path.write_text(json.dumps({"channels": channels}), encoding="utf-8")


def _onboard(tmp_path: Path, channel_id: str, repo: str, source: Path) -> Path:
    manager = WorkspaceManager(workspaces_dir=str(tmp_path / "workspaces"), copy_mode="symlink")
    manager.add_resource(channel_id, "repository", str(source), repo, content_type="code")
    return manager.get_workspace_path(channel_id)


def test_load_channel_state_missing_and_invalid(tmp_path: Path):
    missing = tmp_path / "nope.json"
    assert load_channel_state(missing) == {"channels": {}}

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_channel_state(bad) == {"channels": {}}

    not_object = tmp_path / "list.json"
    not_object.write_text("[1]", encoding="utf-8")
    assert load_channel_state(not_object) == {"channels": {}}


def test_list_and_resolve_exact_repo(tmp_path: Path):
    source = tmp_path / "src" / "example"
    source.mkdir(parents=True)
    (source / "README.md").write_text("# example\n", encoding="utf-8")
    _onboard(tmp_path, "C1", "acme/example", source)

    state_file = tmp_path / "state.json"
    _write_state(
        state_file,
        {"C1": {"repo": "acme/example", "onboarded_at": "2026-01-01T00:00:00Z"}},
    )
    resolver = ProjectResolver(load_channel_state(state_file), tmp_path / "workspaces")

    projects = resolver.list_projects()
    assert len(projects) == 1
    assert projects[0].repo == "acme/example"
    assert projects[0].channel_id == "C1"
    assert projects[0].source_path == source.resolve()

    resolved = resolver.resolve(repo="acme/example")
    assert resolved.repo == "acme/example"


def test_resolve_by_basename_and_cwd(tmp_path: Path):
    source = tmp_path / "src" / "example"
    source.mkdir(parents=True)
    (source / "nested").mkdir()
    _onboard(tmp_path, "C1", "acme/example", source)

    state_file = tmp_path / "state.json"
    _write_state(state_file, {"C1": {"repo": "acme/example"}})
    resolver = ProjectResolver(load_channel_state(state_file), tmp_path / "workspaces")

    assert resolver.resolve(repo="example").repo == "acme/example"
    assert resolver.resolve(cwd=source / "nested").repo == "acme/example"


def test_single_project_default(tmp_path: Path):
    source = tmp_path / "repo"
    source.mkdir()
    _onboard(tmp_path, "C1", "solo", source)
    state_file = tmp_path / "state.json"
    _write_state(state_file, {"C1": {"repo": "solo"}})
    resolver = ProjectResolver(load_channel_state(state_file), tmp_path / "workspaces")
    assert resolver.resolve().repo == "solo"


def test_ambiguous_without_repo(tmp_path: Path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _onboard(tmp_path, "C1", "org/a", a)
    _onboard(tmp_path, "C2", "org/b", b)
    state_file = tmp_path / "state.json"
    _write_state(state_file, {"C1": {"repo": "org/a"}, "C2": {"repo": "org/b"}})
    resolver = ProjectResolver(load_channel_state(state_file), tmp_path / "workspaces")

    with pytest.raises(ProjectResolutionError, match="Multiple Benedict projects"):
        resolver.resolve()


def test_unknown_repo(tmp_path: Path):
    source = tmp_path / "repo"
    source.mkdir()
    _onboard(tmp_path, "C1", "org/known", source)
    state_file = tmp_path / "state.json"
    _write_state(state_file, {"C1": {"repo": "org/known"}})
    resolver = ProjectResolver(load_channel_state(state_file), tmp_path / "workspaces")

    with pytest.raises(ProjectResolutionError, match="No onboarded"):
        resolver.resolve(repo="missing")


def test_empty_state(tmp_path: Path):
    resolver = ProjectResolver({"channels": {}}, tmp_path / "workspaces")
    with pytest.raises(ProjectResolutionError, match="No Benedict projects"):
        resolver.resolve()


def test_ambiguous_basename(tmp_path: Path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _onboard(tmp_path, "C1", "one/app", a)
    _onboard(tmp_path, "C2", "two/app", b)
    state_file = tmp_path / "state.json"
    _write_state(state_file, {"C1": {"repo": "one/app"}, "C2": {"repo": "two/app"}})
    resolver = ProjectResolver(load_channel_state(state_file), tmp_path / "workspaces")

    with pytest.raises(ProjectResolutionError, match="matches multiple"):
        resolver.resolve(repo="app")
