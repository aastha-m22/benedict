"""Method Writer

Writes and updates .benedict.method.yaml files.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class MethodWriter:
    """Writes and updates method files."""

    def write_method(self, directory: Path, method_data: Dict[str, Any]) -> None:
        """Write method file to directory.

        Writes to .benedict.method.yaml.

        Args:
            directory: Directory path
            method_data: Method data dictionary (should have "method" key at top level)
        """
        directory = Path(directory)

        # Use .benedict.method.yaml as the standard filename
        method_file = directory / ".benedict.method.yaml"

        # Check if method_file exists as a directory (conflict)
        if method_file.exists() and method_file.is_dir():
            logger.warning(
                f"Method file path exists as directory at {method_file}, skipping write"
            )
            raise ValueError(f"Cannot write method file: path exists as directory: {method_file}")

        # Ensure the directory exists before writing
        directory.mkdir(parents=True, exist_ok=True)

        try:
            with open(method_file, "w", encoding="utf-8") as f:
                yaml.dump(
                    method_data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                    width=120,
                )
            
            # Verify the file was actually created
            if not method_file.exists():
                raise IOError(f"Method file was not created at {method_file}")
            
            logger.info(f"Successfully wrote method file to {method_file}")
        except Exception as e:
            logger.error(f"Error writing method file to {method_file}: {e}", exc_info=True)
            raise

    def update_pc(
        self, directory: Path, phase: Optional[str] = None, iteration: Optional[int] = None, step: Optional[str] = None
    ) -> None:
        """Update program counter (pc) section.

        Args:
            directory: Directory path
            phase: Optional phase name to update
            iteration: Optional iteration number to update
            step: Optional step name to update
        """
        from benedict.method import MethodReader

        reader = MethodReader()
        method_data = reader.read_method(directory)

        if not method_data:
            # Create new method file structure
            method_data = {"method": {"pc": {}, "concerns": {}, "concern_definitions": {}, "sequence": {}}}

        method = method_data.get("method", {})
        pc = method.get("pc", {})

        if phase is not None:
            pc["phase"] = phase
        if iteration is not None:
            pc["iteration"] = iteration
        if step is not None:
            pc["step"] = step

        method["pc"] = pc
        method_data["method"] = method

        self.write_method(directory, method_data)

    def update_concern(self, directory: Path, concern: str, state: str) -> None:
        """Update a concern's current state.

        Args:
            directory: Directory path
            concern: Concern name (e.g., "scope", "documentation")
            state: New state value
        """
        from benedict.method import MethodReader

        reader = MethodReader()
        method_data = reader.read_method(directory)

        if not method_data:
            # Create new method file structure
            method_data = {"method": {"pc": {}, "concerns": {}, "concern_definitions": {}, "sequence": {}}}

        method = method_data.get("method", {})
        concerns = method.get("concerns", {})

        concerns[concern] = state
        method["concerns"] = concerns
        method_data["method"] = method

        self.write_method(directory, method_data)

    def update_sequence_phase_status(
        self, directory: Path, phase: str, status: str, iteration: Optional[int] = None
    ) -> None:
        """Update a sequence phase's status and optionally iteration.

        Args:
            directory: Directory path
            phase: Phase name (e.g., "conception", "design", "sprint", "review")
            status: New status (e.g., "complete", "active", "pending")
            iteration: Optional iteration number to update
        """
        from benedict.method import MethodReader

        reader = MethodReader()
        method_data = reader.read_method(directory)

        if not method_data:
            # Create new method file structure
            method_data = {"method": {"pc": {}, "concerns": {}, "concern_definitions": {}, "sequence": {}}}

        method = method_data.get("method", {})
        sequence = method.get("sequence", {})

        phase_data = sequence.get(phase, {})
        phase_data["status"] = status
        if iteration is not None:
            phase_data["iteration"] = iteration

        sequence[phase] = phase_data
        method["sequence"] = sequence
        method_data["method"] = method

        self.write_method(directory, method_data)

    def update_method_data(self, directory: Path, updates: Dict[str, Any]) -> None:
        """Update method file with arbitrary updates.

        Updates are merged into the existing method data structure.

        Args:
            directory: Directory path
            updates: Dictionary of updates to apply (nested structure supported)
        """
        from benedict.method import MethodReader

        reader = MethodReader()
        method_data = reader.read_method(directory)

        if not method_data:
            method_data = {"method": {"pc": {}, "concerns": {}, "concern_definitions": {}, "sequence": {}}}

        # Deep merge updates into method_data
        self._deep_merge(method_data, updates)

        self.write_method(directory, method_data)

    def _deep_merge(self, base: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """Deep merge updates into base dictionary.

        Args:
            base: Base dictionary to merge into
            updates: Dictionary of updates to merge
        """
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
