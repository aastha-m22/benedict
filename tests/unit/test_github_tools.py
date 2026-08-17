"""Tests for RunGithubTool."""

import subprocess
from unittest.mock import patch

from benedict.commands.github_tools import RunGithubTool, _normalize_argv, _redact_tokens, _truncate


def test_normalize_argv_list_and_strip_gh():
    assert _normalize_argv(["pr", "list"]) == ["pr", "list"]
    assert _normalize_argv(["gh", "pr", "list"]) == ["pr", "list"]
    assert _normalize_argv("pr view 12 --json title") == ["pr", "view", "12", "--json", "title"]
    assert _normalize_argv(None) is None
    assert _normalize_argv({"bad": True}) is None


def test_truncate_and_redact():
    assert _truncate("short") == "short"
    long = "a" * 32010
    truncated = _truncate(long, limit=32)
    assert truncated.startswith("a" * 32)
    assert "omitted" in truncated
    assert "[redacted-token]" in _redact_tokens("token ghp_abc123XYZ rest")
    assert "[redacted-token]" in _redact_tokens("pat github_pat_abc rest")


def test_rejects_empty_and_auth_token(tmp_path):
    tool = RunGithubTool()
    missing = tool.execute({"argv": []}, {"workspace_path": str(tmp_path)})
    assert missing.success is False
    assert "empty" in missing.error

    blocked = tool.execute({"argv": ["auth", "token"]}, {"workspace_path": str(tmp_path)})
    assert blocked.success is False
    assert "auth token" in blocked.error


def test_requires_workspace_dir(tmp_path):
    tool = RunGithubTool()
    no_ctx = tool.execute({"argv": ["pr", "list"]})
    assert no_ctx.success is False

    missing_dir = tool.execute({"argv": ["pr", "list"]}, {"workspace_path": str(tmp_path / "nope")})
    assert missing_dir.success is False


@patch("benedict.commands.github_tools.shutil.which", return_value=None)
def test_missing_gh_binary(mock_which, tmp_path):
    tool = RunGithubTool()
    result = tool.execute({"argv": ["pr", "list"]}, {"workspace_path": str(tmp_path)})
    assert result.success is False
    assert "not installed" in result.error
    mock_which.assert_called()


@patch("benedict.commands.github_tools.shutil.which", return_value="/usr/bin/gh")
@patch("benedict.commands.github_tools.subprocess.run")
def test_runs_gh_with_locked_cwd(mock_run, mock_which, tmp_path):
    mock_run.return_value = subprocess.CompletedProcess(
        args=["gh", "pr", "list"], returncode=0, stdout='[{"title":"x"}]', stderr=""
    )
    tool = RunGithubTool()
    result = tool.execute({"argv": ["pr", "list"]}, {"workspace_path": str(tmp_path)})

    assert result.success is True
    assert result.message == '[{"title":"x"}]'
    assert result.data["exit_code"] == 0
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == ["gh", "pr", "list"]
    assert kwargs["cwd"] == str(tmp_path)
    assert kwargs["timeout"] == 30
    assert kwargs.get("shell") in (None, False)


@patch("benedict.commands.github_tools.shutil.which", return_value="/usr/bin/gh")
@patch("benedict.commands.github_tools.subprocess.run")
def test_cannot_switch_binary(mock_run, mock_which, tmp_path):
    mock_run.return_value = subprocess.CompletedProcess(
        args=["gh", "rm", "-rf", "/"], returncode=1, stdout="", stderr="unknown command"
    )
    tool = RunGithubTool()
    # argv is appended to `gh`; there is no way to run a different binary
    result = tool.execute({"argv": ["rm", "-rf", "/"]}, {"workspace_path": str(tmp_path)})
    assert result.success is True
    assert args_started_with_gh(mock_run)
    assert result.data["exit_code"] == 1


def args_started_with_gh(mock_run):
    return mock_run.call_args[0][0][0] == "gh"


@patch("benedict.commands.github_tools.shutil.which", return_value="/usr/bin/gh")
@patch("benedict.commands.github_tools.subprocess.run")
def test_timeout(mock_run, mock_which, tmp_path):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)
    tool = RunGithubTool(timeout_s=30)
    result = tool.execute({"argv": ["pr", "list"]}, {"workspace_path": str(tmp_path)})
    assert result.success is False
    assert "timed out" in result.error


@patch("benedict.commands.github_tools.shutil.which", return_value="/usr/bin/gh")
@patch("benedict.commands.github_tools.subprocess.run")
def test_redacts_tokens_in_output(mock_run, mock_which, tmp_path):
    mock_run.return_value = subprocess.CompletedProcess(
        args=["gh", "pr", "list"],
        returncode=0,
        stdout="secret ghp_ABCDEFG123 rest",
        stderr="",
    )
    tool = RunGithubTool()
    result = tool.execute({"argv": ["pr", "list"]}, {"workspace_path": str(tmp_path)})
    assert "ghp_" not in result.message
    assert "[redacted-token]" in result.message
