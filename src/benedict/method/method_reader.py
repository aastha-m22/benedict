"""Method Reader

Reads and parses .benedict.method.yaml files.
"""

import logging
import os
import yaml
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class MethodReader:
    """Reads and parses method files."""

    def __init__(self, method_file_path: Optional[str] = None):
        """Initialize method reader.

        Args:
            method_file_path: Optional path to method file (from env var or explicit)
                             If None, uses BENEDICT_METHOD_FILE env var or defaults to .benedict.method.yaml
        """
        self.method_file_path = method_file_path or os.environ.get("BENEDICT_METHOD_FILE")

    def read_method(self, directory: Path) -> Optional[Dict[str, Any]]:
        """Read method file from directory.

        Priority order:
        1. Repo-specific .benedict.method.yaml file in the directory (highest priority)
        2. BENEDICT_METHOD_FILE env var path (only if repo-specific file doesn't exist)
        
        This ensures each repository uses its own method file, not a shared one.

        Args:
            directory: Directory path

        Returns:
            Method dictionary or None if not found
        """
        directory = Path(directory)

        # FIRST: Always check for repo-specific method file (highest priority)
        repo_method_file = directory / ".benedict.method.yaml"
        if repo_method_file.exists():
            try:
                with open(repo_method_file, "r", encoding="utf-8") as f:
                    method_data = yaml.safe_load(f)
                logger.debug(f"Read repo-specific method file from {repo_method_file}")
                return method_data
            except Exception as e:
                logger.warning(f"Error reading repo-specific method file from {repo_method_file}: {e}")
                # Fall through to check env var

        # SECOND: Fall back to env var if repo-specific file doesn't exist
        if self.method_file_path:
            method_file = Path(self.method_file_path)
            # If path is relative, resolve relative to directory
            if not method_file.is_absolute():
                method_file = directory / method_file
            else:
                # Absolute path - use as-is
                method_file = method_file
            
            if method_file.exists():
                try:
                    with open(method_file, "r", encoding="utf-8") as f:
                        method_data = yaml.safe_load(f)
                    logger.debug(f"Read method file from env var path: {method_file}")
                    return method_data
                except Exception as e:
                    logger.warning(f"Error reading method file from env var path {method_file}: {e}")
                    return None

        # No method file found
        return None

    def method_exists(self, directory: Path) -> bool:
        """Check if method file exists for directory.

        Priority order:
        1. Repo-specific .benedict.method.yaml file in the directory (highest priority)
        2. BENEDICT_METHOD_FILE env var path (only if repo-specific file doesn't exist)

        Args:
            directory: Directory path

        Returns:
            True if method file exists, False otherwise
        """
        directory = Path(directory)

        # FIRST: Check for repo-specific method file (highest priority)
        repo_method_file = directory / ".benedict.method.yaml"
        if repo_method_file.exists():
            return True

        # SECOND: Fall back to env var if repo-specific file doesn't exist
        if self.method_file_path:
            method_file = Path(self.method_file_path)
            if not method_file.is_absolute():
                method_file = directory / method_file
            return method_file.exists()
        
        return False

    def get_current_phase(self, directory: Path) -> Optional[str]:
        """Get current phase from method file.

        Args:
            directory: Directory path

        Returns:
            Current phase name or None
        """
        method_data = self.read_method(directory)
        if not method_data:
            return None

        method = method_data.get("method", {})
        pc = method.get("pc", {})
        return pc.get("phase")

    def get_current_concerns(self, directory: Path) -> Optional[Dict[str, str]]:
        """Get current concern states from method file.

        Args:
            directory: Directory path

        Returns:
            Dictionary mapping concern names to their current states, or None
        """
        method_data = self.read_method(directory)
        if not method_data:
            return None

        method = method_data.get("method", {})
        concerns = method.get("concerns", {})
        return concerns

    def get_concern_rules(self, directory: Path, concern: str) -> Optional[List[str]]:
        """Get rules for a specific concern.

        Args:
            directory: Directory path
            concern: Concern name (e.g., "scope", "documentation")

        Returns:
            List of rules for the concern, or None
        """
        method_data = self.read_method(directory)
        if not method_data:
            return None

        method = method_data.get("method", {})
        concern_definitions = method.get("concern_definitions", {})
        concern_def = concern_definitions.get(concern, {})
        return concern_def.get("rules")

    def get_concern_definition(self, directory: Path, concern: str) -> Optional[Dict[str, Any]]:
        """Get full definition for a specific concern.

        Args:
            directory: Directory path
            concern: Concern name

        Returns:
            Concern definition dictionary or None
        """
        method_data = self.read_method(directory)
        if not method_data:
            return None

        method = method_data.get("method", {})
        concern_definitions = method.get("concern_definitions", {})
        return concern_definitions.get(concern)

    def get_sequence_phase(self, directory: Path, phase: str) -> Optional[Dict[str, Any]]:
        """Get sequence definition for a specific phase.

        Args:
            directory: Directory path
            phase: Phase name (e.g., "conception", "design", "sprint", "review")

        Returns:
            Phase definition dictionary or None
        """
        method_data = self.read_method(directory)
        if not method_data:
            return None

        method = method_data.get("method", {})
        sequence = method.get("sequence", {})
        return sequence.get(phase)

    def find_method_files(self, workspace_path: Path) -> List[Path]:
        """Find all .benedict.method.yaml files in workspace.

        Args:
            workspace_path: Workspace root path

        Returns:
            List of .benedict.method.yaml file paths
        """
        workspace_path = Path(workspace_path)
        method_files = []
        for method_file in workspace_path.rglob(".benedict.method.yaml"):
            if method_file.is_file():
                method_files.append(method_file)
        return method_files

    def get_method_summary(self, directory: Path) -> Optional[str]:
        """Get a summary of the method file state.

        Args:
            directory: Directory path

        Returns:
            Summary string or None
        """
        method_data = self.read_method(directory)
        if not method_data:
            return None

        method = method_data.get("method", {})
        pc = method.get("pc", {})
        concerns = method.get("concerns", {})

        phase = pc.get("phase", "unknown")
        iteration = pc.get("iteration", "?")
        step = pc.get("step", "?")

        summary_parts = [f"Phase: {phase} (iteration {iteration}, step: {step})"]

        if concerns:
            concern_states = ", ".join([f"{k}: {v}" for k, v in concerns.items()])
            summary_parts.append(f"Concerns: {concern_states}")

        return " | ".join(summary_parts)
