"""Tests for conversation routing past the metadata classifier."""

from pathlib import Path
from types import SimpleNamespace

from benedict.agent import RepoAgent
from benedict.commands.tool_registry_factory import create_tool_registry
from benedict.conversation_repository.conversation_repository_mock import (
    MockConversationRepository,
)
from benedict.llm.llm_mock import MockLLM
from benedict.repo_reader.repo_reader_mock import MockRepoReader
from benedict.workspace import WorkspaceManager

METADATA_YAML = """\
summary: Example service
purpose: Demo repository
files:
  - name: README.md
    purpose: Intro
"""

GITHUB_ISSUE_TEXT = (
    "Can you create a github issue regarding how its not clearly defined "
    "how benedict executes commands using llms."
)


class MetadataToolCallingLLM:
    """Calls a metadata tool when those tools are offered; otherwise returns text.

    Reproduces the production failure: the classifier only has metadata tools,
    so a GitHub request can still produce a metadata tool call.
    """

    def __init__(self, metadata_tool_name="get_repository_summary", metadata_input=None):
        self.metadata_tool_name = metadata_tool_name
        self.metadata_input = metadata_input or {}

    def generate(self, messages, system="", max_tokens=2000, tools=None):
        names = [tool.get("name") for tool in tools or [] if tool.get("name")]
        if self.metadata_tool_name in names:
            return {
                "tool_calls": [
                    {
                        "name": self.metadata_tool_name,
                        "input": self.metadata_input,
                    }
                ]
            }
        last = ""
        for msg in reversed(messages or []):
            if msg.get("role") == "user":
                last = str(msg.get("content", ""))
                break
        return f"[conversation] {last}"


def _onboarded_agent(tmp_path: Path, llm, with_metadata: bool = False, run_recorder=None) -> RepoAgent:
    repo = "example-org/example-repo"
    workspace_manager = WorkspaceManager(
        workspaces_dir=str(tmp_path / "workspaces"), copy_mode="copy"
    )
    agent = RepoAgent(
        state_file=str(tmp_path / "state.json"),
        llm=llm,
        repo_reader=MockRepoReader(repos={repo: {"README.md": "# Example\n"}}),
        workspace_manager=workspace_manager,
        conversation_repository=MockConversationRepository(),
        run_recorder=run_recorder,
    )
    agent.set_channel_repo("C123", repo, "Ualice")
    repo_path = workspace_manager.get_workspace_path("C123") / repo
    repo_path.mkdir(parents=True)
    (repo_path / "README.md").write_text("# Example\n", encoding="utf-8")
    if with_metadata:
        (repo_path / ".metadata.benedict").write_text(METADATA_YAML, encoding="utf-8")
    return agent


def test_github_issue_request_is_not_a_metadata_command():
    assert RepoAgent.is_metadata_command(GITHUB_ISSUE_TEXT) is False
    assert RepoAgent.is_metadata_command("show metadata for README.md") is True
    assert RepoAgent.is_metadata_command("list files") is True
    assert RepoAgent.is_metadata_command("get repository summary") is True


def test_create_github_issue_does_not_fail_on_missing_metadata(tmp_path):
    agent = _onboarded_agent(tmp_path, MockLLM())
    success, message = agent.handle_conversation("C123", GITHUB_ISSUE_TEXT, "111.222")

    assert success is True
    assert "Metadata file not found" not in message
    assert "Some operations failed" not in message


def test_github_issue_skips_classifier_even_when_metadata_exists(tmp_path):
    """If the classifier ran, this LLM would return repository summary YAML."""
    agent = _onboarded_agent(tmp_path, MetadataToolCallingLLM(), with_metadata=True)
    success, message = agent.handle_conversation("C123", GITHUB_ISSUE_TEXT, "111.223")

    assert success is True
    assert "Example service" not in message
    assert "Some operations failed" not in message
    assert "[conversation]" in message


def test_missing_metadata_does_not_register_classifier_tools(tmp_path):
    """repo_path wiring: no sidecar means the classifier has no tools to call."""
    llm = MetadataToolCallingLLM()
    agent = _onboarded_agent(tmp_path, llm, with_metadata=False)
    success, message = agent.handle_conversation(
        "C123", "show metadata for README.md", "111.224"
    )

    assert success is True
    assert "Metadata file not found" not in message
    assert "[conversation]" in message


def test_failed_metadata_tools_fall_through_to_conversation(tmp_path):
    llm = MetadataToolCallingLLM(
        metadata_tool_name="get_file_metadata",
        metadata_input={"file_path": "missing.py"},
    )
    agent = _onboarded_agent(tmp_path, llm, with_metadata=True)
    success, message = agent.handle_conversation(
        "C123", "show metadata for missing.py", "111.225"
    )

    assert success is True
    assert "Some operations failed" not in message
    assert "[conversation]" in message


def test_conversation_records_llm_prompt(tmp_path):
    from benedict.operator_ui.recorder import JsonlRunRecorder

    recorder = JsonlRunRecorder(tmp_path / "runs.jsonl")
    agent = _onboarded_agent(tmp_path, MockLLM(), run_recorder=recorder)
    run = recorder.begin(query="what is this repo?", channel_id="C123")
    success, message = agent.handle_conversation("C123", "what is this repo?", "111.226")
    run.finish(status="ok" if success else "error", reply=message)

    assert success is True
    loaded = recorder.get(run.id)
    llm_stages = [stage for stage in loaded["stages"] if stage["name"] == "llm"]
    assert llm_stages
    prompt = llm_stages[-1]["detail"]
    assert "You are Benedict" in prompt["system"]
    assert "example-org/example-repo" in prompt["system"]
    assert any(
        msg.get("role") == "user" and "what is this repo?" in str(msg.get("content"))
        for msg in prompt["messages"]
    )


def test_tool_registry_skips_tools_when_metadata_missing():
    reader = SimpleNamespace(metadata_exists=lambda _path: False)
    registry = create_tool_registry(metadata_reader=reader, repo_path=Path("/tmp"))
    assert registry.list_tools() == []
