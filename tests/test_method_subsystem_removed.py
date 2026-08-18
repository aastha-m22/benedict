"""Regression tests for method-subsystem removal."""

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from benedict.agent import RepoAgent
from benedict.commands.command_definitions import COMMAND_DEFINITIONS, CommandType
from benedict.commands.tool_registry_factory import create_tool_registry
from benedict.utils.context import build_context


def test_method_package_is_gone():
    with pytest.raises((ModuleNotFoundError, ImportError)):
        from benedict.method import MethodReader  # noqa: F401


def test_method_tools_module_is_gone():
    with pytest.raises(ModuleNotFoundError):
        __import__("benedict.commands.method_tools")


def test_command_types_have_no_method_operations():
    names = {member.name for member in CommandType}
    assert not {"READ_METHOD", "UPDATE_METHOD", "CREATE_METHOD"} & names


def test_command_definitions_have_no_method_commands():
    names = {definition.name for definition in COMMAND_DEFINITIONS}
    assert not {"read_method", "update_method", "create_method"} & names


def test_tool_registry_without_metadata_has_no_tools():
    registry = create_tool_registry()
    assert registry.list_tools() == []


def test_tool_registry_registers_only_metadata_tools():
    reader = SimpleNamespace(metadata_exists=lambda _path: True)
    registry = create_tool_registry(metadata_reader=reader, repo_path=Path("/tmp"))
    names = {tool.name for tool in registry.list_tools()}
    assert names == {"get_file_metadata", "list_key_files", "get_repository_summary"}
    assert "get_method_state" not in names
    assert "update_pc" not in names
    assert "create_method" not in names


def test_tool_registry_skips_tools_when_metadata_missing():
    reader = SimpleNamespace(metadata_exists=lambda _path: False)
    registry = create_tool_registry(metadata_reader=reader, repo_path=Path("/tmp"))
    assert registry.list_tools() == []


def test_create_tool_registry_from_method_data_is_gone():
    import benedict.commands as commands

    assert not hasattr(commands, "create_tool_registry_from_method_data")


def test_build_context_does_not_accept_method_reader():
    signature = inspect.signature(build_context)
    assert "method_reader" not in signature.parameters


def test_repo_agent_has_no_method_io(tmp_path):
    agent = RepoAgent(state_file=str(tmp_path / "state.json"))
    assert not hasattr(agent, "method_reader")
    assert not hasattr(agent, "method_writer")
    assert not hasattr(agent, "handle_create_method")
    assert not hasattr(agent, "handle_method_update")
    assert not hasattr(agent, "is_create_method_command")
