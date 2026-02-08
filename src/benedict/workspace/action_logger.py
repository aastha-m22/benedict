"""Action Logger

Logs all agent actions in workspace for traceability and context.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class ActionLogger:
    """Logs agent actions in workspace."""

    def __init__(self, workspace_path: Path):
        """Initialize action logger for workspace.

        Args:
            workspace_path: Path to workspace directory
        """
        self.workspace_path = Path(workspace_path)
        self.log_file = self.workspace_path / "workspace_log.json"

        # Ensure workspace exists
        self.workspace_path.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Initialized ActionLogger for workspace {workspace_path}")

    def log_action(
        self, action: str, content_type: str, resource: Optional[str] = None, **kwargs
    ) -> None:
        """Log an action.

        Args:
            action: Action name (e.g., "symlink_repository", "index_repository")
            content_type: Content type (e.g., "code", "conversation_history")
            resource: Optional resource name
            **kwargs: Additional metadata
        """
        action_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "content_type": content_type,
            "resource": resource,
            **kwargs,
        }

        # Load existing log
        log_data = self._load_log()

        # Append new action
        log_data["actions"].append(action_entry)

        # Save log
        self._save_log(log_data)

        logger.debug(f"Logged action: {action} for resource {resource}")

    def get_recent_actions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent actions.

        Args:
            limit: Maximum number of actions to return

        Returns:
            List of action dictionaries, most recent first
        """
        log_data = self._load_log()
        actions = log_data.get("actions", [])

        # Return most recent actions
        return list(reversed(actions[-limit:]))

    def get_actions_since(self, since: datetime) -> List[Dict[str, Any]]:
        """Get actions since a specific datetime.

        Args:
            since: Datetime to get actions since

        Returns:
            List of action dictionaries since the specified datetime
        """
        log_data = self._load_log()
        actions = log_data.get("actions", [])

        since_iso = since.isoformat() + "Z"

        filtered = [action for action in actions if action.get("timestamp", "") >= since_iso]

        return filtered

    def _load_log(self) -> Dict[str, Any]:
        """Load action log from file.

        Returns:
            Log data dictionary
        """
        if not self.log_file.exists():
            return {"actions": []}

        try:
            with open(self.log_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error loading action log: {e}, creating new log")
            return {"actions": []}

    def _save_log(self, log_data: Dict[str, Any]) -> None:
        """Save action log to file.

        Args:
            log_data: Log data dictionary
        """
        try:
            with open(self.log_file, "w") as f:
                json.dump(log_data, f, indent=2)
        except IOError as e:
            logger.error(f"Error saving action log: {e}")
