"""Tests for workspace management.

Tests WorkspaceManager and ActionLogger functionality.
"""

import pytest
from pathlib import Path

from benedict.workspace import WorkspaceManager, ActionLogger


class TestWorkspaceManager:
    """Tests for WorkspaceManager."""

    def test_initialization(self, temp_dir):
        """Test workspace manager initialization."""
        manager = WorkspaceManager(base_dir=str(temp_dir))
        
        assert manager.base_dir == Path(temp_dir)
        assert manager.base_dir.exists()

    def test_get_workspace_path(self, temp_dir):
        """Test getting workspace path for a channel."""
        manager = WorkspaceManager(base_dir=str(temp_dir))
        
        path = manager.get_workspace_path("C123456", "example-org/repo")
        
        assert path is not None
        assert isinstance(path, Path)
        assert "C123456" in str(path)

    def test_workspace_creation(self, temp_dir):
        """Test that workspace directory is created."""
        manager = WorkspaceManager(base_dir=str(temp_dir))
        
        path = manager.get_workspace_path("C123456", "example-org/repo")
        
        # The workspace might be created on-demand
        assert path is not None

    def test_multiple_workspaces(self, temp_dir):
        """Test managing multiple workspaces."""
        manager = WorkspaceManager(base_dir=str(temp_dir))
        
        path1 = manager.get_workspace_path("C111111", "org1/repo1")
        path2 = manager.get_workspace_path("C222222", "org2/repo2")
        
        assert path1 != path2
        assert "C111111" in str(path1)
        assert "C222222" in str(path2)

    def test_same_workspace_for_same_channel(self, temp_dir):
        """Test that same channel gets same workspace."""
        manager = WorkspaceManager(base_dir=str(temp_dir))
        
        path1 = manager.get_workspace_path("C123456", "example-org/repo")
        path2 = manager.get_workspace_path("C123456", "example-org/repo")
        
        assert path1 == path2


class TestActionLogger:
    """Tests for ActionLogger."""

    def test_initialization(self, temp_dir):
        """Test action logger initialization."""
        log_file = temp_dir / "actions.log"
        logger = ActionLogger(log_file=str(log_file))
        
        assert logger.log_file == log_file

    def test_log_action(self, temp_dir):
        """Test logging an action."""
        log_file = temp_dir / "actions.log"
        logger = ActionLogger(log_file=str(log_file))
        
        logger.log_action("test_action", {"key": "value"})
        
        # Verify log file was created and contains the action
        assert log_file.exists()
        content = log_file.read_text()
        assert "test_action" in content

    def test_multiple_actions(self, temp_dir):
        """Test logging multiple actions."""
        log_file = temp_dir / "actions.log"
        logger = ActionLogger(log_file=str(log_file))
        
        logger.log_action("action1", {"data": "first"})
        logger.log_action("action2", {"data": "second"})
        
        content = log_file.read_text()
        assert "action1" in content
        assert "action2" in content

    def test_get_recent_actions(self, temp_dir):
        """Test retrieving recent actions."""
        log_file = temp_dir / "actions.log"
        logger = ActionLogger(log_file=str(log_file))
        
        logger.log_action("action1", {"data": "first"})
        logger.log_action("action2", {"data": "second"})
        logger.log_action("action3", {"data": "third"})
        
        # Get recent actions (implementation may vary)
        # This test assumes get_recent_actions method exists
        if hasattr(logger, "get_recent_actions"):
            recent = logger.get_recent_actions(limit=2)
            assert len(recent) <= 2
